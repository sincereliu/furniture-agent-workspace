import assert from "node:assert/strict";
import { registerHooks } from "node:module";
import * as THREE from "../../../../../vendor/three/0.186.0/three.module.js";

registerHooks({
  resolve(specifier, context, next) {
    if (specifier === "three") specifier = new URL("../../../../../vendor/three/0.186.0/three.module.js", import.meta.url).href;
    else if (specifier.startsWith("/vendor/three/0.186.0/")) specifier = new URL(`../../../../..${specifier}`, import.meta.url).href;
    return next(specifier, context);
  },
});

const { addInk } = await import("./layout_scene.js");
const { createCartoonOutline } = await import("./cartoon_outline.js");
const { addSofa, addChair, addCoffeeTable, addDesk, ROOM_LAYER } = await import("./layout_meshes.js");
const maskFrames = [];
let activeTarget = null;
const renderer = {
  autoClear: true,
  clearColor: new THREE.Color(0xf2efe9), clearAlpha: 1,
  getDrawingBufferSize: value => value.set(2400, 1600),
  getSize: value => value.set(1200, 800),
  getRenderTarget: () => activeTarget,
  setRenderTarget: value => { activeTarget = value; },
  getClearColor(value) { return value.copy(this.clearColor); },
  getClearAlpha() { return this.clearAlpha; },
  setClearColor(value, alpha) { this.clearColor.set(value); this.clearAlpha = alpha; },
  render(scene) {
    scene.updateMatrixWorld(true);
    const objects = [];
    scene.traverseVisible(mesh => {
      if (!mesh.isMesh) return;
      mesh.onBeforeRender();
      objects.push({ mesh, opacity: mesh.material.uniforms?.uOpacity?.value });
    });
    maskFrames.push({ objects, target: activeTarget, autoClear: this.autoClear });
  },
};
const drawOutline = createCartoonOutline(renderer);
const camera = new THREE.PerspectiveCamera();
camera.layers.enable(ROOM_LAYER);
const samples = [
  [addSofa, 900, 800, 750],
  [addSofa, 2100, 900, 850],
  [addChair, 600, 600, 850],
  [addCoffeeTable, 1200, 600, 400],
  [addDesk, 1200, 600, 750],
];
for (const [add, width, depth, height] of samples) {
  for (const [selected, blocked, color] of [[false, false, 0x28231d], [true, false, 0xf59e0b], [true, true, 0xd93838]]) {
    const group = new THREE.Group();
    const pickables = [];
    const item = {
      id: "shaped", width, depth, height, z_start: 0,
      footprint: [[3000, 0], [3000, width], [3000 - depth, width], [3000 - depth, 0]],
    };
    assert.equal(add(group, pickables, item, selected, blocked, addInk), true);
    assert.ok(pickables.length > 0);
    group.updateMatrixWorld(true);
    for (const mesh of pickables) {
      const ink = mesh.userData.ink;
      assert.ok(ink.isLineSegments, "部件内部结构线与整体粗外框分开绘制");
      assert.equal(ink.layers.mask, 1 << ROOM_LAYER);
      assert.equal(ink.material.color.getHex(), color);
      assert.equal(mesh.userData.cartoonInk.color, color);
      assert.equal(ink.material.opacity, 0.45, "内部接缝降低对比，外轮廓保持实色");
      assert.equal(ink.material.depthTest, true, "背后的边线仍受前方几何遮挡");
      assert.equal(ink.castShadow, false);
      const hits = [];
      ink.raycast(new THREE.Raycaster(), hits);
      assert.deepEqual(hits, [], "边线不影响家具点选");
      mesh.geometry.computeBoundingBox();
      ink.geometry.computeBoundingBox();
      assert.ok(ink.geometry.boundingBox.equals(mesh.geometry.boundingBox), "贴墙的线必须留在原部件边界上");
      const positions = ink.geometry.getAttribute("position");
      assert.equal(positions.count, 24, "十二条真实棱边，不包含盒体对角线");
      const bounds = mesh.geometry.boundingBox;
      for (let i = 0; i < positions.count; i++) {
        const point = new THREE.Vector3().fromBufferAttribute(positions, i);
        for (const axis of ["x", "y", "z"]) {
          assert.ok(point[axis] === bounds.min[axis] || point[axis] === bounds.max[axis]);
        }
        const bodyWorld = point.clone().applyMatrix4(mesh.matrixWorld);
        const inkWorld = point.clone().applyMatrix4(ink.matrixWorld);
        assert.ok(bodyWorld.distanceTo(inkWorld) < 1e-6, "旋转后的轮廓与部件重合");
      }
    }
    const obstacles = new THREE.Group();
    for (const opacity of [1, 0.3, 0]) {
      const wall = new THREE.Mesh(new THREE.BoxGeometry(10, 900, 900), new THREE.MeshBasicMaterial({ opacity }));
      obstacles.add(wall);
    }
    obstacles.updateMatrixWorld(true);
    maskFrames.length = 0;
    drawOutline([group, obstacles], camera);
    assert.equal(maskFrames.length, 2, "先绘制可见整体蒙版，再合成粗轮廓");
    const [mask, composite] = maskFrames;
    assert.equal(mask.objects.length, pickables.length + 2, "部件进入同一蒙版；边线与全透明墙不进入蒙版");
    for (const original of pickables) {
      const copied = mask.objects.find(({ mesh }) => mesh.geometry === original.geometry).mesh;
      assert.equal(copied.material.color.getHex(), color);
      assert.ok(copied.matrixWorld.equals(original.matrixWorld), "整体蒙版保留部件世界变换");
    }
    const opaque = mask.objects.find(({ mesh }) => mesh.geometry === obstacles.children[0].geometry).mesh;
    assert.equal(opaque.material.opacity, 0);
    assert.equal(opaque.material.depthWrite, true, "前方实体清空轮廓蒙版并保留深度遮挡");
    const faded = mask.objects.find(({ mesh }) => mesh.geometry === obstacles.children[1].geometry);
    assert.equal(faded.opacity, 0.3);
    assert.equal(faded.mesh.material.blendDstAlpha, THREE.OneMinusSrcAlphaFactor);
    assert.equal(mask.target.width, 2400);
    assert.equal(mask.target.height, 1600);
    assert.deepEqual(composite.objects[0].mesh.material.uniforms.uCssPixel.value.toArray(), [1 / 1200, 1 / 800]);
    assert.equal(composite.autoClear, false);
    assert.equal(renderer.getRenderTarget(), null);
    assert.equal(renderer.clearColor.getHex(), 0xf2efe9);
    assert.equal(renderer.clearAlpha, 1);
    assert.equal(renderer.autoClear, true);
  }
}

const plainBox = new THREE.Mesh(new THREE.BoxGeometry(400, 500, 600));
assert.ok(addInk(plainBox).isMesh, "普通盒体保留原来的膨胀轮廓");
const plane = new THREE.Mesh(new THREE.PlaneGeometry(400, 500));
plane.layers.set(ROOM_LAYER);
assert.ok(addInk(plane).isLineSegments);
assert.equal(plane.userData.ink.layers.mask, plane.layers.mask);
maskFrames.length = 0;
drawOutline([new THREE.Group()], camera);
assert.equal(maskFrames.length, 0, "没有卡通家具时不执行额外绘制");
console.log("Cartoon outlines use a whole-furniture mask, light internal seams, wall occlusion and selection colors.");
