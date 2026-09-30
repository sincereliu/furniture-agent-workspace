// 房间点和方向统一为 [x, y, z]：X 宽/向东、Y 深/向南、Z 高/向上；点以毫米为单位。
// Three.js 点和方向为 [x, y, z]：Y 向上。只在渲染/API 边界转换一次。
export function roomToThree(x, y, z) {
  return [x, z, y];
}

export function threeToRoom(x, y, z) {
  return [x, z, y];
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
