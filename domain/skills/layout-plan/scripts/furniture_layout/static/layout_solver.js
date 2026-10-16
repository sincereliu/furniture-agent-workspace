/**
 * 房间内家具碰撞、越界、门窗遮挡、四向净距与整数毫米拖拽求解（与 placement_check.py 对应）。
 */

export const EPSILON_MM = 1e-6;

const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

export function rangesOverlap(a0, a1, b0, b1) {
  return Math.min(a1, b1) > Math.max(a0, b0) + EPSILON_MM;
}

/** SAT：底面正面积重叠，贴边接触放行。干涉需再加高度重叠。 */
export function polygonsOverlap(first, second) {
  for (const polygon of [first, second]) {
    for (let index = 0; index < polygon.length; index += 1) {
      const point = polygon[index];
      const next = polygon[(index + 1) % polygon.length];
      const axis = [-(next[1] - point[1]), next[0] - point[0]];
      let minA = Infinity, maxA = -Infinity, minB = Infinity, maxB = -Infinity;
      for (const candidate of first) {
        const value = candidate[0] * axis[0] + candidate[1] * axis[1];
        if (value < minA) minA = value;
        if (value > maxA) maxA = value;
      }
      for (const candidate of second) {
        const value = candidate[0] * axis[0] + candidate[1] * axis[1];
        if (value < minB) minB = value;
        if (value > maxB) maxB = value;
      }
      if (maxA <= minB + EPSILON_MM || maxB <= minA + EPSILON_MM) return false;
    }
  }
  return true;
}

export function spanOnWall(room, wall, footprint) {
  const xs = footprint.map((point) => point[0]);
  const ys = footprint.map((point) => point[1]);
  if (wall === "north" && Math.min(...ys) <= EPSILON_MM) return [Math.min(...xs), Math.max(...xs)];
  if (wall === "east" && Math.max(...xs) >= room.width_mm - EPSILON_MM) return [Math.min(...ys), Math.max(...ys)];
  if (wall === "south" && Math.max(...ys) >= room.depth_mm - EPSILON_MM) {
    return [room.width_mm - Math.max(...xs), room.width_mm - Math.min(...xs)];
  }
  if (wall === "west" && Math.min(...xs) <= EPSILON_MM) {
    return [room.depth_mm - Math.max(...ys), room.depth_mm - Math.min(...ys)];
  }
  return null;
}

export function blockerAt(scene, footprint, zStart, zEnd, ignoreId) {
  const room = scene.room;
  const xs = footprint.map((point) => point[0]);
  const ys = footprint.map((point) => point[1]);
  if (
    Math.min(...xs) < -EPSILON_MM ||
    Math.max(...xs) > room.width_mm + EPSILON_MM ||
    Math.min(...ys) < -EPSILON_MM ||
    Math.max(...ys) > room.depth_mm + EPSILON_MM
  ) {
    return { label: "房间边界", id: null, reason: "outside_room" };
  }
  for (const obstacle of scene.obstacles || []) {
    if (rangesOverlap(zStart, zEnd, obstacle.z_start, obstacle.z_end) && polygonsOverlap(footprint, obstacle.footprint)) {
      return { label: obstacle.label || "障碍物", id: null, reason: "interference" };
    }
  }
  for (const other of scene.items || []) {
    if (other.id === ignoreId) continue;
    if (rangesOverlap(zStart, zEnd, other.z_start, other.z_end) && polygonsOverlap(footprint, other.footprint)) {
      return { label: other.label, id: other.id, reason: "interference" };
    }
  }
  for (const opening of scene.openings || []) {
    const span = spanOnWall(room, opening.wall, footprint);
    if (!span) continue;
    if (
      rangesOverlap(span[0], span[1], opening.offset_mm, opening.offset_mm + opening.width_mm) &&
      rangesOverlap(zStart, zEnd, opening.sill_height_mm, opening.sill_height_mm + opening.height_mm)
    ) {
      return { label: "门窗", id: null, reason: "blocked_opening" };
    }
  }
  return null;
}

export function placementStop(blocker) {
  if (!blocker) return "超出可放范围";
  if (blocker.reason === "outside_room") return "会越出房间";
  if (blocker.reason === "blocked_opening") return "会遮挡门窗洞口";
  return `会与 ${blocker.label} 干涉`;
}

export function contactStop(blocker) {
  if (blocker.reason === "outside_room") return "已停在房间边界";
  if (blocker.reason === "blocked_opening") return "再过去会遮挡门窗洞口";
  return `已与 ${blocker.label} 贴到接触，再过去会干涉`;
}

/** 从 from（必须可用）朝 to 走，二分找最远的可用整数位置。 */
export function resolveInteger(from, to, probe) {
  const startBlocker = probe(from);
  if (startBlocker) return { value: from, blocker: startBlocker };
  if (from === to) return { value: from, blocker: null };
  const step = to > from ? 1 : -1;
  const endBlocker = probe(to);
  if (!endBlocker) return { value: to, blocker: null };
  let low = from, high = to, blocker = endBlocker;
  while (Math.abs(high - low) > 1) {
    const middle = low + step * Math.floor(Math.abs(high - low) / 2);
    const hit = probe(middle);
    if (hit) {
      high = middle;
      blocker = hit;
    } else {
      low = middle;
    }
  }
  return { value: low, blocker };
}

export function boxOf(footprint) {
  const xs = footprint.map((point) => point[0]);
  const ys = footprint.map((point) => point[1]);
  return { x0: Math.min(...xs), x1: Math.max(...xs), y0: Math.min(...ys), y1: Math.max(...ys) };
}

export function distancesOf(scene, item) {
  const room = scene.room;
  const box = boxOf(item.footprint);
  const neighbours = [];
  for (const other of scene.items || []) {
    if (other.id === item.id) continue;
    neighbours.push({ label: other.label, box: boxOf(other.footprint), z0: other.z_start, z1: other.z_end });
  }
  for (const obstacle of scene.obstacles || []) {
    neighbours.push({ label: obstacle.label || "障碍物", box: boxOf(obstacle.footprint), z0: obstacle.z_start, z1: obstacle.z_end });
  }
  const result = {};
  for (const dir of ["west", "east", "north", "south"]) {
    const horizontal = dir === "west" || dir === "east";
    let best = null;
    for (const other of neighbours) {
      if (!rangesOverlap(item.z_start, item.z_end, other.z0, other.z1)) continue;
      if (horizontal) {
        if (!rangesOverlap(box.y0, box.y1, other.box.y0, other.box.y1)) continue;
      } else if (!rangesOverlap(box.x0, box.x1, other.box.x0, other.box.x1)) {
        continue;
      }
      let gap;
      if (dir === "west") {
        if (other.box.x1 > box.x0 + EPSILON_MM) continue;
        gap = box.x0 - other.box.x1;
      } else if (dir === "east") {
        if (other.box.x0 < box.x1 - EPSILON_MM) continue;
        gap = other.box.x0 - box.x1;
      } else if (dir === "north") {
        if (other.box.y1 > box.y0 + EPSILON_MM) continue;
        gap = box.y0 - other.box.y1;
      } else {
        if (other.box.y0 < box.y1 - EPSILON_MM) continue;
        gap = other.box.y0 - box.y1;
      }
      if (!best || gap < best.gap) best = { gap, label: other.label };
    }
    const wallGap = dir === "west" ? box.x0
      : dir === "east" ? room.width_mm - box.x1
      : dir === "north" ? box.y0
      : room.depth_mm - box.y1;
    result[dir] = best && best.gap <= wallGap + EPSILON_MM
      ? { gap: best.gap, label: best.label }
      : { gap: wallGap, label: "墙" };
  }
  return result;
}

export function frontVector(item) {
  const rad = (item.placement.rotation_z_deg || 0) * Math.PI / 180;
  return [-Math.sin(rad), Math.cos(rad)];
}

export function frontCompass(item) {
  const vector = frontVector(item);
  const parts = [];
  if (vector[0] > 0.38) parts.push("东");
  else if (vector[0] < -0.38) parts.push("西");
  if (vector[1] > 0.38) parts.push("南");
  else if (vector[1] < -0.38) parts.push("北");
  return parts.join("") || "—";
}

export function footprintCenter(item) {
  const count = item.footprint.length || 1;
  return [
    item.footprint.reduce((s, p) => s + p[0], 0) / count,
    item.footprint.reduce((s, p) => s + p[1], 0) / count,
  ];
}

export function localFootprint(item, originX, originY, rotationDeg) {
  const angle = rotationDeg * Math.PI / 180;
  const cosine = Math.cos(angle);
  const sine = Math.sin(angle);
  return [[0, 0], [item.width, 0], [item.width, item.depth], [0, item.depth]].map(
    ([x, y]) => [originX + x * cosine - y * sine, originY + x * sine + y * cosine],
  );
}

export function snapAngle(deg, step) {
  return Math.round(deg / step) * step;
}

export function normalizeAngle(deg) {
  return ((deg % 360) + 360) % 360;
}

export function wallNormal(wall) {
  return { north: [0, 1], east: [-1, 0], south: [0, -1], west: [1, 0] }[wall] || null;
}

export function wallLabel(wall) {
  return { north: "北", east: "东", south: "南", west: "西" }[wall] || wall;
}

export function anchorFreeCell(x, y, probe) {
  if (!probe(x, y)) return [x, y];
  for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1], [1, 1], [-1, -1], [1, -1], [-1, 1]]) {
    if (!probe(x + dx, y + dy)) return [x + dx, y + dy];
  }
  return null;
}

export function heightProbe(scene, item, footprint) {
  const room = scene.room;
  return (z) => (z < 0 || z + item.height > room.height_mm + EPSILON_MM)
    ? { label: "层高", id: null, reason: "outside_room" }
    : blockerAt(scene, footprint, z, z + item.height, item.id);
}

export function setItemHeight(item, z) {
  item.placement.origin_z_mm = z;
  item.z_start = z;
  item.z_end = z + item.height;
}

export function solvePlanarDrag(scene, item, startOrigin, dx, dy) {
  const placement = item.placement;
  if (placement.mode === "wall") return null;
  const rotation = placement.rotation_z_deg || 0;
  const at = (x, y) => localFootprint(item, x, y, rotation);
  const probe = (x, y) => blockerAt(scene, at(x, y), item.z_start, item.z_end, item.id);
  const anchor = anchorFreeCell(Math.round(startOrigin[0]), Math.round(startOrigin[1]), probe);
  if (!anchor) return { label: "无处可移", id: null };
  const solvedX = resolveInteger(anchor[0], anchor[0] + Math.round(dx), (x) => probe(x, anchor[1]));
  const solvedY = resolveInteger(anchor[1], anchor[1] + Math.round(dy), (y) => probe(solvedX.value, y));
  placement.origin_x_mm = solvedX.value;
  placement.origin_y_mm = solvedY.value;
  item.footprint = at(solvedX.value, solvedY.value);
  return solvedX.blocker || solvedY.blocker;
}

export function solveElevationDrag(scene, item, startOrigin, startZ, horizontal, dHoriz, dVert) {
  const placement = item.placement;
  const rotation = placement.rotation_z_deg || 0;
  const baseZ = Math.round(startZ);
  let blocker = null;
  if (placement.mode !== "wall") {
    const at = (x, y) => localFootprint(item, x, y, rotation);
    const probe = (x, y) => heightProbe(scene, item, at(x, y))(baseZ);
    const anchor = anchorFreeCell(Math.round(startOrigin[0]), Math.round(startOrigin[1]), probe);
    if (anchor) {
      const want = Math.round(dHoriz * horizontal.sign);
      const solved = horizontal.axis === 0
        ? resolveInteger(anchor[0], anchor[0] + want, (x) => probe(x, anchor[1]))
        : resolveInteger(anchor[1], anchor[1] + want, (y) => probe(anchor[0], y));
      const nx = horizontal.axis === 0 ? solved.value : anchor[0];
      const ny = horizontal.axis === 1 ? solved.value : anchor[1];
      placement.origin_x_mm = nx;
      placement.origin_y_mm = ny;
      item.footprint = at(nx, ny);
      blocker = solved.blocker;
    }
  }
  const zSolved = resolveInteger(baseZ, baseZ + Math.round(dVert), heightProbe(scene, item, item.footprint));
  setItemHeight(item, zSolved.value);
  return blocker || zSolved.blocker;
}

export function solveRotation(scene, item, center, rotationDeg) {
  const room = scene.room;
  const current = item.placement;
  const target = Math.round(normalizeAngle(rotationDeg) * 10) / 10;
  if (current.mode === "wall" && normalizeAngle(target) === normalizeAngle(current.rotation_z_deg || 0)) {
    return { applied: false, blocker: null };
  }
  const angle = target * Math.PI / 180;
  const cosine = Math.cos(angle);
  const sine = Math.sin(angle);
  const halfWidth = item.width / 2;
  const halfDepth = item.depth / 2;
  let originX = Math.round(center[0] - (halfWidth * cosine - halfDepth * sine));
  let originY = Math.round(center[1] - (halfWidth * sine + halfDepth * cosine));
  let footprint = localFootprint(item, originX, originY, target);
  const xs = footprint.map((point) => point[0]);
  const ys = footprint.map((point) => point[1]);
  const shiftX = clamp(0, -Math.min(...xs), room.width_mm - Math.max(...xs));
  const shiftY = clamp(0, -Math.min(...ys), room.depth_mm - Math.max(...ys));
  if (shiftX || shiftY) {
    originX += shiftX > 0 ? Math.ceil(shiftX) : Math.floor(shiftX);
    originY += shiftY > 0 ? Math.ceil(shiftY) : Math.floor(shiftY);
    footprint = localFootprint(item, originX, originY, target);
  }
  const blocker = blockerAt(scene, footprint, item.z_start, item.z_end, item.id);
  if (blocker) return { applied: false, blocker };
  current.mode = "free";
  current.host_wall = null;
  current.origin_x_mm = originX;
  current.origin_y_mm = originY;
  current.rotation_z_deg = target;
  item.footprint = footprint;
  return { applied: true, blocker: null };
}

export function coordText(item) {
  const xs = item.footprint.map((point) => point[0]);
  const ys = item.footprint.map((point) => point[1]);
  const x0 = Math.round(Math.min(...xs)), x1 = Math.round(Math.max(...xs));
  const y0 = Math.round(Math.min(...ys)), y1 = Math.round(Math.max(...ys));
  return `X ${x0}~${x1} · Y ${y0}~${y1} mm（距西墙 ${x0} · 距北墙 ${y0}）`;
}

export function detailValues(scene, item) {
  const gaps = distancesOf(scene, item);
  const round = (n) => Math.round(n);
  return {
    mode: item.placement.mode === "wall" ? "靠墙" : "自由",
    position: item.placement.mode === "wall"
      ? `靠${wallLabel(item.placement.host_wall)}墙`
      : `X ${round(item.placement.origin_x_mm)} · Y ${round(item.placement.origin_y_mm)} mm`,
    rotation: round(normalizeAngle(item.placement.rotation_z_deg || 0)),
    front: `前朝${frontCompass(item)}`,
    height: round(item.z_start),
    width: round(item.width),
    depth: round(item.depth),
    boxHeight: round(item.height),
    ceiling: round(scene.room.height_mm - item.z_end),
    coord: coordText(item),
    gaps: {
      west: round(gaps.west.gap),
      east: round(gaps.east.gap),
      north: round(gaps.north.gap),
      south: round(gaps.south.gap),
    },
    who: {
      west: gaps.west.label,
      east: gaps.east.label,
      north: gaps.north.label,
      south: gaps.south.label,
    },
  };
}
