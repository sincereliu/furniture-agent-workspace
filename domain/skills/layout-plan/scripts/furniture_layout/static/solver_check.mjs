import assert from "node:assert/strict";
import {
  blockerAt,
  detailValues,
  distancesOf,
  localFootprint,
  polygonsOverlap,
  rangesOverlap,
  resolveInteger,
  solvePlanarDrag,
  solveRotation,
} from "./layout_solver.js";

const box = (x, y, w = 1000, d = 500) => [
  [x, y], [x + w, y], [x + w, y + d], [x, y + d],
];

// 贴边接触放行，正面积重叠才算干涉（与 test_room_scene_placement.py 一致）
assert.equal(polygonsOverlap(box(0, 0), box(1000, 0)), false);
assert.equal(polygonsOverlap(box(0, 0), box(999, 0)), true);
assert.equal(rangesOverlap(0, 500, 500, 900), false);
assert.equal(rangesOverlap(0, 500, 499, 900), true);

const scene = {
  room: { width_mm: 3000, depth_mm: 2000, height_mm: 2400 },
  obstacles: [],
  openings: [
    { id: "win", kind: "window", wall: "north", offset_mm: 1200, width_mm: 600, sill_height_mm: 900, height_mm: 1000 },
  ],
  items: [
    {
      id: "desk",
      label: "书桌",
      width: 1000,
      depth: 500,
      height: 750,
      z_start: 0,
      z_end: 750,
      placement: { mode: "free", origin_x_mm: 0, origin_y_mm: 500, rotation_z_deg: 0 },
      footprint: localFootprint({ width: 1000, depth: 500 }, 0, 500, 0),
    },
    {
      id: "cabinet",
      label: "高柜",
      width: 800,
      depth: 500,
      height: 2000,
      z_start: 0,
      z_end: 2000,
      placement: { mode: "free", origin_x_mm: 1800, origin_y_mm: 500, rotation_z_deg: 0 },
      footprint: localFootprint({ width: 800, depth: 500 }, 1800, 500, 0),
    },
  ],
};

// 四向净距：书桌东侧最近邻是高柜（净距 800mm），其余三侧到墙
const gaps = distancesOf(scene, scene.items[0]);
assert.deepEqual(gaps.east, { gap: 800, label: "高柜" });
assert.deepEqual(gaps.west, { gap: 0, label: "墙" });
assert.deepEqual(gaps.north, { gap: 500, label: "墙" });
assert.deepEqual(gaps.south, { gap: 1000, label: "墙" });

// 二分整数求解：书桌往东最多走 800mm 贴住高柜，再往东被挡住
const blocker = solvePlanarDrag(scene, scene.items[0], [0, 500], 1200, 0);
assert.equal(scene.items[0].placement.origin_x_mm, 800);
assert.equal(blocker && blocker.id, "cabinet");

// 旋转求解：贴墙件绕中心旋转自动收回房间内并转为 free
const rotated = solveRotation(scene, scene.items[0], [500, 750], 90);
assert.equal(rotated.applied, true);
assert.equal(scene.items[0].placement.mode, "free");
assert.equal(scene.items[0].placement.rotation_z_deg, 90);

// 遮挡北墙窗洞（z 900..1900）的高柜被判为 blocked_opening
const tallAtWindow = localFootprint(scene.items[1], 1300, 0, 0);
const winBlocker = blockerAt(scene, tallAtWindow, 0, 2000, "cabinet");
assert.equal(winBlocker && winBlocker.reason, "blocked_opening");

// 低于窗台（z 0..750 < 900）的矮桌贴北墙窗下放行
const lowAtWindow = localFootprint(scene.items[0], 1300, 0, 0);
assert.equal(blockerAt(scene, lowAtWindow, 0, 750, "desk"), null);

const detail = detailValues(scene, scene.items[1]);
assert.equal(detail.width, 800);
assert.equal(detail.ceiling, 400);

const binary = resolveInteger(0, 100, (v) => (v > 37 ? { reason: "interference" } : null));
assert.equal(binary.value, 37);

console.log("layout solver collision, clearance, and integer contact stop ok");
