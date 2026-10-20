# 网页 Codex 接入边界

本机家具项目调用已安装的 Codex CLI，通过 `app-server --listen stdio://` 通信。
模块根目录为 `domain/modules/ai/`。接入入口在 `furniture_ai/__init__.py`，Codex 通信与登录在
`furniture_ai/codex.py`，路径和环境契约在 `furniture_ai/isolation.py`。
模块职责与公开接口见 [AI 接入层维护](ai-integration.md)。

## 独立数据

- 固定使用 `%USERPROFILE%/.furniture-agent/codex-home`，不提供网页或模型可修改的路径参数。
  不使用可能被 Windows 打包应用重定向到 App 缓存的 `AppData/Local`（即使绝对路径也可能被重定向）。
- 必须位于当前仓库、其他 Git 工作区、默认或父进程指定的 Codex App 数据目录之外；目录联接解析后仍须满足该条件。
- `CODEX_HOME`、`CODEX_SQLITE_HOME` 只传给子进程；不修改父进程或系统环境变量。
- 子进程的工作目录、SQLite 状态、日志均指向独立目录。凭据存储固定为 `file`，不复用 App 的系统凭据库。
  握手后通过 `config/read` 复核生效目录和凭据库，若被本机策略覆盖则拒绝继续。
- 不复制、读取或迁移 App 的 OAuth 文件。继承的 Codex/OpenAI 凭据环境变量从子进程环境移除。用户需要在家具项目中独立登录一次。
- 不修改安装文件或全局配置，不连接 App 的守护进程，不操作已有 App 聊天。只关闭本项目 `Popen` 创建的进程。

`ephemeral` 只控制聊天记录的持久化，不能代替上述数据目录隔离。
同账号的订阅额度仍然共享。

## 登录接口

- `GET /api/llm/codex/status`：仅返回 `authenticated`、`status`、`isolated`，不返回邮箱、账号 ID 或令牌。
- `POST /api/llm/codex/login`：通过独立进程的 `account/login/start` 发起浏览器登录。
  只接受官方 HTTPS 登录地址；临时 `auth_url` 只供当前页面打开，不落入项目配置、聊天历史或浏览器存储。
- 两个接口只接受本机来源和本机 Host；拒绝跨来源 Origin 与跨站 Fetch Metadata。响应禁止缓存。
- 网页设置有“单独登录 Codex”按钮；首次未登录时不显示“已就绪”。弹窗关闭后停止页面轮询。
- OAuth 凭据由官方 Codex 在独立目录维护和刷新，家具 Python 代码不解析凭据文件。
  对外错误使用固定摘要，不透出 CLI 原始错误或标准错误输出。

登录信息不属于版本控制产物。项目中只保存模型设置和家具对话，不保存新 Codex OAuth 凭据。
现有 `store/_llm_config.json` 中其他 API 通道已保存的密钥不在此次迁移范围内，`store/` 继续由 Git 忽略。

## 验证

```powershell
.\.venv\Scripts\python.exe domain/skills/cad-generated/scripts/run_tests.py -p test_codex_isolation.py
.\.venv\Scripts\python.exe domain/skills/cad-generated/scripts/run_tests.py -p test_web_agent_chat.py
```

新增运行时判断仅用于路径和来源验证、凭据状态与 JSON-RPC 协议、进程及文件副作用。
自然语言理解、家具方案和阶段提案仍由模型完成，没有自然语言匹配例外。

官方协议：[环境变量](https://learn.chatgpt.com/docs/config-file/environment-variables)、
[认证](https://learn.chatgpt.com/docs/auth)、
[App Server](https://learn.chatgpt.com/docs/app-server)。
