# 视频总结（Video Summary MCP）

一个面向 ChatGPT / MCP 客户端的 B 站视频总结应用。用户发送 bilibili 或 b23.tv 链接后，应用可以读取公开元数据与公开字幕，生成结构化总结，并把总结持续积累为个人视频知识库。

> 当前仓库名为 `lwfdz/lwfdz-video-summary-plugin`。建议后续在 GitHub 设置中重命名为 `video-summary-plugin`，地址会更简洁。

## 第一版已经具备的能力

- 解析 `b23.tv` 短链接和标准 B 站视频链接
- 读取标题、UP 主、简介、分 P、时长和互动数据
- 获取公开字幕，优先选择中文字幕
- 支持简短、标准、深入三种总结强度
- 支持指定关注方向，例如财经逻辑、知识点、论证漏洞
- 可选使用 OpenAI API 在服务端生成总结
- 不配置 API Key 时，把字幕材料返回给 ChatGPT，由 ChatGPT 本身完成总结
- 将总结保存为本地 JSON 知识库，并支持搜索与读取
- 提供 Streamable HTTP MCP 端点：`/mcp`
- 提供健康检查端点：`/health`

## MCP 工具

| 工具 | 用途 |
| --- | --- |
| `get_video_info` | 读取视频基本信息，不拉取完整字幕 |
| `extract_video_transcript` | 提取公开字幕，适合逐段分析或核对原话 |
| `summarize_video` | 提取字幕并生成/准备最终总结 |
| `save_video_note` | 保存 ChatGPT 已经完成的总结 |
| `search_video_library` | 搜索个人视频知识库 |
| `get_video_note` | 按条目 ID 读取完整总结 |

## 工作方式

### 无 OpenAI API Key

这是最省钱的默认模式：

1. MCP 服务负责解析链接和提取字幕。
2. `summarize_video` 返回 `source_material` 和总结要求。
3. 调用它的 ChatGPT 直接完成最终总结。
4. ChatGPT 可继续调用 `save_video_note` 保存结果。

### 配置 OpenAI API Key

服务端会调用 `SUMMARY_MODEL` 生成总结，并可自动保存知识库。默认模型为：

```text
gpt-5.6-luna
```

可在环境变量中改成你有权限使用的其他文本模型。

## 本地运行

需要 Python 3.12。

```bash
python -m venv .venv
source .venv/bin/activate      # Windows 使用 .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app:app --host 0.0.0.0 --port 8000
```

检查服务：

```bash
curl http://localhost:8000/health
```

MCP 地址：

```text
http://localhost:8000/mcp
```

也可以使用 MCP Inspector：

```bash
npx -y @modelcontextprotocol/inspector
```

然后连接 `http://localhost:8000/mcp`。

## Docker 运行

```bash
docker build -t video-summary-mcp .
docker run --rm -p 8000:8000 --env-file .env video-summary-mcp
```

## 部署到 Render

仓库已经提供 `render.yaml` 和 `Dockerfile`。

1. 在 Render 中选择 **New > Blueprint**。
2. 连接本 GitHub 仓库。
3. Render 会读取 `render.yaml` 创建服务。
4. 部署完成后访问：

```text
https://你的服务域名.onrender.com/health
```

MCP 地址为：

```text
https://你的服务域名.onrender.com/mcp
```

### 环境变量

| 变量 | 是否必需 | 说明 |
| --- | --- | --- |
| `OPENAI_API_KEY` | 否 | 配置后启用服务端总结 |
| `SUMMARY_MODEL` | 否 | 默认 `gpt-5.6-luna` |
| `BILIBILI_COOKIE` | 否 | 某些字幕可能需要登录态；只用于自己的私有部署 |
| `DATA_DIR` | 否 | 默认 `data` |
| `PORT` | 云平台通常自动提供 | 默认 8000 |

> Render 免费实例的本地文件系统可能在重启或重新部署后丢失，因此免费部署适合测试，不适合作为长期知识库。后续版本应接入 Supabase、PostgreSQL 或其他持久数据库。

## 在 ChatGPT 中连接

当前自定义应用采用远程 MCP，而不是旧式 `ai-plugin.json` 插件。

一般流程是：

1. 先把本项目部署到公网 HTTPS 地址。
2. 在 ChatGPT 网页端打开开发者模式或创建自定义应用入口。
3. 填入远程 MCP 地址：`https://你的域名/mcp`。
4. 应用连接成功后，可在聊天中选择或 `@视频总结` 调用。

ChatGPT 的开发者模式、可用套餐和移动端支持会随产品更新而变化。若手机端没有创建入口，请在网页端完成首次连接和测试。

## 示例

```text
@视频总结 总结这个视频，重点分析作者对中国经济的判断是否有依据：
https://b23.tv/xxxxxxx
```

```text
@视频总结 搜索我之前看过的关于香港、AI 和金融中心的视频
```

## 当前限制

- 第一版只支持 B 站链接。
- 依赖视频公开字幕；没有公开字幕时不会凭空编造总结。
- 尚未自动下载音频并转写，因为这会显著增加部署成本、版权风险和处理时间。
- B 站接口可能受地区、登录状态、风控或接口调整影响。
- JSON 知识库适合单实例 MVP，不适合多人和大规模数据。
- 公开发布前需要补齐正式隐私政策、认证、限流和安全审计。

## 下一阶段计划

- 接入音频转写，覆盖无字幕视频
- 接入 Supabase/PostgreSQL，实现真正持久的个人知识库
- 自动提取主题、人物、公司、事件和时间线
- 支持多个视频横向比较
- 支持 YouTube、播客和本地视频文件
- 增加交互式总结卡片 UI
- 增加用户登录、配额和隐私控制

## 开发检查

```bash
pip install -r requirements-dev.txt
ruff check .
pytest -q
```

## Skill 与知识卡

仓库现在同时包含三层：

- `skills/video-summary/SKILL.md`：规定视频总结、证据分级、事实核查和知识卡工作流。
- `plugin-manifest.json`：本仓库的 MCP 服务描述清单；它用于说明服务入口和工具列表，不是某个客户端专属的导入格式。
- `app.py` 与 `video_summary/`：远程 MCP 后端，负责 B 站链接、公开字幕和知识库读写。

证据等级的含义是：A 代表有完整材料并完成关键事实核查；B 代表有可用字幕或转写；C 代表只有页面元数据和来源线索；D 代表只有链接或极少信息。没有完整字幕时，系统不会把标题或简介冒充成完整视频总结。

知识库会按 BVID、规范链接或原始链接自动更新已有记录，避免同一视频重复入库。每条记录还可以保存 `source_type`、`evidence_basis`、`fact_check`、`topics`、`personal_value` 和 `learning_status`。`video_knowledge_base_stats` 可查看证据等级、学习状态、标签和主题统计。

当前版本仍不自动下载或转写音频；没有公开字幕时会明确返回证据限制。后续如加入音频转写，必须继续遵守平台权限、版权、成本和隐私边界。

### 连接 MCP

部署 Render 后，在 MCP 客户端中连接 `https://你的服务域名/mcp`。如使用 `skills/video-summary/agents/openai.yaml`，将其中的 `YOUR-RENDER-SERVICE` 替换为你的服务域名。不要把 `OPENAI_API_KEY` 或 `BILIBILI_COOKIE` 写入客户端配置；它们只能作为 Render Secret 配置。

## 安全提示

不要把以下内容提交到 GitHub：

- `OPENAI_API_KEY`
- B 站完整 Cookie 或 `SESSDATA`
- 用户私人视频、字幕或知识库数据

更多说明见 [PRIVACY.md](PRIVACY.md)。

## 许可证

MIT
