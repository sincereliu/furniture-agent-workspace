/**
 * 预览里的固定椅子。纯几何，不依赖 three。
 *
 * 局部坐标与沙发相同：u 沿宽度，v 从靠背指向正面（局部 +Y），w 向上。
 * 块都在外形尺寸里面。朝向跟足迹一致：足迹第 0 点是靠背左下角。
 * 只认规范字段 category === "chair"。要做成柜的椅子仍是盒子。
 */

const EXECUTABLE = new Set(["floor_cabinet", "wall_cabinet"]);

export function isFixedChair(item) {
  if (!item || item.category !== "chair") return false;
  if (item.manufacture === false) return true;
  return !EXECUTABLE.has(item.furniture_category);
}

function clamp(value, lo, hi) {
  return Math.min(hi, Math.max(lo, value));
}

/**
 * 后方两条立柱立腿贯穿到底顶并支撑靠背，前方两条腿支撑座面，座面与靠背之间保持通透。
 * 放不下就返回 null，调用方改画盒子。
 * 每块是 { role, box:[u0,v0,w0,u1,v1,w1] }。相邻的面至少错开 2 mm，避免共面闪烁。
 */
export function chairParts(width, depth, height) {
  const W = width;
  const D = depth;
  const H = height;
  if (!(W >= 240 && D >= 240 && H >= 350)) return null;

  const gap = 2;
  const leg = clamp(Math.min(W, D) * 0.08, 22, 44);
  const inset = clamp(Math.min(W, D) * 0.06, 12, 32);
  if (inset + leg > W / 2 - 8 || inset + leg > D / 2 - 8) return null;

  const seatTop = clamp(H * 0.48, 120, H * 0.62);
  const seatT = clamp(H * 0.05, 20, 50);
  const seatBottom = seatTop - seatT;
  const legTop = seatBottom - gap;
  if (legTop < 60 || H - seatTop < 100) return null;

  const parts = [];
  const add = (role, box) => parts.push({ role, box });

  // 1. 后方两条通顶立柱/腿：左后、右后，从地面 0 到 H
  const uL0 = inset;
  const uL1 = inset + leg;
  const uR0 = W - inset - leg;
  const uR1 = W - inset;
  const vRear0 = inset;
  const vRear1 = inset + leg;

  add("leg", [uL0, vRear0, 0, uL1, vRear1, H]);
  add("leg", [uR0, vRear0, 0, uR1, vRear1, H]);

  // 2. 前方两条落地腿：左前、右前，从地面 0 到座面下方 legTop
  const vFront0 = D - inset - leg;
  const vFront1 = D - inset;
  add("leg", [uL0, vFront0, 0, uL1, vFront1, legTop]);
  add("leg", [uR0, vFront0, 0, uR1, vFront1, legTop]);

  // 3. 座面：在后立柱前方与前腿上方，横跨左右
  const seatU0 = clamp(inset * 0.5, 4, inset - 2);
  const seatU1 = W - seatU0;
  const seatV0 = vRear1 + gap;
  const seatV1 = D - clamp(inset * 0.5, 4, inset - 2);
  if (seatU1 - seatU0 < 60 || seatV1 - seatV0 < 60) return null;

  add("seat", [seatU0, seatV0, seatBottom, seatU1, seatV1, seatTop]);

  // 4. 靠背板：横跨在两根后立柱之间上段
  const backU0 = uL1 + gap;
  const backU1 = uR0 - gap;
  if (backU1 - backU0 < 40) return null;

  const backT = clamp(leg * 0.8, 14, 30);
  const backV0 = vRear0 + clamp((leg - backT) / 2, gap, leg);
  const backV1 = backV0 + backT;

  const backH = clamp((H - seatTop) * 0.45, 80, 220);
  const backW1 = H - clamp(H * 0.02, 6, 20);
  const backW0 = backW1 - backH;
  if (backW0 <= seatTop + gap) return null;

  add("back", [backU0, backV0, backW0, backU1, backV1, backW1]);

  // 5. 中间腰部支撑横档（若空间充裕）
  if (backW0 - seatTop >= 120) {
    const midH = clamp(backH * 0.28, 16, 36);
    const midW0 = seatTop + clamp((backW0 - seatTop - midH) / 2, 20, 80);
    const midW1 = midW0 + midH;
    if (midW1 < backW0 - gap && midW0 > seatTop + gap) {
      add("back", [backU0, backV0, midW0, backU1, backV1, midW1]);
    }
  }

  return parts;
}
