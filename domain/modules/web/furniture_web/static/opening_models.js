import * as THREE from "three";
import { celMaterial } from "./layout_diorama.js";
import { createOpeningMarker, updateOpeningMarker } from "./opening_markers.js";
import { roomToThree } from "./layout_frame.js";

/** Architectural display details only; opening dimensions remain owned by layout. */
export function createOpeningModel(solid, opening) {
  const [x0, y0, z0, x1, y1, z1] = solid.box;
  const horizontal = solid.wall === "north" || solid.wall === "south";
  const span = horizontal ? x1 - x0 : y1 - y0;
  // Leave a millimetre of clearance against the cut wall/floor surfaces.
  const clearance = Math.min(1, span / 100, (z1 - z0) / 100);
  const width = span - clearance * 2;
  const height = z1 - z0 - clearance * 2;
  const depth = horizontal ? y1 - y0 : x1 - x0;
  const group = new THREE.Group();
  // Local x runs across the opening, y up, z toward the room on every wall.
  const inward = new THREE.Vector3(
    horizontal ? 0 : (solid.wall === "west" ? 1 : -1), 0,
    horizontal ? (solid.wall === "north" ? 1 : -1) : 0,
  );
  const up = new THREE.Vector3(0, 1, 0);
  const across = up.clone().cross(inward);
  group.setRotationFromMatrix(new THREE.Matrix4().makeBasis(across, up, inward));
  group.position.set(...roomToThree(
    solid.wall === "south" || solid.wall === "west" ? x1 : x0,
    solid.wall === "north" || solid.wall === "west" ? y1 : y0,
    z0,
  ));
  group.position.addScaledVector(across, clearance).addScaledVector(up, clearance);
  const isWindow = solid.kind === "window";
  const frame = Math.min(isWindow ? 52 : 66, width * 0.12, height * 0.08);
  const materials = {
    frame: celMaterial(isWindow ? 0xe7e5dc : 0xb39876, { transparent: true }),
    trim: celMaterial(isWindow ? 0xf5f1e8 : 0xd6bd9b, { transparent: true }),
    leaf: celMaterial(0xc7aa85, { transparent: true }),
    panel: celMaterial(0xb99b77, { transparent: true }),
    seal: celMaterial(0x646d69, { transparent: true }),
    metal: new THREE.MeshStandardMaterial({ color: 0x737a78, metalness: 0.65, roughness: 0.3, transparent: true }),
    glass: new THREE.MeshPhongMaterial({
      color: 0x7d98ba, specular: 0xdbe9ff, shininess: 100,
      transparent: true, opacity: 0.22, depthWrite: false, side: THREE.DoubleSide,
    }),
    glint: new THREE.MeshBasicMaterial({ color: 0xe0ecff, transparent: true, opacity: 0.12, depthWrite: false, side: THREE.DoubleSide }),
  };
  const add = (role, a, b, c, w, h, d, bevel = 0) => {
    const r = Math.min(bevel, w / 5, h / 5, d / 5);
    let geometry;
    if (r > 0) {
      const shape = new THREE.Shape();
      shape.moveTo(-w / 2 + r, -h / 2 + r);
      shape.lineTo(w / 2 - r, -h / 2 + r);
      shape.lineTo(w / 2 - r, h / 2 - r);
      shape.lineTo(-w / 2 + r, h / 2 - r);
      shape.closePath();
      geometry = new THREE.ExtrudeGeometry(shape, {
        depth: d - 2 * r, bevelEnabled: true, bevelSize: r,
        bevelThickness: r, bevelSegments: 1, steps: 1, curveSegments: 1,
      });
      geometry.translate(0, 0, -d / 2 + r);
    } else geometry = new THREE.BoxGeometry(w, h, d);
    const mesh = new THREE.Mesh(geometry, materials[role]);
    mesh.position.set(a, b, c);
    mesh.layers.set(1);
    mesh.userData.openingRole = role;
    mesh.castShadow = role !== "glass" && role !== "glint";
    mesh.receiveShadow = mesh.castShadow;
    group.add(mesh);
    return mesh;
  };
  const bar = (role, a, b, w, h, c, d) => add(role, a, b, c, w, h, d, Math.min(3, frame * 0.08));
  // The jamb has real reveal depth; the face trim sits inside the existing hole.
  bar("frame", frame / 2, height / 2, frame, height, -depth / 2, depth);
  bar("frame", width - frame / 2, height / 2, frame, height, -depth / 2, depth);
  bar("frame", width / 2, height - frame / 2, width - 2 * frame, frame, -depth / 2, depth);
  if (isWindow) bar("frame", width / 2, frame / 2, width - 2 * frame, frame, -depth / 2, depth);
  for (const face of [3, -depth - 3]) {
    bar("trim", frame * 0.38, height / 2, frame * 0.76, height, face, 12);
    bar("trim", width - frame * 0.38, height / 2, frame * 0.76, height, face, 12);
    bar("trim", width / 2, height - frame * 0.38, width - frame * 1.52, frame * 0.76, face, 12);
  }
  if (isWindow) {
    const sash = frame * 0.52;
    const paneWidth = (width - 2 * frame) / 2;
    const paneHeight = height - 2 * frame;
    const gasket = Math.min(2.5, frame * 0.08);
    const at = -depth * 0.48;
    for (let i = 0; i < 2; i += 1) {
      const center = frame + paneWidth * (i + 0.5);
      // Open rails around actual transparent glazing, with a narrow dark gasket.
      for (const [x, y, w, h] of [
        [center - paneWidth / 2 + sash / 2, height / 2, sash, paneHeight],
        [center + paneWidth / 2 - sash / 2, height / 2, sash, paneHeight],
        [center, frame + sash / 2, paneWidth - 2 * sash, sash],
        [center, height - frame - sash / 2, paneWidth - 2 * sash, sash],
      ]) {
        bar("seal", x, y, w + gasket * 2, h + gasket * 2, at - 2, 28);
        bar("trim", x, y, w, h, at + 2, 32);
      }
      const gw = paneWidth - 2 * sash - gasket * 2, gh = paneHeight - 2 * sash - gasket * 2;
      add("glass", center, height / 2, at, gw, gh, 5);
      // Restrained reflection bands; no painted opaque blue pane.
      const reflection = add("glint", center - gw * 0.2, height / 2, at + 3, gw * 0.13, gh * 0.78, 0.5);
      reflection.rotation.z = -Math.min(0.15, gw * 0.25 / gh);
      bar("metal", center + (i === 0 ? 1 : -1) * (paneWidth / 2 - sash / 2), height * 0.49, sash * 0.42, frame * 1.55, at + 28, 12);
    }
    bar("trim", width / 2, frame * 0.24, width, frame * 0.48, -depth / 2 + 22, depth + 52);
  } else {
    const gap = Math.min(4, frame * 0.08);
    const bottom = Math.min(10, height * 0.015);
    const w = width - 2 * frame - 2 * gap;
    const h = height - frame - bottom - gap;
    const centerY = bottom + h / 2;
    const at = -depth * 0.48;
    const leafDepth = Math.min(42, depth * 0.48);
    bar("leaf", width / 2, centerY, w, h, at, leafDepth);
    for (const direction of [1, -1]) {
      const face = at + direction * (leafDepth / 2 + 1);
      // Shallow moulded panels give volume without dense decorative outlines.
      for (const [fraction, size] of [[0.72, 0.34], [0.28, 0.29]]) {
        const panelY = bottom + h * fraction;
        bar("panel", width / 2, panelY, w * 0.74, h * size, face, 3);
        const border = Math.min(12, frame * 0.24);
        for (const [x, y, pw, ph] of [
          [width / 2 - w * 0.37, panelY, border, h * size],
          [width / 2 + w * 0.37, panelY, border, h * size],
          [width / 2, panelY - h * size / 2, w * 0.74, border],
          [width / 2, panelY + h * size / 2, w * 0.74, border],
        ]) bar("leaf", x, y, pw, ph, face + direction * 3, 6);
      }
      const handleX = width / 2 + w * 0.37;
      const handleY = bottom + h * 0.48;
      bar("metal", handleX, handleY, frame * 0.58, frame * 1.6, face + direction * 4, 6);
      bar("metal", handleX, handleY + frame * 0.27, frame * 0.24, frame * 0.24, face + direction * 15, 22);
      bar("metal", handleX - frame * 0.52, handleY + frame * 0.27, frame * 1.25, frame * 0.22, face + direction * 26, 12);
      bar("metal", handleX, handleY - frame * 0.38, frame * 0.12, frame * 0.22, face + direction * 8, 3);
    }
    for (const fraction of [0.18, 0.5, 0.82]) {
      bar("metal", frame + gap, bottom + h * fraction, frame * 0.22, frame * 1.35, at + leafDepth / 2, 14);
    }
  }
  // Each material is shared only inside this opening, so fade it once per frame.
  const used = new Set(group.children.map(mesh => mesh.material));
  for (const material of Object.values(materials)) if (!used.has(material)) material.dispose();
  group.userData.surfaces = [...used].map(material => ({ material, opacity: material.opacity, depthWrite: material.depthWrite }));
  group.userData.marker = createOpeningMarker(solid, opening);
  return group;
}

export function updateOpeningModel(model, opacity) {
  for (const surface of model.userData.surfaces) {
    surface.material.opacity = surface.opacity * opacity;
    surface.material.depthWrite = surface.depthWrite && opacity >= 0.999;
  }
  updateOpeningMarker(model.userData.marker, 1 - opacity);
}
