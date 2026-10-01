import * as THREE from "../../../../../../vendor/three/0.186.0/three.module.js";
import assert from "node:assert/strict";
import { cameraThreePosition, roomToThree, threeToRoom } from "./layout_frame.js";
import { roomAxes, dimensionAnnotations } from "./layout_annotations.js";
import { normalizeItems } from "./layout_payload.js";

const mapped = roomToThree(1000, 200, 300);
if (mapped[0] !== 1000 || mapped[1] !== 300 || mapped[2] !== 200) {
  throw new Error(`roomToThree mapped to ${mapped}`);
}

const target = [2000, 1800, 900];
const position = cameraThreePosition(Math.PI / 2, 0, 5000, target);
const camera = new THREE.PerspectiveCamera(48, 16 / 9, 10, 100000);
camera.up.set(0, 1, 0);
camera.position.set(position[0], position[1], position[2]);
camera.lookAt(target[0], target[2], target[1]);
camera.updateMatrixWorld(true);

const forward = new THREE.Vector3();
camera.getWorldDirection(forward);
const right = new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 0);
if (forward.z > -0.99 || Math.abs(forward.x) > 0.02 || Math.abs(forward.y) > 0.02) {
  throw new Error(`front view should look north, got ${forward.toArray()}`);
}
if (right.x < 0.99 || Math.abs(right.y) > 0.02 || Math.abs(right.z) > 0.02) {
  throw new Error(`front view should put east on the right, got ${right.toArray()}`);
}
console.log("frame ok");

assert.deepEqual(threeToRoom(...mapped), [1000, 200, 300]);
const room = { width_mm: 4200, depth_mm: 3600, height_mm: 2800 };
const axes = roomAxes(room);
assert.deepEqual(axes.map((axis) => axis.to), [[4200, 0, 0], [0, 3600, 0], [0, 0, 2800]]);
assert.deepEqual(axes.map((axis) => roomToThree(...axis.to)), [[4200, 0, 0], [0, 0, 3600], [0, 2800, 0]]);
assert.deepEqual(axes.map((axis) => axis.text), ["X 4200", "Y 3600", "Z 2800"]);
assert.deepEqual(axes.map((axis) => axis.anchor), [[2100, -25, 0], [-25, 1800, 0], [-25, 0, 1400]]);

const item = {
  footprint: [[600, 800], [1800, 800], [1800, 1300], [600, 1300]],
  z_start: 300, z_end: 2000, height: 1700,
  clearances_mm: { west: 600, east: 2400, north: 800, south: 2300 },
};
const annotations = dimensionAnnotations(room, item);
assert.deepEqual(annotations.map((spec) => spec.text), ["宽 1200", "深 500", "高 1700", "离墙 600", "离墙 2400", "离墙 800", "离墙 2300"]);
assert.deepEqual(annotations.map((spec) => spec.anchor), [
  [1200, 710, 308], [510, 1050, 308], [1890, 1300, 1150],
  [300, 1050, 308], [3000, 1050, 308], [1200, 400, 308], [1200, 2450, 308],
]);
assert.deepEqual(annotations.slice(0, 3).map((spec) => roomToThree(...spec.anchor)), [
  [1200, 308, 710], [510, 308, 1050], [1890, 1150, 1300],
]);


// 旋转后宽深仍是件的局部尺寸，标签必须在线中点；吊柜高度不依赖地面为零。
for (const angle of [Math.PI / 2, Math.PI / 6]) {
  const rotated = dimensionAnnotations(room, {
    ...item, clearances_mm: {},
    footprint: [[0, 0], [1200, 0], [1200, 500], [0, 500]].map(([x, y]) => [
      1600 + x * Math.cos(angle) - y * Math.sin(angle),
      900 + x * Math.sin(angle) + y * Math.cos(angle),
    ]),
  });
  assert.deepEqual(rotated.map((spec) => spec.text), ["宽 1200", "深 500", "高 1700"]);
  if (angle === Math.PI / 2) {
    const expected = [[1690, 1500, 308], [1350, 810, 308], [1100, 2190, 1150]];
    rotated.forEach((spec, index) => spec.anchor.forEach((value, i) => {
      assert.ok(Math.abs(value - expected[index][i]) < 1e-8);
    }));
  }
  for (const [index, spec] of rotated.entries()) {
    const length = Math.hypot(...spec.to.map((value, i) => value - spec.from[i]));
    assert.ok(Math.abs(length - [1200, 500, 1700][index]) < 1e-8);
    assert.deepEqual(spec.anchor, spec.from.map((value, i) => (value + spec.to[i]) / 2));
  }
}
assert.deepEqual(dimensionAnnotations(room, { ...item, clearances_mm: { west: 0, north: 0 } }).map((spec) => spec.text), ["宽 1200", "深 500", "高 1700"]);
console.log("room axes and dimension anchors ok (0°, 90°, 30°)");

// 两个立方体占用同一空间，但 P0 与正面不同；标注必须沿各自局部边，不能按包围框重排。
const cube = {
  height: 600, z_start: 300, z_end: 900,
  footprint: [[2000, 1800], [2600, 1800], [2600, 2400], [2000, 2400]],
};
const turnedCube = {
  ...cube,
  footprint: [[2600, 1800], [2600, 2400], [2000, 2400], [2000, 1800]],
};
const cubeAnnotations = dimensionAnnotations(room, cube);
const turnedAnnotations = dimensionAnnotations(room, turnedCube);
assert.deepEqual(cubeAnnotations.map((spec) => spec.text), ["宽 600", "深 600", "高 600"]);
assert.deepEqual(turnedAnnotations.map((spec) => spec.text), ["宽 600", "深 600", "高 600"]);
assert.deepEqual(cubeAnnotations.map((spec) => spec.anchor), [
  [2300, 1710, 308], [1910, 2100, 308], [2690, 2400, 600],
]);
assert.deepEqual(turnedAnnotations.map((spec) => spec.anchor), [
  [2690, 2100, 308], [2300, 1710, 308], [2000, 2490, 600],
]);

console.log("symmetric envelopes retain local axes and ordered footprint");

// The page accepts the canonical serialized layout, then converts it once.
const canonical = {
  id: "cabinet", placement: { origin_z_mm: 300 }, height: 1700,
  footprint: item.footprint.map(([x_mm, y_mm]) => ({ x_mm, y_mm })),
  clearances_mm: { ...item.clearances_mm },
};
const [canvasItem] = normalizeItems([canonical]);
assert.deepEqual(canvasItem.footprint, item.footprint);
assert.equal(canvasItem.z_start, 300);
assert.equal(canvasItem.z_end, 2000);
assert.deepEqual(dimensionAnnotations(room, canvasItem), annotations);
canvasItem.placement.origin_z_mm = 400;
canvasItem.footprint[0][0] = 700;
assert.equal(canonical.placement.origin_z_mm, 300);
assert.equal(canonical.footprint[0].x_mm, 600);
assert.equal(dimensionAnnotations(room, { ...item, z_start: 400, z_end: 2100 })[2].text, "高 1700");
console.log("canonical layout payload converted without mutating source");
