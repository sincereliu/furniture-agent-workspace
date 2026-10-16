import * as THREE from "three";
import { roomToThree } from "./layout_frame.js";
import { WALL_THICKNESS_MM } from "./wall_solid.js";

export const INK = 0x2a2118;
const BASE_SCALE = 1.22;

const CEL_RAMP = (() => {
  const data = new Uint8Array([184, 214, 236, 255]);
  const texture = new THREE.DataTexture(data, 4, 1);
  texture.format = THREE.RedFormat;
  texture.magFilter = THREE.NearestFilter;
  texture.minFilter = THREE.NearestFilter;
  texture.needsUpdate = true;
  return texture;
})();

export function celMaterial(color, extra) {
  return new THREE.MeshToonMaterial(Object.assign({
    color,
    gradientMap: CEL_RAMP,
    side: THREE.DoubleSide,
  }, extra));
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
      ctx.fillStyle = "#c4b39e";
      ctx.fillRect(0, 0, 256, 256);
      for (let row = 0; row < 8; row += 1) {
        ctx.fillStyle = row % 2 ? "#d5c6b2" : "#bba78f";
        ctx.fillRect(0, row * 32, 256, 30);
        ctx.fillStyle = "rgba(62, 48, 38, 0.2)";
        ctx.fillRect(0, row * 32 + 30, 256, 2);
        ctx.fillStyle = "rgba(255, 248, 236, 0.2)";
        ctx.fillRect(18 + (row % 3) * 40, row * 32 + 8, 70, 3);
      }
    });
  }
  return textureFromBoard(cachedWoodBoard);
}

export function pavementTexture() {
  if (!cachedPavementBoard) {
    cachedPavementBoard = makeBoard(256, 256, (ctx) => {
      ctx.fillStyle = "#12110f";
      ctx.fillRect(0, 0, 256, 256);
      ctx.strokeStyle = "rgba(186, 168, 146, 0.14)";
      ctx.lineWidth = 2;
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
  if (category === "sofa" || category === "chair") return 0x8d8276;
  if (category === "bed") return 0xd9d0c4;
  if (category === "coffee_table" || category === "table" || category === "desk") return 0xd4cbbd;
  if (item.furniture_category === "wall_cabinet") return 0xfaf7f2;
  return 0xf4f0e8;
}

export function addSky() {
  const sky = new THREE.Mesh(
    new THREE.SphereGeometry(180000, 28, 18),
    new THREE.ShaderMaterial({
      side: THREE.BackSide,
      depthWrite: false,
      vertexShader: `
        varying vec3 vDir;
        void main() {
          vDir = normalize(position);
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
      `,
      fragmentShader: `
        varying vec3 vDir;
        float hash(vec3 p) {
          p = fract(p * vec3(123.34, 345.45, 678.91));
          p += dot(p, p + 34.45);
          return fract(p.x * p.y);
        }
        void main() {
          vec3 n = normalize(vDir);
          float h = clamp(n.y * 0.5 + 0.5, 0.0, 1.0);
          vec3 zenith = vec3(0.025, 0.028, 0.036);
          vec3 mid = vec3(0.07, 0.065, 0.06);
          vec3 horizon = vec3(0.32, 0.22, 0.16);
          vec3 col = mix(horizon, mid, smoothstep(0.02, 0.42, h));
          col = mix(col, zenith, smoothstep(0.28, 0.9, h));
          float band = pow(1.0 - abs(n.y), 10.0);
          col += vec3(0.55, 0.38, 0.22) * band * 0.16;
          vec3 moon = normalize(vec3(-0.45, 0.78, -0.28));
          col += vec3(0.92, 0.9, 0.84) * smoothstep(0.9972, 0.9992, dot(n, moon));
          float stars = step(0.997, hash(floor(n * 180.0)));
          col += vec3(0.92, 0.9, 0.86) * stars * step(0.18, n.y);
          gl_FragColor = vec4(col, 1.0);
        }
      `,
    }),
  );
  sky.frustumCulled = false;
  sky.renderOrder = -2;
  return sky;
}

function addLamp(parent, east, south, glow) {
  const pole = new THREE.Mesh(new THREE.CylinderGeometry(14, 20, 640, 8), celMaterial(0x242b3d));
  pole.position.set(...roomToThree(east, south, 320));
  parent.add(pole);
  const bulb = new THREE.Mesh(
    new THREE.SphereGeometry(34, 12, 10),
    new THREE.MeshBasicMaterial({ color: glow }),
  );
  bulb.position.set(...roomToThree(east, south, 680));
  parent.add(bulb);
}

function addNeonRim(parent, width, depth, side) {
  const x0 = width / 2 - side / 2;
  const y0 = depth / 2 - side / 2;
  const specs = [
    [width / 2, y0 + 16, side, 32, 0xa6845c],
    [width / 2, y0 + side - 16, side, 32, 0xa6845c],
    [x0 + 16, depth / 2, 32, side, 0xa6845c],
    [x0 + side - 16, depth / 2, 32, side, 0xa6845c],
  ];
  for (const [cx, cy, east, south, color] of specs) {
    const mesh = new THREE.Mesh(
      new THREE.BoxGeometry(east, 18, south),
      new THREE.MeshBasicMaterial({ color }),
    );
    mesh.position.set(...roomToThree(cx, cy, 6));
    parent.add(mesh);
  }
}

function addTown(parent, width, depth, side, addInk) {
  const x0 = width / 2 - side / 2;
  const y0 = depth / 2 - side / 2;
  const southGap = y0 + side - depth;
  const eastGap = x0 + side - width;
  const yard = WALL_THICKNESS_MM;
  if (southGap > 180) {
    const hedgeDepth = Math.min(120, southGap * 0.28);
    const hedge = new THREE.Mesh(
      new THREE.BoxGeometry(width * 0.42, 140, hedgeDepth),
      celMaterial(0x1d3a32),
    );
    hedge.position.set(...roomToThree(width * 0.5, depth + yard + 48 + hedgeDepth / 2, 70));
    parent.add(hedge);
    addInk(hedge, 0x0e1c18);
    const lampOut = (gap) => Math.max(gap, yard + 48);
    addLamp(parent, width * 0.18, depth + lampOut(southGap * 0.62), 0xf0e2cc);
    addLamp(parent, width * 0.78, depth + lampOut(southGap * 0.5), 0xf0e2cc);
  }
  if (eastGap > 200) addLamp(parent, width + Math.max(eastGap * 0.55, yard + 48), depth * 0.3, 0xf0e2cc);
}

/** 正方形厚底座。房间和室外小景都落在它上面，夜色停在底座边缘。 */
export function addDiorama(parent, width, depth, addInk) {
  const side = Math.max(width, depth) * BASE_SCALE;
  const thick = Math.min(340, Math.max(200, side * 0.05));
  const pavement = pavementTexture();
  pavement.repeat.set(side / 900, side / 900);
  const topZ = -8;
  const top = new THREE.Mesh(new THREE.PlaneGeometry(side, side), celMaterial(0xffffff, { map: pavement }));
  top.rotation.x = -Math.PI / 2;
  top.position.set(...roomToThree(width / 2, depth / 2, topZ + 1));
  parent.add(top);
  const plinth = new THREE.Mesh(new THREE.BoxGeometry(side, thick, side), celMaterial(0x121722));
  plinth.position.set(...roomToThree(width / 2, depth / 2, topZ - thick / 2));
  parent.add(plinth);
  addInk(plinth, 0x07080e);
  addNeonRim(parent, width, depth, side);
  addTown(parent, width, depth, side, addInk);
}
