import * as THREE from "three";
import { roomToThree } from "./layout_frame.js";
import { furnitureEdges } from "./furniture_edges.js";

const CONTACT_MM = 0.5;

// 线段与真实墙块的交集；门窗已经从 wallBoxes 中扣除。
function interval(a, b, box) {
  let lo = 0, hi = 1;
  for (const axis of ["x", "y", "z"]) {
    const delta = b[axis] - a[axis];
    const min = box.min[axis] - CONTACT_MM, max = box.max[axis] + CONTACT_MM;
    if (Math.abs(delta) < 1e-9) {
      if (a[axis] < min || a[axis] > max) return null;
    } else {
      const t0 = (min - a[axis]) / delta, t1 = (max - a[axis]) / delta;
      lo = Math.max(lo, Math.min(t0, t1));
      hi = Math.min(hi, Math.max(t0, t1));
      if (hi <= lo) return null;
    }
  }
  return [lo, hi];
}

export function createWallContactUpdater() {
  const states = new Map();
  return (roots, camera) => {
    const boxes = [], sources = [];
    for (const root of roots) {
      root.updateWorldMatrix(true, true);
      root.traverseVisible(mesh => {
        if (!mesh.isMesh || !camera.layers.test(mesh.layers)) return;
        if (mesh.userData.cartoonInk) sources.push(mesh);
        if (mesh.material.opacity <= 0.002 || mesh.material.visible === false) return;
        for (const box of mesh.geometry.userData.wallBoxes || []) {
          boxes.push(new THREE.Box3().setFromPoints([
            new THREE.Vector3(...roomToThree(...box.slice(0, 3))),
            new THREE.Vector3(...roomToThree(...box.slice(3))),
          ]).applyMatrix4(mesh.matrixWorld));
        }
      });
    }
    const wallKey = boxes.map(box => [...box.min, ...box.max].join(",")).join(";");
    const active = new Set(sources);
    for (const [source, state] of states) if (!active.has(source)) {
      state.texture.dispose();
      // 不持有已移除家具；线几何仍由原场景释放。
      states.delete(source);
    }
    for (const source of sources) {
      const ink = source.userData.ink;
      let state = states.get(source);
      if (!state || state.geometry !== source.geometry || state.ink !== ink) {
        state?.texture.dispose();
        const edges = furnitureEdges(source.geometry);
        state = {
          geometry: source.geometry, ink,
          positions: edges.getAttribute("position").clone(),
          texture: new THREE.DataTexture(new Float32Array(8), 2, 1, THREE.RGBAFormat, THREE.FloatType),
        };
        edges.dispose();
        states.set(source, state);
      }
      const key = `${wallKey}|${source.matrixWorld.elements.join(",")}`;
      if (state.key === key) continue;
      state.key = key;
      const positions = state.positions;
      const kept = [], contacts = new Set();
      const a = new THREE.Vector3(), b = new THREE.Vector3();
      const localA = new THREE.Vector3(), localB = new THREE.Vector3();
      for (let i = 0; i < positions.count; i += 2) {
        localA.fromBufferAttribute(positions, i); localB.fromBufferAttribute(positions, i + 1);
        a.copy(localA).applyMatrix4(source.matrixWorld); b.copy(localB).applyMatrix4(source.matrixWorld);
        const cuts = [];
        for (const box of boxes) {
          const cut = interval(a, b, box);
          if (cut) { cuts.push(cut); contacts.add(box); }
        }
        cuts.sort((left, right) => left[0] - right[0]);
        const push = (lo, hi) => {
          if (hi <= lo) return;
          kept.push(...localA.clone().lerp(localB, lo), ...localA.clone().lerp(localB, hi));
        };
        let start = 0;
        for (const [lo, hi] of cuts) { push(start, lo); start = Math.max(start, hi); }
        push(start, 1);
      }
      // 光滑软包可能面接触墙而包边不接触；蒙版仍按真实曲面三角形判断。
      if (source.geometry.userData.seamPositions) {
        const surface = source.geometry.getAttribute("position"), index = source.geometry.index;
        const bounds = new THREE.Box3().setFromBufferAttribute(surface).applyMatrix4(source.matrixWorld);
        const triangle = new THREE.Triangle();
        for (const box of boxes) {
          if (contacts.has(box) || !bounds.intersectsBox(box.clone().expandByScalar(CONTACT_MM))) continue;
          const expanded = box.clone().expandByScalar(CONTACT_MM);
          for (let i = 0; i < index.count; i += 3) {
            [triangle.a, triangle.b, triangle.c].forEach((point, offset) => {
              point.fromBufferAttribute(surface, index.getX(i + offset)).applyMatrix4(source.matrixWorld);
            });
            if (expanded.intersectsTriangle(triangle)) { contacts.add(box); break; }
          }
        }
      }
      if (ink?.isLineSegments) {
        const current = ink.geometry.getAttribute("position");
        if (current.array.length === kept.length) {
          current.array.set(kept);
          current.needsUpdate = true;
        } else {
          const previous = ink.geometry;
          ink.geometry = new THREE.BufferGeometry();
          ink.geometry.setAttribute("position", new THREE.Float32BufferAttribute(kept, 3));
          previous.dispose();
        }
        ink.geometry.computeBoundingBox();
        ink.geometry.computeBoundingSphere();
      }
      state.texture.dispose();
      const data = new Float32Array(Math.max(1, contacts.size) * 8);
      [...contacts].forEach((box, i) => data.set([...box.min, 0, ...box.max, 0], i * 8));
      state.texture = new THREE.DataTexture(data, 2, Math.max(1, contacts.size), THREE.RGBAFormat, THREE.FloatType);
      state.texture.needsUpdate = true;
      state.count = contacts.size;
    }
    return states;
  };
}

// 只裁颜色蒙版，家具身份保持完整，避免接触区域被当成新的内部外框。
export function contactMaskMaterial() {
  const material = new THREE.MeshBasicMaterial({ side: THREE.DoubleSide, toneMapped: false });
  const uniforms = {
    uContactBoxes: { value: null }, uContactCount: { value: 0 },
    uContactRows: { value: 1 }, uContactPixels: { value: 1 },
  };
  material.userData.contactUniforms = uniforms;
  material.onBeforeCompile = shader => {
    Object.assign(shader.uniforms, uniforms);
    shader.vertexShader = `varying vec3 vContactWorld;\n${shader.vertexShader}`.replace(
      "#include <begin_vertex>",
      "#include <begin_vertex>\nvContactWorld = (modelMatrix * vec4(position, 1.0)).xyz;",
    );
    shader.fragmentShader = `
      varying vec3 vContactWorld;
      uniform sampler2D uContactBoxes;
      uniform int uContactCount;
      uniform float uContactRows;
      uniform float uContactPixels;
      ${shader.fragmentShader}`.replace("#include <opaque_fragment>", `
        #include <opaque_fragment>
        for (int i = 0; i < uContactCount; i++) {
          float row = (float(i) + 0.5) / uContactRows;
          vec3 lo = texture2D(uContactBoxes, vec2(0.25, row)).xyz;
          vec3 hi = texture2D(uContactBoxes, vec2(0.75, row)).xyz;
          vec3 delta = max(max(lo - vContactWorld, vContactWorld - hi), vec3(0.0));
          float d = max(max(delta.x, delta.y), delta.z);
          // 覆盖外扩的屏幕像素，近看、远看和 DPR 变化时都不漏出粗线。
          if (d <= ${CONTACT_MM} + fwidth(d) * uContactPixels) gl_FragColor = vec4(0.0);
        }
      `);
  };
  material.customProgramCacheKey = () => "cartoon-wall-contact";
  return material;
}
