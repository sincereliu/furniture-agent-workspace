import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { registerHooks } from "node:module";
import * as THREE from "../../../../../vendor/three/0.186.0/three.module.js";
import { cameraThreePosition, roomToThree } from "../../furniture_web/static/render/room/layout_frame.js";
import { INK_VIEW_BIAS_MM, biasInkView, inkViewBiasGlsl, logWindowDepth } from "../../furniture_web/static/render/outline/ink_depth.js";
registerHooks({ resolve(specifier, context, next) {
  return next(specifier === "three" ? new URL("../../../../../vendor/three/0.186.0/three.module.js", import.meta.url).href : specifier, context);
} });
const { addFurnitureInk, addStageInk } = await import("../../furniture_web/static/render/outline/layout_ink.js");

const NEAR = 10;
const FAR = 500000;
const ULP = 1 / 16777216;
const sceneJs = readFileSync(new URL("../../furniture_web/static/render/room/layout_scene.js", import.meta.url), "utf8");

assert.equal(INK_VIEW_BIAS_MM, 1);
assert.equal(inkViewBiasGlsl(), [
  "#include <project_vertex>",
  "mvPosition.z += 1.0;",
  "gl_Position = projectionMatrix * mvPosition;",
].join("\n\t"));
assert.match(sceneJs, /logarithmicDepthBuffer:\s*true/);
for (const add of [mesh => addFurnitureInk(mesh, { itemId: "depth", color: 0x28231d }), addStageInk]) {
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(100, 100));
  const ink = add(mesh);
  const shader = { vertexShader: "#include <project_vertex>" };
  ink.material.onBeforeCompile(shader);
  assert.match(shader.vertexShader, /mvPosition\.z \+= 1\.0;/, "真实细线材质接入视线偏移");
  assert.equal(ink.material.depthTest, true);
}

function viewPoint(camera, roomPoint) {
  camera.updateMatrixWorld(true);
  const [x, y, z] = roomToThree(...roomPoint);
  return new THREE.Vector4(x, y, z, 1).applyMatrix4(camera.matrixWorldInverse);
}

function clipOf(camera, eye) {
  return new THREE.Vector4(eye.x, eye.y, eye.z, 1).applyMatrix4(camera.projectionMatrix);
}

function linearWindow(clip) {
  return (clip.z / clip.w) * 0.5 + 0.5;
}

// 北墙面上的一点。相机在房间里朝北看，视线的视图 Z 必须为负。
const wallPoint = [2000, 0, 800];
for (const distance of [4000, 12000, 96000]) {
  const position = cameraThreePosition(Math.PI / 2, 0.72, distance, wallPoint);
  const camera = new THREE.PerspectiveCamera(48, 16 / 9, NEAR, FAR);
  camera.up.set(0, 1, 0);
  camera.position.set(position[0], position[1], position[2]);
  camera.lookAt(...roomToThree(...wallPoint));

  const eye = viewPoint(camera, wallPoint);
  assert.ok(eye.z < -100, `distance ${distance}: point should be in front of the camera`);
  // 透视裁剪的 w 就是视距 -eye.z。这个等式来自投影矩阵，不来自拉近函数。
  const wallClip = clipOf(camera, eye);
  assert.ok(Math.abs(wallClip.w + eye.z) < 1e-4, `distance ${distance}: clip.w should be -eye.z`);

  const pulled = biasInkView(eye.x, eye.y, eye.z);
  assert.equal(pulled[2] - eye.z, INK_VIEW_BIAS_MM);
  const lineClip = clipOf(camera, new THREE.Vector3(...pulled));
  assert.ok(Math.abs((wallClip.w - lineClip.w) - INK_VIEW_BIAS_MM) < 1e-4);

  const wallDepth = logWindowDepth(wallClip.w, FAR);
  const lineDepth = logWindowDepth(lineClip.w, FAR);
  assert.ok(lineDepth < wallDepth, `distance ${distance}: ink should be closer than the wall`);
  assert.ok(wallDepth - lineDepth > 4 * ULP, `distance ${distance}: log depth gap should clear several ulps`);

  // 沿同一视线再近 2 毫米的面仍在线的前面。拉近量不能把边线翻到这块面之前。
  const aheadClip = clipOf(camera, new THREE.Vector3(eye.x, eye.y, eye.z + 2));
  const aheadDepth = logWindowDepth(aheadClip.w, FAR);
  assert.ok(aheadDepth < lineDepth, `distance ${distance}: a face 2mm closer should hide the ink`);

  if (distance === 96000) {
    const linearGap = linearWindow(wallClip) - linearWindow(lineClip);
    assert.ok(linearGap > 0);
    assert.ok(linearGap < ULP, "elevation distance: a 1mm pull is below one linear depth step");
  }
}

console.log("ink stays in front of a flush wall and behind a nearer face");
