import * as THREE from "three";

// 软包仅改变预览表面；每个曲面仍完整落在 sofaParts 给出的包围盒内。
export function sofaPartGeometry(part, size) {
  if (!part.surface) return new THREE.BoxGeometry(...size);
  const half = size.map(value => value / 2);
  const radius = Math.min(...size) * (part.surface === "shell" || part.surface === "base" ? 0.25 : 0.44);
  const crown = Math.min(size[1] * 0.16, 22);
  const lean = part.surface === "back" ? Math.min(size[2] * 0.18, size[1] * 0.1) : 0;
  const smooth = t => t * t * (3 - 2 * t);
  const shape = point => {
    const core = point.map((value, axis) => THREE.MathUtils.clamp(value, -half[axis] + radius, half[axis] - radius));
    const delta = point.map((value, axis) => value - core[axis]);
    const length = Math.hypot(...delta);
    const rounded = core.map((value, axis) => value + delta[axis] * radius / length);
    // 靠背框保留平整背面，但其四角也收圆；正面与上沿过渡为软包。
    const blend = part.surface === "shell" ? smooth((point[2] / half[2] + 1) / 2) : 1;
    const rear = [...point];
    if (part.surface === "shell") {
      const fraction = Math.max(Math.abs(point[0] / half[0]), Math.abs(point[1] / half[1]));
      if (fraction > 0) {
        const border = point.slice(0, 2).map(value => value / fraction);
        const center = border.map((value, axis) => THREE.MathUtils.clamp(value, -half[axis] + radius, half[axis] - radius));
        const offset = border.map((value, axis) => value - center[axis]);
        const scale = radius / Math.hypot(...offset);
        for (let axis = 0; axis < 2; axis++) rear[axis] = (center[axis] + offset[axis] * scale) * fraction;
      }
    }
    const p = rear.map((value, axis) => value + (rounded[axis] - value) * blend);
    const nx = p[0] / half[0], ny = p[1] / half[1], nz = p[2] / half[2];
    if (part.surface === "seat" || part.surface === "arm") {
      const dome = Math.pow(Math.max(0, (1 - nx * nx) * (1 - nz * nz)), 0.65);
      const sink = part.surface === "seat"
        ? size[1] * 0.1 * Math.exp(-nx * nx / 0.22 - (nz + 0.18) ** 2 / 0.24) : 0;
      p[1] -= Math.max(0, ny) ** 2 * (crown * (1 - dome) + sink);
    }
    if (part.surface === "back") {
      const dome = Math.pow(Math.max(0, (1 - nx * nx) * (1 - ny * ny)), 0.65);
      p[2] -= Math.max(0, nz) ** 2 * Math.min(size[2] * 0.2, 42) * (1 - dome);
      p[2] = p[2] * (1 - lean / size[2]) - lean * ny / 2;
    }
    if (part.surface === "arm") p[0] *= 1 - 0.12 * (ny * ny + nz * nz);
    return p;
  };

  const segments = [24, 20, 20];
  const grid = new THREE.BoxGeometry(...size, ...segments);
  const source = grid.getAttribute("position");
  const positions = [], indices = [], remap = [], welded = new Map();
  for (let i = 0; i < source.count; i++) {
    // 在圆角区保留五段采样；宽沙发也不会把窄圆角拉成单个斜面。
    const sample = [source.getX(i), source.getY(i), source.getZ(i)].map((value, axis) => {
      const step = Math.round((value / size[axis] + 0.5) * segments[axis]);
      if (step <= 5) return -half[axis] + radius * step / 5;
      if (step >= segments[axis] - 5) return half[axis] - radius * (segments[axis] - step) / 5;
      return -half[axis] + radius + (size[axis] - 2 * radius) * (step - 5) / (segments[axis] - 10);
    });
    const p = shape(sample);
    const key = p.map(value => Math.round(value * 10000)).join(",");
    if (!welded.has(key)) { welded.set(key, positions.length / 3); positions.push(...p); }
    remap.push(welded.get(key));
  }
  for (const index of grid.index.array) indices.push(remap[index]);
  grid.dispose();
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();

  // 坐垫保留侧面包边，靠背框保留后缘；其余软包靠轮廓和接触表现分件。
  const seam = [];
  if (part.surface === "arm" || part.surface === "back" || part.surface === "base") {
    geometry.userData.seamPositions = seam;
    return geometry;
  }
  const axes = part.surface === "seat" || part.surface === "arm" ? [0, 2] : [0, 1];
  const [a, b] = axes;
  const seamRadius = radius;
  const ring = [];
  for (let corner = 0; corner < 4; corner++) {
    const angle = corner * Math.PI / 2;
    const signA = corner === 0 || corner === 3 ? 1 : -1;
    const signB = corner < 2 ? 1 : -1;
    for (let step = 0; step <= 12; step++) {
      const theta = angle + step * Math.PI / 24;
      const p = [0, 0, 0];
      p[a] = signA * (half[a] - seamRadius) + seamRadius * Math.cos(theta);
      p[b] = signB * (half[b] - seamRadius) + seamRadius * Math.sin(theta);
      if (part.surface === "shell") p[2] = -half[2];
      ring.push(p);
    }
  }
  for (let i = 0; i < ring.length; i++) seam.push(...ring[i], ...ring[(i + 1) % ring.length]);
  geometry.userData.seamPositions = seam;
  return geometry;
}
