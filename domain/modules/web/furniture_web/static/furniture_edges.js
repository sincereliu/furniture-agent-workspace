import * as THREE from "three";
import { OUTLINE_STYLE } from "./outline_style.js";

export function furnitureEdges(geometry) {
  if (!geometry.userData.seamPositions) return new THREE.EdgesGeometry(geometry, OUTLINE_STYLE.edgeAngleDeg);
  const edges = new THREE.BufferGeometry();
  edges.setAttribute("position", new THREE.Float32BufferAttribute(geometry.userData.seamPositions, 3));
  return edges;
}
