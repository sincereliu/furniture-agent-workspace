/**
 * 地面拖动换算：屏幕像素 → 房间毫米（纯函数，可直接在 node 里断言，见 drag_check.mjs）。
 *
 * 为什么不用"光标射线的地面交点"：抓在家具上半身时，那条射线打到地面已经在很远处
 * （接近地平线），几个像素就能换出好几米——实测一次拖动把 2.4m 宽的柜子从北墙甩到
 * y=2777，用户看到的现象是"拖一下，离墙的距离就不对了"。
 *
 * 这里改成按**家具脚下那一点**的比例换算：
 *   · 横向：屏幕右向量落在地面上的分量，1px = scale 毫米（scale 见 verticalPlaneScale）；
 *   · 纵向：地面在屏幕上被压扁了 sin(俯仰)，所以 1px = scale / sin(俯仰) 毫米，方向朝相机。
 * 于是同样 12px，在任何抓取高度都走同样的距离——"跟手"指的是家具跟手，不是光标的地面投影跟手。
 */

/** @returns {[number, number]} 房间坐标下的位移（mm）。 */
export function groundDragDelta({ dx, dy, scale, right, forward }) {
  const rightLength = Math.hypot(right[0], right[1]) || 1;
  const forwardLength = Math.hypot(forward[0], forward[1]) || 1;
  // 相机越平（|forward[2]| 越小），纵向每像素走得越多；留个下限，免得贴地平线时爆炸。
  const flatten = Math.max(0.2, Math.abs(forward[2]));
  const along = dx * scale;
  const depth = (dy * scale) / flatten;
  return [
    (right[0] / rightLength) * along - (forward[0] / forwardLength) * depth,
    (right[1] / rightLength) * along - (forward[1] / forwardLength) * depth,
  ];
}

//: 轴对齐的转角 → 背面贴的那面墙。沿墙位置由包络贴合算出，不在这里取偏移。
const WALL_BY_ANGLE = {
  0: "north",
  90: "east",
  180: "south",
  270: "west",
};

/**
 * 自由摆放的件贴回墙边时，重新认成"靠墙"。
 *
 * 为什么需要它：离开墙面之后它就是自由件。贴回墙面要重新认成靠墙，这条回路才是可逆的。
 * 沿墙位置不在这里算，服务端按包络重贴。
 *
 * 条件卡得很死，不做"自动摆正"：转角必须轴对齐、背面必须**正好**落在墙上（容差 0.5mm）、
 * 而且整件都在房间里。任何一条不满足就返回 `null`，不猜。
 *
 * @returns {{host_wall: string} | null}
 */
export function wallSnap({ footprint, rotation, room }) {
  const angle = (((Math.round(rotation * 10) / 10) % 360) + 360) % 360;
  const wall = WALL_BY_ANGLE[angle];
  if (!wall) return null;
  const xs = footprint.map((point) => (Array.isArray(point) ? point[0] : point.x_mm));
  const ys = footprint.map((point) => (Array.isArray(point) ? point[1] : point.y_mm));
  const box = {
    minX: Math.min(...xs),
    maxX: Math.max(...xs),
    minY: Math.min(...ys),
    maxY: Math.max(...ys),
  };
  const eps = 0.5;
  const inside =
    box.minX >= -eps &&
    box.minY >= -eps &&
    box.maxX <= room.width_mm + eps &&
    box.maxY <= room.depth_mm + eps;
  if (!inside) return null;
  const touching = {
    north: Math.abs(box.minY) <= eps,
    east: Math.abs(box.maxX - room.width_mm) <= eps,
    south: Math.abs(box.maxY - room.depth_mm) <= eps,
    west: Math.abs(box.minX) <= eps,
  };
  if (!touching[wall]) return null;
  return { host_wall: wall };
}
