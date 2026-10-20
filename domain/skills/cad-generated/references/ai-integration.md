# AI 接入层维护

`scripts/furniture_ai/` 负责模型连接；它不导入家具工作流、布局、板件或 CAD 包，
不读取家具项目、不执行模型返回的工具调用。接入层接收调用方提供的消息与工具 Schema，
返回统一的 `thinking`、`content`、`tool_calls`。

## 文件归属

| 文件 | 职责 |
| --- | --- |
| `furniture_ai/__init__.py` | 对外公开接口 |
| `furniture_ai/service.py` | 通道分发、Codex 登录状态及登录入口、预热与关闭 |
| `furniture_ai/settings.py` | 模型设置读写、脱敏、连接参数准入 |
| `furniture_ai/contracts.py` | 公共错误 `AIConnectionError`、规范枚举和超时 |
| `furniture_ai/codex.py` | Codex App Server 通信、独立登录和进程生命周期 |
| `furniture_ai/isolation.py` | 仓库外数据目录、子进程环境和路径约束 |
| `furniture_ai/agy.py` | AGY 参数与结构化输出适配 |
| `furniture_ai/openai_compatible.py` | OpenAI 兼容 HTTP 接口与消息适配 |
| `furniture_ai/cli_protocol.py` | CLI 消息格式、输出 Schema 和增量字符串解析 |
| `furniture_ai/discovery.py` | 本机 CLI 发现和短时缓存 |
| `furniture_chat/conversation.py` | 家具项目上下文、对话历史、并发保护、阶段准入与工具执行循环 |
| `furniture_chat/http.py` | AI HTTP 路由、本机访问检查、错误响应与连接关闭挂钩 |
| `furniture_chat/integration.py` | 唯一宿主挂载点：注册路由、静态资源、页面扩展和退出清理 |
| `furniture_chat/page.py` | 组装可选页面片段，提供聊天 URL 和两个布局回调 |
| `furniture_chat/templates/` | 助手面板、模型弹窗、按钮和样式；启用时内联输出，保持原有页面交付方式 |
| `furniture_chat/static/layout_chat.js` | 消息显示、模型设置和登录按钮；只从 `/web-chat/` 提供 |
| `furniture_workflow/web_agent_chat.py` | 原公开调用的兼容入口；核心工作流不导入它 |
| `server.py` | 读取功能开关，向可选路由传入项目读取、Store 路径和本机权限检查 |

布局阶段只定义空的 `PageExtension` 插槽，不导入 AI 包，也不嵌入聊天 URL、UI 或脚本。
扩展通过 `pageHost.onProjectUpdated` 请求刷新项目，或通过 `pageHost.onStatusToast` 显示状态。
只读和分享页面即使收到扩展参数，也不会输出它。换模型或修改连接方式时，
先改所属通道文件；阶段技能、家具默认值和方案判断不放进接入层。

## 调用约定

宿主通过 `furniture_ai` 的公开接口调用，不访问提供方的内部客户端：

```python
import furniture_ai as ai

config = ai.load_llm_config(store_root)
ai.validate_connection_config(config)
step = ai.complete(config, messages, tools, on_reply_delta=show_progress)
# 由宿主校验并执行 step["tool_calls"]；complete 不执行它们。
```

连接配置接口为 `load_llm_config`、`public_llm_config`、`save_llm_config`。
Codex 登录接口为 `codex_authentication_state()`、`start_codex_login()`；
`prewarm_llm(config)` 只预热已配置的连接，不发起登录或推理。
`shutdown()` 关闭持有的模型连接，并阻止已排队的预热再次启动进程；宿主退出时调用。
`AIConnectionError` 包含 `code`、`message`、`status_code`，现有网页错误契约保持不变。

各通道都接收规范化的 OpenAI 风格消息和函数 Schema；工具内容由调用方决定。
具体家具项目的 `allowed_tools`、`project_id` 范围、确认和冻结由工作流检查。

Codex 的仓库外目录、凭据和进程边界见 [Codex 隔离](codex-isolation.md)。
提取模块不会迁移凭据、修改 App 配置或改变登录状态。

## 启用与彻底禁用

启动预览服务前，在同一个 PowerShell 进程设置：

```powershell
$env:FURNITURE_WEB_CHAT = "0"
.\.venv\Scripts\python.exe domain/skills/cad-generated/scripts/server.py
```

开关只接受 `0` / `1`，默认 `1` 保持现有行为。修改后须退出并重启预览服务；仅刷新页面不会改变正在运行的服务。
`0` 时，宿主不导入 `furniture_chat` / `furniture_ai`，不注册模型配置、登录和项目聊天路由；这些请求返回 404。
不挂载 `/web-chat/`，页面不输出助手按钮、面板、模型弹窗、聊天样式或脚本，浏览器也不会发起 AI 初始化请求。
核心家具工作流与项目文件保持可用。禁用不会清除模型配置、登录凭据或聊天记录。
此开关控制网页接入；显式调用通用 `furniture_ai` API 的其他宿主自行管理其生命周期。

恢复时将变量设为 `1`，或 `Remove-Item Env:FURNITURE_WEB_CHAT` 后重新启动。

## 验证

```powershell
.\.venv\Scripts\python.exe domain/skills/cad-generated/scripts/run_tests.py -p test_ai_providers.py
.\.venv\Scripts\python.exe domain/skills/cad-generated/scripts/run_tests.py -p test_codex_isolation.py
.\.venv\Scripts\python.exe domain/skills/cad-generated/scripts/run_tests.py -p test_web_agent_chat.py
.\.venv\Scripts\python.exe domain/skills/cad-generated/scripts/run_tests.py -p test_web_chat_feature.py
```

通道和参数测试不依赖真实账号；独立导入测试检查接入包不会加载家具运行时或启动子进程。
家具项目测试检查模型调用结果仍经过当前项目的工具准入、阶段状态和历史持久化。
功能开关测试在全新解释器中阻止两个可选包导入，检查禁用后的真实 ASGI 响应、核心板件生成及布局预览。
同时验证启用后的资源与七个 HTTP 动作继续使用宿主访问检查，页面分享模式不携带 AI 扩展。

边界审计：迁移的规范枚举和输出 Schema 属于 `schema`，配置、路径和来源检查属于
`validation`，登录及进程状态属于 `state`，消息和通道适配属于 `structured_protocol`，
配置文件、子进程和 HTTP 属于 `side_effect`。没有新增自然语言理解或家具方案选择逻辑。
