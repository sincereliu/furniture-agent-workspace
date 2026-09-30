// 本模块只计算房间坐标 [x, y, z]，不依赖 Three.js 或屏幕投影。
export const ROOM_AXES = [
  { key: "x", label: "X 宽", color: 0xdc2626, direction: [1, 0, 0] },
  { key: "y", label: "Y 深", color: 0x047857, direction: [0, 1, 0] },
  { key: "z", label: "Z 高", color: 0x2563eb, direction: [0, 0, 1] },
];

export function roomAxes(room) {
  const lengths = [room.width_mm, room.depth_mm, room.height_mm];
  const nudge = 25;
  const anchors = [
    [lengths[0] / 2, -nudge, 0],
    [-nudge, lengths[1] / 2, 0],
    [-nudge, 0, lengths[2] / 2],
  ];
  return ROOM_AXES.map((axis, index) => ({
    ...axis,
    from: [0, 0, 0],
    to: axis.direction.map((value) => value * lengths[index]),
    anchor: anchors[index],
    text: `${axis.key.toUpperCase()} ${Math.round(lengths[index])}`,
  }));
}

/** 布局足迹兼容毫米字段对象与 [x, y]，两者都属于房间平面坐标。 */
export function footprintPoint(point) {
  return Array.isArray(point) ? [point[0], point[1]] : [point.x_mm, point.y_mm];
}

export function itemZRange(item) {
  if (Number.isFinite(item.z_start) && Number.isFinite(item.z_end)) {
    return [item.z_start, item.z_end];
  }
  const base = item.placement && Number.isFinite(item.placement.origin_z_mm)
    ? item.placement.origin_z_mm : 0;
  return [base, base + (Number.isFinite(item.height) ? item.height : 0)];
}

/** 尺寸线跟随件的局部宽/深方向；四向净距线沿房间轴。标签统一取线中点。 */
export function dimensionAnnotations(room, item) {
  const points = item.footprint.map(footprintPoint);
  const [zStart, zEnd] = itemZRange(item);
  const z = zStart + 8;
  const specs = [];
  const add = (text, from, to, color) => specs.push({
    text, from, to, color,
    anchor: from.map((value, index) => (value + to[index]) / 2),
  });
  const fmt = (value) => `${Math.round(value)}`;
  const [backLeft, backRight, frontRight, frontLeft] = points;
  const width = Math.hypot(backRight[0] - backLeft[0], backRight[1] - backLeft[1]);
  const depth = Math.hypot(frontLeft[0] - backLeft[0], frontLeft[1] - backLeft[1]);
  const widthDir = backRight.map((value, index) => (value - backLeft[index]) / width);
  const depthDir = frontLeft.map((value, index) => (value - backLeft[index]) / depth);
  const shifted = (point, direction, gap) => [point[0] + direction[0] * gap, point[1] + direction[1] * gap, z];
  const sizeGap = 90;
  add(`宽 ${fmt(width)}`, shifted(backLeft, depthDir, -sizeGap), shifted(backRight, depthDir, -sizeGap), 0x334155);
  add(`深 ${fmt(depth)}`, shifted(backLeft, widthDir, -sizeGap), shifted(frontLeft, widthDir, -sizeGap), 0x334155);
  const heightPoint = shifted(frontRight, widthDir, sizeGap);
  add(`高 ${fmt(zEnd - zStart)}`, [heightPoint[0], heightPoint[1], zStart], [heightPoint[0], heightPoint[1], zEnd], 0x334155);

  const xs = points.map((point) => point[0]);
  const ys = points.map((point) => point[1]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs);
  const y0 = Math.min(...ys), y1 = Math.max(...ys);
  const midX = (x0 + x1) / 2, midY = (y0 + y1) / 2;
  const gaps = item.clearances_mm || {};
  const gapSpecs = [
    { key: "west", from: [0, midY, z], to: [x0, midY, z] },
    { key: "east", from: [x1, midY, z], to: [room.width_mm, midY, z] },
    { key: "north", from: [midX, 0, z], to: [midX, y0, z] },
    { key: "south", from: [midX, y1, z], to: [midX, room.depth_mm, z] },
  ];
  for (const spec of gapSpecs) {
    const raw = gaps[spec.key];
    const gap = typeof raw === "number" ? raw : (raw && typeof raw.gap === "number" ? raw.gap : null);
    if (gap === null || gap <= 0.5) continue;
    add(`离墙 ${fmt(gap)}`, spec.from, spec.to, 0x7c3aed);
  }
  return specs;
}
