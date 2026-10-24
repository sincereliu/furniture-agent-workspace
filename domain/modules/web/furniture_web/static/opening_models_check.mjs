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
const { createOpeningModel, updateOpeningModel } = await import("./opening_models.js");
const { disposeObject } = await import("./layout_meshes.js");
for (const wall of ["north", "east", "south", "west"]) {
  for (const kind of ["door", "window"]) {
    for (const [width, height] of [[300, 400], [300, 2100], [900, 2100], [1800, 1400]]) {
      const source = { id: "opening", kind, wall, offset_mm: 300, width_mm: width, height_mm: height,
        sill_height_mm: kind === "window" ? 900 : 0 };
      const solid = openingSolids(3600, 3000, [source])[0];
      const model = createOpeningModel(solid, source);
      model.updateMatrixWorld(true);
      for (const mesh of model.children) {
        mesh.geometry.computeBoundingBox();
        const local = mesh.geometry.boundingBox.clone().applyMatrix4(mesh.matrix);
        assert.ok(local.min.x >= -0.01 && local.max.x <= width + 0.01, "details stay within the hole width");
        assert.ok(local.min.y >= -0.01 && local.max.y <= height + 0.01, "details preserve sill and head heights");
        assert.ok([...mesh.geometry.attributes.position.array].every(Number.isFinite));
        assert.equal(mesh.layers.mask, 2);
      }
      const world = new THREE.Box3().setFromObject(model);
      const horizontal = wall === "north" || wall === "south";
      assert.ok(Math.abs((horizontal ? world.min.x : world.min.z) - solid.box[horizontal ? 0 : 1] - 1) < 0.01);
      assert.ok(Math.abs((horizontal ? world.max.x : world.max.z) - solid.box[horizontal ? 3 : 4] + 1) < 0.01);
      assert.ok(Math.abs(world.min.y - source.sill_height_mm - 1) < 0.01);
      assert.ok(Math.abs(world.max.y - source.sill_height_mm - height + 1) < 0.01);
      const glass = model.children.filter(mesh => mesh.userData.openingRole === "glass");
      assert.equal(glass.length, kind === "window" ? 2 : 0);
      for (const pane of glass) {
        assert.equal(pane.material.depthWrite, false);
        assert.equal(pane.castShadow, false);
        // A ray through a clear part of each pane must not meet a filled backing frame.
        const origin = model.localToWorld(pane.position.clone().add(new THREE.Vector3(0, 0, 500)));
        const direction = new THREE.Vector3(0, 0, -1).transformDirection(model.matrixWorld);
        const ray = new THREE.Raycaster(origin, direction);
        assert.equal(ray.intersectObjects(model.children, false).filter(h => !["glass", "glint"].includes(h.object.userData.openingRole)).length, 0);
      }
      for (const opacity of [0.5, 0, 1, 0.3, 1]) {
        updateOpeningModel(model, opacity);
        for (const surface of model.userData.surfaces) {
          assert.equal(surface.material.opacity, surface.opacity * opacity);
          assert.equal(surface.material.depthWrite, surface.depthWrite && opacity >= 0.999);
        }
        assert.equal(model.userData.marker.visible, opacity < 0.998);
      }
      let disposed = 0;
      for (const mesh of model.children) mesh.geometry.addEventListener("dispose", () => disposed++);
      const surfaceCount = model.userData.surfaces.length;
      let disposedMaterials = 0;
      for (const surface of model.userData.surfaces) surface.material.addEventListener("dispose", () => disposedMaterials++);
      disposeObject(model);
      disposeObject(model.userData.marker);
      assert.equal(disposed, model.children.length);
      assert.equal(disposedMaterials, surfaceCount);
    }
  }
}
console.log("Opening models: four wall mounts, dimensions, transparent glazing, fades, depth and disposal pass.");
