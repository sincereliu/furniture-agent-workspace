import * as THREE from "three";
import { roomToThree } from "./layout_frame.js";

/** Hidden walls retain only these unfilled, depth-tested door/window guides. */
export function createOpeningMarker(solid, opening) {
  const [x0, y0, z0, x1, y1, z1] = solid.box;
  const horizontal = solid.wall === "north" || solid.wall === "south";
  // Draw just inside the room, clear of the wall and the floor depth surfaces.
  const at = (along, z) => roomToThree(
    horizontal ? along : (solid.wall === "west" ? x1 + 2 : x0 - 2),
    horizontal ? (solid.wall === "north" ? y1 + 2 : y0 - 2) : along,
    Math.max(3, z),
  );
  const a = horizontal ? x0 : y0;
  const b = horizontal ? x1 : y1;
  const isWindow = solid.kind === "window";
  const color = isWindow ? 0x69a5bd : 0x9a7446;
  const group = new THREE.Group();
  const outline = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints([
      at(a, z0), at(a, z1), at(b, z1), at(b, z0), at(a, z0),
    ].map(point => new THREE.Vector3(...point))),
    new THREE.LineDashedMaterial({
      color, dashSize: 65, gapSize: 45,
      transparent: true, opacity: 0.72, depthTest: true, depthWrite: false,
    }),
  );
  outline.computeLineDistances();
  group.add(outline);
  if (!isWindow) {
    // WebGL line widths vary by platform; a narrow solid bar makes the sill legible.
    const threshold = new THREE.Mesh(
      new THREE.BoxGeometry(horizontal ? b - a : 12, 5, horizontal ? 12 : b - a),
      new THREE.MeshBasicMaterial({ color, transparent: true, depthTest: true, depthWrite: false }),
    );
    threshold.position.set(...at((a + b) / 2, z0 + 3));
    group.add(threshold);
  }
  for (const child of group.children) child.userData.openingMarker = group;
  const kind = isWindow ? "窗" : "门";
  group.userData = {
    color, highlightColor: isWindow ? 0x2586be : 0xbd7818,
    opacity: 0, hovered: false,
    text: `${kind} · ${opening.id} · 宽 ${Math.round(opening.width_mm)} × 高 ${Math.round(opening.height_mm)} mm`
      + (isWindow ? ` · 窗台高 ${Math.round(opening.sill_height_mm || 0)} mm` : ""),
  };
  group.visible = false;
  return group;
}

export function updateOpeningMarker(marker, opacity, hovered = marker.userData.hovered) {
  marker.userData.opacity = opacity;
  marker.userData.hovered = hovered;
  marker.visible = opacity > 0.002;
  for (const child of marker.children) {
    child.material.opacity = opacity * (hovered ? 1 : 0.72);
    child.material.color.setHex(hovered ? marker.userData.highlightColor : marker.userData.color);
  }
}

/** Pick only the visible guide strokes, respecting furniture and other scene surfaces. */
export function pickOpeningMarker(markers, raycaster, occluders) {
  const strokes = markers.filter(marker => marker.visible).flatMap(marker => marker.children);
  const hit = raycaster.intersectObjects(strokes, false)[0];
  if (!hit) return null;
  const blocker = raycaster.intersectObjects(occluders, false)[0];
  if (blocker && blocker.distance < hit.distance - 2) return null;
  return hit.object.userData.openingMarker;
}
