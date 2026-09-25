// 房间坐标：X 东、Y 南、Z 上。three.js 是 Y 朝上的右手系。
// 对应关系只有这一处：three (x, y, z) = 房间 (东, 上, 南)。
export function roomToThree(x, y, z) {
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
