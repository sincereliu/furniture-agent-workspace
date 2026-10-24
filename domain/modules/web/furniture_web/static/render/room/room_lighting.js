import * as THREE from "three";
import { roomToThree } from "./layout_frame.js";
import { openingSolids, wallSolids, WALL_THICKNESS_MM } from "./wall_solid.js";

/** Indoor illumination is independent of the camera's architectural cutaway. */
export function createRoomLighting(scene, room, openings, wallShells) {
  const { width_mm: width, depth_mm: depth, height_mm: height } = room;
  const diagonal = Math.hypot(width, depth, height);
  const group = new THREE.Group();
  const blockers = new THREE.Group();
  group.add(blockers);
  scene.add(group);
  const lights = [];
  // r186 samples native shadow depth textures in projection depth. Main-camera logarithmic
  // depth must not be written into perspective spot shadow maps (it shadows the entire room).
  const depthMaterial = new THREE.MeshDepthMaterial();
  depthMaterial.customProgramCacheKey = () => "room-shadow-projection-depth";
  depthMaterial.onBeforeCompile = shader => {
    for (const chunk of ["logdepthbuf_pars_vertex", "logdepthbuf_vertex"]) {
      shader.vertexShader = shader.vertexShader.replace(`#include <${chunk}>`, "");
    }
    for (const chunk of ["logdepthbuf_pars_fragment", "logdepthbuf_fragment"]) {
      shader.fragmentShader = shader.fragmentShader.replace(`#include <${chunk}>`, "");
    }
  };
  // Only the shadow pass writes these surfaces. They are outside the outline and pick roots.
  const shadowMaterial = new THREE.MeshBasicMaterial({
    colorWrite: false, depthWrite: false, side: THREE.DoubleSide,
    shadowSide: THREE.DoubleSide,
  });
  const shadowMesh = (geometry, matrix) => {
    const mesh = new THREE.Mesh(geometry, shadowMaterial);
    if (matrix) mesh.applyMatrix4(matrix);
    mesh.layers.set(1);
    mesh.castShadow = true;
    mesh.customDepthMaterial = depthMaterial;
    mesh.raycast = () => {};
    blockers.add(mesh);
    return mesh;
  };
  const box = ([x0, y0, z0, x1, y1, z1]) => {
    const mesh = shadowMesh(new THREE.BoxGeometry(x1 - x0, z1 - z0, y1 - y0));
    mesh.position.set(...roomToThree((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2));
    return mesh;
  };
  for (const wall of wallSolids(width, depth, height, openings)) {
    for (const bounds of wall.boxes) box(bounds);
  }
  const thickness = WALL_THICKNESS_MM;
  const roof = box([-thickness, -thickness, height, width + thickness, depth + thickness, height + thickness]);
  // Retain doors, frames and mullions in shadows even when their visual wall fades out.
  for (const wall of wallShells) {
    wall.updateWorldMatrix(true, true);
    for (const opening of wall.userData.openings) opening.traverse(node => {
      if (node.isMesh && node.castShadow) shadowMesh(node.geometry.clone(), node.matrixWorld);
    });
  }
  const bounce = new THREE.AmbientLight(0xfff4e4, 0.4);
  bounce.layers.set(1);
  group.add(bounce);
  function spot(color, position, target, intensity, angle, penumbra, size) {
    // Geometry is in mm, hence inverse-square intensity also scales by mm squared.
    const light = new THREE.SpotLight(color, intensity, diagonal * 3, angle, penumbra, 2);
    light.position.set(...roomToThree(...position));
    light.target.position.set(...roomToThree(...target));
    light.layers.set(1);
    light.castShadow = true;
    light.shadow.mapSize.set(size, size);
    light.shadow.camera.near = Math.max(1, height * 0.003);
    light.shadow.bias = -0.00008;
    light.shadow.normalBias = 1.5;
    // Camera movement/fading must not change the physical lighting or repaint shadow maps.
    light.shadow.autoUpdate = false;
    light.shadow.needsUpdate = true;
    group.add(light, light.target);
    lights.push(light);
    return light;
  }
  const ceilingY = height - Math.min(65, height * 0.025);
  const ceiling = spot(0xffecd2, [width / 2, depth / 2, ceilingY], [width / 2, depth / 2, 0],
    ceilingY ** 2 * 1.1, Math.min(1.45, Math.atan2(Math.hypot(width, depth) * 0.75, ceilingY)), 0.55, 2048);
  ceiling.userData.source = "ceiling";
  for (const opening of openingSolids(width, depth, openings)) {
    if (opening.kind !== "window") continue;
    const [x0, y0, z0, x1, y1, z1] = opening.box;
    const horizontal = opening.wall === "north" || opening.wall === "south";
    const span = horizontal ? x1 - x0 : y1 - y0;
    const normal = horizontal
      ? [0, opening.wall === "north" ? 1 : -1]
      : [opening.wall === "west" ? 1 : -1, 0];
    const reach = Math.max(span, z1 - z0) * 0.8;
    const center = [(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2];
    const position = [center[0] - normal[0] * reach, center[1] - normal[1] * reach, center[2] + reach * 0.28];
    const light = spot(0xc1d7ff, position, center,
      (reach + Math.min(width, depth) * 0.4) ** 2 * 0.08,
      Math.atan2(Math.hypot(span, z1 - z0) * 0.62, reach), 0.28, 1024);
    light.userData.source = "window";
    light.userData.wall = opening.wall;
  }
  function invalidate(roots = []) {
    for (const root of roots) root.traverse(node => {
      if (node.isMesh && node.castShadow) node.customDepthMaterial = depthMaterial;
    });
    for (const light of lights) light.shadow.needsUpdate = true;
  }
  function dispose() {
    scene.remove(group);
    for (const light of lights) light.shadow.dispose();
    for (const mesh of blockers.children) mesh.geometry.dispose();
    shadowMaterial.dispose();
    depthMaterial.dispose();
    group.clear();
  }
  return { group, blockers, roof, lights, bounce, invalidate, dispose };
}
