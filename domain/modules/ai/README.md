# AI 助手模块

独立应用模块，不属于六阶段家具流程。代码、界面、测试和维护文档集中在这里。

```text
domain/modules/ai/
  furniture_ai/     模型连接、配置、登录和进程生命周期
  furniture_chat/   网页助手、会话、HTTP、界面与静态资源
  tests/           本模块的测试及 ASGI 测试辅助
  references/      维护、禁用与登录隔离说明
```

`furniture_ai` 不导入家具工作流或 CAD。`furniture_chat` 依赖宿主提供的项目和布局能力，经 `integration.install()` 接入预览服务；六阶段生成不依赖助手。

宿主的 `runtime_paths.bootstrap_runtime_paths()` 加载本模块路径，现有启动命令和 Python 包名不变。单独复用模型接入层时，将本目录加入 Python 导入路径即可，无需加载家具阶段包。

启动前设置 `FURNITURE_WEB_CHAT=0` 并重启预览服务，即可停止加载 AI 包、注册接口和输出页面资源；默认 `1`。配置与历史记录不会删除。

- [维护、启用和禁用](references/ai-integration.md)
- [Codex 登录与进程隔离](references/codex-isolation.md)

仍使用同一个测试入口，自动发现阶段测试与本模块测试：

```powershell
.\.venv\Scripts\python.exe domain/stages/cad-generated/scripts/run_tests.py
.\.venv\Scripts\python.exe domain/stages/cad-generated/scripts/run_tests.py -p test_ai_providers.py
.\.venv\Scripts\python.exe domain/stages/cad-generated/scripts/run_tests.py -p test_web_chat_feature.py
```
