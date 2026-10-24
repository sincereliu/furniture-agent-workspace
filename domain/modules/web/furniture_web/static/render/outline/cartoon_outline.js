import * as THREE from "three";
import { contactMaskMaterial, createWallContactUpdater } from "./wall_contact.js";
import { OUTLINE_STYLE, furnitureInkRadius } from "./outline_style.js";

const OUTLINE_RADIUS_PX = OUTLINE_STYLE.sampleRadiusPx;

// 将同一件家具的所有部件投成整体蒙版，只在整体外侧扩出粗轮廓。
// 墙和其他实体保留遮挡，半透明墙按实际透明度衰减蒙版。
export function createCartoonOutline(renderer) {
  const target = new THREE.WebGLRenderTarget(1, 1, { samples: 4 });
  // ID 不做颜色插值或多重采样，避免相邻家具混合出不存在的 ID。
  const idTarget = new THREE.WebGLRenderTarget(1, 1, {
    minFilter: THREE.NearestFilter, magFilter: THREE.NearestFilter,
  });
  const maskScene = new THREE.Scene();
  const idScene = new THREE.Scene();
  const proxies = new Map();
  const items = new Map();
  const updateContacts = createWallContactUpdater();
  let contacts = null;
  const prepare = (roots, camera) => {
    camera.updateMatrixWorld(true);
    contacts = updateContacts(roots, camera);
  };
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
      uIds: { value: idTarget.texture },
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
      uniform sampler2D uIds;
      uniform vec2 uCssPixel;
      varying vec2 vUv;
      void main() {
        vec4 center = texture2D(uMask, vUv);
        vec4 centerId = texture2D(uIds, vUv);
        bool inside = dot(centerId.rgb, centerId.rgb) > 0.0;
        vec4 neighbor = vec4(0.0);
        float coverage = 0.0;
        for (int y = -${OUTLINE_RADIUS_PX}; y <= ${OUTLINE_RADIUS_PX}; y++) {
          for (int x = -${OUTLINE_RADIUS_PX}; x <= ${OUTLINE_RADIUS_PX}; x++) {
            float d = float(x * x + y * y);
            if (d > ${OUTLINE_RADIUS_PX * OUTLINE_RADIUS_PX}.0) continue;
            if (d == 0.0) continue;
            vec2 sampleUv = vUv + vec2(float(x), float(y)) * uCssPixel;
            vec4 sampleId = texture2D(uIds, sampleUv);
            if (dot(sampleId.rgb, sampleId.rgb) == 0.0) continue;
            if (inside) {
              // 同件家具不描部件粗框；不同家具交界各画半宽，避免双倍粗线。
              if (distance(sampleId.rgb, centerId.rgb) < 0.5 / 255.0) continue;
            }
            // 整圈保留基础外框，仅在背光侧小幅加重，不把迎光侧削成内部细线。
            vec2 outward = -vec2(float(x), float(y)) / sqrt(d);
            float weight = float(${OUTLINE_STYLE.weightBase}) - float(${OUTLINE_STYLE.weightVariation}) * dot(outward, vec2(${OUTLINE_STYLE.lightDirection.join(", ")}));
            float radius = sampleId.a * ${OUTLINE_RADIUS_PX}.0 * weight;
            if (inside) radius *= 0.5;
            float edge = 1.0 - smoothstep(radius - float(${OUTLINE_STYLE.edgeSoftnessPx}), radius + float(${OUTLINE_STYLE.edgeSoftnessPx}), sqrt(d));
            vec4 sampleMask = texture2D(uMask, sampleUv);
            sampleMask *= edge;
            if (sampleMask.a > neighbor.a) {
              neighbor = sampleMask;
              coverage = edge;
            }
          }
        }
        if (neighbor.a < 0.01) discard;
        if (inside) {
          if (center.a < 0.01) discard;
          gl_FragColor = vec4(center.rgb / center.a, center.a * coverage);
        } else {
          gl_FragColor = vec4(neighbor.rgb / neighbor.a, neighbor.a * (1.0 - center.a));
        }
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

  const draw = (roots, camera) => {
    if (!contacts) throw new Error("Call prepare(roots, camera) before each outline draw");
    const preparedContacts = contacts;
    contacts = null;
    renderer.getSize(size);
    const inks = new Set();
    for (const root of roots) root.traverse(node => {
      if (node.userData.ink) inks.add(node.userData.ink);
    });
    const activeSources = new Set();
    const activeItems = new Map();
    const itemBounds = new Map();
    const partBounds = new THREE.Box3();
    for (const root of roots) root.traverseVisible(source => {
      if (!source.isMesh || inks.has(source) || source.material.visible === false) return;
      const style = source.userData.cartoonInk;
      const opacity = source.material.opacity;
      if (opacity <= 0.002) return;
      let maskMaterial = blocker;
      let idMaterial = blocker;
      if (style) {
        const itemId = source.userData.itemId;
        if (!itemBounds.has(itemId)) itemBounds.set(itemId, new THREE.Box3());
        if (!source.geometry.boundingBox) source.geometry.computeBoundingBox();
        partBounds.copy(source.geometry.boundingBox).applyMatrix4(source.matrixWorld);
        itemBounds.get(itemId).union(partBounds);
        if (!activeItems.has(itemId)) activeItems.set(itemId, activeItems.size + 1);
        if (!items.has(itemId)) items.set(itemId, {
          id: new THREE.MeshBasicMaterial({ side: THREE.DoubleSide, toneMapped: false, blending: THREE.NoBlending }),
        });
        const item = items.get(itemId);
        const index = activeItems.get(itemId);
        item.id.color.setRGB((index & 255) / 255, ((index >> 8) & 255) / 255, ((index >> 16) & 255) / 255);
        idMaterial = item.id;
      } else if (opacity < 0.999) {
        maskMaterial = fade;
      }
      activeSources.add(source);
      if (!proxies.has(source)) {
        const proxy = {
          mask: new THREE.Mesh(source.geometry, maskMaterial),
          id: new THREE.Mesh(source.geometry, idMaterial), opacity,
          inkMaterial: style ? contactMaskMaterial() : null,
        };
        proxy.mask.matrixAutoUpdate = proxy.id.matrixAutoUpdate = false;
        proxy.mask.onBeforeRender = () => {
          if (proxy.mask.material === fade) {
            fade.uniforms.uOpacity.value = proxy.opacity;
            fade.uniformsNeedUpdate = true;
          }
        };
        proxies.set(source, proxy);
        maskScene.add(proxy.mask);
        idScene.add(proxy.id);
      }
      const proxy = proxies.get(source);
      if (style) {
        if (!proxy.inkMaterial) proxy.inkMaterial = contactMaskMaterial();
        maskMaterial = proxy.inkMaterial;
        maskMaterial.color.setHex(style.color);
        const contact = preparedContacts.get(source);
        const uniforms = maskMaterial.userData.contactUniforms;
        uniforms.uContactBoxes.value = contact?.texture || null;
        uniforms.uContactCount.value = contact?.count || 0;
        uniforms.uContactRows.value = Math.max(1, contact?.count || 0);
        uniforms.uContactPixels.value = (OUTLINE_RADIUS_PX + 1) * renderer.getPixelRatio();
      }
      proxy.opacity = opacity;
      proxy.mask.material = maskMaterial;
      proxy.id.material = idMaterial;
      // 半透明墙只衰减颜色蒙版，不抹掉墙后家具的身份。
      proxy.id.visible = maskMaterial !== fade;
      for (const mesh of [proxy.mask, proxy.id]) {
        mesh.geometry = source.geometry;
        mesh.matrix.copy(source.matrixWorld);
        mesh.layers.mask = source.layers.mask;
        mesh.userData.itemId = style ? source.userData.itemId : null;
      }
    });
    for (const [itemId, bounds] of itemBounds) {
      // 身份蒙版的 RGB 保留 ID，alpha 携带同一件家具共享的线宽。
      items.get(itemId).id.opacity = furnitureInkRadius(bounds, camera, size.y) / OUTLINE_RADIUS_PX;
    }
    for (const [source, proxy] of proxies) if (!activeSources.has(source)) {
      maskScene.remove(proxy.mask);
      idScene.remove(proxy.id);
      proxies.delete(source); // 几何由原场景拥有，此处只移除借用它的代理。
      proxy.inkMaterial?.dispose();
    }
    for (const [itemId, item] of items) if (!activeItems.has(itemId)) {
      item.id.dispose();
      items.delete(itemId);
    }
    if (!activeItems.size) return;
    renderer.getDrawingBufferSize(size);
    if (target.width !== size.x || target.height !== size.y) target.setSize(size.x, size.y);
    if (idTarget.width !== size.x || idTarget.height !== size.y) idTarget.setSize(size.x, size.y);
    renderer.getSize(size);
    material.uniforms.uCssPixel.value.set(1 / size.x, 1 / size.y);
    const previousTarget = renderer.getRenderTarget();
    const previousClear = renderer.getClearColor(clearColor).clone();
    const previousAlpha = renderer.getClearAlpha();
    const previousAutoClear = renderer.autoClear;
    try {
      renderer.setClearColor(0, 0);
      renderer.autoClear = true;
      renderer.setRenderTarget(target);
      renderer.render(maskScene, camera);
      renderer.setRenderTarget(idTarget);
      renderer.render(idScene, camera);
      renderer.setRenderTarget(previousTarget);
      renderer.setClearColor(previousClear, previousAlpha);
      renderer.autoClear = false;
      renderer.render(composite, screenCamera);
    } finally {
      renderer.setRenderTarget(previousTarget);
      renderer.setClearColor(previousClear, previousAlpha);
      renderer.autoClear = previousAutoClear;
    }
  };
  return { prepare, draw };
}
