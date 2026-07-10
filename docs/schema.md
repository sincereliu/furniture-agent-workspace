# Schema

Schema 层是 Agent、领域包和服务共同使用的纯数据契约，不依赖 CAD
引擎。

## 已实现的核心契约

- `DesignIntent`：用户想建造什么；包含成品外包尺寸、布局要求、结构
  偏好、约束、假设、未决项和确认状态。
- `Project`：一个持续迭代的家具设计项目。
- `Revision`：一次不可混淆的意图版本，记录父版本、意图哈希、工作流、
  验证和产物。
- `WorkflowState`：只记录当前运行时真正执行过的阶段。
- `ValidationReport`：带稳定错误码、严重级别和字段路径的验证结果。
- `ArtifactManifest`：产物路径、SHA-256、文件大小、来源 Revision 和
  过期状态。

`FurnitureSpec` 仍作为现有柜体规划器的窄执行输入，由 Orchestrator 从
已确认的 DesignIntent 转换得到。它不替代 DesignIntent。
