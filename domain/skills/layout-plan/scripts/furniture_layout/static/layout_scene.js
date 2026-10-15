import * as THREE from "three";
import { OrbitControls } from "/vendor/three/0.186.0/OrbitControls.js";
import { cameraFov, cameraThreePosition, roomToThree, threeToRoom } from "./layout_frame.js";
import { ROOM_AXES, roomAxes, dimensionAnnotations } from "./layout_annotations.js";
import { placeLabels } from "./layout_labels.js";
import { ELEVATION_PITCH, wallVisibility } from "./wall_view.js";
import { WALL_THICKNESS_MM, openingSolids, wallSolids } from "./wall_solid.js";
import { isFixedCoffeeTable, coffeeTableParts } from "./coffee_table_solid.js";
import { isFixedSofa, sofaFrame, sofaLocalBox, sofaMount, sofaParts } from "./sofa_solid.js";
import { inkViewBiasGlsl } from "./ink_depth.js";

export { cameraThreePosition, roomToThree };

function disposeObject(object) {
  const materials = new Set();
  object.traverse((node) => {
    if (node.geometry) node.geometry.dispose();
    const list = node.material
      ? (Array.isArray(node.material) ? node.material : [node.material])
      : [];
    for (const material of list) materials.add(material);
    if (node.userData && node.userData.material) materials.add(node.userData.material);
  });
  for (const material of materials) {
    if (material.map) material.map.dispose();
    material.dispose();
  }
}

function prismGeometry(footprint, z0, z1) {
  const positions = [];
  const n = footprint.length;
  const points = footprint;
  const bottom = points.map(([x, y]) => roomToThree(x, y, z0));
  const top = points.map(([x, y]) => roomToThree(x, y, z1));
  const push = (a, b, c) => positions.push(...a, ...b, ...c);
  for (let i = 0; i < n; i += 1) {
    const j = (i + 1) % n;
    push(bottom[i], bottom[j], top[j]);
    push(bottom[i], top[j], top[i]);
  }
  for (let i = 1; i < n - 1; i += 1) {
    push(top[0], top[i], top[i + 1]);
    push(bottom[0], bottom[i + 1], bottom[i]);
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.computeVertexNormals();
  return geometry;
}

function line(points, color) {
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(points.flat(), 3));
  // 深度偏移：轴线要**贴在**房间边界/地板边上（几何重合），靠偏移而不是靠抬高来避免共面闪烁。
  // 负值让线在深度上稳定地稍靠前一点，屏幕上看不出偏移，但永远不会和轮廓线打架。
  const material = new THREE.LineBasicMaterial({
    color,
    polygonOffset: true,
    polygonOffsetFactor: -2,
    polygonOffsetUnits: -2,
  });
  return new THREE.Line(geometry, material);
}

function lineSegments(values, color, opacity = 1) {
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(values, 3));
  return new THREE.LineSegments(geometry, new THREE.LineBasicMaterial({
    color,
    transparent: opacity < 1,
    opacity,
  }));
}

/**
 * 文字标注走 DOM，不走 sprite。
 *
 * 原因：sprite 是世界空间尺寸，缩放一变字就跟着变小——实测 122mm 高的标签在默认视角只映射到
 * 约 10px，汉字 ~7px，数字糊成一团。DOM 文字是屏幕空间，字号恒定 12px，任何缩放下都清晰。
 */
function ensureLabelLayer(canvas) {
  const host = canvas.parentElement;
  if (!host) return null;
  if (window.getComputedStyle(host).position === "static") host.style.position = "relative";
  let layer = host.querySelector(".scene-labels");
  if (!layer) {
    layer = document.createElement("div");
    layer.className = "scene-labels";
    layer.style.cssText = "position:absolute;inset:0;pointer-events:none;overflow:hidden;z-index:2";
    host.appendChild(layer);
  }
  return layer;
}

function makeLabelElement(layer, label) {
  const el = document.createElement("div");
  el.className = "scene-label";
  el.textContent = label.text;
  el.style.cssText = [
    "position:absolute",
    "left:0",
    "top:0",
    "font:700 12px/1.25 Inter,Microsoft YaHei,system-ui,sans-serif",
    `color:#f7f1e6`,
    "background:rgba(16,14,26,.78)",
    "border:1px solid rgba(255,214,160,.35)",
    "border-radius:4px",
    "padding:1px 4px",
    "white-space:nowrap",
    "transform:translate(0,0)",
    "will-change:transform",
  ].join(";");
  layer.appendChild(el);
  return el;
}

/** 方位指示器固定屏幕尺寸，方向跟随相机投影。 */
function makeAxisGizmo() {
  const SIZE = 96;
  const board = document.createElement("canvas");
  board.width = SIZE;
  board.height = SIZE;
  const el = document.createElement("div");
  el.className = "scene-axis-gizmo";
  el.style.cssText = [
    "position:absolute",
    "right:10px",
    "bottom:10px",
    "width:96px",
    "height:96px",
    "pointer-events:none",
    "z-index:3",
  ].join(";");
  el.appendChild(board);
  return { el, ctx: board.getContext("2d") };
}

/** 房间坐标 AABB [x0, y0, z0, x1, y1, z1] 变成轴对齐盒子。 */
function addRoomBox(parent, box, material) {
  const [x0, y0, z0, x1, y1, z1] = box;
  const mesh = new THREE.Mesh(
    new THREE.BoxGeometry(x1 - x0, z1 - z0, y1 - y0),
    material,
  );
  mesh.position.set(...roomToThree((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2));
  parent.add(mesh);
  return mesh;
}

/** 门窗比洞口略收 1 mm，侧边不和墙垛共面。厚度方向不收，仍填满墙厚。 */
function insetOpening(wall, box) {
  const gap = 1;
  const shrink = (a, b) => (b - a > gap * 2 + 1 ? [a + gap, b - gap] : [a, b]);
  const [x0, y0, z0, x1, y1, z1] = box;
  if (wall === "north" || wall === "south") {
    const [xa, xb] = shrink(x0, x1);
    const [za, zb] = shrink(z0, z1);
    return [xa, y0, za, xb, y1, zb];
  }
  const [ya, yb] = shrink(y0, y1);
  const [za, zb] = shrink(z0, z1);
  return [x0, ya, za, x1, yb, zb];
}

function addMesh(parent, mesh, pickables) {
  parent.add(mesh);
  if (mesh.userData && mesh.userData.kind) pickables.push(mesh);
  return mesh;
}

// 室内和夜景分开受光。家具、地板、墙在 ROOM_LAYER，只吃暖光；
// 底座和室外小景留在 0 层，只吃夜光。相机和拾取两层都看。
const ROOM_LAYER = 1;
const INK = 0x2a2118;
const BASE_SCALE = 1.22;

const CEL_RAMP = (() => {
  const data = new Uint8Array([152, 196, 226, 255]);
  const texture = new THREE.DataTexture(data, 4, 1);
  texture.format = THREE.RedFormat;
  texture.magFilter = THREE.NearestFilter;
  texture.minFilter = THREE.NearestFilter;
  texture.needsUpdate = true;
  return texture;
})();

function celMaterial(color, extra) {
  return new THREE.MeshToonMaterial(Object.assign({
    color,
    gradientMap: CEL_RAMP,
    side: THREE.DoubleSide,
  }, extra));
}

function paintTexture(width, height, draw) {
  const board = document.createElement("canvas");
  board.width = width;
  board.height = height;
  draw(board.getContext("2d"), width, height);
  const texture = new THREE.CanvasTexture(board);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.needsUpdate = true;
  return texture;
}

function woodTexture() {
  return paintTexture(256, 256, (ctx) => {
    ctx.fillStyle = "#f0d2a4";
    ctx.fillRect(0, 0, 256, 256);
    for (let row = 0; row < 8; row += 1) {
      ctx.fillStyle = row % 2 ? "#f6ddb6" : "#e4c08a";
      ctx.fillRect(0, row * 32, 256, 30);
      ctx.fillStyle = "rgba(92, 58, 28, 0.16)";
      ctx.fillRect(0, row * 32 + 30, 256, 2);
      ctx.fillStyle = "rgba(255, 244, 220, 0.28)";
      ctx.fillRect(18 + (row % 3) * 40, row * 32 + 8, 70, 3);
    }
  });
}

function pavementTexture() {
  return paintTexture(256, 256, (ctx) => {
    ctx.fillStyle = "#141a2c";
    ctx.fillRect(0, 0, 256, 256);
    ctx.strokeStyle = "rgba(120, 146, 186, 0.16)";
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
    ctx.fillStyle = "rgba(103, 232, 249, 0.18)";
    ctx.fillRect(0, 148, 256, 9);
    ctx.fillStyle = "rgba(244, 114, 182, 0.16)";
    ctx.fillRect(24, 42, 190, 7);
    ctx.fillStyle = "rgba(255, 214, 160, 0.08)";
    ctx.fillRect(0, 204, 256, 16);
  });
}

function markRoom(mesh) {
  mesh.layers.set(ROOM_LAYER);
  return mesh;
}

function inkMaterial(color) {
  const material = new THREE.LineBasicMaterial({
    color,
    transparent: true,
  });
  // 相同拉近量共用一个程序。颜色仍由各自的材质 uniform 决定。
  material.customProgramCacheKey = () => "ink-view-bias";
  material.onBeforeCompile = (shader) => {
    shader.vertexShader = shader.vertexShader.replace(
      "#include <project_vertex>",
      inkViewBiasGlsl(),
    );
  };
  return material;
}

function addInk(mesh, color = INK) {
  const ink = new THREE.LineSegments(
    new THREE.EdgesGeometry(mesh.geometry, 25),
    inkMaterial(color),
  );
  ink.raycast = () => {};
  mesh.add(ink);
  mesh.userData.ink = ink;
  return ink;
}

function furnitureColor(item, selected, blocked) {
  if (blocked) return 0xd64545;
  if (selected) return 0xf2c56b;
  const category = String(item.category || "");
  if (category === "sofa" || category === "chair") return 0xd48984;
  if (category === "bed") return 0xecd8c8;
  if (category === "coffee_table" || category === "table" || category === "desk") return 0xc9956a;
  if (item.furniture_category === "wall_cabinet") return 0xf0d5b0;
  return 0xd7a36a;
}

/** 按足迹摆一组外形块。放不进外形尺寸时返回 false，调用方改画盒子。 */
function addShapedItem(parent, pickables, item, parts, materials, selected) {
  const frame = sofaFrame(item.footprint, item.z_start);
  if (!parts || !frame) return false;
  const mount = sofaMount(frame);
  const group = new THREE.Group();
  group.position.set(...roomToThree(...mount.origin));
  group.setRotationFromMatrix(new THREE.Matrix4().makeBasis(
    new THREE.Vector3(...mount.x),
    new THREE.Vector3(...mount.y),
    new THREE.Vector3(...mount.z),
  ));
  parent.add(group);
  const ink = selected ? 0x6a4520 : INK;
  for (const part of parts) {
    const local = sofaLocalBox(part.box);
    const mesh = markRoom(new THREE.Mesh(
      new THREE.BoxGeometry(...local.size),
      materials[part.role],
    ));
    mesh.position.set(...local.center);
    mesh.userData = { kind: "item", itemId: item.id };
    addInk(mesh, ink);
    group.add(mesh);
    pickables.push(mesh);
  }
  return true;
}

/** 固定沙发：靠背、扶手、坐垫。 */
function addSofa(parent, pickables, item, selected, blocked) {
  const parts = sofaParts(item.width, item.depth, item.height);
  const base = furnitureColor(item, selected, blocked);
  const fabric = celMaterial(base);
  const materials = selected || blocked
    ? { fabric, deck: fabric, cushion: fabric, wood: fabric }
    : {
        fabric,
        deck: celMaterial(0xb56d68),
        cushion: celMaterial(0xf0c2ba),
        wood: celMaterial(0x5c4030),
      };
  return addShapedItem(parent, pickables, item, parts, materials, selected);
}

/** 固定茶几：桌面、四条腿、下层板。 */
function addCoffeeTable(parent, pickables, item, selected, blocked) {
  const parts = coffeeTableParts(item.width, item.depth, item.height);
  const base = furnitureColor(item, selected, blocked);
  const top = celMaterial(base);
  const materials = selected || blocked
    ? { top, leg: top, shelf: top }
    : {
        top,
        leg: celMaterial(0x6e4b2e),
        shelf: celMaterial(0xd8b48a),
      };
  return addShapedItem(parent, pickables, item, parts, materials, selected);
}

function addSky() {
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
          vec3 zenith = vec3(0.035, 0.05, 0.11);
          vec3 mid = vec3(0.09, 0.11, 0.24);
          vec3 horizon = vec3(0.36, 0.18, 0.40);
          vec3 col = mix(horizon, mid, smoothstep(0.02, 0.38, h));
          col = mix(col, zenith, smoothstep(0.32, 0.92, h));
          float band = pow(1.0 - abs(n.y), 10.0);
          col += vec3(0.15, 0.45, 0.62) * band * 0.22;
          col += vec3(0.85, 0.25, 0.55) * band * 0.08;
          vec3 moon = normalize(vec3(-0.45, 0.78, -0.28));
          col += vec3(0.86, 0.91, 1.0) * smoothstep(0.9972, 0.9992, dot(n, moon));
          float stars = step(0.997, hash(floor(n * 180.0)));
          col += vec3(0.9, 0.93, 1.0) * stars * step(0.18, n.y);
          gl_FragColor = vec4(col, 1.0);
        }
      `,
    }),
  );
  sky.frustumCulled = false;
  sky.renderOrder = -2;
  return sky;
}

function addBuilding(parent, east, south, spanEast, spanSouth, height, color, windowColor) {
  const mesh = new THREE.Mesh(
    new THREE.BoxGeometry(spanEast, height, spanSouth),
    celMaterial(color),
  );
  mesh.position.set(...roomToThree(east, south, height / 2));
  parent.add(mesh);
  addInk(mesh, 0x0c1018);
  const windows = new THREE.Mesh(
    new THREE.PlaneGeometry(spanEast * 0.62, height * 0.42),
    new THREE.MeshBasicMaterial({ color: windowColor, transparent: true, opacity: 0.9 }),
  );
  // 平面默认朝 +Z，也就是房间的南向。默认相机在南边，看见的是楼的南立面。
  windows.position.set(...roomToThree(east, south + spanSouth / 2 + 2, height * 0.58));
  parent.add(windows);
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
    [width / 2, y0 + 16, side, 32, 0x67e8f9],
    [width / 2, y0 + side - 16, side, 32, 0xf472b6],
    [x0 + 16, depth / 2, 32, side, 0xf472b6],
    [x0 + side - 16, depth / 2, 32, side, 0x67e8f9],
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

function addTown(parent, width, depth, side) {
  const x0 = width / 2 - side / 2;
  const y0 = depth / 2 - side / 2;
  const northGap = -y0;
  const southGap = y0 + side - depth;
  const westGap = -x0;
  const eastGap = x0 + side - width;
  // 围墙在室内边界外占一个墙厚。室外小景沿用原来离墙面的空隙，改从外墙面起算。
  const yard = WALL_THICKNESS_MM;
  if (northGap > 240) {
    const span = Math.min(northGap - 70, 720) - yard;
    if (span > 120) {
      const south = -(36 + yard) - span / 2;
      const colors = [0x1a2236, 0x261c38, 0x172433, 0x2c2140];
      const heights = [1100, 1560, 860, 1280];
      const windows = [0xffd2a4, 0x8be7ff, 0xf9a8d4, 0xffe1b0];
      let cursor = Math.max(40, width * 0.06);
      for (let index = 0; index < 4 && cursor < width * 0.92; index += 1) {
        const spanEast = Math.min(520 + (index % 2) * 220, width * 0.92 - cursor);
        if (spanEast < 180) break;
        addBuilding(parent, cursor + spanEast / 2, south, spanEast, span, heights[index], colors[index], windows[index]);
        cursor += spanEast + 80;
      }
    }
  }
  if (westGap > 240) {
    const span = Math.min(westGap - 70, 640) - yard;
    if (span > 120) {
      const east = -(36 + yard) - span / 2;
      addBuilding(parent, east, depth * 0.72, span, Math.min(480, depth * 0.22), 1320, 0x1b243c, 0xf9a8d4);
      addBuilding(parent, east, depth * 0.28, span, Math.min(420, depth * 0.18), 900, 0x241832, 0x8be7ff);
    }
  }
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
    addLamp(parent, width * 0.18, depth + lampOut(southGap * 0.62), 0xffd7a8);
    addLamp(parent, width * 0.78, depth + lampOut(southGap * 0.5), 0x9aefff);
  }
  if (eastGap > 200) addLamp(parent, width + Math.max(eastGap * 0.55, yard + 48), depth * 0.3, 0xffb7d5);
}

/** 正方形厚底座。房间和室外小景都落在它上面，夜色停在底座边缘。 */
function addDiorama(parent, width, depth) {
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
  addTown(parent, width, depth, side);
}

export function mountLayout(canvas) {
  // 对数深度：房间以毫米计，正视图相机又拉得很远。普通深度分不出贴墙的边和墙面。
  const renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: true,
    logarithmicDepthBuffer: true,
  });
  renderer.setClearColor(0x070b16, 1);
  const camera = new THREE.PerspectiveCamera(48, 1, 10, 500000);
  camera.up.set(0, 1, 0);
  /**
   * **全程只用透视相机**，六个正视图靠"把相机拉远 + 等比例收窄 fov"逼近正交。
   *
   * 为什么不再用正交相机：正交与透视的画面必然不同（平行投影 vs 纵向收敛），
   * 实测同一姿态下两者有 6~7.5% 的像素差异——**只要切换投影，那一下就会被看到**
   * （放在动画开头/中途/结尾都一样，用两遍渲染混合又会因半透明墙产生重影）。
   * 全程一种投影就不存在"切换"，抖动从根上消失；代价是立面图有极轻微的透视收敛
   * （实测：拉远 10× 时与真正交差 1.5%，25× 时差 1.07%）。
   */
  const LENS_BASE = 48;          // 自由视角的 fov（度）
  const ELEVATION_PULL = 8;      // 正视图把相机拉远的倍数（越大越接近正交）
  const scene = new THREE.Scene();
  const sky = addSky();
  scene.add(sky);
  const nightFill = new THREE.HemisphereLight(0x31456e, 0x121624, 0.85);
  nightFill.layers.set(0);
  const moon = new THREE.DirectionalLight(0xd5e2ff, 0.42);
  moon.layers.set(0);
  const roomFill = new THREE.HemisphereLight(0xfff6e4, 0xe8a15a, 0.48);
  roomFill.layers.set(ROOM_LAYER);
  const roomKey = new THREE.DirectionalLight(0xffe3b0, 0.42);
  roomKey.layers.set(ROOM_LAYER);
  scene.add(nightFill, moon, roomFill, roomKey);
  const content = new THREE.Group();
  scene.add(content);
  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = false;
  // 滚轮倍率由页面统一维护，避免 OrbitControls 距离与页面倍率各算一次。
  controls.enableZoom = false;
  controls.screenSpacePanning = true;
  controls.mouseButtons = {
    LEFT: THREE.MOUSE.ROTATE,
    MIDDLE: THREE.MOUSE.PAN,
    RIGHT: THREE.MOUSE.PAN,
  };
  controls.minPolarAngle = 0.02;
  controls.maxPolarAngle = Math.PI - 0.02;
  camera.layers.enable(ROOM_LAYER);
  const raycaster = new THREE.Raycaster();
  raycaster.layers.enable(ROOM_LAYER);
  const ndc = new THREE.Vector2();
  const floor = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
  const hitPoint = new THREE.Vector3();
  const wallViewDirection = new THREE.Vector3();
  let pickables = [];
  let wallShells = [];
  let labelLayer = null;
  let labelLeaders = null;
  let labelEntries = [];
  let axisGizmo = null;
  const WALL_FADE_MS = 150;  // 墙显隐/透明度的过渡时长：判据是二值的，靠它摊开突变
  let wallFade = [];         // 每面墙当前的渐变透明度
  let wallFadeFrom = [];     // 本趟渐变的起点
  let wallFadeTargets = [];  // 本趟渐变的目标
  let wallFadeStarted = 0;   // 本趟渐变的开始时刻（0 = 没有在跑的渐变）
  function setLens(fovDeg) {
    const next = Math.max(0.1, Math.min(150, Number(fovDeg) || LENS_BASE));
    if (Math.abs(camera.fov - next) < 1e-6) return;
    camera.fov = next;
    camera.updateProjectionMatrix();
  }

  // 标注锚点始终是房间坐标，只在 refreshLabels() 的投影边界转为 Three.js 坐标。
  function addLabel(label) {
    if (!labelLayer) return;
    const leader = document.createElementNS("http://www.w3.org/2000/svg", "line");
    leader.setAttribute("stroke", `#${label.color.toString(16).padStart(6, "0")}`);
    leader.setAttribute("stroke-width", "1");
    leader.setAttribute("opacity", ".65");
    labelLeaders.appendChild(leader);
    labelEntries.push({ ...label, leader, el: makeLabelElement(labelLayer, label) });
  }

  /** DOM 标注：每帧把房间锚点投影到屏幕像素。字号恒定。 */
  function refreshLabels() {
    if (!labelLayer || !labelEntries.length) return;
    const rect = canvas.getBoundingClientRect();
    camera.updateMatrixWorld(true);
    const shown = [];
    // 先摆房间标尺，再摆家具标注，使方位标尺位置稳定。
    const entries = [...labelEntries].sort((a, b) => Number(Boolean(b.key)) - Number(Boolean(a.key)));
    for (const entry of entries) {
      const projected = new THREE.Vector3(...roomToThree(...entry.anchor)).project(camera);
      const x = (projected.x * 0.5 + 0.5) * rect.width;
      const y = (-projected.y * 0.5 + 0.5) * rect.height;
      const visible = projected.z >= -1 && projected.z < 1 && x >= 0 && y >= 0 && x <= rect.width && y <= rect.height;
      entry.el.style.display = visible ? "block" : "none";
      entry.leader.style.display = "none";
      if (visible) shown.push({ entry, x, y, width: entry.el.offsetWidth, height: entry.el.offsetHeight, offset: entry.offset });
    }
    const positions = placeLabels(shown, rect.width, rect.height);
    for (const [i, position] of positions.entries()) {
      const { entry, x, y } = shown[i];
      entry.offset = position.offset;
      entry.el.style.transform = `translate(${Math.round(position.x)}px, ${Math.round(position.y)}px) translate(-50%,-50%)`;
      if (Math.hypot(...position.offset) > 6) {
        entry.leader.style.display = "block";
        entry.leader.setAttribute("x1", x);
        entry.leader.setAttribute("y1", y);
        entry.leader.setAttribute("x2", position.x);
        entry.leader.setAttribute("y2", position.y);
      }
    }
    drawAxisGizmo();
  }

  /** 右下角方位指示器：世界方向经相机真实投影后，以固定屏幕尺寸画出。 */
  function drawAxisGizmo() {
    if (!axisGizmo) return;
    const { ctx } = axisGizmo;
    const S = 96;
    const R = 30;
    ctx.clearRect(0, 0, S, S);
    ctx.save();
    ctx.translate(S * 0.46, S * 0.60);
    ctx.beginPath();
    ctx.arc(0, 0, 42, 0, Math.PI * 2);
    ctx.fillStyle = "rgba(8, 10, 20, 0.55)";
    ctx.fill();
    camera.updateMatrixWorld(true);
    // 相机的屏幕基：right / up（用真实矩阵列，不手写映射）
    const m = camera.matrixWorld;
    const col = (i) => new THREE.Vector3(m.elements[i * 4], m.elements[i * 4 + 1], m.elements[i * 4 + 2]).normalize();
    const right = col(0);
    const camUp = col(1);
    const toScreen = (dir) => ({ dx: dir.dot(right) * R, dy: -dir.dot(camUp) * R });
    ctx.lineWidth = 2.4;
    ctx.font = "700 11px Inter,Microsoft YaHei,sans-serif";
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    for (const [index, axis] of ROOM_AXES.entries()) {
      const { dx, dy } = toScreen(new THREE.Vector3(...roomToThree(...axis.direction)));
      const anchor = [0, 0.42, 0.82][index];
      ctx.strokeStyle = `#${axis.color.toString(16).padStart(6, "0")}`;
      ctx.fillStyle = ctx.strokeStyle;
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.lineTo(dx, dy);
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(dx, dy, 3.4, 0, Math.PI * 2);
      ctx.fill();
      // 标签沿箭头方向错开，避免三条挤在原点处
      ctx.fillText(axis.label, dx + anchor * 26 + 5, dy + anchor * 26);
    }
    ctx.fillStyle = "#f6efe4";
    ctx.beginPath();
    ctx.arc(0, 0, 2.8, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  function isElevation() {
    const [x, y, z] = threeToRoom(...camera.position.clone().sub(controls.target).toArray());
    return Math.abs(Math.atan2(z, Math.hypot(x, y))) < ELEVATION_PITCH;
  }

  /** 固定房间边线只在场景内容更新时构建。 */
  function buildOutline() {
    const { width } = content.userData.outline;
    content.add(lineSegments([
      ...roomToThree(0, 0, 0), ...roomToThree(width, 0, 0),
    ], 0x6b4e32));
  }

  /** 轴端点与标签共享房间坐标定义；实体网格仅在场景内容更新时构建。 */
  function buildAxes() {
    const { width, depth, height, axes } = content.userData.outline;
    const axesGroup = new THREE.Group();
    content.add(axesGroup);
    const radius = Math.max(12, Math.min(width, depth, height) * 0.006);
    const head = Math.max(70, Math.min(width, depth, height) * 0.032);
    for (const axis of axes) {
      const from = new THREE.Vector3(...roomToThree(...axis.from));
      const to = new THREE.Vector3(...roomToThree(...axis.to));
      const dir = to.clone().sub(from).normalize();
      const material = new THREE.MeshBasicMaterial({ color: axis.color });
      const shaftLength = from.distanceTo(to) - head;
      const shaft = new THREE.Mesh(new THREE.CylinderGeometry(radius, radius, shaftLength, 12), material);
      shaft.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir);
      shaft.position.copy(from).addScaledVector(dir, shaftLength / 2);
      shaft.userData.kind = null;
      axesGroup.add(shaft);
      const cone = new THREE.Mesh(new THREE.ConeGeometry(head * 0.45, head, 18), material);
      cone.quaternion.copy(shaft.quaternion);
      cone.position.copy(to).addScaledVector(dir, -head * 0.5);
      cone.userData.kind = null;
      axesGroup.add(cone);
      addLabel(axis);
    }
  }

  /**
   * 把当前的墙与相机喂给纯函数 wallVisibility()，再把结果写回材质。
   *
   * **加一层短时渐变**（约 150ms）：判据本身是二值的（`visible: !cameraOutside`），
   * 相机一越过阈值，墙就会在**某一帧**瞬间出现/消失。留下的墙是不透明的，
   * 渐变只发生在 0 和 1 之间。
   * 实测这一步没有掉帧（变化帧 16.4~17.0ms，与其它帧一致，着色器程序数恒为 5），
   * 所以那个"顿"是**画面突变**而不是卡顿。把突变摊成 150ms 的过渡即可。
   * 墙一律用 `opacity` 表达（不靠 visible 开关）。落到不透明才写入深度，
   * 渐变中途的半透明墙不会把后面的家具从深度缓冲里抠掉。
   */
  function refreshWalls() {
    if (!wallShells.length) return;
    const geometry = wallShells.map((wall) => ({
      id: wall.userData.wallId,
      center: [wall.userData.wallCenter.x, wall.userData.wallCenter.y, wall.userData.wallCenter.z],
      normal: [wall.userData.wallNormal.x, wall.userData.wallNormal.y, wall.userData.wallNormal.z],
    }));
    // 相机刚被 setView 挪过时世界矩阵还是旧的，getWorldDirection 会给出上一次的朝向
    camera.updateMatrixWorld(true);
    camera.getWorldDirection(wallViewDirection);
    const result = wallVisibility(
      geometry,
      [camera.position.x, camera.position.y, camera.position.z],
      [wallViewDirection.x, wallViewDirection.y, wallViewDirection.z],
      { elevation: isElevation() },
    );
    const now = Date.now();
    const targets = result.walls.map((state) => (state.visible ? state.opacity : 0));
    if (!wallFade.length) {
      // 首帧：直接落到目标（否则一进页面墙会从 0 淡入）
      wallFade = [...targets];
      wallFadeTargets = [...targets];
      wallFadeStarted = 0;
    } else {
      // 目标变了就重开一趟渐变，起点取**当前**透明度。
      // 注意：**必须按"距开头的时间"算，不能按"距上一帧的时间"逐帧累乘**——
      // 逐帧累乘是渐近的，永远到不了目标（实测停在 0.05），
      // 而且相机一停 tick 就不再重绘，渐变会冻结在中间值，留下一面淡淡的墙。
      let changed = false;
      for (let i = 0; i < targets.length; i += 1) {
        if (Math.abs(targets[i] - wallFadeTargets[i]) > 1e-4) changed = true;
      }
      if (changed || wallFadeStarted === 0) {
        wallFadeFrom = [...wallFade];
        wallFadeTargets = [...targets];
        wallFadeStarted = now;
      }
      const t = Math.min(1, (now - wallFadeStarted) / WALL_FADE_MS);
      for (let i = 0; i < wallFade.length; i += 1) {
        wallFade[i] = wallFadeFrom[i] + (wallFadeTargets[i] - wallFadeFrom[i]) * t;
      }
      if (t >= 1) wallFadeStarted = 0;
    }
    result.walls.forEach((state, index) => {
      const wall = wallShells[index];
      const opacity = wallFade[index];
      // 完全透明才真正不画；否则留着，让渐变可见
      wall.visible = opacity > 0.002;
      wall.userData.material.opacity = opacity;
      wall.userData.material.depthWrite = opacity >= 0.999;
      // 背景墙用更亮的暖石膏色。侧墙沿用材质上的浅暖色。留下的墙都不透明。
      wall.userData.material.color.setHex(state.color === null ? wall.userData.baseColor : state.color);
      for (const ink of wall.userData.inks) {
        ink.visible = wall.visible;
        ink.material.opacity = Math.min(1, opacity * 1.35);
        ink.material.depthWrite = opacity >= 0.999;
      }
    });
  }

  /** 墙的渐变是否还没跑完（tick 据此继续重绘，否则渐变会冻结在中间值）。 */
  function wallFadeRunning() {
    return wallFadeStarted !== 0;
  }

  function resize() {
    const width = canvas.clientWidth || 960;
    const height = canvas.clientHeight || 600;
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    renderer.setPixelRatio(ratio);
    renderer.setSize(width, height, false);
    camera.aspect = width / Math.max(height, 1);
    camera.updateProjectionMatrix();
  }

  function clientNdc(clientX, clientY) {
    const rect = canvas.getBoundingClientRect();
    ndc.x = ((clientX - rect.left) / rect.width) * 2 - 1;
    ndc.y = -((clientY - rect.top) / rect.height) * 2 + 1;
  }

  /** 相机到目标的距离下限 = 房间对角线。低于它相机就进到房间里了——
   *  一旦进入房间，近端的地板边会画到墙顶之上（看起来像"平面上多了一个更高的线框"），
   *  而且随手一拖就冲进室内，视角会"不可控"。这条下限在 sync() 里按房间尺寸算一次。 */
  function applyRoomLimits() {
    const diagonal = content.userData.roomDiagonal || 0;
    controls.minDistance = Math.max(200, diagonal);
  }

  function setView(yaw, pitch, distance, target) {
    const position = cameraThreePosition(yaw, pitch, distance, target);
    camera.position.set(position[0], position[1], position[2]);
    controls.target.set(...roomToThree(...target));
    camera.up.set(0, 1, 0);
    camera.lookAt(controls.target);
    controls.maxDistance = Math.max(distance * 6, 8000);
    applyRoomLimits();
    controls.update();
    refreshWalls();
    refreshLabels();
  }

  function readView() {
    const offset = camera.position.clone().sub(controls.target);
    const [east, south, up] = threeToRoom(...offset.toArray());
    const horizontal = Math.hypot(east, south);
    return {
      yaw: Math.atan2(south, east),
      pitch: Math.atan2(up, horizontal),
      distance: offset.length(),
      target: threeToRoom(...controls.target.toArray()),
    };
  }

  function basis() {
    camera.updateMatrixWorld(true);
    const right = new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 0);
    const up = new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 1);
    const forward = new THREE.Vector3();
    camera.getWorldDirection(forward);
    return {
      position: threeToRoom(...camera.position.toArray()),
      fov: camera.fov,
      forward: threeToRoom(...forward.toArray()),
      right: threeToRoom(...right.toArray()),
      up: threeToRoom(...up.toArray()),
    };
  }

  function project(x, y, z) {
    const projected = new THREE.Vector3(...roomToThree(x, y, z)).project(camera);
    const rect = canvas.getBoundingClientRect();
    return {
      x: (projected.x * 0.5 + 0.5) * rect.width,
      y: (-projected.y * 0.5 + 0.5) * rect.height,
      depth: projected.z,
    };
  }

  function ground(clientX, clientY) {
    clientNdc(clientX, clientY);
    raycaster.setFromCamera(ndc, camera);
    const hit = raycaster.ray.intersectPlane(floor, hitPoint);
    if (!hit) return null;
    return threeToRoom(...hit.toArray()).slice(0, 2);
  }

  function pick(clientX, clientY) {
    clientNdc(clientX, clientY);
    raycaster.setFromCamera(ndc, camera);
    const hits = raycaster.intersectObjects(pickables, false);
    if (!hits.length) return null;
    const data = hits[0].object.userData;
    return data && data.kind ? { kind: data.kind, itemId: data.itemId } : null;
  }

  /**
   * 绘制。**全程只有一个透视相机**，不做投影切换，也不做两遍叠加。
   *
   * 曾经试过"正视图换正交相机"和"两遍渲染做渐变"，都放弃了：
   * 正交与透视的画面必然不同，只要切换那一下就会被看到；
   * 而两遍叠加时，房间的墙是**半透明**的，会在两个略微错开的位置各混合一次、
   * 墙面上出现两道错开的边——那是两遍混合与透视墙设计的固有冲突，调参数解决不了。
   * 现在正视图靠"相机拉远 + fov 同比例收窄"逼近正交，没有切换，也就没有那一下。
   */
  function draw() {
    sky.position.copy(controls.target);
    renderer.autoClear = true;
    renderer.render(scene, camera);
  }

  /** 倍率控制视场角；相机距离只随透视收窄倍数改变，不随滚轮进入房间。 */
  function setFovForZoom(zoom) {
    const z = Math.max(0.02, Number(zoom) || 1);
    setLens(cameraFov(z));
  }

  /** 正视图把相机拉远的倍数；页面用它乘取景距离。 */
  function elevationPull() {
    return ELEVATION_PULL;
  }

  function sync(data, options) {
    const room = data.room;
    const selectedId = options.selectedId;
    const readOnly = options.readOnly;
    const dimsMode = options.dims === false ? "off" : (options.dims || "selected");
    disposeObject(content);
    content.clear();
    wallFade = [];               // 墙是新对象，旧的渐变状态作废
    wallFadeFrom = [];
    wallFadeTargets = [];
    wallFadeStarted = 0;
    pickables = [];
    // 标注层也要跟着重建：DOM 元素不是 three 对象，content.clear() 不会清掉它们
    for (const entry of labelEntries) entry.el.remove();
    labelEntries = [];
    labelLayer = labelLayer || ensureLabelLayer(canvas);
    if (!labelLeaders && labelLayer) {
      labelLeaders = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      labelLeaders.setAttribute("aria-hidden", "true");
      labelLeaders.style.cssText = "position:absolute;inset:0;width:100%;height:100%;overflow:hidden";
      labelLayer.prepend(labelLeaders);
    }
    if (labelLeaders) labelLeaders.replaceChildren();
    if (!axisGizmo && labelLayer) {
      axisGizmo = makeAxisGizmo();
      labelLayer.parentElement.appendChild(axisGizmo.el);
    }
    const width = room.width_mm;
    const depth = room.depth_mm;
    const height = room.height_mm;
    roomKey.position.set(...roomToThree(width * 0.15, depth * 1.35, height * 2.4));
    moon.position.set(...roomToThree(-width, -depth * 0.4, height * 4));
    addDiorama(content, width, depth);
    const boards = woodTexture();
    boards.repeat.set(Math.max(width / 700, 1), Math.max(depth / 700, 1));
    const floorMesh = markRoom(new THREE.Mesh(
      new THREE.PlaneGeometry(width, depth),
      celMaterial(0xffffff, { map: boards }),
    ));
    floorMesh.rotation.x = -Math.PI / 2;
    floorMesh.position.set(...roomToThree(width / 2, depth / 2, 0));
    content.add(floorMesh);
    addInk(floorMesh, 0x6b4e32);
    const lamp = new THREE.Mesh(
      new THREE.SphereGeometry(Math.min(width, depth) * 0.025, 16, 12),
      new THREE.MeshBasicMaterial({ color: 0xfff1d4 }),
    );
    lamp.position.set(...roomToThree(width / 2, depth / 2, Math.max(height - 180, height * 0.72)));
    content.add(lamp);
    const pool = new THREE.Mesh(
      new THREE.CircleGeometry(Math.min(width, depth) * 0.22, 28),
      new THREE.MeshBasicMaterial({
        color: 0xffd7a1,
        transparent: true,
        opacity: 0.32,
        side: THREE.DoubleSide,
        depthWrite: false,
      }),
    );
    pool.rotation.x = -Math.PI / 2;
    pool.position.set(...roomToThree(width / 2, depth / 2, 6));
    content.add(pool);
    const step = [200, 250, 500, 1000, 2000, 5000].find((value) => Math.max(width, depth) / value <= 14) || 5000;
    const grid = [];
    for (let x = step; x < width; x += step) grid.push(...roomToThree(x, 0, 2), ...roomToThree(x, depth, 2));
    for (let y = step; y < depth; y += step) grid.push(...roomToThree(0, y, 2), ...roomToThree(width, y, 2));
    if (grid.length) content.add(lineSegments(grid, 0xd7b48a, 0.28));
    // outline 内的几何和标注定义都使用房间坐标。
    content.userData.outline = {
      width, depth, height, axes: roomAxes(room),
    };
    // 相机到目标的距离下限用房间对角线：保证相机始终在房间外（见 applyRoomLimits）。
    content.userData.roomDiagonal = Math.hypot(width, depth, height);
    const wallMaterial = celMaterial(0xf4e0c8, {
      transparent: true,
      opacity: 1,
      depthWrite: true,
    });
    // 墙的显隐与透明度按人眼习惯逐帧算（见 wall_view.js）。
    // 每面墙是一组有厚度的盒子（见 wall_solid.js），共用一份材质。
    const shells = [];
    for (const solid of wallSolids(width, depth, height, data.openings || [])) {
      const material = wallMaterial.clone();
      const group = new THREE.Group();
      const inks = [];
      for (const box of solid.boxes) {
        const mesh = markRoom(addRoomBox(group, box, material));
        inks.push(addInk(mesh, 0x6a5344));
      }
      group.userData.material = material;
      group.userData.inks = inks;
      group.userData.wallCenter = new THREE.Vector3(...roomToThree(...solid.center));
      group.userData.wallNormal = new THREE.Vector3(...roomToThree(...solid.normal)).normalize();
      group.userData.wallId = solid.id;
      group.userData.baseColor = wallMaterial.color.getHex();
      shells.push(group);
      content.add(group);
    }
    wallMaterial.dispose();
    wallShells = shells;
    for (const opening of openingSolids(width, depth, data.openings || [])) {
      const windowGlow = opening.kind === "window";
      addRoomBox(
        content,
        insetOpening(opening.wall, opening.box),
        new THREE.MeshBasicMaterial({
          color: windowGlow ? 0xffe1b0 : 0xc4956a,
          transparent: true,
          opacity: windowGlow ? 0.94 : 0.88,
          side: THREE.DoubleSide,
        }),
      );
    }
    for (const obstacle of data.obstacles || []) {
      const obstacleMesh = markRoom(new THREE.Mesh(
        prismGeometry(obstacle.footprint, obstacle.z_start, obstacle.z_end),
        celMaterial(0xd98986),
      ));
      addInk(obstacleMesh, 0x6a3030);
      content.add(obstacleMesh);
    }
    for (const item of data.items || []) {
      const selected = item.id === selectedId;
      const blocked = selected && options.blockedId === item.id;
      // 页面边界已把规范字段转换成画布模型。
      const itemZStart = item.z_start, itemZEnd = item.z_end;
      const drewShape = (isFixedSofa(item) && addSofa(content, pickables, item, selected, blocked))
        || (isFixedCoffeeTable(item) && addCoffeeTable(content, pickables, item, selected, blocked));
      if (!drewShape) {
        const mesh = markRoom(new THREE.Mesh(
          prismGeometry(item.footprint, itemZStart, itemZEnd),
          celMaterial(furnitureColor(item, selected, blocked)),
        ));
        addInk(mesh, selected ? 0x6a4520 : INK);
        mesh.userData = { kind: "item", itemId: item.id };
        addMesh(content, mesh, pickables);
      }
      if (item.footprint.length >= 4) {
        const frontZ = (itemZStart + itemZEnd) / 2;
        const a = item.footprint[3];
        const b = item.footprint[2];
        content.add(line([
          roomToThree(a[0], a[1], frontZ),
          roomToThree(b[0], b[1], frontZ),
        ], 0x047857));
      }
      // 标注三态：'off' 不画 / 'selected' 只画选中件 / 'all' 全部（默认 selected）。
      // **必须放在 `if (!selected) continue` 之前**——"全部"模式正是在没选中时也要画，
      // 原先放在其后，导致"标注·全部"永远不生效。
      const dimMode = dimsMode === "off" ? "off" : (dimsMode === "all" ? "all" : (selected ? "selected" : "off"));
      if (dimMode !== "off" && (dimMode === "all" || selected)) {
        addDimensions(content, data, item, addLabel);
      }
      if (!selected) continue;
      const center = footprintCenter(item.footprint);
      if (!readOnly) {
        const fillsWall = item.placement && item.placement.fill;
        if (!fillsWall && item.footprint.length >= 4) {
          addRotateDial(content, pickables, item, (itemZStart + itemZEnd) / 2);
        }
        const heightHandle = new THREE.Mesh(
          new THREE.SphereGeometry(26, 16, 12),
          new THREE.MeshBasicMaterial({ color: 0x3b82f6 }),
        );
        heightHandle.position.set(...roomToThree(center[0], center[1], itemZEnd + 72));
        heightHandle.userData = { kind: "height", itemId: item.id };
        addMesh(content, heightHandle, pickables);
      }
    }
    refreshWalls();
    buildOutline();
    buildAxes();
    applyRoomLimits();
    refreshLabels();
    draw();
  }

  function setEnabled(enabled) {
    controls.enabled = enabled;
  }

  function setShiftPan(enabled) {
    controls.mouseButtons.LEFT = enabled ? THREE.MOUSE.PAN : THREE.MOUSE.ROTATE;
  }

  resize();
  // 近墙显隐要跟着相机走：转视角 / 缩放 / 平移都要重算，所以常驻一帧循环（只在相机动过时才画）
  let lastView = "";
  const viewKey = () => [
    camera.position.x, camera.position.y, camera.position.z,
    controls.target.x, controls.target.y, controls.target.z,
  ].map((value) => Math.round(value * 10)).join(",");
  const tick = () => {
    const key = viewKey();
    if (key !== lastView) {
      lastView = key;
      refreshWalls();
      refreshLabels();
      draw();
    } else if (wallFadeRunning()) {
      // 相机停了但墙的渐变还没跑完：继续重绘，否则渐变会冻结在中间值（留下一面淡淡的墙）。
      refreshWalls();
      draw();
    }
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);

  /**
   * `sync` 外面套一层"载荷签名"缓存。
   *
   * 为什么必须套：`sync()` 第一件事就是 `disposeObject(content)` + `content.clear()`，
   * 并把标注的 DOM 元素全部删掉重建。而**相机动画每帧都会调用 sync**——内容其实没变，
   * 却每秒重建 60 次几何体、材质和 DOM 节点。实测后果：切视角期间频繁掉帧
   * （真实窗口下 90 分位帧间隔 62~77ms，最大 120ms，约 14~21 次掉帧），而 WebGL 单帧只要 0.1ms。
   *
   * 签名只取"影响场景内容"的量（房间、家具、选中项、标注档位、只读、阻塞项），
   * **不含相机**——相机动了只需重画，不需要重建。签名变化时照旧全量重建。
   */
  let lastSyncKey = null;
  function syncCached(data, options) {
    const key = JSON.stringify([
      data && data.room, data && data.items, data && data.openings,
      options.selectedId, options.dims, options.readOnly, options.blockedId,
    ]);
    if (key === lastSyncKey) return false;
    lastSyncKey = key;
    sync(data, options);
    return true;
  }

  // 调试口：便于核对取景/绘制参数（renderer 用来统计每帧绘制次数）。
  window.__diag = { scene, camera, controls, content, renderer, syncCached };
  // 对外只暴露页面真正用到的接口。新增前先确认调用方存在——
  // 之前多导出了 lensBase / setLens / syncNow，页面一个都没用；
  // 其中 syncNow 还会绕过载荷缓存，谁用谁把每帧全量重建带回来（泄漏 + 掉帧）。
  return {
    controls, resize, setView, readView, basis, project, ground, pick, sync: syncCached, draw, setEnabled, setShiftPan,
    setFovForZoom, elevationPull,
  };
}

const DIAL_COLOR = 0xf5c400;

/** 高度正中两小段贴平的黄色圆弧箭头，相对而放，都顺着同一个转向。 */
function addRotateDial(parent, pickables, item, z) {
  const center = footprintCenter(item.footprint);
  const a = item.footprint[3];
  const b = item.footprint[2];
  let fx = (a[0] + b[0]) / 2 - center[0];
  let fy = (a[1] + b[1]) / 2 - center[1];
  const length = Math.hypot(fx, fy) || 1;
  fx /= length;
  fy /= length;
  const px = -fy;
  const py = fx;
  let radius = 160;
  for (const [x, y] of item.footprint) {
    radius = Math.max(radius, Math.hypot(x - center[0], y - center[1]));
  }
  const at = (angle, distance, height) => {
    const c = Math.cos(angle);
    const s = Math.sin(angle);
    return roomToThree(
      center[0] + (fx * c + px * s) * distance,
      center[1] + (fy * c + py * s) * distance,
      height,
    );
  };
  // 环和箭头留在外廓外面，高度取这件的正中，避免和柜体侧面叠在同一个面上。
  const band = Math.min(48, Math.max(18, radius * 0.04));
  const head = Math.min(120, Math.max(band * 2.6, radius * 0.12));
  const gap = 160;
  radius += gap + band / 2 + head * 0.72;
  const positions = [];
  const sweep = 0.72;
  const pushArrow = (mid) => {
    const steps = 8;
    const tail = mid - sweep / 2;
    const neck = mid + sweep / 2 - 0.26;
    for (let i = 0; i < steps; i += 1) {
      const a0 = tail + (neck - tail) * (i / steps);
      const a1 = tail + (neck - tail) * ((i + 1) / steps);
      const inner0 = at(a0, radius - band / 2, z);
      const outer0 = at(a0, radius + band / 2, z);
      const inner1 = at(a1, radius - band / 2, z);
      const outer1 = at(a1, radius + band / 2, z);
      positions.push(...inner0, ...outer0, ...outer1, ...inner0, ...outer1, ...inner1);
    }
    const tip = at(mid + sweep / 2, radius, z);
    const baseIn = at(neck, radius - head * 0.72, z);
    const baseOut = at(neck, radius + head * 0.72, z);
    positions.push(...tip, ...baseOut, ...baseIn);
  };
  pushArrow(Math.PI / 2);
  pushArrow(Math.PI * 1.5);
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  const arrow = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({
    color: DIAL_COLOR,
    side: THREE.DoubleSide,
    polygonOffset: true,
    polygonOffsetFactor: -1,
    polygonOffsetUnits: -1,
  }));
  arrow.userData = { kind: "rotate", itemId: item.id };
  addMesh(parent, arrow, pickables);

  const grab = new THREE.Mesh(
    new THREE.TorusGeometry(radius, band, 6, 64),
    new THREE.MeshBasicMaterial({ transparent: true, opacity: 0, depthWrite: false }),
  );
  grab.rotation.x = Math.PI / 2;
  grab.position.set(...roomToThree(center[0], center[1], z));
  grab.userData = { kind: "ring", itemId: item.id };
  addMesh(parent, grab, pickables);
}

function footprintCenter(footprint) {
  const count = footprint.length || 1;
  const points = footprint;
  return [
    points.reduce((sum, point) => sum + point[0], 0) / count,
    points.reduce((sum, point) => sum + point[1], 0) / count,
  ];
}

/** 尺寸线进入 Three.js 时转换；标签仍交接房间坐标。 */
function addDimensions(parent, data, item, onLabel) {
  for (const annotation of dimensionAnnotations(data.room, item)) {
    const dimension = line([
      roomToThree(...annotation.from), roomToThree(...annotation.to),
    ], annotation.color);
    // 标注覆盖家具表面，文字与量线始终能对应；仅影响标注，不改变实体遮挡。
    dimension.material.depthTest = false;
    dimension.material.depthWrite = false;
    dimension.material.transparent = true;
    dimension.material.opacity = .8;
    dimension.renderOrder = 10;
    parent.add(dimension);
    onLabel(annotation);
  }
}
