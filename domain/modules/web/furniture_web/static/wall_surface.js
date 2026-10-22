import { roomToThree } from "./layout_frame.js";

// Room-coordinate wall boxes become one closed surface in Three coordinates.
// The shared grid splits T junctions and omits faces inside the union, including
// when padded boxes overlap to form the inverted outline hull.
export function wallSurfacePositions(boxes, padding = 0) {
  if (!boxes.length) return [];
  const solids = boxes.map(([x0, y0, z0, x1, y1, z1]) => [
    roomToThree(x0 - padding, y0 - padding, z0 - padding),
    roomToThree(x1 + padding, y1 + padding, z1 + padding),
  ]);
  const axes = [0, 1, 2].map((axis) => (
    [...new Set(solids.flatMap(([lo, hi]) => [lo[axis], hi[axis]]))].sort((a, b) => a - b)
  ));
  const indices = axes.map((values) => new Map(values.map((value, index) => [value, index])));
  const [nx, ny, nz] = axes.map((values) => values.length - 1);
  const key = (x, y, z) => (x * ny + y) * nz + z;
  const filled = new Set();
  for (const [lo, hi] of solids) {
    const start = lo.map((value, axis) => indices[axis].get(value));
    const end = hi.map((value, axis) => indices[axis].get(value));
    for (let x = start[0]; x < end[0]; x += 1) {
      for (let y = start[1]; y < end[1]; y += 1) {
        for (let z = start[2]; z < end[2]; z += 1) filled.add(key(x, y, z));
      }
    }
  }
  const occupied = (x, y, z) => (
    x >= 0 && x < nx && y >= 0 && y < ny && z >= 0 && z < nz && filled.has(key(x, y, z))
  );
  // Corner index = x * 4 + y * 2 + z; quads wind outwards.
  const faces = [
    [-1, 0, 0, [0, 1, 3, 2]], [1, 0, 0, [4, 6, 7, 5]],
    [0, -1, 0, [0, 4, 5, 1]], [0, 1, 0, [2, 3, 7, 6]],
    [0, 0, -1, [0, 2, 6, 4]], [0, 0, 1, [1, 5, 7, 3]],
  ];
  const positions = [];
  for (let x = 0; x < nx; x += 1) {
    for (let y = 0; y < ny; y += 1) {
      for (let z = 0; z < nz; z += 1) {
        if (!occupied(x, y, z)) continue;
        const corners = [];
        for (let dx = 0; dx <= 1; dx += 1) {
          for (let dy = 0; dy <= 1; dy += 1) {
            for (let dz = 0; dz <= 1; dz += 1) {
              corners.push([axes[0][x + dx], axes[1][y + dy], axes[2][z + dz]]);
            }
          }
        }
        for (const [dx, dy, dz, quad] of faces) {
          if (occupied(x + dx, y + dy, z + dz)) continue;
          const [a, b, c, d] = quad.map((index) => corners[index]);
          positions.push(...a, ...b, ...c, ...a, ...c, ...d);
        }
      }
    }
  }
  return positions;
}
