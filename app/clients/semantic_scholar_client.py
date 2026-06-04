"""semantic_scholar_client Semantic Scholar API 客户端。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import requests

from app.api_error import SearchResponseParseError, SearchSourceUnavailableError
from app.config import get_settings
from app.constant.paper_constant import PAPER_SOURCE_SEMANTIC_SCHOLAR

logger = logging.getLogger(__name__)

S2_BASE_URL = "https://api.semanticscholar.org/graph/v1"
S2_SEARCH_FIELDS = "paperId,title,abstract,authors,year,externalIds,url,citationCount,referenceCount,fieldsOfStudy,publicationDate,isOpenAccess,openAccessPdf,tldr"
S2_PAPER_FIELDS = "paperId,title,abstract,authors,year,externalIds,url,citationCount,referenceCount,fieldsOfStudy,publicationDate,isOpenAccess,openAccessPdf,tldr,citations,references"
S2_GRAPH_FIELDS = "paperId,title,year,citationCount,authors"


class SemanticScholarClient:
    """SemanticScholarClient Semantic Scholar API 客户端。"""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.timeout = 30

    def search_papers(self, query: str, max_results: int, year_range: Optional[str] = None) -> List[Dict[str, Any]]:
        """search_papers 搜索论文，返回原始结构化数据（含 TLDR、引用数等）。"""
        params = {
            "query": query,
            "limit": max_results,
            "fields": S2_SEARCH_FIELDS,
            "isOpenAccess": "true",
        }
        if year_range:
            params["year"] = year_range
        try:
            response = requests.get(
                f"{S2_BASE_URL}/paper/search",
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.RequestException as error:
            raise SearchSourceUnavailableError("SemanticScholar", str(error)) from error

        try:
            payload = response.json()
        except ValueError as error:
            raise SearchResponseParseError("SemanticScholar", str(error)) from error

        return payload.get("data", []) or []

    def get_paper(self, paper_id: str) -> Optional[Dict[str, Any]]:
        """get_paper 获取单篇论文详情（含引用和参考文献列表）。"""
        try:
            response = requests.get(
                f"{S2_BASE_URL}/paper/{paper_id}",
                params={"fields": S2_PAPER_FIELDS},
                timeout=self.timeout,
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
        except requests.RequestException as error:
            logger.warning("SemanticScholar.get_paper failed: %s", error)
            return None
        try:
            return response.json()
        except ValueError:
            return None

    def get_citation_graph(self, paper_id: str, depth: int = 1) -> Dict[str, Any]:
        """get_citation_graph 获取以某篇论文为起点的引用图。

        depth=1 表示获取该论文的直接引用和被引论文；
        depth=2 表示进一步扩展一跳。
        """
        paper = self.get_paper(paper_id)
        if not paper:
            return {"nodes": [], "edges": []}

        nodes: Dict[str, Dict[str, Any]] = {}
        edges: List[Dict[str, Any]] = []

        self._add_node(nodes, paper)

        # 引用论文 (this paper cites them)
        for ref in (paper.get("references") or [])[:20]:
            ref_paper = ref.get("paperId")
            if ref_paper and ref_paper not in nodes:
                self._add_node(nodes, ref, is_seed=False)
                edges.append({"source": paper_id, "target": ref_paper, "type": "cites"})

        # 被引论文 (they cite this paper)
        for cit in (paper.get("citations") or [])[:20]:
            cit_paper = cit.get("paperId")
            if cit_paper and cit_paper not in nodes:
                self._add_node(nodes, cit, is_seed=False)
                edges.append({"source": cit_paper, "target": paper_id, "type": "cites"})

        # depth=2: expand top-cited nodes
        if depth >= 2:
            top_nodes = sorted(
                [n for n in nodes.values() if n["id"] != paper_id],
                key=lambda n: n.get("citation_count", 0),
                reverse=True,
            )[:5]
            for node in top_nodes:
                sub_paper = self.get_paper(node["id"])
                if not sub_paper:
                    continue
                for ref in (sub_paper.get("references") or [])[:10]:
                    ref_id = ref.get("paperId")
                    if ref_id and ref_id not in nodes:
                        self._add_node(nodes, ref, is_seed=False)
                        edges.append({"source": node["id"], "target": ref_id, "type": "cites"})
                for cit in (sub_paper.get("citations") or [])[:10]:
                    cit_id = cit.get("paperId")
                    if cit_id and cit_id not in nodes:
                        self._add_node(nodes, cit, is_seed=False)
                        edges.append({"source": cit_id, "target": node["id"], "type": "cites"})

        return {"nodes": list(nodes.values()), "edges": edges}

    def get_paper_recommendations(self, paper_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """get_paper_recommendations 基于单篇论文推荐相似论文。"""
        try:
            response = requests.get(
                f"{S2_BASE_URL}/paper/ForRecommender",
                params={
                    "fields": S2_SEARCH_FIELDS,
                    "limit": limit,
                },
                json={"positivePaperIds": [paper_id]},
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.RequestException as error:
            logger.warning("SemanticScholar.get_paper_recommendations failed: %s", error)
            return []
        try:
            return response.json().get("data", []) or []
        except ValueError:
            return []

    def batch_get_citation_counts(self, paper_ids: List[str]) -> Dict[str, int]:
        """batch_get_citation_counts 批量获取引用计数。"""
        if not paper_ids:
            return {}
        try:
            response = requests.post(
                f"{S2_BASE_URL}/paper/batch",
                params={"fields": "paperId,citationCount,year"},
                json={"ids": paper_ids[:500]},
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.RequestException as error:
            logger.warning("SemanticScholar.batch_get_citation_counts failed: %s", error)
            return {}
        try:
            data = response.json()
            return {
                item["paperId"]: item.get("citationCount", 0)
                for item in data
                if item and item.get("paperId")
            }
        except ValueError:
            return {}

    @staticmethod
    def _add_node(nodes: Dict[str, Dict[str, Any]], paper: Dict[str, Any], is_seed: bool = True) -> None:
        """_add_node 添加节点到图谱。"""
        pid = paper.get("paperId", "")
        if not pid or pid in nodes:
            return
        authors_list = []
        for a in (paper.get("authors") or []):
            name = a.get("name", "").strip()
            if name:
                authors_list.append(name)
        tldr = ""
        tldr_obj = paper.get("tldr")
        if isinstance(tldr_obj, dict):
            tldr = tldr_obj.get("text", "")
        nodes[pid] = {
            "id": pid,
            "title": paper.get("title", ""),
            "year": paper.get("year"),
            "citation_count": paper.get("citationCount", 0),
            "authors": authors_list,
            "abstract": paper.get("abstract", ""),
            "tldr": tldr,
            "is_seed": is_seed,
            "fields_of_study": paper.get("fieldsOfStudy") or [],
        }
