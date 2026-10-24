import assert from "node:assert/strict";
import { registerHooks } from "node:module";
import * as THREE from "../../../../../vendor/three/0.186.0/three.module.js";
registerHooks({ resolve(specifier, context, next) {
  return next(specifier === "three" ? new URL("../../../../../vendor/three/0.186.0/three.module.js", import.meta.url).href : specifier, context);
} });
const { createWallContactUpdater } = await import("../../furniture_web/static/render/outline/wall_contact.js");
const { wallGeometry, addDesk, addChair, addSofa, addCoffeeTable, ROOM_LAYER } = await import("../../furniture_web/static/render/room/layout_meshes.js");
const { addFurnitureInk } = await import("../../furniture_web/static/render/outline/layout_ink.js");
const { sofaPartGeometry } = await import("../../furniture_web/static/render/furniture/sofa_upholstery.js");
const root = new THREE.Group(), camera = new THREE.PerspectiveCamera();
camera.layers.enable(ROOM_LAYER);
const wall = new THREE.Mesh(wallGeometry([[-1000, -100, 0, 3000, 0, 2000]]), new THREE.MeshBasicMaterial());
root.add(wall);
for (const add of [addDesk, addChair, addSofa, addCoffeeTable]) {
  const group = new THREE.Group(), parts = [];
  root.add(group);
  add(group, parts, { id: "sample", width: 1200, depth: 600, height: 750, z_start: 0,
    footprint: [[0, 0], [1200, 0], [1200, 600], [0, 600]],
  }, false, false, addFurnitureInk);
  const baseZ = -new THREE.Box3().setFromObject(group).min.z;
  group.position.z = baseZ;
  const update = createWallContactUpdater();
  const touching = update([root], camera);
  assert.ok(parts.some(mesh => touching.get(mesh).count > 0));
  for (const mesh of parts) {
    const state = touching.get(mesh);
    const lines = mesh.userData.ink.geometry.getAttribute("position");
    if (!state.count) assert.equal(lines.count, state.positions.count, "退让部件保留原有棱边或包边");
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
    assert.equal(mesh.userData.ink.geometry.getAttribute("position").count, touching.get(mesh).positions.count, "移离墙后恢复棱边和包边");
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
// 靠包曲面能接触墙，而侧面中线包边并不接触：蒙版不能只检查包边。
const curved = new THREE.Mesh(sofaPartGeometry({ surface: "back" }, [600,400,200]), new THREE.MeshBasicMaterial());
curved.geometry.computeBoundingBox();
curved.position.set(500,600,-curved.geometry.boundingBox.min.z);
addFurnitureInk(curved, { itemId:"curved", color:0x28231d }); root.add(curved);
const updateCurved = createWallContactUpdater();
const curvedState = updateCurved([root], camera).get(curved);
assert.ok(curvedState.count > 0, "无接触包边时仍检测真实软包曲面");
assert.equal(curved.userData.ink.geometry.getAttribute("position").count, curvedState.positions.count);
curved.position.z += 2;
assert.equal(updateCurved([root],camera).get(curved).count, 0, "软包移离墙后恢复蒙版外框");
root.remove(curved); updateCurved([root], camera);
curved.geometry.dispose(); curved.material.dispose();
// 一个接触棱跨过窗洞时，只保留洞口范围的线，不整条隐藏。
const spanning = new THREE.Mesh(new THREE.BoxGeometry(1000, 200, 500), new THREE.MeshBasicMaterial());
spanning.position.set(500, 600, 250);
addFurnitureInk(spanning, { itemId: "spanning", color: 0x28231d }); root.add(spanning);
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

// 有限地板与真实落地点：只裁接地棱边，不把离地、越出地板或缩进的部件一并消线。
const groundRoot = new THREE.Group();
const floor = new THREE.Mesh(new THREE.PlaneGeometry(2000, 2000), new THREE.MeshBasicMaterial());
floor.rotation.x = -Math.PI / 2;
floor.userData.floorContact = true;
groundRoot.add(floor);
const cabinet = new THREE.Mesh(new THREE.BoxGeometry(900, 1800, 350), new THREE.MeshBasicMaterial());
cabinet.position.y = 900;
addFurnitureInk(cabinet, { itemId: "bookcase", color: 0x28231d });
groundRoot.add(cabinet);
const updateGround = createWallContactUpdater();
const groundState = updateGround([groundRoot], camera).get(cabinet);
assert.equal(groundState.count, 1);
const groundLines = cabinet.userData.ink.geometry.getAttribute("position");
for (let i = 0; i < groundLines.count; i += 2) {
  const a = new THREE.Vector3().fromBufferAttribute(groundLines, i).applyMatrix4(cabinet.matrixWorld);
  const b = new THREE.Vector3().fromBufferAttribute(groundLines, i + 1).applyMatrix4(cabinet.matrixWorld);
  assert.ok(a.y > 0.49 || b.y > 0.49, "接地底边不再叠内部细线");
}
assert.equal(groundLines.count, 16, "上框和四根竖棱保留");
for (const gap of [2, 80]) {
  cabinet.position.y = 900 + gap;
  updateGround([groundRoot], camera);
  assert.equal(groundState.count, 0, "真实离地间隙恢复完整外框");
  assert.equal(cabinet.userData.ink.geometry.getAttribute("position").count, groundState.positions.count);
}
cabinet.position.set(1600, 900, 0);
updateGround([groundRoot], camera);
assert.equal(groundState.count, 0, "地板平面不向边界外无限延伸");
cabinet.position.set(900, 900, 0);
updateGround([groundRoot], camera);
assert.equal(groundState.count, 1);
assert.ok(cabinet.userData.ink.geometry.getAttribute("position").count > 16, "越出地板的底边片段保留");
groundRoot.remove(cabinet); updateGround([groundRoot], camera);
for (const add of [addDesk, addChair, addSofa, addCoffeeTable]) {
  const group = new THREE.Group(), parts = [];
  groundRoot.add(group);
  add(group, parts, {id:"grounded",width:1200,depth:600,height:750,z_start:0,
    footprint:[[-600,-300],[600,-300],[600,300],[-600,300]],
  }, false, false, addFurnitureInk);
  const states = updateGround([groundRoot], camera);
  assert.ok(parts.some(mesh => states.get(mesh).count > 0), "真实桌椅/沙发脚参与地板接触");
  assert.ok(parts.some(mesh => states.get(mesh).count === 0), "离地桌面、坐垫保留描边");
  groundRoot.remove(group); updateGround([groundRoot], camera);
}
console.log("Finite floor contacts clip grounded edges; lifted cabinets and raised furniture parts keep their outlines.");
