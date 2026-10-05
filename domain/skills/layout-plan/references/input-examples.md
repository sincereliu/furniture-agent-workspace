# 布局输入示例

需要核对 `rooms[]` 的字段或 `manufacture: false` 的写法时再读。坐标和沿墙铺满的计算以[空间布局规则](spatial-layout-rules.md)为准。

一间卧室，一个要做的书柜靠北墙，一个要做的衣柜沿西墙铺满：

```yaml
rooms:
  - id: bedroom
    width_mm: 3600
    depth_mm: 4200
    height_mm: 2800
    openings:
      - id: door-1
        kind: door
        wall: south
        offset_mm: 400
        width_mm: 900
        height_mm: 2100
    items:
      - id: bookcase
        category: bookcase
        furniture_category: floor_cabinet
        width: 1200
        depth: 400
        height: 2100
        placement:
          mode: wall
          host_wall: north
          offset_mm: 900
      - id: wardrobe
        category: wardrobe
        furniture_category: floor_cabinet
        kind: wardrobe          # 铺满要写柜类：按工艺目录展开成可制造的单元
        depth: 600
        height: 2400
        placement:
          mode: wall
          host_wall: west
          fill: true
```

客户说房间里已有一件、不用做时，只给那一件加 `manufacture: false`。下面的书柜仍占位置，确认后不进板件：

```yaml
- id: bookcase
  category: bookcase
  furniture_category: floor_cabinet
  manufacture: false
  width: 900
  depth: 350
  height: 2100
  placement:
    mode: wall
    host_wall: east
    offset_mm: 200
```
