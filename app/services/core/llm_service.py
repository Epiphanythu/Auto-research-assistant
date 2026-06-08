"""llm_service 大模型调用服务（带重试与流式输出）。"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, Dict, Generator, List, Optional

import requests

from app.api_error import APIError
from app.config import get_settings
from app.constant.llm_constant import (
    LLM_EVENT_CACHE_HIT,
    LLM_EVENT_CACHE_WRITE,
    LLM_EVENT_FAILURE,
    LLM_EVENT_REQUEST,
    LLM_EVENT_SUCCESS,
)
from app.services.infrastructure.llm_cache import LLMCache
from app.services.infrastructure.structured_logging import (
    emit_event,
    get_current_stats,
)

logger = logging.getLogger(__name__)

LLM_MAX_RETRIES = 5
LLM_RETRY_BACKOFF = 3.0  # seconds, exponential base (3s → 6s → 12s → 24s → 48s)
# 进程级并发上限，避免短时间内 fan-out 触发 GLM 等 provider 的 CC（concurrent calls）限速
LLM_MAX_CONCURRENCY = 4
_LLM_CONCURRENCY_SEMAPHORE = threading.BoundedSemaphore(LLM_MAX_CONCURRENCY)


class LLMConfigurationError(APIError):
    """LLMConfigurationError 大模型配置缺失异常。"""

    def __init__(self) -> None:
        super().__init__(
            status_code=503,
            error_code="llm_config_missing",
            title="模型配置缺失",
            detail="当前系统已配置为强依赖大模型模式，请先设置 LLM_BASE_URL、LLM_API_KEY 和 LLM_MODEL。",
            suggestion="请在启动后端前补充模型服务地址、密钥和模型名称，然后重新提交研究任务。",
        )


class LLMRequestError(APIError):
    """LLMRequestError 大模型请求失败异常。"""

    def __init__(self, detail: str) -> None:
        super().__init__(
            status_code=502,
            error_code="llm_request_failed",
            title="模型请求失败",
            detail=detail,
            suggestion="请检查模型服务可用性、网络连通性和接口兼容性。",
        )


class LLMResponseFormatError(APIError):
    """LLMResponseFormatError 大模型返回格式异常。"""

    def __init__(self, detail: str) -> None:
        super().__init__(
            status_code=502,
            error_code="llm_response_invalid",
            title="模型返回格式异常",
            detail=detail,
            suggestion="请检查模型是否支持 JSON 输出，并确认提示词与响应格式配置正确。",
        )


class LLMService:
    """LLMService OpenAI 兼容接口调用器（带指数退避重试和流式支持）。"""

    def __init__(self) -> None:
        self.settings = get_settings()
        # 1. 缓存初始化：仅在显式开启时实例化，避免无谓创建目录
        self._cache: Optional[LLMCache] = None
        if self.settings.is_llm_cache_enabled():
            self._cache = LLMCache(self.settings.get_llm_cache_dir())

    def is_enabled(self) -> bool:
        """is_enabled 判断是否启用外部大模型。"""
        return self.settings.is_llm_enabled()

    def ensure_enabled(self) -> None:
        """ensure_enabled 校验大模型配置是否完整。"""
        if self.is_enabled():
            return
        raise LLMConfigurationError()

    def ask_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        required_keys: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """ask_json 请求模型并解析 JSON（带指数退避重试 + 字段缺失重试）。"""
        self.ensure_enabled()
        last_error: Optional[Exception] = None

        for attempt in range(LLM_MAX_RETRIES):
            try:
                result = self._do_ask_json(system_prompt, user_prompt, temperature, max_tokens)
                if required_keys:
                    missing = [k for k in required_keys if k not in result]
                    if missing:
                        if attempt < 2:
                            logger.warning(
                                "LLM response missing keys %s (attempt %d), retrying",
                                missing, attempt + 1,
                            )
                            temperature = min(temperature + 0.1, 0.8)
                            continue
                        logger.warning("LLM response still missing keys after retries: %s", missing)
                return result
            except (LLMRequestError, LLMResponseFormatError) as error:
                last_error = error
                if attempt < LLM_MAX_RETRIES - 1:
                    wait = LLM_RETRY_BACKOFF * (2 ** attempt)
                    logger.warning(
                        "LLM call failed (attempt %d/%d), retrying in %.1fs: %s",
                        attempt + 1, LLM_MAX_RETRIES, wait, error,
                    )
                    time.sleep(wait)
                else:
                    logger.error("LLM call failed after %d retries: %s", LLM_MAX_RETRIES, error)

        raise last_error  # type: ignore[misc]

    def ask_text(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
    ) -> str:
        """ask_text 请求模型返回纯文本（带重试）。"""
        self.ensure_enabled()
        last_error: Optional[Exception] = None

        for attempt in range(LLM_MAX_RETRIES):
            try:
                return self._do_ask_text(system_prompt, user_prompt, temperature, max_tokens)
            except (LLMRequestError, LLMResponseFormatError) as error:
                last_error = error
                if attempt < LLM_MAX_RETRIES - 1:
                    wait = LLM_RETRY_BACKOFF * (2 ** attempt)
                    time.sleep(wait)

        raise last_error  # type: ignore[misc]

    def stream_chat(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
    ) -> Generator[str, None, None]:
        """stream_chat 流式请求模型，逐 token 产出文本片段。"""
        self.ensure_enabled()
        try:
            # 1. 流式请求也纳入全局并发限制，并用上下文管理器保证中断时释放连接。
            with _LLM_CONCURRENCY_SEMAPHORE:
                with requests.post(
                    f"{self.settings.get_llm_base_url().rstrip('/')}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.settings.get_llm_api_key()}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.settings.get_llm_model(),
                        "temperature": temperature,
                        "stream": True,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                    },
                    timeout=self.settings.get_request_timeout_seconds(),
                    stream=True,
                ) as response:
                    response.raise_for_status()
                    # 2. 逐行解析 OpenAI 兼容 SSE 数据，只产出有效 content 片段。
                    for line in response.iter_lines(decode_unicode=True):
                        if not line or not line.startswith("data: "):
                            continue
                        data = line[6:]
                        if data.strip() == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            delta = chunk["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
        except requests.RequestException as error:
            raise LLMRequestError(f"流式调用模型服务失败：{error}") from error

    def _do_ask_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: Optional[int],
    ) -> Dict[str, Any]:
        """_do_ask_json 单次 JSON 请求（含缓存与结构化日志）。"""
        model = self.settings.get_llm_model()
        # 1. 命中缓存优先返回；缓存键含 model + system + user + temperature
        cache_key: Optional[str] = None
        if self._cache is not None:
            cache_key = LLMCache.build_key(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
            )
            cached = self._cache.load(cache_key)
            if cached is not None:
                emit_event(
                    logger, LLM_EVENT_CACHE_HIT,
                    model=model, cache_key=cache_key[:12],
                    user_prompt_len=len(user_prompt),
                )
                stats = get_current_stats()
                if stats is not None:
                    stats.add_call(cache_hit=True)
                return cached

        # 2. 实际请求模型服务
        _t0 = time.monotonic()
        body: Dict[str, Any] = {
            "model": model,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if max_tokens:
            body["max_tokens"] = max_tokens

        emit_event(
            logger, LLM_EVENT_REQUEST,
            model=model, temperature=temperature,
            system_prompt_len=len(system_prompt),
            user_prompt_len=len(user_prompt),
        )

        try:
            # 1. 通过进程级信号量限制并发，避免触发 provider 端 CC 限速
            with _LLM_CONCURRENCY_SEMAPHORE:
                response = requests.post(
                    f"{self.settings.get_llm_base_url().rstrip('/')}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.settings.get_llm_api_key()}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                    timeout=self.settings.get_request_timeout_seconds(),
                )
            response.raise_for_status()
        except requests.RequestException as error:
            emit_event(logger, LLM_EVENT_FAILURE, model=model, error=str(error))
            raise LLMRequestError(f"调用模型服务失败：{error}") from error

        try:
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as error:
            emit_event(logger, LLM_EVENT_FAILURE, model=model, error=str(error))
            raise LLMResponseFormatError("模型返回结果无法解析为合法 JSON 对象。") from error

        # 3. 解析与字段提取（兼容代码块包裹）
        parsed_payload = self._extract_json(content)
        if parsed_payload is None:
            emit_event(
                logger, LLM_EVENT_FAILURE,
                model=model, error="not_json", preview=content[:200],
            )
            raise LLMResponseFormatError("模型返回结果不是合法的 JSON 对象。")

        # 4. 成功事件 + 全局统计累计 + 写缓存
        elapsed_ms = int((time.monotonic() - _t0) * 1000)
        usage = payload.get("usage", {}) or {}
        prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
        completion_tokens = int(usage.get("completion_tokens", 0) or 0)
        emit_event(
            logger, LLM_EVENT_SUCCESS,
            model=model, elapsed_ms=elapsed_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            keys=list(parsed_payload.keys()),
        )
        stats = get_current_stats()
        if stats is not None:
            stats.add_call(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                elapsed_ms=elapsed_ms,
            )
        if self._cache is not None and cache_key is not None:
            self._cache.save(cache_key, parsed_payload)
            emit_event(logger, LLM_EVENT_CACHE_WRITE, cache_key=cache_key[:12])
        return parsed_payload

    @staticmethod
    def _unwrap_json(result: Any) -> Optional[Dict[str, Any]]:
        """Unwrap JSON: if it's a list with one dict element, unwrap it."""
        if isinstance(result, dict):
            return result
        if isinstance(result, list) and len(result) == 1 and isinstance(result[0], dict):
            return result[0]
        if isinstance(result, list) and len(result) > 0 and isinstance(result[0], dict):
            # Try to find the first dict that looks like a result object
            return result[0]
        return None

    @staticmethod
    def _extract_json(content: str) -> Optional[Dict[str, Any]]:
        """_extract_json 从模型返回内容中提取 JSON，兼容 markdown 代码块包裹和数组包裹。"""
        import re
        content = content.strip()
        # 1. 直接解析
        try:
            result = json.loads(content)
            unwrapped = LLMService._unwrap_json(result)
            if unwrapped:
                return unwrapped
        except json.JSONDecodeError:
            pass
        # 2. 从 ```json ... ``` 代码块中提取
        match = re.search(r"```(?:json)?\s*\n?(.*?)```", content, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group(1).strip())
                unwrapped = LLMService._unwrap_json(result)
                if unwrapped:
                    return unwrapped
            except json.JSONDecodeError:
                pass
        # 3. 找第一个 { 和最后一个 }
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end > start:
            try:
                result = json.loads(content[start:end + 1])
                unwrapped = LLMService._unwrap_json(result)
                if unwrapped:
                    return unwrapped
            except json.JSONDecodeError:
                pass
        # 4. Try first [ to last ] for array-wrapped JSON
        start = content.find("[")
        end = content.rfind("]")
        if start != -1 and end > start:
            try:
                result = json.loads(content[start:end + 1])
                unwrapped = LLMService._unwrap_json(result)
                if unwrapped:
                    return unwrapped
            except json.JSONDecodeError:
                pass
        return None

    def _do_ask_text(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: Optional[int],
    ) -> str:
        """_do_ask_text 单次纯文本请求。"""
        body: Dict[str, Any] = {
            "model": self.settings.get_llm_model(),
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if max_tokens:
            body["max_tokens"] = max_tokens

        try:
            # 1. 通过进程级信号量限制并发，避免触发 provider 端 CC 限速
            with _LLM_CONCURRENCY_SEMAPHORE:
                response = requests.post(
                    f"{self.settings.get_llm_base_url().rstrip('/')}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.settings.get_llm_api_key()}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                    timeout=self.settings.get_request_timeout_seconds(),
                )
            response.raise_for_status()
        except requests.RequestException as error:
            raise LLMRequestError(f"调用模型服务失败：{error}") from error

        try:
            payload = response.json()
            return payload["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as error:
            raise LLMResponseFormatError("模型返回结果无法解析。") from error
