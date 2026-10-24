import * as THREE from "three";
import { roomToThree } from "../room/layout_frame.js";

let grassBoard = null;

function grassTexture() {
  if (!grassBoard) {
    grassBoard = document.createElement("canvas");
    grassBoard.width = grassBoard.height = 512;
    const ctx = grassBoard.getContext("2d");
    ctx.fillStyle = "#929b80";
    ctx.fillRect(0, 0, 512, 512);
    let seed = 731;
    const random = () => ((seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0) / 4294967296);
    for (let i = 0; i < 3200; i += 1) {
      const x = random() * 512, y = random() * 512;
      ctx.strokeStyle = i % 2 ? "rgba(49,70,43,.16)" : "rgba(211,215,177,.15)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x, y);
      ctx.lineTo(x + random() * 4 - 2, y - 2 - random() * 4);
      ctx.stroke();
    }
  }
  const texture = new THREE.CanvasTexture(grassBoard);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
  return texture;
}

function courtyardGeometry(side, radius) {
  const a = side / 2, r = radius;
  const shape = new THREE.Shape();
  shape.moveTo(-a + r, -a);
  shape.lineTo(a - r, -a);
  shape.quadraticCurveTo(a, -a, a, -a + r);
  shape.lineTo(a, a - r);
  shape.quadraticCurveTo(a, a, a - r, a);
  shape.lineTo(-a + r, a);
  shape.quadraticCurveTo(-a, a, -a, a - r);
  shape.lineTo(-a, -a + r);
  shape.quadraticCurveTo(-a, -a, -a + r, -a);
  return new THREE.ShapeGeometry(shape, 8);
}

/** Fixed preview scenery: a stone court, lawn and a distant, low tree belt. */
export function addNightLandscape(parent, { width, depth, side, groundZ, horizonColor, pavement }) {
  const center = new THREE.Vector2(width / 2, depth / 2);
  function material(color, map) {
    const mat = new THREE.MeshStandardMaterial({ color, map, roughness: 1, metalness: 0, side: THREE.FrontSide });
    mat.customProgramCacheKey = () => "night-landscape-distance-haze";
    mat.onBeforeCompile = shader => {
      shader.uniforms.uHorizonColor = { value: horizonColor };
      shader.uniforms.uGroundCenter = { value: center };
      shader.uniforms.uGroundHaze = { value: new THREE.Vector2(side * 2.5, side * 18) };
      shader.vertexShader = "varying vec3 vGroundPosition;\n" + shader.vertexShader;
      shader.vertexShader = shader.vertexShader.replace("#include <worldpos_vertex>",
        "#include <worldpos_vertex>\nvGroundPosition = (modelMatrix * vec4(transformed, 1.0)).xyz;");
      shader.fragmentShader = "varying vec3 vGroundPosition;\nuniform vec3 uHorizonColor;\nuniform vec2 uGroundCenter;\nuniform vec2 uGroundHaze;\n" + shader.fragmentShader;
      shader.fragmentShader = shader.fragmentShader.replace("#include <opaque_fragment>", `
        float groundDistance = length(vGroundPosition.xz - uGroundCenter);
        outgoingLight = mix(outgoingLight, uHorizonColor, smoothstep(uGroundHaze.x, uGroundHaze.y, groundDistance));
        #include <opaque_fragment>
      `);
    };
    return mat;
  }
  const extent = Math.max(1000000, side * 100);
  const grass = grassTexture();
  grass.repeat.set(extent / 2200, extent / 2200);
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(extent, extent), material(0x455b43, grass));
  ground.name = "night-ground";
  ground.rotation.x = -Math.PI / 2;
  ground.position.set(...roomToThree(width / 2, depth / 2, groundZ));
  ground.receiveShadow = true;
  ground.renderOrder = -2;
  ground.raycast = () => {};
  parent.add(ground);

  const courtSide = side + Math.max(1800, side * 0.55);
  const radius = Math.min(500, courtSide * 0.08);
  const edging = new THREE.Mesh(courtyardGeometry(courtSide, radius), material(0x49514d, null));
  edging.name = "courtyard-edging";
  edging.rotation.x = -Math.PI / 2;
  edging.position.set(...roomToThree(width / 2, depth / 2, groundZ + 1));
  edging.receiveShadow = true;
  edging.renderOrder = -2;
  edging.raycast = () => {};
  parent.add(edging);
  // ShapeGeometry UVs are measured in mm, unlike the unit UVs of PlaneGeometry.
  pavement.repeat.set(1 / 4800, 1 / 4800);
  const court = new THREE.Mesh(courtyardGeometry(courtSide - 220, radius - 110), material(0x60696b, pavement));
  court.name = "stone-courtyard";
  court.rotation.x = -Math.PI / 2;
  court.position.set(...roomToThree(width / 2, depth / 2, groundZ + 2));
  court.receiveShadow = true;
  court.renderOrder = -2;
  court.raycast = () => {};
  parent.add(court);

  const trees = new THREE.Group();
  trees.name = "night-treeline";
  const count = 176;
  const trunks = new THREE.InstancedMesh(new THREE.CylinderGeometry(1, 1.2, 1, 5),
    new THREE.MeshBasicMaterial({ color: 0xffffff, depthWrite: false }), count);
  const crowns = new THREE.InstancedMesh(new THREE.IcosahedronGeometry(1, 1),
    new THREE.MeshBasicMaterial({ color: 0xffffff, depthWrite: false }), count * 3);
  // Background trees respect terrain depth, while room inspection draws over them.
  trunks.renderOrder = crowns.renderOrder = -1;
  trunks.raycast = crowns.raycast = () => {};
  trees.add(trunks, crowns);
  parent.add(trees);
  let seed = 1867;
  const random = () => ((seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0) / 4294967296);
  const transform = new THREE.Object3D();
  const innerRadius = Math.max(36000, side * 9);
  const treeHeight = Math.min(4500, side * 0.65);
  const color = new THREE.Color();
  for (let i = 0; i < count; i += 1) {
    const angle = (i + random() * 0.75) * Math.PI * 2 / count;
    const distance = innerRadius * (1 + random() * 0.6);
    const x = width / 2 + Math.cos(angle) * distance;
    const y = depth / 2 + Math.sin(angle) * distance;
    const height = treeHeight * (0.58 + random() * 0.42);
    const spread = height * (0.28 + random() * 0.12);
    const haze = THREE.MathUtils.smoothstep(distance, side * 2.5, side * 18);
    color.setHex(i % 3 ? 0x10231d : 0x172b23).lerp(horizonColor, haze);
    transform.position.set(...roomToThree(x, y, groundZ + height * 0.32));
    transform.scale.set(height * 0.025, height * 0.64, height * 0.025);
    transform.rotation.set(0, angle, 0);
    transform.updateMatrix();
    trunks.setMatrixAt(i, transform.matrix);
    trunks.setColorAt(i, color);
    for (let lobe = 0; lobe < 3; lobe += 1) {
      const offset = (lobe - 1) * spread * 0.45;
      transform.position.set(...roomToThree(x - Math.sin(angle) * offset, y + Math.cos(angle) * offset,
        groundZ + height * (lobe === 1 ? 0.78 : 0.65)));
      transform.scale.set(spread * (lobe === 1 ? 1 : 0.8), height * 0.26, spread * 0.82);
      transform.rotation.set(random() * 0.15, random() * Math.PI, random() * 0.15);
      transform.updateMatrix();
      crowns.setMatrixAt(i * 3 + lobe, transform.matrix);
      crowns.setColorAt(i * 3 + lobe, color);
    }
  }
  for (const mesh of [trunks, crowns]) {
    mesh.instanceMatrix.needsUpdate = true;
    mesh.instanceColor.needsUpdate = true;
    mesh.computeBoundingSphere();
  }
}
