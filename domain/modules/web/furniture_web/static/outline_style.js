import * as THREE from "three";
import { INK } from "./layout_diorama.js";

// 已确认的显示参数。贴墙/遮挡模块只决定可见性，不拥有这些风格参数。
export const OUTLINE_STYLE = Object.freeze({
  sampleRadiusPx: 3,
  minRadiusPx: 0.85,
  maxRadiusPx: 2.4,
  radiusOffsetPx: 0.8,
  radiusPerProjectedPixel: 0.006,
  weightBase: 1.12,
  weightVariation: 0.12,
  lightDirection: Object.freeze([-0.6, 0.8]),
  edgeSoftnessPx: 0.5,
  seamOpacity: 0.45,
  edgeAngleDeg: 25,
});

export function furnitureInkColor(selected, blocked) {
  return blocked ? 0xd93838 : selected ? 0xf59e0b : INK;
}

export function furnitureInkRadius(bounds, camera, cssHeight) {
  const center = bounds.getCenter(new THREE.Vector3()).applyMatrix4(camera.matrixWorldInverse);
  const diameter = bounds.getSize(new THREE.Vector3()).length();
  const depth = camera.isPerspectiveCamera ? Math.max(camera.near, -center.z) : 1;
  const pixels = diameter * Math.abs(camera.projectionMatrix.elements[5]) * cssHeight / (2 * depth);
  return THREE.MathUtils.clamp(
    OUTLINE_STYLE.radiusOffsetPx + pixels * OUTLINE_STYLE.radiusPerProjectedPixel,
    OUTLINE_STYLE.minRadiusPx, OUTLINE_STYLE.maxRadiusPx,
  );
}
