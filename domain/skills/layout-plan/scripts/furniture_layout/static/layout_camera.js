/**
 * 相机视场、正视图预设与过渡辅助函数。
 */

export const ORTHO_VIEWS = ["top", "bottom", "front", "back", "left", "right"];
export const isOrthoView = (name) => ORTHO_VIEWS.includes(name);
export const ELEVATION_MAX_PITCH = 0.12;

export function baseFit(canvas, diagonal) {
  const aspect = (canvas.clientWidth || 960) / Math.max(canvas.clientHeight || 600, 1);
  const vFov = 48 * Math.PI / 180;
  const limit = Math.min(vFov, 2 * Math.atan(Math.tan(vFov / 2) * aspect));
  return diagonal * 0.5 / Math.sin(limit / 2) * 1.32;
}

export function fitDistance(canvas, diagonal, view, viewName) {
  return baseFit(canvas, diagonal) * ((viewName && isOrthoView(viewName)) ? view.elevationPull() : 1);
}

export function verticalPlaneScale(canvas, cam, point) {
  const rel = [point[0] - cam.position[0], point[1] - cam.position[1], (point[2] || 0) - cam.position[2]];
  const depth = rel[0] * cam.forward[0] + rel[1] * cam.forward[1] + rel[2] * cam.forward[2];
  const fov = cam.fov * Math.PI / 180;
  return 2 * Math.tan(fov / 2) * Math.max(depth, 1) / (canvas.clientHeight || 600);
}

export function rotationSign(project, roomWidth, center, height) {
  const probe = 10 * Math.PI / 180;
  const radius = Math.max(200, roomWidth * 0.1);
  const origin = project([center[0], center[1], height]);
  const base = project([center[0] + radius, center[1], height]);
  const turned = project([center[0] + radius * Math.cos(probe), center[1] + radius * Math.sin(probe), height]);
  const a0 = Math.atan2(base.y - origin.y, base.x - origin.x);
  const a1 = Math.atan2(turned.y - origin.y, turned.x - origin.x);
  return a1 > a0 ? 1 : -1;
}

export function horizontalAxis(cam) {
  const right = cam.right;
  const axis = Math.abs(right[0]) >= Math.abs(right[1]) ? 0 : 1;
  return { axis, sign: right[axis] >= 0 ? 1 : -1 };
}

export function nearAngle(gap) {
  return Math.abs(((gap + Math.PI) % (2 * Math.PI) + 2 * Math.PI) % (2 * Math.PI) - Math.PI);
}
