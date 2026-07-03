# 板件定位规范（Panel Placement Specification）

> 本文档定义柜体各板件的 min corner 坐标和尺寸计算公式，供代码生成、验证和排错使用。
> 手改任何坐标前，先对照此表确认目标值。

---

## 零、坐标系

```
原点: 柜体左-后-下角 (min corner of the cabinet bounding box)
X → 右 (柜体宽度方向)
Y → 前 (柜体深度方向)
Z → 上 (柜体高度方向)

所有坐标均指板件 min corner。
```

**约定**：
- 所有 `Pos(x, y, z) * Box(...)` 中的 `(x, y, z)` 是 min corner
- `Box(Align.MIN, Align.MIN, Align.MIN)` 保证初始 min corner 在 `(0, 0, 0)`
- `_face_place(panel, x, y, z)` 的 `(x, y, z)` 是 min corner
- **禁止**：`Pos(x + size/2, y + size/2, z)` — 这是中心点定位，与本文档矛盾

---

## 一、通用变量

| 变量 | 来源 | 落柜示例值 | 说明 |
|------|------|-----------|------|
| W | 用户输入 | 800 | 柜体总宽 mm |
| H | 用户输入 | 1000 | 柜体总高 mm |
| D_total | 用户输入 | 600 | 柜体总深 mm |
| T | DEFAULT_DIMS | 18 | 柜体板厚 mm |
| T_back | DEFAULT_DIMS | 9 | 背板厚 mm |
| T_door | DEFAULT_DIMS | 18 | 门板厚 mm |
| toe_kick_h | DEFAULT_DIMS | 50 | 踢脚线高 mm |
| back_offset | DEFAULT_DIMS | 18 | 背板距后 mm |
| door_margin | DEFAULT_DIMS | 1.5 | 门板四周缝 mm |
| door_hinge_gap | DEFAULT_DIMS | 2.0 | 门铰链深度间隙 mm |
| side_depth | D_total - T_door - door_hinge_gap | 580 | 侧板深度 mm |
| internal_W | W - 2T | 764 | 内部净宽 mm |
| internal_H | H - toe_kick_h - 2T | 914 | 内部净高 mm |
| shelf_y_start | back_offset + T_back | 27 | 层板/中立板 Y 起点 mm |
| shelf_d | side_depth - back_offset - T_back | 553 | 层板/中立板深度 mm |

---

## 二、板件定位一览表

所有坐标 = `(x_min, y_min, z_min)` — 即板件左下前角。

### 2.1 侧板 (side)

| 字段 | 左侧板 | 右侧板 |
|------|--------|--------|
| x_min | `0` | `W - T` |
| y_min | `0` | `0` |
| z_min | `0` | `0` |
| size | `(T, side_depth, H)` | `(T, side_depth, H)` |
| 说明 | 从背面延伸到前面，通高 | 同左 |

```
左侧板 min=(0, 0, 0)        max=(18, 580, 1000)
右侧板 min=(782, 0, 0)      max=(800, 580, 1000)
```

### 2.2 顶板 (top)

| 字段 | 值 |
|------|-----|
| x_min | 左侧板右侧面 (FaceQuery.placed_between_x) |
| y_min | `0` |
| z_min | 侧板顶面 - T |
| size | `(internal_W, side_depth, T)` |

```
顶板 min=(18, 0, 982)    max=(782, 580, 1000)
```

### 2.3 底板 (bottom)

| 字段 | 值 |
|------|-----|
| x_min | 左侧板右侧面 |
| y_min | `0` |
| z_min | `toe_kick_h` |
| size | `(internal_W, side_depth, T)` |

```
底板 min=(18, 0, 50)    max=(782, 580, 68)
```

### 2.4 背板 (back)

| 字段 | 值 |
|------|-----|
| x_min | 左侧板右侧面 |
| y_min | `back_offset` |
| z_min | `toe_kick_h` |
| size | `(internal_W, T_back, H - toe_kick_h)` |

```
背板 min=(18, 18, 50)  max=(782, 27, 1000)
距后 18mm 插槽安装
```

### 2.5 后踢脚板 (toe_kick_back)

| 字段 | 值 |
|------|-----|
| x_min | 左侧板右侧面 |
| y_min | `0` （紧贴背面） |
| z_min | `0` |
| size | `(internal_W, T, toe_kick_h)` |

```
后踢脚 min=(18, 0, 0)  max=(782, 18, 50)
```

### 2.6 前踢脚板 (toe_kick_front)

| 字段 | 值 |
|------|-----|
| x_min | 左侧板右侧面 |
| y_min | `side_depth - T` （紧贴前面） |
| z_min | `0` |
| size | `(internal_W, T, toe_kick_h)` |

```
前踢脚 min=(18, 562, 0)  max=(782, 580, 50)
```

### 2.7 踢脚支撑板 (toe_kick_support)

| 字段 | 值 |
|------|-----|
| x_min | 沿 X 均匀分布（间隙 = kick_w / 3） |
| y_min | `T` （后踢脚板前方） |
| z_min | `0` |
| size | `(T, side_depth - 2T, toe_kick_h)` |

```
支撑1 min=(273, 18, 0)  max=(291, 562, 50)
支撑2 min=(527, 18, 0)  max=(545, 562, 50)
```

### 2.8 固定/活动层板 (shelf)

| 字段 | 值 |
|------|-----|
| x_min | 左侧板右侧面（或有中立板时的分区） |
| y_min | `back_offset + T_back` |
| z_min | `z_center - T / 2` |
| size | `(shelf_w, side_depth - back_offset - T_back, T)` |

```
层板1 min=(18, 27, 233)  max=(782, 580, 251)
层板2 min=(18, 27, 416)  max=(782, 580, 434)
层板3 min=(18, 27, 598)  max=(782, 580, 616)
层板4 min=(18, 27, 781)  max=(782, 580, 799)
```
层板 Y 从背板槽后方起，深度不足以穿透背板。

### 2.9 中立板 (divider)

| 字段 | 值 |
|------|-----|
| x_min | `x_center - T / 2` |
| y_min | `back_offset + T_back`（同层板） |
| z_min | `from_z`（默认=z_bottom_internal） |
| size | `(T, side_depth - back_offset - T_back, dh)` |

```
深度同层板，不穿透背板。
```

### 2.10 门板 (door)

| 字段 | 值 |
|------|-----|
| x_min | `door_margin` (左) 或 `W - door_margin - door_w` (右) |
| y_min | `side_depth + door_hinge_gap` |
| z_min | `toe_kick_h + door_margin` |
| size | `(door_w, T_door, door_h)` |

```
左门 min=(2, 582, 52)    max=(398, 600, 998)
右门 min=(402, 582, 52)  max=(798, 600, 998)
门板在侧板前方，留 2mm 铰链间隙。
```

---

## 三、禁止的定位模式

以下模式会导致板件定位错误，**禁止使用**：

```python
# ❌ 禁止：中心点定位
Pos(x + size_x / 2, y + size_y / 2, z) * solid

# ❌ 禁止：门板 Y 不加铰链间隙
door_y = side_depth  # 门板嵌在侧板里

# ❌ 禁止：踢脚支撑沿 Y 方向分布
y = T + (i + 1) * gap  # 支撑板飞出柜体

# ❌ 禁止：层板/中立板从 Y=0 开始
y = 0  # 穿透背板槽
```

对应的正确写法见 `core/generator.py`。

---

## 四、验证命令

每次修改定位代码后运行：

```bash
python -c "
import sys; sys.path.insert(0,'skills/furniture')
from core.generator import CabinetGenerator
from templates.floor_cabinet import FloorCabinet
gen = CabinetGenerator(800,1000,600)
FloorCabinet(shelf_count=4, n_doors=2).build(gen)
for p in gen.panels:
    print(f'{p.label}: x=[{p.pos_x:.0f},{p.pos_x+p.size_x:.0f}] y=[{p.pos_y:.0f},{p.pos_y+p.size_y:.0f}] z=[{p.pos_z:.0f},{p.pos_z+p.size_z:.0f}]')
"
```

对照上表确认所有板件的 Y 范围、X 范围和 Z 范围。

---

*最后更新: 2026-07-01*