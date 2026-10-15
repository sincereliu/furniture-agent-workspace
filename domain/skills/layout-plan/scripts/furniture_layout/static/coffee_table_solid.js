/**
 * 预览里的固定茶几。纯几何，不依赖 three。
 *
 * 局部坐标与沙发相同：u 沿宽度，v 指向正面，w 向上。
 * 块都在外形尺寸里面。只认规范字段 category === "coffee_table"。
 * 要做成柜的茶几仍是盒子。
 */

const EXECUTABLE = new Set(["floor_cabinet", "wall_cabinet"]);

export function isFixedCoffeeTable(item) {
  if (!item || item.category !== "coffee_table") return false;
  if (item.manufacture === false) return true;
  return !EXECUTABLE.has(item.furniture_category);
}

function clamp(value, lo, hi) {
  return Math.min(hi, Math.max(lo, value));
}

/**
 * 整块桌面盖住外形的顶，四条腿缩在四角，中间一块层板。
 * 放不下就返回 null，调用方改画盒子。
 * 每块是 { role, box:[u0,v0,w0,u1,v1,w1] }。相邻的面至少错开 2 mm。
 */
export function coffeeTableParts(width, depth, height) {
  const W = width;
  const D = depth;
  const H = height;
  if (!(W >= 160 && D >= 160 && H >= 80)) return null;

  const gap = 2;
  const topT = clamp(H * 0.12, 16, 46);
  const leg = clamp(Math.min(W, D) * 0.07, 26, 52);
  const inset = clamp(Math.min(W, D) * 0.05, 14, 36);
  const legTop = H - topT - gap;
  if (legTop < 36) return null;
  if (inset + leg > W / 2 - 8 || inset + leg > D / 2 - 8) return null;

  const parts = [];
  const add = (role, box) => parts.push({ role, box });
  add("top", [0, 0, H - topT, W, D, H]);
  const feet = [
    [inset, inset],
    [W - inset - leg, inset],
    [inset, D - inset - leg],
    [W - inset - leg, D - inset - leg],
  ];
  for (const [u, v] of feet) add("leg", [u, v, 0, u + leg, v + leg, legTop]);

  const shelfT = clamp(H * 0.07, 12, 24);
  const shelfZ = clamp(legTop * 0.34, 24, legTop - shelfT - gap);
  const u0 = inset + leg + gap;
  const v0 = inset + leg + gap;
  const u1 = W - u0;
  const v1 = D - v0;
  if (u1 - u0 >= 40 && v1 - v0 >= 40 && shelfZ + shelfT <= legTop - gap) {
    add("shelf", [u0, v0, shelfZ, u1, v1, shelfZ + shelfT]);
  }
  return parts;
}
