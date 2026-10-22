import * as THREE from "three";

// 桌面的圆角仅改变预览实体，外接尺寸仍与布局足迹一致。
export function deskPartGeometry(part, size) {
  if (part.role !== "top") return new THREE.BoxGeometry(...size);
  const [width, height, depth] = size;
  const r = Math.min(32, width * 0.06, depth * 0.08);
  const x = width / 2, z = depth / 2;
  const shape = new THREE.Shape();
  shape.moveTo(-x + r, -z);
  shape.lineTo(x - r, -z);
  shape.quadraticCurveTo(x, -z, x, -z + r);
  shape.lineTo(x, z - r);
  shape.quadraticCurveTo(x, z, x - r, z);
  shape.lineTo(-x + r, z);
  shape.quadraticCurveTo(-x, z, -x, z - r);
  shape.lineTo(-x, -z + r);
  shape.quadraticCurveTo(-x, -z, -x + r, -z);
  const geometry = new THREE.ExtrudeGeometry(shape, {
    depth: height, bevelEnabled: false, curveSegments: 6, steps: 1,
  });
  geometry.translate(0, 0, -height / 2);
  geometry.rotateX(-Math.PI / 2);
  // 只沿桌面的上下边缘描细线，不把圆角离散面画成竖条。
  const points = shape.getPoints(6);
  const seams = [];
  for (const y of [-height / 2, height / 2]) {
    for (let i = 1; i < points.length; i++) {
      const a = points[i - 1], b = points[i];
      seams.push(a.x, y, -a.y, b.x, y, -b.y);
    }
  }
  geometry.userData.seamPositions = seams;
  return geometry;
}
