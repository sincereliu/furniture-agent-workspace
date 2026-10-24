import * as THREE from "three";
import { roomToThree } from "../room/layout_frame.js";
import { addNightLandscape } from "./night_landscape.js";

export const INK = 0x28231d;
const BASE_SCALE = 1.22;
const HORIZON_COLOR = new THREE.Color(0x131e2e);

const CEL_RAMP = (() => {
  const data = new Uint8Array([85, 155, 215, 255]);
  const texture = new THREE.DataTexture(data, 4, 1);
  texture.format = THREE.RedFormat;
  texture.magFilter = THREE.NearestFilter;
  texture.minFilter = THREE.NearestFilter;
  texture.needsUpdate = true;
  return texture;
})();

function applyDryBrushRim(material) {
  material.customProgramCacheKey = () => "cel-dry-brush";
  material.onBeforeCompile = (shader) => {
    shader.fragmentShader = shader.fragmentShader.replace(
      "vec3 outgoingLight = reflectedLight.directDiffuse + reflectedLight.indirectDiffuse + totalEmissiveRadiance;",
      `
      vec3 outgoingLight = reflectedLight.directDiffuse + reflectedLight.indirectDiffuse + totalEmissiveRadiance;
      // Studio dry-brush rim highlight (手办干扫高光与边缘微光)
      float rimTerm = pow(1.0 - clamp(dot(normal, normalize(vViewPosition)), 0.0, 1.0), 3.2);
      float topBias = clamp(normal.y * 0.35 + 0.65, 0.45, 1.0);
      outgoingLight += vec3(0.98, 0.96, 0.92) * (rimTerm * 0.32 * topBias);
      `
    );
  };
  const origClone = material.clone;
  material.clone = function () {
    const cloned = origClone.call(this);
    applyDryBrushRim(cloned);
    return cloned;
  };
  return material;
}

export function celMaterial(color, extra) {
  const mat = new THREE.MeshToonMaterial(Object.assign({
    color,
    gradientMap: CEL_RAMP,
    side: THREE.DoubleSide,
  }, extra));
  return applyDryBrushRim(mat);
}

function makeBoard(width, height, draw) {
  const board = document.createElement("canvas");
  board.width = width;
  board.height = height;
  draw(board.getContext("2d"), width, height);
  return board;
}

let cachedWoodBoard = null;
let cachedPavementBoard = null;

function textureFromBoard(board) {
  const texture = new THREE.CanvasTexture(board);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.needsUpdate = true;
  return texture;
}

export function woodTexture() {
  if (!cachedWoodBoard) {
    cachedWoodBoard = makeBoard(256, 256, (ctx) => {
      ctx.fillStyle = "#ebe7e0";
      ctx.fillRect(0, 0, 256, 256);
      const tiles = [
        [0, 0, "#efece6"],
        [128, 0, "#e9e5de"],
        [0, 128, "#e7e3dc"],
        [128, 128, "#edeae4"],
      ];
      for (const [x, y, tone] of tiles) {
        ctx.fillStyle = tone;
        ctx.fillRect(x + 1, y + 1, 126, 126);
      }
      ctx.strokeStyle = "rgba(155, 148, 138, 0.28)";
      ctx.lineWidth = 1.5;
      for (const pos of [0.75, 128, 255.25]) {
        ctx.beginPath();
        ctx.moveTo(0, pos);
        ctx.lineTo(256, pos);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(pos, 0);
        ctx.lineTo(pos, 256);
        ctx.stroke();
      }
    });
  }
  return textureFromBoard(cachedWoodBoard);
}

export function pavementTexture() {
  if (!cachedPavementBoard) {
    cachedPavementBoard = makeBoard(256, 256, (ctx) => {
      ctx.fillStyle = "#e2ded6";
      ctx.fillRect(0, 0, 256, 256);
      ctx.strokeStyle = "rgba(148, 142, 132, 0.18)";
      ctx.lineWidth = 1.5;
      for (let i = 0; i <= 4; i += 1) {
        ctx.beginPath();
        ctx.moveTo(0, i * 64);
        ctx.lineTo(256, i * 64);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(i * 64, 0);
        ctx.lineTo(i * 64, 256);
        ctx.stroke();
      }
    });
  }
  return textureFromBoard(cachedPavementBoard);
}

export function furnitureColor(item, selected, blocked) {
  if (blocked) return 0xd64545;
  if (selected) return 0xf2c56b;
  const category = String(item.category || "");
  if (category === "sofa" || category === "chair") return 0x948b80;
  if (category === "bed") return 0xd6cbc0;
  if (category === "coffee_table" || category === "table" || category === "desk") return 0xd8cab8;
  if (item.furniture_category === "wall_cabinet") return 0xf0e9df;
  return 0xe8dfd1;
}

let nightSkyTexturePromise = null;

function nightSkyTexture() {
  if (!nightSkyTexturePromise) nightSkyTexturePromise = (async () => {
    const response = await fetch(new URL("../../images/milky-way-eso0932a.jpg", import.meta.url));
    if (!response.ok) throw new Error(`Night sky texture: HTTP ${response.status}`);
    // Decode a same-origin fetch rather than an <img>, respecting the page's connect-src CSP.
    const bitmap = await createImageBitmap(await response.blob(), { imageOrientation: "flipY" });
    const texture = new THREE.Texture(bitmap);
    texture.flipY = false;
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.wrapS = THREE.RepeatWrapping;
    texture.needsUpdate = true;
    return texture;
  })();
  return nightSkyTexturePromise;
}

export function addSky(onReady) {
  const sky = new THREE.Mesh(
    new THREE.SphereGeometry(180000, 96, 48),
    new THREE.MeshBasicMaterial({
      color: 0x080f21, side: THREE.BackSide, depthWrite: false, toneMapped: false,
    }),
  );
  sky.name = "milky-way-sky";
  // Keep the galactic centre above the physical horizon, with a diagonal band.
  sky.quaternion.setFromUnitVectors(new THREE.Vector3(1, 0, 0), new THREE.Vector3(-0.64, 0.08, -0.73).normalize());
  sky.rotateX(0.55);
  sky.material.customProgramCacheKey = () => "night-sky-horizon";
  sky.material.onBeforeCompile = shader => {
    shader.uniforms.uHorizonColor = { value: HORIZON_COLOR };
    shader.vertexShader = "varying vec3 vSkyDirection;\n" + shader.vertexShader;
    shader.vertexShader = shader.vertexShader.replace("#include <begin_vertex>",
      "#include <begin_vertex>\nvSkyDirection = (modelMatrix * vec4(position, 0.0)).xyz;");
    shader.fragmentShader = "varying vec3 vSkyDirection;\nuniform vec3 uHorizonColor;\n" + shader.fragmentShader;
    shader.fragmentShader = shader.fragmentShader.replace("#include <opaque_fragment>", `
      float elevation = normalize(vSkyDirection).y;
      outgoingLight = mix(uHorizonColor, outgoingLight, smoothstep(0.0, 0.10, elevation));
      #include <opaque_fragment>
    `);
  };
  sky.frustumCulled = false;
  sky.renderOrder = -3;
  sky.raycast = () => {};
  sky.userData.ready = nightSkyTexture().then(texture => {
    sky.material.map = texture;
    sky.material.color.setHex(0xb8c9ee);
    sky.material.needsUpdate = true;
    onReady?.();
  }).catch(error => {
    sky.userData.loadError = String(error);
    console.error(error);
  });
  return sky;
}

/** A grounded architectural model: a light terrace on a quiet, moonlit stone field. */
export function addDiorama(parent, width, depth, addStageInk, environment) {
  const side = Math.max(width, depth) * BASE_SCALE;
  const thick = Math.min(260, Math.max(160, side * 0.04));
  const pavement = pavementTexture();
  pavement.repeat.set(side / 1200, side / 1200);
  const topZ = -8;
  const top = new THREE.Mesh(new THREE.PlaneGeometry(side, side), celMaterial(0xffffff, { map: pavement }));
  top.name = "room-terrace";
  top.rotation.x = -Math.PI / 2;
  top.position.set(...roomToThree(width / 2, depth / 2, topZ + 1));
  top.receiveShadow = true;
  top.layers.enable(1);
  parent.add(top);
  const plinth = new THREE.Mesh(new THREE.BoxGeometry(side, thick, side), celMaterial(0xd6d1c7));
  plinth.name = "room-plinth";
  plinth.position.set(...roomToThree(width / 2, depth / 2, topZ - thick / 2));
  plinth.receiveShadow = true;
  plinth.castShadow = true;
  plinth.layers.enable(1);
  parent.add(plinth);
  addStageInk(plinth, 0x3d352e, 16);

  addNightLandscape(environment, {
    width, depth, side, groundZ: topZ - thick + 2, horizonColor: HORIZON_COLOR,
    pavement: pavementTexture(),
  });
}
