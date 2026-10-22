import assert from "node:assert/strict";
import { registerHooks } from "node:module";
import * as THREE from "../../../../../vendor/three/0.186.0/three.module.js";
import { openingSolids } from "./wall_solid.js";

registerHooks({
  resolve(specifier, context, next) {
    return next(specifier === "three"
      ? new URL("../../../../../vendor/three/0.186.0/three.module.js", import.meta.url).href
      : specifier, context);
  },
});
const { createOpeningMarker, updateOpeningMarker, pickOpeningMarker } = await import("./opening_markers.js");

for (const wall of ["north", "east", "south", "west"]) {
  for (const kind of ["door", "window"]) {
    const opening = {
      id: `${wall}_${kind}`, wall, kind, offset_mm: 300, width_mm: 800,
      height_mm: kind === "door" ? 2100 : 1000, sill_height_mm: kind === "door" ? 0 : 900,
    };
    const solid = openingSolids(3600, 3000, [opening])[0];
    const marker = createOpeningMarker(solid, opening);
    assert.equal(marker.visible, false);
    const positions = marker.children[0].geometry.getAttribute("position");
    assert.equal(positions.count, 5);
    const points = Array.from({ length: positions.count }, (_, index) => new THREE.Vector3().fromBufferAttribute(positions, index));
    const bounds = new THREE.Box3().setFromPoints(points);
    assert.equal(bounds.min.y, Math.max(3, opening.sill_height_mm));
    assert.equal(bounds.max.y, opening.sill_height_mm + opening.height_mm);
    const horizontal = wall === "north" || wall === "south";
    assert.equal(horizontal ? bounds.max.x - bounds.min.x : bounds.max.z - bounds.min.z, 800);
    const along = horizontal ? 0 : 1;
    assert.equal(horizontal ? bounds.min.x : bounds.min.z, solid.box[along]);
    assert.equal(marker.children.length, kind === "door" ? 2 : 1);
    assert.ok(marker.children[0].geometry.getAttribute("lineDistance"));
    updateOpeningMarker(marker, 1);
    for (const child of marker.children) {
      assert.equal(child.material.depthTest, true);
      assert.equal(child.material.depthWrite, false);
      assert.equal(child.castShadow, false);
      assert.equal(child.material.opacity, 0.72);
    }
    updateOpeningMarker(marker, 0.5, true);
    assert.equal(marker.children[0].material.opacity, 0.5);
    assert.equal(marker.children[0].material.color.getHex(), marker.userData.highlightColor);
    updateOpeningMarker(marker, 0, false);
    assert.equal(marker.visible, false);
    assert.equal(marker.children[0].material.color.getHex(), marker.userData.color);
  }
}

const source = { id: "entry", wall: "north", kind: "door", offset_mm: 300, width_mm: 800, height_mm: 2100 };
const marker = createOpeningMarker(openingSolids(3600, 3000, [source])[0], source);
updateOpeningMarker(marker, 1);
marker.updateMatrixWorld(true);
const raycaster = new THREE.Raycaster(new THREE.Vector3(300, 1000, 2000), new THREE.Vector3(0, 0, -1));
raycaster.params.Line.threshold = 10;
assert.equal(pickOpeningMarker([marker], raycaster, []), marker);
const blocker = new THREE.Mesh(new THREE.BoxGeometry(100, 100, 100), new THREE.MeshBasicMaterial());
blocker.position.set(300, 1000, 1000);
blocker.updateMatrixWorld(true);
assert.equal(pickOpeningMarker([marker], raycaster, [blocker]), null, "furniture must block hovering behind it");
blocker.position.z = -1000;
blocker.updateMatrixWorld(true);
assert.equal(pickOpeningMarker([marker], raycaster, [blocker]), marker, "furniture behind the guide must not block it");
updateOpeningMarker(marker, 0);
assert.equal(pickOpeningMarker([marker], raycaster, []), null);
console.log("Door/window outlines keep wall coordinates and sill heights; fades, hover and occlusion pass.");
