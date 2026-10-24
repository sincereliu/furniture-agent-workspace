# 网页展示模块

拥有房间页、项目列表、板件页及其三维展示。布局求解、板件规划、制造与 CAD 由对应阶段负责。

```text
furniture_web/
  *.py                   页面组装、静态服务挂载
  templates/             HTML 与房间页配置引导
  static/
    pages/room/          相机、手势、属性、同步、租约、房间导航
    pages/panels/        板件选择、侧栏、属性编辑与保存
    render/room/         房间场景、墙体、门窗、照明、标注与投影
    render/furniture/    家具预览几何与真实边缘
    render/outline/      整体描边、细线、接触消线与深度
    render/environment/  天空、庭院与场景材质
    render/panels/       冻结板件的场景、材质与取景
    shared/              页面与助手共用的响应式信号
    images/              运行时素材与许可
tests/node/              Node 行为检查
tests/browser/           WebGL 检查页与实际项目夹具，仅供测试
scripts/                 检查命令与夹具服务
references/              边界、视觉、检查方法与参考图
```

维护入口各自保留一类信息：

- [页面与模块边界](references/web-preview.md)：代码归属、模块接口和协作顺序。
- [三维预览视觉规范](references/visual-style.md)：已确认的卡通手办风、效果要求与参考图；改画面前必读。
- [检查方法](references/testing.md)：命令、覆盖范围、截图与运行环境。
- [统一 Web 待办](../../../backlog/web.md)：已复现问题、修复条件与落地状态；改描边接触或遮挡前核对。

新增代码按实际职责放入已有模块。入口负责组装，状态由对应控制器持有；页面把规范操作交给所属阶段，不复制布局或板件规则。不要把测试页放回 `static/`，也不在本模块另建待办状态体系。
