/**
 * 固定椅子要有立柱/立腿、座面、靠背与下方和中间的通透空档。
 * 运行：node domain/modules/web/tests/node/chair_solid_check.mjs
 */
import { chairParts, isFixedChair } from "../../furniture_web/static/render/furniture/chair_solid.js";

function expect(condition, message) {
  if (!condition) throw new Error(message);
}

function overlapSpan(a0, a1, b0, b1) {
  return Math.min(a1, b1) - Math.max(a0, b0);
}

function contains(box, u, v, w) {
  return u > box[0] && u < box[3] && v > box[1] && v < box[4] && w > box[2] && w < box[5];
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

function expectChair(width, depth, height) {
  const parts = chairParts(width, depth, height);
  expect(parts, `放得下的椅子要能拆开 ${width}×${depth}×${height}`);
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

  const legs = parts.filter((part) => part.role === "leg");
  expect(legs.length === 4, "四条腿（两根后立柱与两根前腿）");
  expect(legs.every((part) => part.box[2] === 0), "四条腿全部落地");
  const tallLegs = legs.filter((part) => Math.abs(part.box[5] - height) < 1e-6);
  expect(tallLegs.length === 2, "两根后立柱贯穿到顶支撑靠背");

  const seats = parts.filter((part) => part.role === "seat");
  expect(seats.length === 1, "一块座面");
  const seat = seats[0].box;
  expect(seat[2] > height * 0.35 && seat[5] < height * 0.7, "座面位于适宜高度");

  const backs = parts.filter((part) => part.role === "back");
  expect(backs.length >= 1, "至少一块靠背板");
  const topBack = backs[0].box;
  expect(topBack[5] > height * 0.8 && topBack[2] > seat[5], "靠背板位于座面上方高位");

  const airUnder = seat[2] / 2;
  expect(!parts.some((part) => contains(part.box, width / 2, depth / 2, airUnder)), "座面下方中间是空的");
  const airAbove = (seat[5] + topBack[2]) / 2;
  expect(!parts.some((part) => contains(part.box, width / 2, depth * 0.7, airAbove)), "座面上方前段是空的");
}

expectChair(500, 500, 850);
expectChair(450, 480, 800);
expectChair(600, 600, 950);
expectChair(300, 300, 400);
expectChair(550, 520, 780);
expect(chairParts(100, 100, 100) === null, "太小的外形继续用盒子");

expect(isFixedChair({ category: "chair" }), "没写成柜的椅子用椅子外形");
expect(
  isFixedChair({ category: "chair", manufacture: false, furniture_category: "floor_cabinet" }),
  "点名不生产的椅子用椅子外形",
);
expect(!isFixedChair({ category: "chair", furniture_category: "floor_cabinet" }), "要做成柜的椅子仍是盒子");
expect(!isFixedChair({ category: "chair", furniture_category: "wall_cabinet" }), "要做成吊柜的椅子仍是盒子");
expect(!isFixedChair({ category: "desk" }), "只认椅子，书桌仍是盒子");
expect(!isFixedChair({ category: "sofa" }), "只认椅子，沙发用沙发外形");
expect(!isFixedChair({ category: "coffee_table" }), "只认椅子");
expect(!isFixedChair({ category: "椅子" }), "不把名称当分类");

console.log("fixed chair keeps legs, seat, back, and open air inside the envelope");
