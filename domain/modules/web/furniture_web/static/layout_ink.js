import * as THREE from "three";
import { INK } from "./layout_diorama.js";
import { footprintCenter, prismGeometry, wallGeometry } from "./layout_meshes.js";
import { inkViewBiasGlsl } from "./ink_depth.js";
import { OUTLINE_STYLE } from "./outline_style.js";
import { furnitureEdges } from "./furniture_edges.js";

// 内部细线与场景平面线共用深度偏移；家具整体外框由 cartoon_outline 绘制。
function addEdges(mesh, color, opacity) {
  const ink = new THREE.LineSegments(
    furnitureEdges(mesh.geometry), inkMaterial(color),
  );
  ink.material.opacity = opacity;
  ink.raycast = () => {};
  ink.layers.mask = mesh.layers.mask;
  mesh.add(ink);
  mesh.userData.ink = ink;
  return ink;
}

// 家具入口不接受毫米厚度；注册整件身份和颜色，只创建内部细线。
export function addFurnitureInk(mesh, { itemId, color }) {
  mesh.userData.itemId = itemId;
  mesh.userData.cartoonInk = { color };
  return addEdges(mesh, color, OUTLINE_STYLE.seamOpacity);
}

function inkMaterial(color) {
  const material = new THREE.LineBasicMaterial({
    color,
    transparent: true,
  });
  material.customProgramCacheKey = () => "ink-view-bias";
  material.onBeforeCompile = (shader) => {
    shader.vertexShader = shader.vertexShader.replace(
      "#include <project_vertex>",
      inkViewBiasGlsl(),
    );
  };
  return material;
}

function createOutlineMaterial(thickness = 14, color = INK, opacity = 1.0) {
  const mat = new THREE.ShaderMaterial({
    uniforms: {
      uThickness: { value: thickness },
      uColor: { value: new THREE.Color(color) },
      opacity: { value: opacity },
    },
    vertexShader: `
      #include <common>
      #include <logdepthbuf_pars_vertex>
      uniform float uThickness;
      void main() {
        vec4 mv = modelViewMatrix * vec4(position, 1.0);
        vec3 n = normalize(normalMatrix * normal);
        mv.xyz += n * uThickness;
        gl_Position = projectionMatrix * mv;
        #include <logdepthbuf_vertex>
      }
    `,
    fragmentShader: `
      #include <common>
      #include <logdepthbuf_pars_fragment>
      uniform vec3 uColor;
      uniform float opacity;
      void main() {
        #include <logdepthbuf_fragment>
        gl_FragColor = vec4(uColor, opacity);
      }
    `,
    side: THREE.BackSide,
    transparent: opacity < 0.999,
    depthWrite: opacity >= 0.999,
  });
  Object.defineProperty(mat, "opacity", {
    get() {
      return this.uniforms.opacity.value;
    },
    set(v) {
      this.uniforms.opacity.value = v;
      this.transparent = v < 0.999;
    },
  });
  return mat;
}

function outlineMaterial(color = INK, opacity = 1.0) {
  let currentOpacity = opacity;
  const mat = new THREE.MeshBasicMaterial({
    color: new THREE.Color(color),
    side: THREE.BackSide,
    transparent: opacity < 0.999,
    opacity,
    depthWrite: opacity >= 0.999,
  });
  Object.defineProperty(mat, "opacity", {
    get() {
      return currentOpacity;
    },
    set(v) {
      const wasTrans = this.transparent;
      currentOpacity = v;
      const nowTrans = v < 0.999;
      if (wasTrans !== nowTrans) {
        this.transparent = nowTrans;
        this.depthWrite = !nowTrans;
        this.needsUpdate = true;
      }
    },
  });
  return mat;
}

function expandFootprint(footprint, t) {
  if (!footprint || footprint.length < 3) return footprint;
  const getXY = (p) => (Array.isArray(p) ? [p[0], p[1]] : [p.x_mm ?? p.x, p.y_mm ?? p.y]);
  const pts = footprint.map(getXY);
  if (pts.length === 4) {
    const p0 = pts[0], p1 = pts[1], p2 = pts[2], p3 = pts[3];
    const ux = p1[0] - p0[0], uy = p1[1] - p0[1];
    const vx = p3[0] - p0[0], vy = p3[1] - p0[1];
    const ul = Math.hypot(ux, uy) || 1;
    const vl = Math.hypot(vx, vy) || 1;
    const u = [ux / ul, uy / ul];
    const v = [vx / vl, vy / vl];
    return [
      [p0[0] - (u[0] + v[0]) * t, p0[1] - (u[1] + v[1]) * t],
      [p1[0] + (u[0] - v[0]) * t, p1[1] + (u[1] - v[1]) * t],
      [p2[0] + (u[0] + v[0]) * t, p2[1] + (u[1] + v[1]) * t],
      [p3[0] - (u[0] - v[0]) * t, p3[1] - (u[1] - v[1]) * t],
    ];
  }
  const center = footprintCenter(pts);
  return pts.map(([x, y]) => {
    const dx = x - center[0];
    const dy = y - center[1];
    const dist = Math.hypot(dx, dy) || 1;
    return [x + (dx / dist) * t, y + (dy / dist) * t];
  });
}

export function addStageInk(mesh, color = INK, thickness = 14) {
  if (mesh.geometry?.type === "PlaneGeometry") return addEdges(mesh, color, 1);

  const scaleFactor = thickness / 14;
  let outlineGeo = null;
  if (mesh.geometry && mesh.geometry.userData.wallBoxes) {
    mesh.geometry.computeBoundingBox();
    const size = mesh.geometry.boundingBox.getSize(new THREE.Vector3());
    const minDim = Math.min(size.x, size.y, size.z);
    const t = Math.min(thickness, Math.max(1.8 * scaleFactor, minDim * 0.11 * scaleFactor));
    outlineGeo = wallGeometry(mesh.geometry.userData.wallBoxes, t);
  } else if (mesh.geometry && mesh.geometry.type === "BoxGeometry" && mesh.geometry.parameters) {
    const { width, height, depth } = mesh.geometry.parameters;
    const minDim = Math.min(width, height, depth);
    const t = Math.min(thickness, Math.max(1.8 * scaleFactor, minDim * 0.11 * scaleFactor));
    outlineGeo = new THREE.BoxGeometry(width + 2 * t, height + 2 * t, depth + 2 * t);
  } else if (mesh.geometry && mesh.geometry.userData && mesh.geometry.userData.footprint) {
    const { footprint, z0, z1 } = mesh.geometry.userData;
    let minDim = Math.abs(z1 - z0);
    for (let i = 0; i < footprint.length; i += 1) {
      const next = (i + 1) % footprint.length;
      const edge = Math.hypot(footprint[next][0] - footprint[i][0], footprint[next][1] - footprint[i][1]);
      if (edge > 10) minDim = Math.min(minDim, edge);
    }
    const t = Math.min(thickness, Math.max(2 * scaleFactor, minDim * 0.11 * scaleFactor));
    outlineGeo = prismGeometry(expandFootprint(footprint, t), z0 - t, z1 + t);
  }

  const outline = new THREE.Mesh(
    outlineGeo || mesh.geometry,
    outlineGeo ? outlineMaterial(color) : createOutlineMaterial(thickness, color),
  );
  outline.castShadow = false;
  outline.receiveShadow = false;
  outline.raycast = () => {};
  if (mesh.layers) outline.layers.mask = mesh.layers.mask;
  mesh.add(outline);
  mesh.userData.ink = outline;
  return outline;
}

