/** One gesture owns a private candidate. The page publishes it only on commit. */
import { groundDragDelta, wallSnap } from "./layout_drag.js";
import {
  poseBlocker, footprintCenter, heightProbe, localFootprint, normalizeAngle, resolveInteger, setItemHeight,
  snapAngle, solveElevationDrag, solvePlanarDrag, solveRotation,
  syncPlacementGeometry,
} from "./layout_solver.js";

export function canAttachToWall(item) {
  return item.manufacture !== false
    && ["floor_cabinet", "wall_cabinet"].includes(item.furniture_category);
}

export function poseOperation(item) {
  const p = item.placement;
  const op = { op: "set_pose", item_id: item.id, mode: p.mode,
    origin_x_mm: p.origin_x_mm, origin_y_mm: p.origin_y_mm,
    origin_z_mm: p.origin_z_mm, rotation_z_deg: normalizeAngle(p.rotation_z_deg) };
  if (p.mode === "wall") op.host_wall = p.host_wall;
  return op;
}

function samePose(a, b) {
  return a.mode === b.mode && (a.host_wall || null) === (b.host_wall || null)
    && ["origin_x_mm", "origin_y_mm", "origin_z_mm"].every(key => a[key] === b[key])
    && Math.abs(((a.rotation_z_deg - b.rotation_z_deg + 540) % 360) - 180) < 1e-6;
}

export function createDragTransaction({ scene, item, kind, screen, pointerId,
  basis, scale, elevation = false, horizontal, wallScreenNormal = null,
  projectWallNormal, rotationOrigin, rotationSign = 1, threshold = 4, detachThreshold = 26 }) {
  if (!["move", "rotate", "height"].includes(kind)) throw new Error("unsupported gesture kind");
  if (item.placement.fill && kind !== "height") throw new Error("a fill item only supports height gestures");
  const before = structuredClone(item);
  const candidate = structuredClone(item);
  let segmentScreen = [...screen];
  let segmentOrigin = [candidate.placement.origin_x_mm, candidate.placement.origin_y_mm];
  let wallNormal = wallScreenNormal;
  let moved = false, closed = false, accumulated = 0;
  let lastAngle = rotationOrigin
    ? Math.atan2(screen[1] - rotationOrigin.y, screen[0] - rotationOrigin.x) * 180 / Math.PI : 0;
  const center = footprintCenter(before);
  const startZ = before.placement.origin_z_mm;
  const startRotation = before.placement.rotation_z_deg;

  function preview(document = scene) {
    return { ...document, items: document.items.map(entry => entry.id === candidate.id ? candidate : entry) };
  }
  function detach() {
    candidate.placement.mode = "free";
    candidate.placement.host_wall = null;
    delete candidate.placement.against;
  }
  function update(nextScreen, { fine = false } = {}) {
    if (closed) throw new Error("drag transaction is closed");
    const dx = nextScreen[0] - segmentScreen[0], dy = nextScreen[1] - segmentScreen[1];
    if (!moved && Math.hypot(dx, dy) < threshold) return { moved: false, blocker: null };
    moved = true;
    let blocker = null;
    if (kind === "height") {
      const wanted = Math.round(-dy * scale / (basis.up[2] || 1));
      const solved = resolveInteger(startZ, startZ + wanted, heightProbe(scene, candidate, candidate.footprint));
      setItemHeight(candidate, solved.value);
      blocker = solved.blocker;
    } else if (kind === "rotate") {
      const angle = Math.atan2(nextScreen[1] - rotationOrigin.y, nextScreen[0] - rotationOrigin.x) * 180 / Math.PI;
      let delta = angle - lastAngle;
      if (delta > 180) delta -= 360;
      if (delta < -180) delta += 360;
      accumulated += delta;
      lastAngle = angle;
      const result = solveRotation(scene, candidate, center,
        snapAngle(startRotation + rotationSign * accumulated, fine ? 1 : 15));
      blocker = result.blocker;
    } else if (elevation) {
      if (candidate.placement.mode === "wall" && !canAttachToWall(candidate) && !candidate.placement.fill) detach();
      blocker = solveElevationDrag(scene, candidate, segmentOrigin, startZ, horizontal, dx * scale, -dy * scale);
    } else {
      if (candidate.placement.mode === "wall") {
        if (!canAttachToWall(candidate)) detach();
        else if (wallNormal && dx * wallNormal.x + dy * wallNormal.y > detachThreshold) detach();
      }
      const delta = groundDragDelta({ dx, dy, scale, right: basis.right, forward: basis.forward });
      blocker = solvePlanarDrag(scene, candidate, segmentOrigin, delta[0], delta[1]);
      if (candidate.placement.mode === "free" && canAttachToWall(candidate)) {
        const snap = wallSnap({ footprint: candidate.footprint,
          rotation: candidate.placement.rotation_z_deg, room: scene.room });
        if (snap) {
          const p = candidate.placement;
          const rotation = { north: 0, east: 90, south: 180, west: 270 }[snap.host_wall];
          const x = snap.host_wall === "west" ? 0 : snap.host_wall === "east" ? scene.room.width_mm : p.origin_x_mm;
          const y = snap.host_wall === "north" ? 0 : snap.host_wall === "south" ? scene.room.depth_mm : p.origin_y_mm;
          const footprint = localFootprint(candidate, x, y, rotation);
          if (!poseBlocker(scene, candidate, footprint, candidate.z_start, candidate.z_end,
            { mode: "wall", host_wall: snap.host_wall, rotation_z_deg: rotation })) {
            Object.assign(p, { mode: "wall", host_wall: snap.host_wall,
              origin_x_mm: x, origin_y_mm: y, rotation_z_deg: rotation });
            // These two origins are a pair. Rebase both on every attachment.
            segmentScreen = [...nextScreen];
            segmentOrigin = [x, y];
            wallNormal = projectWallNormal(snap.host_wall, candidate);
          }
        }
      }
    }
    syncPlacementGeometry(scene.room, candidate);
    return { moved: true, blocker };
  }
  function finish() {
    if (closed) throw new Error("drag transaction is closed");
    closed = true;
    return { before, item: candidate, operation: poseOperation(candidate),
      changed: moved && !samePose(before.placement, candidate.placement) };
  }
  function cancel() { closed = true; }
  return { kind, pointerId, item: candidate, before, preview, update, finish, cancel };
}
