/**
 * 固定沙发要有靠背、扶手和坐垫，并且跟着足迹的正面走。
 * 运行：node domain/skills/layout-plan/scripts/furniture_layout/static/sofa_solid_check.mjs
 */
import * as THREE from "../../../../../../vendor/three/0.186.0/three.module.js";
import { roomToThree } from "./layout_frame.js";
import {
  isFixedSofa,
  sofaFrame,
  sofaLocalBox,
  sofaMount,
  sofaParts,
  sofaRoomPoint,
} from "./sofa_solid.js";

function expect(condition, message) {
  if (!condition) throw new Error(message);
}

function near(actual, expected, eps = 1e-6) {
  if (Math.abs(actual - expected) > eps) {
    throw new Error(`${actual} != ${expected}`);
  }
}

function overlapSpan(a0, a1, b0, b1) {
  return Math.min(a1, b1) - Math.max(a0, b0);
}

function assertNoCoplanar(parts) {
  const faces = [];
  for (const part of parts) {
    const [u0, v0, w0, u1, v1, w1] = part.box;
    faces.push(["u", u0, v0, w0, v1, w1]);
    faces.push(["u", u1, v0, w0, v1, w1]);
    faces.push(["v", v0, u0, w0, u1, w1]);
    faces.push(["v", v1, u0, w0, u1, w1]);
    faces.push(["w", w0, u0, v0, u1, v1]);
    faces.push(["w", w1, u0, v0, u1, v1]);
  }
  for (let i = 0; i < faces.length; i += 1) {
    for (let j = i + 1; j < faces.length; j += 1) {
      const a = faces[i];
      const b = faces[j];
      if (a[0] !== b[0] || Math.abs(a[1] - b[1]) > 0.5) continue;
      if (overlapSpan(a[2], a[4], b[2], b[4]) > 1 && overlapSpan(a[3], a[5], b[3], b[5]) > 1) {
        throw new Error(`共面 ${a[0]}=${a[1]}`);
      }
    }
  }
}

function expectShape(width, depth, height, seats) {
  const parts = sofaParts(width, depth, height);
  expect(parts, `放得下的沙发要能拆开 ${width}×${depth}×${height}`);
  for (const part of parts) {
    const [u0, v0, w0, u1, v1, w1] = part.box;
    expect(u1 - u0 > 8 && v1 - v0 > 8 && w1 - w0 > 8, `块太薄 ${part.box}`);
    expect(
      u0 >= -1e-6 && v0 >= -1e-6 && w0 >= -1e-6
        && u1 <= width + 1e-6 && v1 <= depth + 1e-6 && w1 <= height + 1e-6,
      `块超出外形尺寸 ${part.box}`,
    );
  }
  assertNoCoplanar(parts);
  const back = parts.find((part) => part.role === "fabric" && part.box[1] === 0 && part.box[5] === height);
  expect(back, "靠背贴着背面，顶到外形高度");
  const arms = parts.filter((part) => part.role === "fabric" && part.box[5] < height);
  expect(arms.length === 2, "两侧各一个扶手");
  expect(arms.some((part) => part.box[0] === 0), "左扶手贴着左端");
  expect(arms.some((part) => part.box[3] === width), "右扶手贴着右端");
  expect(arms.every((part) => part.box[5] < height - 4 && part.box[1] > 0), "扶手比靠背矮，并且在靠背前面");
  const seat = parts.filter((part) => part.role === "cushion" && part.box[5] < height * 0.75);
  expect(seat.length === seats, `坐垫 ${seat.length} 块，期望 ${seats}`);
  expect(seat.every((part) => part.box[5] < height - 4 && part.box[1] > back.box[4]), "坐垫在靠背前面，而且更矮");
  const backCushions = parts.filter((part) => part.role === "cushion" && part.box[5] > height * 0.75);
  expect(backCushions.length === seats, "靠垫与坐垫块数相同");
  expect(
    backCushions.every((part) => part.box[4] > back.box[4] + 10 && part.box[5] < height - 4),
    "靠垫探出靠背，顶部留下靠背的上沿",
  );
  expect(parts.filter((part) => part.role === "wood").length === 2, "正面两只脚");
}

expectShape(2100, 900, 850, 3);
expectShape(1500, 850, 800, 2);
expectShape(900, 800, 750, 1);
expectShape(4000, 900, 900, 4);
expect(sofaParts(200, 200, 100) === null, "太小的外形继续用盒子");

expect(isFixedSofa({ category: "sofa" }), "没写成柜的沙发用沙发外形");
expect(isFixedSofa({ category: "sofa", manufacture: false, furniture_category: "floor_cabinet" }), "点名不生产的沙发用沙发外形");
expect(!isFixedSofa({ category: "sofa", furniture_category: "floor_cabinet" }), "要做成柜的沙发仍是盒子");
expect(!isFixedSofa({ category: "sofa", furniture_category: "wall_cabinet" }), "要做成吊柜的沙发仍是盒子");
expect(!isFixedSofa({ category: "chair" }), "只认沙发");
expect(!isFixedSofa({ category: "沙发" }), "不把名称当分类");

// 空间规则里的变换。下面三组角点是手算的，不从沙发函数反推。
const placed = [
  {
    width: 2100,
    depth: 900,
    z0: 0,
    footprint: [[100, 0], [2200, 0], [2200, 900], [100, 900]],
    samples: [[0, 0, 0, 100, 0, 0], [2100, 900, 400, 2200, 900, 400]],
  },
  {
    width: 2100,
    depth: 900,
    z0: 30,
    footprint: [[4000, 200], [4000, 2300], [3100, 2300], [3100, 200]],
    samples: [[0, 900, 100, 3100, 200, 130], [2100, 0, 0, 4000, 2300, 30]],
  },
  {
    width: 1800,
    depth: 800,
    z0: 0,
    footprint: [[3000, 4000], [1200, 4000], [1200, 3200], [3000, 3200]],
    samples: [[0, 800, 200, 3000, 3200, 200], [1800, 0, 0, 1200, 4000, 0]],
  },
];

for (const sample of placed) {
  const frame = sofaFrame(sample.footprint, sample.z0);
  const mount = sofaMount(frame);
  const group = new THREE.Object3D();
  group.position.set(...roomToThree(...mount.origin));
  group.setRotationFromMatrix(new THREE.Matrix4().makeBasis(
    new THREE.Vector3(...mount.x),
    new THREE.Vector3(...mount.y),
    new THREE.Vector3(...mount.z),
  ));
  group.updateMatrixWorld(true);
  const dot = mount.x[0] * mount.z[0] + mount.x[1] * mount.z[1] + mount.x[2] * mount.z[2];
  near(dot, 0, 1e-9);
  for (const [u, v, w, x, y, z] of sample.samples) {
    const room = sofaRoomPoint(frame, u, v, w);
    near(room[0], x);
    near(room[1], y);
    near(room[2], z);
    const local = sofaLocalBox([u, v, w, u, v, w]);
    const placedPoint = new THREE.Vector3(...local.center).applyMatrix4(group.matrixWorld);
    const three = roomToThree(x, y, z);
    near(placedPoint.x, three[0]);
    near(placedPoint.y, three[1]);
    near(placedPoint.z, three[2]);
  }
}

console.log("fixed sofa keeps its back, arms, and cushions inside the envelope");
