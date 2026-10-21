# 视频总结 MCP 服务

本仓库提供 B 站视频字幕提取、总结和个人知识库 MCP 服务。可运行项目位于 [video-summary-plugin/](video-summary-plugin/README.md)。

## 快速开始

```bash
cd video-summary-plugin
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

- 健康检查：`http://localhost:8000/health`
- MCP 端点：`http://localhost:8000/mcp`
- OpenAPI 说明：[video-summary-plugin/openapi.yaml](video-summary-plugin/openapi.yaml)
- 插件描述清单：[video-summary-plugin/plugin-manifest.json](video-summary-plugin/plugin-manifest.json)

仓库根目录的 `render.yaml` 是 Render Blueprint 入口；服务源码和 Dockerfile 位于 `video-summary-plugin/`。
