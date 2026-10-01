// 房间点和方向统一为 [x, y, z]：X 宽/向东、Y 深/向南、Z 高/向上；点以毫米为单位。
// Three.js 点和方向为 [x, y, z]：Y 向上。只在渲染/API 边界转换一次。
export function roomToThree(x, y, z) {
  return [x, z, y];
}

export function threeToRoom(x, y, z) {
  return [x, z, y];
}

// 倍率作用于 tan(fov/2)，使屏幕尺寸与倍率成正比。
export function cameraFov(magnification) {
  return 2 * Math.atan(Math.tan(48 * Math.PI / 360) / magnification) * 180 / Math.PI;
}

export function cameraThreePosition(yaw, pitch, distance, target) {
  const cp = Math.cos(pitch);
  const sp = Math.sin(pitch);
  const cy = Math.cos(yaw);
  const sy = Math.sin(yaw);
  const east = target[0] + distance * cp * cy;
  const south = target[1] + distance * cp * sy;
  const up = target[2] + distance * sp;
  return roomToThree(east, south, up);
}
