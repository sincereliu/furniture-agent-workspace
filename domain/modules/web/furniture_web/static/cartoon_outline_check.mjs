import assert from "node:assert/strict";
import { registerHooks } from "node:module";
import * as THREE from "../../../../../vendor/three/0.186.0/three.module.js";
registerHooks({ resolve(specifier, context, next) {
  return next(specifier === "three" ? new URL("../../../../../vendor/three/0.186.0/three.module.js", import.meta.url).href : specifier, context);
} });
const { createCartoonOutline } = await import("./cartoon_outline.js");

function harness() {
  const frames = [];
  const renderer = {
    autoClear: false, color: new THREE.Color(0xabcdee), alpha: 0.4,
    target: new THREE.WebGLRenderTarget(20, 20), calls: 0, failAt: 0,
    width: 1200, height: 800, ratio: 2,
    getDrawingBufferSize(value) { return value.set(this.width * this.ratio, this.height * this.ratio); },
    getSize(value) { return value.set(this.width, this.height); },
    getPixelRatio() { return this.ratio; },
    getRenderTarget() { return this.target; },
    setRenderTarget(value) { this.target = value; },
    getClearColor(value) { return value.copy(this.color); },
    getClearAlpha() { return this.alpha; },
    setClearColor(value, alpha) { this.color.set(value); this.alpha = alpha; },
    render(scene) {
      if (++this.calls === this.failAt) throw new Error("injected draw failure");
      scene.updateMatrixWorld(true);
      const meshes = [];
      scene.traverseVisible(mesh => { if (mesh.isMesh) { mesh.onBeforeRender(); meshes.push(mesh); } });
      frames.push({ meshes, target: this.target, autoClear: this.autoClear });
    },
  };
  const outline = createCartoonOutline(renderer);
  return { renderer, frames, outline, draw(roots, camera) {
    outline.prepare(roots, camera);
    outline.draw(roots, camera);
  } };
}
function part(itemId, x) {
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(100, 100, 100), new THREE.MeshBasicMaterial());
  mesh.userData = { itemId, cartoonInk: { color: 0x28231d } };
  mesh.position.x = x;
  return mesh;
}
const root = new THREE.Group();
const a1 = part("a", -100), b = part("b", 100), a2 = part("a", 0);
root.add(a1, b, a2); // 故意交错排列，身份不能依赖同件部件是否连续。
root.updateMatrixWorld(true);
const camera = new THREE.PerspectiveCamera();
const { renderer, frames, draw, outline } = harness();
assert.throws(() => outline.draw([root], camera), /prepare/);
draw([root], camera);
assert.throws(() => outline.draw([root], camera), /prepare/, "每帧明确准备一次，不能沿用上一帧的接触状态");
const initialMasks = frames[0].meshes.slice(), initialIds = frames[1].meshes.slice();
const aIds = initialIds.filter(mesh => mesh.userData.itemId === "a");
const bId = initialIds.find(mesh => mesh.userData.itemId === "b");
assert.equal(aIds[0].material, aIds[1].material);
assert.notEqual(aIds[0].material.color.getHex(), bId.material.color.getHex(), "同色家具也有不同身份");

// 同一件的所有部件共用投影线宽；距离、镜头、画布和 DPR 的关系要独立成立。
camera.position.set(0, 0, 1000); camera.lookAt(0, 0, 0);
draw([root], camera);
const nearRadius = aIds[0].material.opacity;
assert.equal(aIds[1].material.opacity, nearRadius);
camera.position.z = 5000;
draw([root], camera);
const farRadius = aIds[0].material.opacity;
assert.ok(farRadius < nearRadius && farRadius > 0);
renderer.ratio = 1;
draw([root], camera);
assert.equal(aIds[0].material.opacity, farRadius, "DPR 不改变 CSS 线宽");
renderer.height = 400;
draw([root], camera);
assert.ok(aIds[0].material.opacity < farRadius, "缩小画布时线宽跟随家具投影收细");
renderer.height = 800; renderer.ratio = 2;
const ortho = new THREE.OrthographicCamera(-300, 300, 200, -200, 1, 10000);
ortho.position.z = 1000;
draw([root], ortho);
const orthoRadius = aIds[0].material.opacity;
ortho.zoom = 0.2; ortho.updateProjectionMatrix();
draw([root], ortho);
assert.ok(aIds[0].material.opacity < orthoRadius, "正交镜头缩远也收细");

frames.length = 0;
a1.position.y = 50;
root.updateMatrixWorld(true);
a1.userData.cartoonInk.color = a2.userData.cartoonInk.color = 0xf59e0b;
draw([root], camera);
for (let i = 0; i < initialMasks.length; i++) {
  assert.equal(frames[0].meshes[i], initialMasks[i], "重绘复用颜色蒙版对象");
  assert.equal(frames[1].meshes[i], initialIds[i], "重绘复用身份蒙版对象");
}
const aMask = initialMasks.find(mesh => mesh.geometry === a1.geometry);
assert.equal(aMask.material.color.getHex(), 0xf59e0b);
assert.ok(aMask.matrixWorld.equals(a1.matrixWorld), "复用时更新位置");

let released = 0, borrowedGeometryDisposals = 0;
const bMask = initialMasks.find(mesh => mesh.geometry === b.geometry);
for (const material of [bMask.material, bId.material]) material.addEventListener("dispose", () => released++);
b.geometry.addEventListener("dispose", () => borrowedGeometryDisposals++);
root.remove(b);
draw([root], camera);
assert.equal(bMask.parent, null);
assert.equal(bId.parent, null);
assert.equal(released, 2, "移除家具时释放专有蒙版材质");
assert.equal(borrowedGeometryDisposals, 0, "不释放原场景拥有的几何");

const replacement = new THREE.BoxGeometry(200, 100, 100);
a1.geometry = replacement;
renderer.width = 900; renderer.height = 600; renderer.ratio = 1;
frames.length = 0;
draw([root], camera);
assert.equal(frames[0].meshes.find(mesh => mesh === aMask).geometry, replacement);
for (const frame of frames.slice(0, 2)) {
  assert.equal(frame.target.width, 900); assert.equal(frame.target.height, 600);
}
assert.deepEqual(frames[2].meshes[0].material.uniforms.uCssPixel.value.toArray(), [1 / 900, 1 / 600]);

for (const failAt of [1, 2, 3]) {
  const audit = harness();
  const previousTarget = audit.renderer.target;
  audit.renderer.failAt = failAt;
  assert.throws(() => audit.draw([root], camera), /injected draw failure/);
  assert.equal(audit.renderer.target, previousTarget);
  assert.equal(audit.renderer.color.getHex(), 0xabcdee);
  assert.equal(audit.renderer.alpha, 0.4);
  assert.equal(audit.renderer.autoClear, false);
  audit.renderer.failAt = 0;
  audit.frames.length = 0;
  audit.draw([root], camera);
  assert.equal(audit.frames.length, 3, "任一阶段失败后可以重新绘制");
}
root.clear();
frames.length = 0;
draw([root], camera);
assert.equal(frames.length, 0);
assert.ok(initialMasks.every(mesh => mesh.parent === null));
console.log("Furniture IDs, cached masks, removal, resize and recovery from all three draw failures pass.");
