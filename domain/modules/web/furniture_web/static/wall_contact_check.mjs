import assert from "node:assert/strict";
import { registerHooks } from "node:module";
import * as THREE from "../../../../../vendor/three/0.186.0/three.module.js";
registerHooks({ resolve(specifier, context, next) {
  return next(specifier === "three" ? new URL("../../../../../vendor/three/0.186.0/three.module.js", import.meta.url).href : specifier, context);
} });
const { createWallContactUpdater } = await import("./wall_contact.js");
const { wallGeometry, addDesk, addChair, addSofa, addCoffeeTable, ROOM_LAYER } = await import("./layout_meshes.js");
const root = new THREE.Group(), camera = new THREE.PerspectiveCamera();
camera.layers.enable(ROOM_LAYER);
const wall = new THREE.Mesh(wallGeometry([[-1000, -100, 0, 3000, 0, 2000]]), new THREE.MeshBasicMaterial());
root.add(wall);
const addInk = mesh => {
  const ink = new THREE.LineSegments(new THREE.EdgesGeometry(mesh.geometry, 25), new THREE.LineBasicMaterial());
  mesh.add(ink); mesh.userData.ink = ink;
};
for (const add of [addDesk, addChair, addSofa, addCoffeeTable]) {
  const group = new THREE.Group(), parts = [];
  root.add(group);
  add(group, parts, { id: "sample", width: 1200, depth: 600, height: 750, z_start: 0,
    footprint: [[0, 0], [1200, 0], [1200, 600], [0, 600]],
  }, false, false, addInk);
  const baseZ = -new THREE.Box3().setFromObject(group).min.z;
  group.position.z = baseZ;
  const update = createWallContactUpdater();
  const touching = update([root], camera);
  assert.ok(parts.some(mesh => touching.get(mesh).count > 0));
  for (const mesh of parts) {
    const state = touching.get(mesh);
    const lines = mesh.userData.ink.geometry.getAttribute("position");
    if (!state.count) assert.equal(lines.count, 24, "退让的桌腿等部件保留全部棱边");
    for (let i = 0; i < lines.count; i += 2) {
      const a = new THREE.Vector3().fromBufferAttribute(lines, i).applyMatrix4(mesh.matrixWorld);
      const b = new THREE.Vector3().fromBufferAttribute(lines, i + 1).applyMatrix4(mesh.matrixWorld);
      assert.ok(Math.abs(a.z) > 0.49 || Math.abs(b.z) > 0.49, "不留下沿墙的接触线段");
    }
  }
  group.position.z = baseZ + 2;
  update([root], camera);
  for (const mesh of parts) {
    assert.equal(touching.get(mesh).count, 0, "真实2mm间隙不算贴墙");
    assert.equal(mesh.userData.ink.geometry.getAttribute("position").count, 24, "移离墙后恢复棱边");
  }
  group.position.z = baseZ;
  wall.material.opacity = 0;
  update([root], camera);
  assert.ok(parts.every(mesh => touching.get(mesh).count === 0), "完全淡出的墙不抹去家具形状");
  wall.material.opacity = 1;
  // 门洞覆盖整件家具，墙仍在两侧。
  wall.geometry = wallGeometry([[-1000, -100, 0, -1, 0, 2000], [1201, -100, 0, 3000, 0, 2000]]);
  update([root], camera);
  assert.ok(parts.every(mesh => touching.get(mesh).count === 0), "门窗洞口不当成实体墙");
  wall.geometry = wallGeometry([[-1000, -100, 0, 3000, 0, 2000]]);
  group.position.set(0, 0, 0);
  group.rotation.y = Math.PI / 2;
  group.position.z = -new THREE.Box3().setFromObject(group).min.z;
  update([root], camera);
  assert.ok(parts.some(mesh => touching.get(mesh).count > 0), "旋转后的实际接触仍被识别");
  let released = 0;
  touching.get(parts[0]).texture.addEventListener("dispose", () => released++);
  root.remove(group);
  update([root], camera);
  assert.equal(touching.size, 0);
  assert.equal(released, 1);
}
// 一个接触棱跨过窗洞时，只保留洞口范围的线，不整条隐藏。
const spanning = new THREE.Mesh(new THREE.BoxGeometry(1000, 200, 500), new THREE.MeshBasicMaterial());
spanning.position.set(500, 600, 250);
spanning.userData.cartoonInk = { color: 0x28231d };
addInk(spanning); root.add(spanning);
wall.geometry = wallGeometry([[-1000, -100, 0, 400, 0, 2000], [600, -100, 0, 3000, 0, 2000]]);
createWallContactUpdater()([root], camera);
const lines = spanning.userData.ink.geometry.getAttribute("position");
const backTop = [];
for (let i = 0; i < lines.count; i += 2) {
  const a = new THREE.Vector3().fromBufferAttribute(lines, i).applyMatrix4(spanning.matrixWorld);
  const b = new THREE.Vector3().fromBufferAttribute(lines, i + 1).applyMatrix4(spanning.matrixWorld);
  if (Math.abs(a.z) < 1e-6 && Math.abs(b.z) < 1e-6 && a.y === 700 && b.y === 700) backTop.push([a.x, b.x].sort((x, y) => x - y));
}
assert.equal(backTop.length, 1);
assert.ok(Math.abs(backTop[0][0] - 400.5) < 0.01 && Math.abs(backTop[0][1] - 599.5) < 0.01);
console.log("Real wall contacts clip seams; gaps, inset parts, openings, rotation, wall fading and cleanup pass.");
