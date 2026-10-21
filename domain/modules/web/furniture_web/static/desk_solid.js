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
 * 整块桌面盖住外形的顶，四条腿立于四角，桌下后侧带加强挡板/背拉条，
 * 两侧带浅横档拉条，正面完全开敞作为开阔的膝部与椅子推入空间（Knee space）。
 * 放不下就返回 null，调用方改画盒子。
 * 每块是 { role, box:[u0,v0,w0,u1,v1,w1] }。相邻的面至少错开 2 mm，避免共面闪烁。
 */
export function deskParts(width, depth, height) {
  const W = width;
  const D = depth;
  const H = height;
  if (!(W >= 400 && D >= 300 && H >= 400)) return null;

  const gap = 2;
  const topT = clamp(H * 0.045, 20, 36);
  const leg = clamp(Math.min(W, D) * 0.06, 28, 48);
  const inset = clamp(Math.min(W, D) * 0.04, 14, 32);
  const legTop = H - topT - gap;
  if (legTop < 200) return null;
  if (inset + leg > W / 2 - 8 || inset + leg > D / 2 - 8) return null;

  const parts = [];
  const add = (role, box) => parts.push({ role, box });

  // 1. 桌面：外形顶部整块面板，厚度 topT
  add("top", [0, 0, H - topT, W, D, H]);

  // 2. 四条桌腿：位于四角，向内缩进 inset，顶在桌面下方 legTop
  const uL0 = inset;
  const uL1 = inset + leg;
  const uR0 = W - inset - leg;
  const uR1 = W - inset;

  const vRear0 = inset;
  const vRear1 = inset + leg;
  const vFront0 = D - inset - leg;
  const vFront1 = D - inset;

  // 四腿：左后、右后、左前、右前
  add("leg", [uL0, vRear0, 0, uL1, vRear1, legTop]);
  add("leg", [uR0, vRear0, 0, uR1, vRear1, legTop]);
  add("leg", [uL0, vFront0, 0, uL1, vFront1, legTop]);
  add("leg", [uR0, vFront0, 0, uR1, vFront1, legTop]);

  // 3. 后方挡板 / 背拉条（Modesty Baffle / Stretcher）
  // 位于左右后腿之间，后侧不落地，给脚部留出悬空空间
  const apronT = clamp(leg * 0.45, 14, 20);
  const rearApronH = clamp(H * 0.22, 100, 220);
  const rearApronTop = legTop - gap;
  const rearApronBottom = rearApronTop - rearApronH;

  const rearU0 = uL1 + gap;
  const rearU1 = uR0 - gap;
  const rearV0 = vRear0 + (leg - apronT) / 2;
  const rearV1 = rearV0 + apronT;

  if (rearU1 - rearU0 >= 40 && rearApronBottom >= 80) {
    add("apron", [rearU0, rearV0, rearApronBottom, rearU1, rearV1, rearApronTop]);
  }

  // 4. 两侧横档拉条（Side Aprons / Rails）
  // 位于前腿与后腿之间，提供结构支撑；顶面下移 2mm 避免与后挡板共面
  const sideApronH = clamp(H * 0.08, 40, 70);
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

  // 正面（vFront 向室内）完全开敞，不设前横档，确保椅子可以轻松推进去，留足膝部活动空间
  return parts;
}
