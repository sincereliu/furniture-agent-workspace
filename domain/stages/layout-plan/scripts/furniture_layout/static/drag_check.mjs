import assert from "node:assert/strict";
import { groundDragDelta, wallSnap } from "./layout_drag.js";

// 正南向下看：右 = 东，前 = 南（z 分量 -0.5 表示俯角 30°）。
const south = { right: [1, 0, 0], forward: [0, 1, -0.5] };

// 横向：往右拖 10px 就是往东走 10×scale，与俯仰无关。
assert.deepEqual(groundDragDelta({ dx: 10, dy: 0, scale: 5, ...south }), [50, 0]);

// 纵向：往拖 10px 是朝相机走 10×scale/sin(俯角)（南为 +y，所以往北是负）。
const down = groundDragDelta({ dx: 0, dy: 10, scale: 5, ...south });
assert.ok(Math.abs(down[0]) < 1e-9, `纵向不该横移: ${down}`);
assert.ok(Math.abs(down[1] + 100) < 1e-9, `往拖 10px 应朝相机走 100mm，实际 ${down[1]}`);

// 线性：同样的屏幕位移，走同样的距离——**与抓在家具哪个高度无关**。
// 旧算法用的是光标射线的地面交点，抓得越高交点越远，同样的手抖换出几米。
const a = groundDragDelta({ dx: 12, dy: 0, scale: 5, ...south });
const b = groundDragDelta({ dx: 12, dy: 0, scale: 5, ...south });
assert.deepEqual(a, b);
assert.ok(Math.hypot(...a) === 60, "12px × 5mm/px 就该是 60mm");

// 贴地平线（|forward[2]| → 0）不许爆炸：下限把它压到 0.2。
const flat = groundDragDelta({ dx: 0, dy: 10, scale: 5, right: [1, 0, 0], forward: [0, 1, 0] });
assert.ok(Math.abs(flat[1]) <= 10 * 5 / 0.2 + 1e-9, `贴地平线时位移要封顶，实际 ${flat[1]}`);

// 相机转到别的方位时，横向跟着相机右向量走，不写死房间轴。
const east = groundDragDelta({ dx: 10, dy: 0, scale: 5, right: [0, 1, 0], forward: [1, 0, -0.5] });
assert.deepEqual(east, [0, 50]);

console.log("ground drag follows the item, not the cursor's ground ray");

/* ---------- 贴回墙面 ---------- */

const room = { width_mm: 3000, depth_mm: 4000 };
const box = (x0, y0, x1, y1) => [
  { x_mm: x0, y_mm: y0 },
  { x_mm: x1, y_mm: y0 },
  { x_mm: x1, y_mm: y1 },
  { x_mm: x0, y_mm: y1 },
];

// 背面正好落在北墙上（y=0）且轴对齐 → 认回靠北墙。沿墙位置不在这一步取。
assert.deepEqual(wallSnap({ footprint: box(322, 0, 2722, 600), rotation: 0, room }), {
  host_wall: "north",
});

// 离墙 2mm：不算贴墙，不许自动吸附（否则"我就要留一条缝"会被悄悄改掉）。
assert.equal(wallSnap({ footprint: box(322, 2, 2722, 602), rotation: 0, room }), null);

// 斜着放的：不吸附，也不自动摆正。
assert.equal(wallSnap({ footprint: box(322, 0, 2722, 600), rotation: 15, room }), null);

// 四面都只认墙，不取沿墙偏移。
assert.deepEqual(wallSnap({ footprint: box(2700, 800, 3000, 1400), rotation: 90, room }), {
  host_wall: "east",
});
assert.deepEqual(wallSnap({ footprint: box(300, 3400, 2700, 4000), rotation: 180, room }), {
  host_wall: "south",
});
assert.deepEqual(wallSnap({ footprint: box(0, 900, 600, 3300), rotation: 270, room }), {
  host_wall: "west",
});

// 贴在墙上但探出房间（比如拖到墙角外）：不认——那份几何本来就不合法。
assert.equal(wallSnap({ footprint: box(322, 0, 3200, 600), rotation: 0, room }), null);
console.log("a free unit dragged flush against a wall becomes wall-mounted again");
