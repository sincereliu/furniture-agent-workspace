// 家具贴墙时，边线和墙的内表面在同一深度上。
// 这个 Three.js 只对填充面打开 POLYGON_OFFSET_FILL，线的 polygonOffset 不改变线的深度，
// 不透明墙会稳定地盖住贴墙的边。
// 线沿视线拉近 INK_VIEW_BIAS_MM。预览同时开对数深度：普通深度在正视图的距离上
// 分不出 1 毫米，对数深度下这一毫米在近处和立面远处都排在墙前，并排在更近的面后。

export const INK_VIEW_BIAS_MM = 1;

/** 视图空间点向相机移近。Three.js 相机朝 -Z，所以 Z 增大。 */
export function biasInkView(eyeX, eyeY, eyeZ) {
  return [eyeX, eyeY, eyeZ + INK_VIEW_BIAS_MM];
}

/**
 * 插在 project_vertex 之后、logdepthbuf_vertex 之前。
 * 先改 mvPosition 再重算 gl_Position，对数深度读到的 w 才是拉近后的视距。
 */
export function inkViewBiasGlsl() {
  return [
    "#include <project_vertex>",
    `mvPosition.z += ${INK_VIEW_BIAS_MM.toFixed(1)};`,
    "gl_Position = projectionMatrix * mvPosition;",
  ].join("\n\t");
}

/** 与 three.js logarithmicDepthBuffer 的片元公式一致。clipW 是透视裁剪坐标的 w。 */
export function logWindowDepth(clipW, far) {
  const logDepthBufFC = 2.0 / (Math.log(far + 1.0) / Math.LN2);
  return Math.log2(1.0 + clipW) * logDepthBufFC * 0.5;
}
