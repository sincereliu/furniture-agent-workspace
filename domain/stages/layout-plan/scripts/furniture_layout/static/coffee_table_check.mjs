/**
 * 固定茶几要有桌面、四条腿和中间的空档。
 * 运行：node domain/stages/layout-plan/scripts/furniture_layout/static/coffee_table_check.mjs
 */
import { coffeeTableParts, isFixedCoffeeTable } from "./coffee_table_solid.js";

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

function expectTable(width, depth, height) {
  const parts = coffeeTableParts(width, depth, height);
  expect(parts, `放得下的茶几要能拆开 ${width}×${depth}×${height}`);
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
  expect(legs.length === 4, "四条腿");
  expect(legs.every((part) => part.box[2] === 0 && part.box[5] < top[2] - 1), "腿落地，顶在桌面下面");
  expect(legs.every((part) => part.box[0] > 0 && part.box[1] > 0), "腿从外沿缩进去");
  const shelves = parts.filter((part) => part.role === "shelf");
  expect(shelves.length === 1, "一层板");
  const shelf = shelves[0].box;
  expect(shelf[2] > 8 && shelf[5] < top[2] - 8, "层板在腿的中段");
  expect(shelf[0] > legs[0].box[3] && shelf[1] > 0, "层板夹在腿之间");
  const air = top[2] - 8;
  expect(!parts.some((part) => contains(part.box, width / 2, depth / 2, air)), "桌面下面中间是空的");
}

expectTable(1200, 600, 400);
expectTable(800, 800, 420);
expectTable(1600, 700, 360);
expect(coffeeTableParts(80, 80, 40) === null, "太小的外形继续用盒子");

expect(isFixedCoffeeTable({ category: "coffee_table" }), "没写成柜的茶几用茶几外形");
expect(
  isFixedCoffeeTable({ category: "coffee_table", manufacture: false, furniture_category: "floor_cabinet" }),
  "点名不生产的茶几用茶几外形",
);
expect(!isFixedCoffeeTable({ category: "coffee_table", furniture_category: "floor_cabinet" }), "要做成柜的茶几仍是盒子");
expect(!isFixedCoffeeTable({ category: "coffee_table", furniture_category: "wall_cabinet" }), "要做成吊柜的茶几仍是盒子");
expect(!isFixedCoffeeTable({ category: "table" }), "只认茶几");
expect(!isFixedCoffeeTable({ category: "desk" }), "书桌仍是盒子");
expect(!isFixedCoffeeTable({ category: "茶几" }), "不把名称当分类");

console.log("fixed coffee table keeps a top, four legs, and open space inside the envelope");
