/**
 * 预览里的固定书桌/写字台。纯几何，不依赖 three。
 *
 * 局部坐标与沙发、茶几相同：u 沿宽度，v 指向正面（局部 +Y），w 向上。
 * 块都在外形尺寸里面。朝向跟足迹一致：背面贴墙（v=0），正面朝室内（v=depth）。
 * 只认规范字段 category === "desk"。要做成柜的书桌仍是盒子。
 */

const EXECUTABLE = new Set(["floor_cabinet", "wall_cabinet"]);

export function isFixedDesk(item) {
  if (!item || item.category !== "desk") return false;
  if (item.manufacture === false) return true;
  return !EXECUTABLE.has(item.furniture_category);
}

function clamp(value, lo, hi) {
  return Math.min(hi, Math.max(lo, value));
}

/**
 * 薄桌面、退入的双抽屉盒与两侧纤细雪橇框架。
 * 抽屉前脸不等分，短拉手退在桌面前沿内；桌下中部保持膝部空间。
 * 放不下就返回 null，调用方改画盒子。
 * 每块是 { role, box:[u0,v0,w0,u1,v1,w1] }。相邻的面至少错开 2 mm，避免共面闪烁。
 */
export function deskParts(width, depth, height) {
  const W = width;
  const D = depth;
  const H = height;
  if (!(W >= 400 && D >= 300 && H >= 400)) return null;

  const gap = 2;
  const topT = clamp(H * 0.032, 18, 26);
  const leg = clamp(Math.min(W, D) * 0.038, 18, 26);
  const inset = clamp(Math.min(W, D) * 0.075, 22, 48);
  const legTop = H - topT - gap;
  if (legTop < 200) return null;
  if (inset + leg > W / 2 - 8 || inset + leg > D / 2 - 8) return null;

  const parts = [];
  const add = (role, box) => parts.push({ role, box });

  // 桌面外接尺寸保持足迹；圆角由渲染几何生成。
  add("top", [0, 0, H - topT, W, D, H]);

  // 两侧框架的立柱和落地横梁，较大的桌面挑出让支架显得轻巧。
  const uL0 = inset;
  const uL1 = inset + leg;
  const uR0 = W - inset - leg;
  const uR1 = W - inset;

  const vRear0 = inset;
  const vRear1 = inset + leg;
  const vFront0 = D - inset - leg;
  const vFront1 = D - inset;

  // 四腿：左后、右后、左前、右前
  add("leg", [uL0, vRear0, leg + gap, uL1, vRear1, legTop]);
  add("leg", [uR0, vRear0, leg + gap, uR1, vRear1, legTop]);
  add("leg", [uL0, vFront0, leg + gap, uL1, vFront1, legTop]);
  add("leg", [uR0, vFront0, leg + gap, uR1, vFront1, legTop]);
  add("foot", [uL0, vRear0, 0, uL1, vFront1, leg]);
  add("foot", [uR0, vRear0, 0, uR1, vFront1, leg]);

  // 纤细后横梁，不再用大挡板压住桌下空间。
  const apronT = leg;
  const rearApronH = leg;
  const rearApronTop = legTop - gap;
  const rearApronBottom = rearApronTop - rearApronH;

  const rearU0 = uL1 + gap;
  const rearU1 = uR0 - gap;
  const rearV0 = vRear0 + (leg - apronT) / 2;
  const rearV1 = rearV0 + apronT;

  if (rearU1 - rearU0 >= 40 && rearApronBottom >= 80) {
    add("apron", [rearU0, rearV0, rearApronBottom, rearU1, rearV1, rearApronTop]);
  }

  // 两侧上横梁，与立柱留出细缝，避免重叠面闪烁。
  const sideApronH = leg;
  const sideApronTop = rearApronTop - gap;
  const sideApronBottom = sideApronTop - sideApronH;

  const sideV0 = vRear1 + gap;
  const sideV1 = vFront0 - gap;
  const leftU0 = uL0 + (leg - apronT) / 2;
  const leftU1 = leftU0 + apronT;
  const rightU0 = uR0 + (leg - apronT) / 2;
  const rightU1 = rightU0 + apronT;

  if (sideV1 - sideV0 >= 40 && sideApronBottom >= 100) {
    add("apron", [leftU0, sideV0, sideApronBottom, leftU1, sideV1, sideApronTop]);
    add("apron", [rightU0, sideV0, sideApronBottom, rightU1, sideV1, sideApronTop]);
  }

  // 退入桌面下的浅抽屉：两块前脸之间保留真实缝隙。
  const drawerU0 = uL1 + gap * 2;
  const drawerU1 = uR0 - gap * 2;
  const drawerTop = legTop - 6;
  const drawerH = clamp(H * 0.09, 38, 70);
  const drawerBottom = drawerTop - drawerH;
  const drawerFront = D - 24;
  const faceT = 16;
  const split = drawerU0 + (drawerU1 - drawerU0) * 0.38;
  add("drawer", [drawerU0, inset + leg + 8, drawerBottom + gap,
    drawerU1, drawerFront - faceT - gap, drawerTop - gap]);
  for (const [u0, u1] of [[drawerU0, split - gap], [split + gap, drawerU1]]) {
    add("front", [u0, drawerFront - faceT, drawerBottom, u1, drawerFront, drawerTop]);
    const pullW = clamp((u1 - u0) * 0.32, 38, 112);
    const pullU = (u0 + u1) / 2;
    add("pull", [pullU - pullW / 2, drawerFront + gap, drawerTop - 18,
      pullU + pullW / 2, drawerFront + 10, drawerTop - 12]);
  }

  return parts;
}
