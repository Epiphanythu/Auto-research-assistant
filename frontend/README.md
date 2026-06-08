# 自动科研助手前端

React + TypeScript + Vite 前端，用于提交研究任务、展示 SSE 进度、查看报告归档、证据包、趋势分析和报告对比。

## 常用命令

```bash
npm ci
npm run dev
npm run check
npm run lint
npm run build
```

## 开发配置

- 默认代理后端：`http://127.0.0.1:8000`
- 可通过 `VITE_PROXY_TARGET` 覆盖代理目标。
- 生产构建默认不生成 sourcemap；如需内部排查，可设置 `VITE_ENABLE_SOURCEMAP=true`。

## 安全说明

- 报告 Markdown 使用 `marked` 渲染，并通过 `DOMPurify` 清洗后再注入页面。
- 动态路径参数在请求前统一使用 `encodeURIComponent` 编码，避免报告 ID 或任务 ID 改变路由语义。
