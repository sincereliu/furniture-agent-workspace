import * as THREE from "./three.module.js";
import { cameraThreePosition, roomToThree } from "./layout_frame.js";

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
