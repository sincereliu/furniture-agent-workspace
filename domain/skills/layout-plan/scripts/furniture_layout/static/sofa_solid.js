/**
 * 预览里的固定沙发。纯几何，不依赖 three。
 *
 * 局部坐标：u 沿宽度，v 从靠背指向正面（局部 +Y），w 向上。
 * 块都在外形尺寸里面。朝向跟足迹一致：足迹第 0 点是靠背左下角。
 * 只认规范字段 category === "sofa"。要做成柜的沙发仍是盒子。
 */

const EXECUTABLE = new Set(["floor_cabinet", "wall_cabinet"]);

export function isFixedSofa(item) {
  if (!item || item.category !== "sofa") return false;
  if (item.manufacture === false) return true;
  return !EXECUTABLE.has(item.furniture_category);
}

function clamp(value, lo, hi) {
  return Math.min(hi, Math.max(lo, value));
}

function seatCount(inner) {
  if (inner >= 2500) return 4;
  if (inner >= 1680) return 3;
  if (inner >= 980) return 2;
  return 1;
}

/**
 * 靠背贴 v=0，扶手在两侧，坐垫在中间。放不下就返回 null，调用方改画盒子。
 * 每块是 { role, box:[u0,v0,w0,u1,v1,w1] }。相邻的面至少错开 2 mm，避免共面闪烁。
 */
export function sofaParts(width, depth, height) {
  const W = width;
  const D = depth;
  const H = height;
  if (!(W >= 280 && D >= 280 && H >= 180)) return null;

  let arm = clamp(W * 0.09, 56, 180);
  let back = clamp(D * 0.26, 70, D * 0.46);
  const legH = clamp(H * 0.1, 28, 100);
  const gap = 2;
  const maxArm = (W - 80) / 2;
  const maxBack = D - 120;
  if (maxArm < 40 || maxBack < 50) return null;
  arm = Math.min(arm, maxArm);
  back = Math.min(back, maxBack);

  let seatTop = clamp(H * 0.46, legH + 36, H * 0.62);
  let armTop = clamp(H * 0.7, seatTop + 24, H - 16);
  if (!(armTop > seatTop + 8 && armTop < H - 4)) return null;

  const cushionH = clamp(H * 0.14, 36, Math.min(120, (seatTop - legH) * 0.55));
  const deckTop = seatTop - cushionH - gap;
  if (deckTop < legH + 8) return null;

  const seatU0 = arm + gap;
  const seatU1 = W - arm - gap;
  const seatV0 = back + gap;
  const jut = Math.min(90, Math.max(28, (D - back) * 0.22));
  const seatV1 = D - gap;
  if (seatU1 - seatU0 < 80 || seatV1 - seatV0 < 80) return null;
  if (back + jut > seatV1 - 24) return null;

  const parts = [];
  const add = (role, box) => parts.push({ role, box });

  add("fabric", [0, 0, 0, W, back, H]);
  add("fabric", [0, back + gap, 0, arm, D, armTop]);
  add("fabric", [W - arm, back + gap, 0, W, D, armTop]);
  add("deck", [seatU0, seatV0, legH, seatU1, seatV1, deckTop]);

  const count = seatCount(seatU1 - seatU0);
  const seam = 14;
  const cushW = (seatU1 - seatU0 - seam * (count - 1)) / count;
  if (cushW < 40) return null;
  for (let i = 0; i < count; i += 1) {
    const u0 = seatU0 + i * (cushW + seam);
    add("cushion", [u0, seatV0 + 6, deckTop + gap, u0 + cushW, seatV1 - 6, seatTop]);
  }

  const backZ0 = Math.max(seatTop + gap, H * 0.5);
  const backZ1 = H - 8;
  const backV1 = back + jut;
  if (backZ1 - backZ0 >= 30) {
    const bcW = (seatU1 - seatU0 - seam * (count - 1)) / count;
    for (let i = 0; i < count; i += 1) {
      const u0 = seatU0 + i * (bcW + seam);
      add("cushion", [u0, back * 0.55, backZ0, u0 + bcW, backV1, backZ1]);
    }
  }

  const leg = clamp(Math.min(arm * 0.42, 42), 22, 42);
  const footV1 = D - 10;
  const footV0 = footV1 - leg;
  if (footV0 > seatV0 + 8) {
    add("wood", [arm + 6, footV0, 0, arm + 6 + leg, footV1, legH - gap]);
    add("wood", [W - arm - 6 - leg, footV0, 0, W - arm - 6, footV1, legH - gap]);
  }

  return parts;
}

/** 由足迹推出靠背原点与单位轴。轴在房间平面里：axisX 沿宽，axisFront 指向正面。 */
export function sofaFrame(footprint, z0) {
  if (!footprint || footprint.length < 4) return null;
  const p0 = footprint[0];
  const p1 = footprint[1];
  const p3 = footprint[3];
  const ux = p1[0] - p0[0];
  const uy = p1[1] - p0[1];
  const vx = p3[0] - p0[0];
  const vy = p3[1] - p0[1];
  const ul = Math.hypot(ux, uy);
  const vl = Math.hypot(vx, vy);
  if (ul < 1 || vl < 1) return null;
  return {
    origin: [p0[0], p0[1], z0],
    axisX: [ux / ul, uy / ul],
    axisFront: [vx / vl, vy / vl],
  };
}

/** 局部 (u, v, w) 落到房间坐标。 */
export function sofaRoomPoint(frame, u, v, w) {
  return [
    frame.origin[0] + frame.axisX[0] * u + frame.axisFront[0] * v,
    frame.origin[1] + frame.axisX[1] * u + frame.axisFront[1] * v,
    frame.origin[2] + w,
  ];
}

/**
 * 给 Three.js 的摆放。origin 是房间坐标；x/y/z 是 three 基（Y 向上）。
 * 局部盒子：X 沿宽，Y 向上，Z 指向正面。
 */
export function sofaMount(frame) {
  return {
    origin: frame.origin,
    x: [frame.axisX[0], 0, frame.axisX[1]],
    y: [0, 1, 0],
    z: [frame.axisFront[0], 0, frame.axisFront[1]],
  };
}

/** 局部盒子换成 three 的尺寸和中心：X 沿宽，Y 向上，Z 指向正面。 */
export function sofaLocalBox(box) {
  const [u0, v0, w0, u1, v1, w1] = box;
  return {
    size: [u1 - u0, w1 - w0, v1 - v0],
    center: [(u0 + u1) / 2, (w0 + w1) / 2, (v0 + v1) / 2],
  };
}
