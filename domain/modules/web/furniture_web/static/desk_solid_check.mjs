/**
 * 固定书桌要有桌面、四条立腿、后方防窥挡板/背拉条与侧面拉条，正面留有开阔的膝部空档（Knee space）。
 * 运行：node domain/modules/web/furniture_web/static/desk_solid_check.mjs
 */
import { deskParts, isFixedDesk } from "./desk_solid.js";

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

function expectDesk(width, depth, height) {
  const parts = deskParts(width, depth, height);
  expect(parts, `放得下的书桌要能拆开 ${width}×${depth}×${height}`);
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

  const tops = parts.filter((part) => part.role === "top");
  expect(tops.length === 1, "一块桌面");
  const top = tops[0].box;
  expect(top[0] === 0 && top[1] === 0 && top[3] === width && top[4] === depth && top[5] === height, "桌面盖住外形的顶");
  expect(top[2] > height * 0.7, "桌面是薄板");

  const legs = parts.filter((part) => part.role === "leg");
  expect(legs.length === 4, "四条桌腿");
  expect(legs.every((part) => part.box[2] === 0 && part.box[5] < top[2] - 1), "腿落地，顶在桌面下面");

  const aprons = parts.filter((part) => part.role === "apron");
  expect(aprons.length >= 1, "包含后方挡板/拉条");

  // 膝部/椅子推入空间通透检查：桌子前部中间下方必须是空的
  const kneeU = width / 2;
  const kneeV = depth * 0.75;
  const kneeW = height * 0.45;
  expect(!parts.some((part) => contains(part.box, kneeU, kneeV, kneeW)), "正面膝部空间通透，椅子可以推入");
}

expectDesk(1400, 700, 750);
expectDesk(1200, 600, 750);
expectDesk(1600, 800, 750);
expectDesk(1000, 500, 720);
expectDesk(800, 400, 700);
expect(deskParts(200, 200, 200) === null, "太小的外形继续用盒子");

expect(isFixedDesk({ category: "desk" }), "没写成柜的书桌用书桌外形");
expect(
  isFixedDesk({ category: "desk", manufacture: false, furniture_category: "floor_cabinet" }),
  "点名不生产的书桌用书桌外形",
);
expect(!isFixedDesk({ category: "desk", furniture_category: "floor_cabinet" }), "要做成柜的书桌仍是盒子");
expect(!isFixedDesk({ category: "desk", furniture_category: "wall_cabinet" }), "要做成吊柜的书桌仍是盒子");
expect(!isFixedDesk({ category: "chair" }), "只认书桌，椅子用椅子外形");
expect(!isFixedDesk({ category: "sofa" }), "只认书桌，沙发用沙发外形");
expect(!isFixedDesk({ category: "coffee_table" }), "只认书桌，茶几用茶几外形");
expect(!isFixedDesk({ category: "书桌" }), "不把名称当分类");

console.log("fixed desk keeps desktop, legs, rear baffle, side aprons, and open knee space inside the envelope");
