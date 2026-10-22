import * as THREE from "three";

// 将同一件家具的所有部件投成整体蒙版，只在整体外侧扩出粗轮廓。
// 墙和其他实体保留遮挡，半透明墙按实际透明度衰减蒙版。
export function createCartoonOutline(renderer) {
  const target = new THREE.WebGLRenderTarget(1, 1, { samples: 4 });
  const maskScene = new THREE.Scene();
  const colors = new Map();
  const blocker = new THREE.MeshBasicMaterial({
    color: 0, opacity: 0, side: THREE.DoubleSide, blending: THREE.NoBlending,
  });
  const fade = new THREE.ShaderMaterial({
    uniforms: { uOpacity: { value: 1 } },
    vertexShader: `
      #include <common>
      #include <logdepthbuf_pars_vertex>
      void main() {
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        #include <logdepthbuf_vertex>
      }
    `,
    fragmentShader: `
      #include <common>
      #include <logdepthbuf_pars_fragment>
      uniform float uOpacity;
      void main() {
        #include <logdepthbuf_fragment>
        gl_FragColor = vec4(0.0, 0.0, 0.0, uOpacity);
      }
    `,
    side: THREE.DoubleSide, transparent: true, depthWrite: false,
    blending: THREE.CustomBlending,
    blendSrc: THREE.ZeroFactor, blendDst: THREE.OneMinusSrcAlphaFactor,
    blendSrcAlpha: THREE.ZeroFactor, blendDstAlpha: THREE.OneMinusSrcAlphaFactor,
  });
  const material = new THREE.ShaderMaterial({
    uniforms: {
      uMask: { value: target.texture },
      uCssPixel: { value: new THREE.Vector2() },
    },
    vertexShader: `
      varying vec2 vUv;
      void main() {
        vUv = uv;
        gl_Position = vec4(position.xy, 0.0, 1.0);
      }
    `,
    fragmentShader: `
      uniform sampler2D uMask;
      uniform vec2 uCssPixel;
      varying vec2 vUv;
      void main() {
        float center = texture2D(uMask, vUv).a;
        if (center > 0.999) discard;
        vec4 nearest = vec4(0.0);
        for (int y = -3; y <= 3; y++) {
          for (int x = -3; x <= 3; x++) {
            float d = float(x * x + y * y);
            if (d > 9.0) continue;
            vec4 sampleMask = texture2D(uMask, vUv + vec2(float(x), float(y)) * uCssPixel);
            if (sampleMask.a > nearest.a) {
              nearest = sampleMask;
            }
          }
        }
        if (nearest.a < 0.01) discard;
        gl_FragColor = vec4(nearest.rgb / nearest.a, nearest.a * (1.0 - center));
        #include <colorspace_fragment>
      }
    `,
    transparent: true, depthTest: false, depthWrite: false,
    toneMapped: false,
  });
  const composite = new THREE.Scene();
  composite.add(new THREE.Mesh(new THREE.PlaneGeometry(2, 2), material));
  const screenCamera = new THREE.Camera();
  const size = new THREE.Vector2();
  const clearColor = new THREE.Color();

  return (roots, camera) => {
    const inks = new Set();
    for (const root of roots) root.traverse(node => {
      if (node.userData.ink) inks.add(node.userData.ink);
    });
    maskScene.clear();
    let hasOutline = false;
    for (const root of roots) root.traverseVisible(source => {
      if (!source.isMesh || inks.has(source)) return;
      const style = source.userData.cartoonInk;
      const opacity = source.material.opacity;
      if (opacity <= 0.002) return;
      let maskMaterial = blocker;
      if (style) {
        if (!colors.has(style.color)) colors.set(style.color, new THREE.MeshBasicMaterial({
          color: style.color, side: THREE.DoubleSide, toneMapped: false,
        }));
        maskMaterial = colors.get(style.color);
        hasOutline = true;
      } else if (opacity < 0.999) {
        maskMaterial = fade;
      }
      const mesh = new THREE.Mesh(source.geometry, maskMaterial);
      mesh.matrixAutoUpdate = false;
      mesh.matrix.copy(source.matrixWorld);
      mesh.layers.mask = source.layers.mask;
      if (maskMaterial === fade) mesh.onBeforeRender = () => {
        fade.uniforms.uOpacity.value = opacity;
        fade.uniformsNeedUpdate = true;
      };
      maskScene.add(mesh);
    });
    if (!hasOutline) return;
    renderer.getDrawingBufferSize(size);
    if (target.width !== size.x || target.height !== size.y) target.setSize(size.x, size.y);
    renderer.getSize(size);
    material.uniforms.uCssPixel.value.set(1 / size.x, 1 / size.y);
    const previousTarget = renderer.getRenderTarget();
    const previousClear = renderer.getClearColor(clearColor).clone();
    const previousAlpha = renderer.getClearAlpha();
    const previousAutoClear = renderer.autoClear;
    renderer.setRenderTarget(target);
    renderer.setClearColor(0, 0);
    renderer.autoClear = true;
    renderer.render(maskScene, camera);
    renderer.setRenderTarget(previousTarget);
    renderer.setClearColor(previousClear, previousAlpha);
    renderer.autoClear = false;
    renderer.render(composite, screenCamera);
    renderer.autoClear = previousAutoClear;
  };
}
