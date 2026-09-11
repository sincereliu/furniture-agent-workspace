# 六面钻 XML 导出（KDTPanelFormat）

回答"如何把已确认孔位导出给柜柜六面钻机床加工"。本子流程仅在用户明确要求出六面钻/机床加工文件时读取，不进入制造方案主流程。

## 契约

- 由 `scripts/furniture_manufacturing/export_six_side_drill.py` + `devices/six_side_drill_guigui.yaml` 完成。
- 从 `drilled-holes.json` 反推板件和孔位，逐板生成 `KDTPanelFormat` XML。
- 槽位尚无设备侧数据契约；输入包含槽位时明确拒绝，避免静默漏加工。

## 坐标与设备映射

- 机床坐标 X=PanelLength, Y=PanelWidth, Z=PanelThickness。
- 设备映射 yaml 按面板类型定义 `sixd_x_from_box`/`sixd_y_from_box`（机床轴）和 `x1_from_hole`/`y1_from_hole`/`z1_from_hole`（局部坐标→机床坐标）。
- 水平孔方向须从世界轴转换为机床轴后再确定 Quadrant。
- 导出层从 `HoleSpec.is_face_hole` 直接读取 TypeNo，不再从世界坐标推导：`True` → TypeNo=1 垂直孔，`False` → TypeNo=2 水平孔。

## 板件轮廓

- `PanelOutline` 顶点严格按 `(0, sixd_y) → (0, 0) → (sixd_x, 0) → (sixd_x, sixd_y)` 逆时针闭合。

## 关联

- 孔位数据源：`manufacturing_bom.py` 的 `emit_drilled_holes()` 把结构化 `panel_type` 写入 `drilled-holes.json` 每块板。
- 产物登记：CAD 阶段 `workflow_artifact_writer.py` 调用 `drill_json_to_xml_files()` 写 `六面钻文件/<panel>.xml`，并登记为 manifest `six_side_drill_xml`。
