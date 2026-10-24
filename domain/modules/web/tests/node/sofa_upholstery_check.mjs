import assert from "node:assert/strict";
import { registerHooks } from "node:module";
import * as THREE from "../../../../../vendor/three/0.186.0/three.module.js";
registerHooks({ resolve(specifier, context, next) {
  return next(specifier === "three" ? new URL("../../../../../vendor/three/0.186.0/three.module.js", import.meta.url).href : specifier, context);
} });
const { sofaPartGeometry } = await import("../../furniture_web/static/render/furniture/sofa_upholstery.js");
const { sofaParts, sofaLocalBox } = await import("../../furniture_web/static/render/furniture/sofa_solid.js");
const { furnitureEdges } = await import("../../furniture_web/static/render/furniture/furniture_edges.js");
for (const dimensions of [[900,800,750], [1500,850,800], [2100,900,850], [4000,900,900], [280,280,180]]) {
  for (const part of sofaParts(...dimensions) || []) {
    const { size } = sofaLocalBox(part.box);
    const geometry = sofaPartGeometry(part, size);
    geometry.computeBoundingBox();
    const p = geometry.getAttribute("position"), n = geometry.getAttribute("normal");
    const bounds = new THREE.Box3(new THREE.Vector3(...size).multiplyScalar(-0.5), new THREE.Vector3(...size).multiplyScalar(0.5));
    for (let i = 0; i < p.count; i++) {
      const point = new THREE.Vector3().fromBufferAttribute(p, i);
      assert.ok(point.toArray().every(Number.isFinite));
      assert.ok(bounds.clone().expandByScalar(0.001).containsPoint(point), "曲面不改变家具尺寸与摆放足迹");
      const normal = new THREE.Vector3().fromBufferAttribute(n, i);
      assert.ok(Math.abs(normal.length() - 1) < 0.001, "曲面法线有效");
    }
    if (part.surface) {
      const edges = new Map();
      const index = geometry.index.array;
      for (let i = 0; i < index.length; i += 3) for (let j = 0; j < 3; j++) {
        const a = index[i + j], b = index[i + (j + 1) % 3];
        const key = a < b ? `${a},${b}` : `${b},${a}`;
        edges.set(key, (edges.get(key) || 0) + 1);
      }
      assert.ok([...edges.values()].every(count => count === 2), `软包是封闭曲面，没有裂缝: ${dimensions}/${part.surface}`);
      const seams = furnitureEdges(geometry);
      assert.ok(seams.getAttribute("position").count < p.count / 4, "内部线只描包边，不描三角网格");
      seams.dispose();
      const corner = new THREE.Vector3(...size).multiplyScalar(0.5);
      assert.ok(!Array.from({ length:p.count }, (_, i) => new THREE.Vector3().fromBufferAttribute(p,i))
        .some(point => point.distanceTo(corner) < 0.01), "软包正面没有直角尖角");
      const mesh = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({ side:THREE.DoubleSide }));
      mesh.updateMatrixWorld(true);
      const ray = new THREE.Raycaster(new THREE.Vector3(0,size[1]*2,0), new THREE.Vector3(0,-1,0));
      assert.ok(ray.intersectObject(mesh).length > 0, "软包曲面可直接参与点选");
      mesh.material.dispose();
    } else assert.equal(geometry.type, "BoxGeometry", "木脚保留硬质结构");
    geometry.dispose();
  }
}
const size = [600, 120, 650];
const seat = sofaPartGeometry({ surface:"seat" }, size);
const p = seat.getAttribute("position");
const top = (x,z) => {
  let y = -Infinity;
  for (let i=0;i<p.count;i++) if (Math.abs(p.getX(i)-x)<0.01 && Math.abs(p.getZ(i)-z)<0.01) y=Math.max(y,p.getY(i));
  assert.ok(Number.isFinite(y)); return y;
};
const shoulder = [];
for (let i=0;i<p.count;i++) if (Math.abs(p.getZ(i))<0.01 && p.getX(i)>60 && p.getX(i)<200) shoulder.push(p.getY(i));
assert.ok(top(0,0) < Math.max(...shoulder), "坐垫中部有轻微压陷");
const back = sofaPartGeometry({surface:"back"}, [600,400,200]);
const bp = back.getAttribute("position");
const centers = new Map();
for(let i=0;i<bp.count;i++) {
  const y=bp.getY(i), row=centers.get(y)||[]; row.push(bp.getZ(i)); centers.set(y,row);
}
const center = y => (Math.min(...centers.get(y))+Math.max(...centers.get(y)))/2;
assert.ok(center(200) < center(-200), "靠包上缘后倾");
seat.dispose(); back.dispose();
console.log("Soft sofa meshes stay closed and inside their envelopes, with cushion compression, reclining backs and sparse seams.");
