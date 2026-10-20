// 柜体结构视图：把板件阶段确认冻结的板件画成能转、能拆开看的盒子。
//
// 柜体坐标 = 阶段自己的坐标：X 宽（0→右）、Y 深（0→门那一面）、Z 高（0→顶）。
// three.js 是 Y 朝上，所以整组绕 X 转 -90°，组内直接用柜体坐标，不做逐块换算。
//
// 这里只画。数据由 cabinet_panel_page.py 从冻结文件投影好，页面通过 payload 递进来。

import * as THREE from "three";
import { OrbitControls } from "/vendor/three/0.186.0/OrbitControls.js";

// 材质：整台柜子只有两种材料——柜体一种木纹，门板白色纯色。
// 木纹是画出来的（画布程序纹理），不从服务器取图：这一页的 CSP 只允许 'self'。
const WOOD_BASE = 0xdcc09a;
const WOOD_SHELL = 0xc9ab86;
const WHITE_FACE = 0xf7f8fa;
// 板件轮廓线：深棕、不透明度 0.7。浅木色底上要看得清板与板的缝，靠的就是它。
const EDGE_COLOR = 0x5b4327;
const EDGE_OPACITY = 0.7;
const SELECT_COLOR = 0x1d4ed8;
const HOVER_COLOR = 0xf59e0b;
const FLOOR_COLOR = 0xdfe5ee;

// 木纹图：纹路是**沿贴图 u 轴**的一条条细线（y 固定，x 从画布左外连到右外）。
//
// 这条约定和板件阶段的 `_grain_uv()` 绑死：那个函数按「这个面的 u 轴是不是顺纹轴」
// 逐个面决定转不转。两边任何一个翻转，症状都是某一类板「纹理横竖不对」：
//   * 只翻贴图方向 → 顺着高的板件（侧板 / 背板）先错；
//   * 只翻旋转方向 → 顺着宽的板件（顶底 / 层板 / 踢脚）先错。
// 所以两处都各有一条测试钉住，改一处必须同步改另一处，并在页面上量一遍：
// 侧板与背板该是竖纹，顶底板 / 层板 / 踢脚板该是横纹。量法见
// `test_wood_grain_is_drawn_along_the_texture_u_axis` 的说明。
//
// 纹理外观是**固定的几张常量**，页面上不提供调节（预设、深浅、粗细那些只是看效果用的，
// 真正要改的是每块板的**顺纹方向**——那是板件的属性，见下面的 `grainEdits`）。
const GRAIN_CYCLE_MM = 220; // 与板件阶段的 `GRAIN_CYCLE_MM` 一致：一张图铺多长
const GRAIN_SIZE = 256; // 贴图边长（像素）。木纹是噪声，256 够用；调大更细也更费显存
const GRAIN_LINES = 12; // 220 / 12 ≈ 18mm 一道：有木纹的样子，也不至于糊成一团
const GRAIN_TONE = "#ddc19b"; // 底色（浅木）
const GRAIN_WIDTH = [2.4, 6.8]; // [最细, 最粗] 线宽（像素）
const GRAIN_DARK_INK = ["158,120,80", 0.16]; // 深纹：颜色 + 基础不透明度
const GRAIN_LIGHT_INK = ["255,248,234", 0.16]; // 浅纹：同上
const GRAIN_DARK_SHARE = 0.68; // 深色线占比
const GRAIN_JITTER = [5, 7, 24, 72]; // 横向 ±px、纵向 ±px、折点步长 [min, max] px
//: 随机种子。固定住 = 每次刷新画出同一张纹理，截图核对才对得上（别换回 `Math.random()`）。
const GRAIN_SEED = 20261016;

function clamp(value, low, high) {
  return Math.min(high, Math.max(low, value));
}

// 固定种子的伪随机：同一个种子永远画出同一张纹理（截图核对靠它）。
// 不用 `Math.random()`——那样每次刷新纹理都不同，两张截图对不上。
function makeRandom(seed) {
  let state = (seed >>> 0) || 1;
  return () => {
    state ^= state << 13;
    state >>>= 0;
    state ^= state >> 17;
    state ^= state << 5;
    state >>>= 0;
    return state / 4294967296;
  };
}

// 往画布上画木纹。纹路是**沿贴图 u 轴**的一条条横线（y 固定、x 一路延伸），
// 面转不转由板件阶段按「这个面的 u 是不是顺纹轴」定（`_grain_uv()`）。
function paintGrain(canvas) {
  const context = canvas.getContext("2d");
  if (!context) throw new Error("2d context unavailable");
  const random = makeRandom(GRAIN_SEED);
  context.fillStyle = GRAIN_TONE;
  context.fillRect(0, 0, GRAIN_SIZE, GRAIN_SIZE);
  for (let index = 0; index < GRAIN_LINES; index += 1) {
    const y = ((index + 0.5) * GRAIN_SIZE) / GRAIN_LINES + (random() - 0.5) * GRAIN_JITTER[0];
    const ink = random() < GRAIN_DARK_SHARE ? GRAIN_DARK_INK : GRAIN_LIGHT_INK;
    context.strokeStyle = `rgba(${ink[0]},${(ink[1] + random() * 0.2).toFixed(3)})`;
    context.lineWidth = GRAIN_WIDTH[0] + random() * (GRAIN_WIDTH[1] - GRAIN_WIDTH[0]);
    context.beginPath();
    context.moveTo(-10, y + (random() - 0.5) * 2);
    let x = 0;
    while (x < GRAIN_SIZE + 10) {
      x += GRAIN_JITTER[2] + random() * (GRAIN_JITTER[3] - GRAIN_JITTER[2]);
      context.lineTo(x, y + (random() - 0.5) * GRAIN_JITTER[1]);
    }
    context.stroke();
  }
}

function makeWoodTexture() {
  const canvas = document.createElement("canvas");
  canvas.width = GRAIN_SIZE;
  canvas.height = GRAIN_SIZE;
  paintGrain(canvas);
  return canvas;
}

function textureFromCanvas(canvas) {
  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 4;
  texture.center.set(0.5, 0.5); // 每个面的旋转都绕贴图中心，转完还铺满整面
  return texture;
}

function materialFor(kind, texture) {
  // **不要 DoubleSide**：板件之间的接缝面本来就是共面的（层板端面贴着中立板、
  // 底板贴着侧板……），双面渲染会让这对共面三角形同时参与深度测试，转一下就闪。
  // 盒子是闭合体，只看外面用默认的 FrontSide 就够。
  // `polygonOffset` 往后退一点，让描边线（贴着板面画的那圈）稳稳压在上面，
  // 否则线与面同深度，也会闪。
  const base = {
    roughness: 0.72,
    metalness: 0.0,
    polygonOffset: true,
    polygonOffsetFactor: 1,
    polygonOffsetUnits: 1,
  };
  if (kind === "white") {
    return new THREE.MeshStandardMaterial({
      ...base,
      color: WHITE_FACE,
      roughness: 0.34,
    });
  }
  return new THREE.MeshStandardMaterial({ ...base, color: WOOD_BASE, map: texture });
}

// 环顾一圈的方向（three.js 坐标，已经含 Z 朝上 → Y 朝上的那次旋转）。

export function formatMm(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  const rounded = Math.round(number);
  if (Math.abs(number - rounded) < 1e-6) return String(rounded);
  return number.toFixed(1);
}

export function triple(values) {
  return values.map(formatMm).join(" × ");
}

export function panelCounts(panels) {
  const counts = {};
  for (const panel of panels) {
    counts[panel.assembly] = (counts[panel.assembly] || 0) + 1;
  }
  return counts;
}

// 页面上材料只有两种，图例也照这个来。
const MATERIAL_LABELS = { wood: "柜体木纹", white: "门板白色" };

export function materialLabel(material) {
  return MATERIAL_LABELS[material] || "柜体木纹";
}

// 顺纹方向：柜体坐标里的轴。规则与判据在板件阶段的 `grain_rules.py`。
// `y`（沿深）不在默认表里，但订单可以特意改成它——所以标签必须认全，不能漏。
const GRAIN_LABELS = { x: "沿宽", y: "沿深", z: "沿高", none: "不限" };

export function grainLabel(axis) {
  return GRAIN_LABELS[axis] || `未知(${axis})`;
}

// 环顾一圈的方向（three.js 坐标，已经含 Z 朝上 → Y 朝上的那次旋转）。
//
// 换算关系是 `世界 = (柜宽 − 柜X, 柜Z, -柜Y)`，其中 x 那次**镜像**是必须的：
// 柜体坐标是「X 宽向右、Y 朝门、Z 朝上」，而站在门前看（门朝你），右手系里
// 柜体 +X 必然落在人的**左手边**——数据却把低 X 叫 `left_side_panel`。不镜像的话
// 整台柜子在页面上是反的：左侧板画在右边，`hinge_side="left"` 的门开到右边。
// 所以这里按「低 X = 屏幕左」渲染；柜宽中点是不动点，取景中心不受影响。
//
// **柜体 +Y（门那一面）在世界里是 -Z**：「正面（门）」必须站在 -Z 看，站到 +Z
// 看到的是背板。这两个弄反的话，人会以为门板没画出来（实测踩过）。
// 镜像之后，「左侧」= 从 +X 看、「右侧」= 从 -X 看。
const VIEWS = {
  iso: [-0.78, 0.62, -0.86],
  front: [0, 0.22, -1.25],
  back: [0, 0.22, 1.25],
  left: [1.25, 0.22, -0.08],
  right: [-1.25, 0.22, -0.08],
  top: [0, 1.35, -0.28],
};

export function mountCabinetStructure(options) {
  const {
    canvas,
    payload,
    hover = null,
    summary = null,
    count = null,
    rows = null,
    detail = null,
    filters = [],
    viewButtons = [],
    toggles = {},
    panelSave = {},
  } = options;

  const panelList = Array.isArray(payload.panels) ? payload.panels : [];
  const envelope = payload.envelope_mm || {};
  const width = Number(envelope.width) || 1;
  const depth = Number(envelope.depth) || 1;
  const height = Number(envelope.height) || 1;
  const center = new THREE.Vector3(width / 2, depth / 2, height / 2);
  const modelRadius = 0.5 * Math.hypot(width, depth, height);
  // 整台柜子进镜头要多少距离：把八个角投到「右 / 上 / 沿视线」三个轴上再解。
  // 用外接球（半径 × 常数）会算得过远——球把柜子外面的空处也算进去了。
  //
  // **取景一律用世界坐标**（`world = (柜宽−柜X, 柜Z, -柜Y)`，含那次镜像），和 VIEWS
  // 同一套；柜体坐标和世界坐标差着一次镜像加一次 Z→Y 的旋转，混着用会瞄错方向（实测踩过）。
  // 柜宽中点是镜像的不动点，所以取景中心还是 (宽/2, 高/2, -深/2)。
  const centerWorld = new THREE.Vector3(width / 2, height / 2, -depth / 2);
  const CORNERS = [];
  for (const x of [0, width]) {
    for (const y of [0, depth]) {
      for (const z of [0, height]) {
        CORNERS.push(new THREE.Vector3(width - x, z, -y));
      }
    }
  }
  const MIN_ASPECT = 1.0;
  // 画面基向量。所有预设视角都不是正俯视（Y 分量远小于 1），所以上方向稳定取世界 +Y。
  const HALF_TAN_V = Math.tan(((38 * Math.PI) / 180) / 2);
  const FIT_UP = [0, 1, 0];

  // 每个角单独解：「相机要退到多远，这个角才落在画面里」。
  // `direction` 是相机→目标的单位向量，所以角在相机前方时 `-(角·direction)` 为正；
  // 这个数越小说明角离相机越近、张角越大，要的余量也越多。取八个角里最大的。
  // 判据是 `|右分量| ≤ halfTanH · (distance − depth)`，上分量同理。
  function fitDistanceFor(direction, aspect) {
    const right = [
      FIT_UP[1] * direction[2] - FIT_UP[2] * direction[1],
      FIT_UP[2] * direction[0] - FIT_UP[0] * direction[2],
      FIT_UP[0] * direction[1] - FIT_UP[1] * direction[0],
    ];
    const rightLength = Math.hypot(right[0], right[1], right[2]) || 1;
    for (let index = 0; index < 3; index += 1) right[index] /= rightLength;
    const up = [
      direction[1] * right[2] - direction[2] * right[1],
      direction[2] * right[0] - direction[0] * right[2],
      direction[0] * right[1] - direction[1] * right[0],
    ];
    const halfTanH = HALF_TAN_V * Math.max(aspect, MIN_ASPECT);
    let needed = 0;
    for (const corner of CORNERS) {
      const depth = -(
        corner.x * direction[0] + corner.y * direction[1] + corner.z * direction[2]
      );
      const horizontal = Math.abs(
        corner.x * right[0] + corner.y * right[1] + corner.z * right[2]
      );
      const vertical = Math.abs(
        corner.x * up[0] + corner.y * up[1] + corner.z * up[2]
      );
      needed = Math.max(
        needed,
        depth + vertical / HALF_TAN_V,
        depth + horizontal / halfTanH
      );
    }
    return needed * 1.04;
  }

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0xeef1f6);
  const camera = new THREE.PerspectiveCamera(38, 1, 1, 200000);
  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.dampingFactor = 0.09;

  const root = new THREE.Group();
  root.rotation.x = -Math.PI / 2; // 柜体坐标 → three.js 坐标
  scene.add(root);

  scene.add(new THREE.AmbientLight(0xffffff, 0.88));
  const hemisphere = new THREE.HemisphereLight(0xffffff, 0x9aa5b4, 0.6);
  scene.add(hemisphere);
  // 前后各一盏：门那一面（世界 -Z）和背面都要看得清，不然浅木纹在正面会是灰的。
  // 世界坐标里柜体的「前」是 -Z，所以前光放在 -Z、后光放在 +Z。
  const sun = new THREE.DirectionalLight(0xffffff, 1.0);
  sun.position.set(modelRadius * 1.2, modelRadius * 2.0, -modelRadius * 1.8);
  scene.add(sun);
  const fill = new THREE.DirectionalLight(0xffffff, 0.6);
  fill.position.set(-modelRadius * 1.0, modelRadius * 0.9, modelRadius * 1.6);
  scene.add(fill);
  // 跟着相机走的补光：转到哪一面，那一面就有一点直射光。没有它，不看光的那一面
  // （比如默认视角下的门）会暗成灰的，白色门板看不出白。
  const headlamp = new THREE.PointLight(0xffffff, 0.55, 0, 0);
  headlamp.position.set(0, 0, 0);
  scene.add(headlamp);

  const floor = new THREE.Mesh(
    new THREE.PlaneGeometry(width * 2.6, depth * 2.6),
    new THREE.MeshBasicMaterial({ color: FLOOR_COLOR, transparent: true, opacity: 0.75 })
  );
  floor.position.set(width / 2, depth / 2, -2);
  root.add(floor);

  const boxGeometry = new THREE.BoxGeometry(1, 1, 1);
  const edgeGeometry = new THREE.EdgesGeometry(boxGeometry);

  // 板件的种类只看 payload 里的 `panel_type`（`cabinet_panel_page.py` 给的那个字段）。
  // 这里曾经读 `panel.group`——payload 里从来没有这个字段，于是「门板」「背板」两个开关
  // 和透视都作用在 `undefined` 上，等于没接线（页面上按了没反应）。改字段前先看投影。
  const FRONT_TYPES = new Set(["door", "drawer_front"]);
  const BACK_TYPES = new Set(["back", "back_rail"]);

  // 开门最多转到 85°：转到 90° 时门板和侧板共面，看着像一块贴片，也和「拆开」分不清。
  const MAX_OPEN = Math.PI * 0.5 * 0.95;

  const isFrontPanel = (panel) => FRONT_TYPES.has(panel.panel_type);

  // 材料只有两种，所以「白色」直接用投影给的材料名。
  const isWhitePanel = (panel) => panel.material === "white";

  // 每块板错开一点贴图原点用的随机数：也跟着种子走，所以同一份配置画出来完全一样。
  const grainRandom = makeRandom(GRAIN_SEED ^ 0x9e3779b9);
  const grainCanvas = makeWoodTexture();
  const woodTexture = textureFromCanvas(grainCanvas);
  const meshes = [];
  for (const panel of panelList) {
    const [sx, sy, sz] = panel.size_mm.map(Number);
    const [px, py, pz] = panel.pos_mm.map(Number);
    const white = isWhitePanel(panel);
    const material = materialFor(panel.material, woodTexture);
    if (!white) {
      // 一块板一份贴图：整台柜子共用一张图的话，每块板的花纹位置会一模一样。
      // 怎么转、每个面铺几遍都由投影算好（`grain.faces`，键是板件六个面的名字）：
      // 木纹在图上沿贴图的 u 轴画，面转不转由板件阶段按「u 是不是顺纹轴」定。
      // 规则与换算在 `panel_grain_axis()` / `_grain_uv()`，这里只照着摆。
      // 克隆共用同一张画布，所以纹理只画一次、每块板只错开原点。
      const map = material.map.clone();
      map.rotation = panel.grain.rotation;
      // 每块板错开一点贴图原点，花纹才不会块块对齐得像印刷品。
      map.offset.set(grainRandom() * 0.5, grainRandom() * 0.5);
      material.map = map;
    }
    const mesh = new THREE.Mesh(boxGeometry, material);
    mesh.scale.set(sx, sy, sz);
    // 世界 x 是镜像过的（柜宽 − 柜X）：低 X 落在屏幕左侧，见文件顶部 VIEWS 的说明。
    const home = new THREE.Vector3(width - (px + sx / 2), py + sy / 2, pz + sz / 2);
    mesh.position.copy(home);
    const edges = new THREE.LineSegments(
      edgeGeometry,
      new THREE.LineBasicMaterial({ color: EDGE_COLOR, transparent: true, opacity: EDGE_OPACITY })
    );
    edges.scale.copy(mesh.scale);
    edges.position.copy(home);
    const record = {
      panel,
      mesh,
      edges,
      material,
      home,
      exploded: new THREE.Vector3(),
      // 本色与那张木纹图：悬停/选中时把 map 摘掉，回到纯色才不会花。
      baseColor: white ? WHITE_FACE : WOOD_BASE,
      woodMap: white ? null : material.map,
      // 这块板六个面各铺几遍、朝哪转（由投影给）。见 `paint()`。
      grainFaces: white ? null : panel.grain.faces,
      // 最大面的名字（投影给的是**面名**，不是那个面的数据）：不指着某块板时按它铺。
      homeFace: white ? null : panel.grain.home,
      edgeMaterial: edges.material,
    };
    record.exploded.copy(home).sub(center);
    if (record.exploded.lengthSq() < 1e-9) record.exploded.set(0, 0, 1);
    record.exploded.normalize().multiplyScalar(0.35 * modelRadius + 0.5 * Math.max(sx, sy, sz));
    record.exploded.add(home);
    mesh.userData.record = record;
    root.add(mesh);
    root.add(edges);
    meshes.push(record);
  }

  const state = {
    visible: true,
    doors: true,
    back: true,
    wire: false,
    explode: 0,
    // 开门角度（0–1），只作用在有铰链侧的门上。
    open: 0,
    hovered: null,
    // 鼠标压在哪一块板的哪一个面上（'px'/'nx'/'py'/'ny'/'pz'/'nz'）。只看方向，不看位置。
    hoverFace: null,
    selected: null,
  };

  // 开关作用在哪些板上：门板 / 抽屉面一组，背板 / 背拉条一组。
  const isSuppressed = (panel) =>
    (!state.doors && isFrontPanel(panel)) || (!state.back && BACK_TYPES.has(panel.panel_type));

  // 三种状态：本色（木纹或白门）、悬停（描边琥珀 + 一点自发光）、选中（描边蓝 + 自发光）。
  // **不换掉 `map`**：纹理要一直看得见，否则点一块板就看不见它的纹理方向了（踩过）。
  const LOOK = {
    normal: { emissive: 0x000000, emissiveIntensity: 1, edge: EDGE_COLOR, edgeOpacity: EDGE_OPACITY },
    hover: { emissive: 0x8a4d00, emissiveIntensity: 0.22, edge: HOVER_COLOR, edgeOpacity: 1 },
    select: { emissive: SELECT_COLOR, emissiveIntensity: 0.1, edge: SELECT_COLOR, edgeOpacity: 1 },
  };

  function paint() {
    for (const record of meshes) {
      const { panel } = record;
      const shape = panel.size_mm;
      record.mesh.scale.set(shape[0], shape[1], shape[2]);
      record.edges.scale.copy(record.mesh.scale);
      const position = state.explode > 0
        ? record.home.clone().lerp(record.exploded, state.explode)
        : record.home.clone();
      record.mesh.position.copy(position);
      record.edges.position.copy(position);

      // 开门：绕门的一条竖边转。**柜体数据的左右和屏幕相反**（世界 x 镜像过），
      // 所以「左开＝铰链在柜体低 X 那条边＝屏幕上看到的左边」。绕 z 轴转，
      // 门心相对铰链边的偏移是半个门宽；往柜外（+Y，也就是朝人）转。
      // 铰链侧由**板件阶段**给（`hinge_side`）；没给的门不动——它还没定
      // 往哪边开，按门序猜一个就是替人做决定。
      const hinge = hingeSideOf(panel);
      let angle = 0;
      if ((hinge === "left" || hinge === "right") && state.open > 0) {
        angle = (hinge === "left" ? -1 : 1) * state.open * MAX_OPEN;
      }
      if (angle !== 0) {
        // 铰链边在门心哪一侧：左开在世界 x 的**大**的一侧（镜像后）。
        const arm = (hinge === "left" ? 1 : -1) * (shape[0] / 2);
        // 铰链轴跟着「拆开」一起位移，否则门会绕着空气转。
        const pivotX = record.home.x + arm + (position.x - record.home.x);
        const cos = Math.cos(angle);
        const sin = Math.sin(angle);
        position.set(pivotX - arm * cos, position.y - arm * sin, position.z);
        record.mesh.position.copy(position);
        record.edges.position.copy(position);
      }
      record.mesh.rotation.z = angle;
      record.edges.rotation.z = angle;

      const suppressed = isSuppressed(panel);
      record.mesh.visible = state.visible && !suppressed;
      record.edges.visible = state.visible && !suppressed;

      const inFilter = state.filter ? state.filter(panel) : true;
      record.mesh.visible = record.mesh.visible && inFilter;
      record.edges.visible = record.edges.visible && inFilter;

      // 透视只把**正面**（门板 / 抽屉面）变透，柜体和层板保持不透明：想让里面看得见，
      // 只需要让挡在前面的那一层让路。全都变透反而互相穿透，什么也看不清。
      const faded = state.wire && isWhitePanel(panel);
      const selected = panel.id === state.selected;
      const hovered = panel.id === state.hovered;
      const look = selected ? LOOK.select : hovered ? LOOK.hover : LOOK.normal;
      const highlighted = selected || hovered;

      // 换到哪个面就看哪个面的重复次数。盒子的六个面各有各的 (u, v) 轴，同一块板上
      // 「大面」和「小边」的尺寸差十倍，用同一组重复次数必然有一面被拉成条纹。
      // 鼠标停在某块板上时，整体按它那个面的数铺——旁边一块板可能跟着变一下比例，
      // 停手就复原；换来的是「手指哪儿，哪儿的纹理就是对的」。
      //
      // 重复次数改的是**那张木纹图**，所以不看 `material.map` 当前挂没挂：悬停/选中时
      // map 会被摘掉回到纯色，若用 `material.map` 当条件，手指到哪块板，那块板的
      // 比例就停在最后一次没被高亮时的数（踩过）。
      if (record.grainFaces) {
        const face = panel.id === state.hovered ? state.hoverFace : null;
        const target = (face && record.grainFaces[face]) || record.grainFaces[record.homeFace];
        record.woodMap.repeat.fromArray(target.repeat);
      }

      // 悬停 / 选中**保留木纹**，只加自发光并把描边换成醒目色。
      //
      // 原来这里是把 `map` 摘掉、整块涂成纯色——点一块板就看不见它的纹理了，
      // 而"点板件 = 翻纹理"正是靠看纹理才能确认，于是现象成了「只有文字变了」。
      record.material.map = isWhitePanel(panel) ? null : record.woodMap;
      record.material.color.setHex(record.baseColor);
      record.material.emissive.setHex(highlighted ? look.emissive : 0x000000);
      record.material.emissiveIntensity = highlighted ? look.emissiveIntensity : 1;
      record.material.transparent = faded;
      record.material.opacity = faded ? 0.22 : 1;
      record.material.depthWrite = !faded;

      record.edgeMaterial.color.setHex(highlighted ? look.edge : EDGE_COLOR);
      record.edgeMaterial.opacity = Math.min(1, highlighted ? look.edgeOpacity : EDGE_OPACITY);
    }
  }

  function draw() {
    const size = canvas.clientWidth || 960;
    const other = canvas.clientHeight || 640;
    renderer.setSize(size, other, false);
    camera.aspect = size / Math.max(other, 1);
    camera.updateProjectionMatrix();
    controls.update();
    // 补光吊在相机与目标之间、偏相机那一侧，跟着转。
    headlamp.position
      .copy(camera.position)
      .lerp(controls.target, 0.35)
      .sub(controls.target)
      .multiplyScalar(0.75)
      .add(controls.target);
    renderer.render(scene, camera);
    requestAnimationFrame(draw);
  }

  function setView(name) {
    const raw = VIEWS[name] || VIEWS.iso;
    // 方向只取朝向，距离由 distance 单独定——不归一化的话每个视角离得远近会不一样。
    const length = Math.hypot(raw[0], raw[1], raw[2]) || 1;
    const direction = [raw[0] / length, raw[1] / length, raw[2] / length];
    const canvasAspect =
      (canvas.clientWidth || 960) / Math.max(canvas.clientHeight || 640, 1);
    const distance = fitDistanceFor(direction, canvasAspect);
    camera.position.set(
      centerWorld.x + direction[0] * distance,
      centerWorld.y + direction[1] * distance,
      centerWorld.z + direction[2] * distance
    );
    // 近平面跟着取景距离走。固定 `near = 1` 而 `far` 是几万，深度精度全耗在近处，
    // 远处相邻两张面就会打架——转起来是"闪烁/起条纹"。按距离给 near，精度能好几倍。
    camera.near = Math.max(1, distance / 1000);
    camera.far = distance * 6;
    camera.updateProjectionMatrix();
    controls.target.copy(centerWorld);
    controls.update();
    for (const button of viewButtons) {
      button.setAttribute("aria-pressed", String(button.dataset.view === name));
    }
  }

  // 按钮与代码走同一条路：显示开关只有这一处实现，别在界面上再改一遍状态。
  function setDoors(on) {
    state.doors = on;
    if (toggles.doors) toggles.doors.setAttribute("aria-pressed", String(on));
    paint();
  }

  function setBack(on) {
    state.back = on;
    if (toggles.back) toggles.back.setAttribute("aria-pressed", String(on));
    paint();
  }

  function setWire(on) {
    state.wire = on;
    if (toggles.wire) toggles.wire.setAttribute("aria-pressed", String(on));
    paint();
  }

  function setExplode(percent) {
    state.explode = percent / 100;
    if (toggles.explode) toggles.explode.value = String(percent);
    paint();
  }

  function setOpen(percent) {
    state.open = percent / 100;
    if (toggles.open) toggles.open.value = String(percent);
    paint();
  }

  function toggle(what) {
    if (what === "doors") setDoors(!state.doors);
    else if (what === "back") setBack(!state.back);
    else if (what === "wire") setWire(!state.wire);
    else throw new Error(`unknown toggle: ${what}`);
  }

  function renderRows() {
    if (!rows) return;
    rows.replaceChildren();
    for (const panel of panelList) {
      const row = document.createElement("tr");
      row.dataset.panel = panel.id;
      row.setAttribute("aria-selected", "false");
      row.title = panel.role || panel.panel_type;
      const nameCell = document.createElement("td");
      const dot = document.createElement("span");
      dot.className = `dot ${panel.material === "white" ? "white" : "wood"}`;
      nameCell.append(dot, document.createTextNode(panel.name));
      const role = document.createElement("div");
      role.className = "role";
      role.textContent = panel.role || panel.panel_type;
      nameCell.append(role);
      const sizeCell = document.createElement("td");
      sizeCell.className = "num";
      sizeCell.textContent = triple(panel.size_mm);
      const posCell = document.createElement("td");
      posCell.className = "num";
      posCell.textContent = `(${panel.pos_mm.map(formatMm).join(", ")})`;
      row.append(nameCell, sizeCell, posCell);
      row.addEventListener("click", () => select(panel.id === state.selected ? null : panel.id));
      rows.append(row);
    }
    if (count) count.textContent = String(panelList.length);
  }

  function renderDetail(panel) {
    if (!detail) return;
    if (!panel) {
      detail.hidden = true;
      detail.replaceChildren();
      return;
    }
    detail.hidden = false;
    detail.replaceChildren();
    const title = document.createElement("strong");
    title.textContent = panel.name;
    const list = document.createElement("dl");
    list.className = "kv";
    const facts = [
      ["角色", panel.role || "—"],
      ["类型", panel.panel_type || "—"],
      ["尺寸", `${triple(panel.size_mm)} mm`],
      ["位置", `(${panel.pos_mm.map(formatMm).join(", ")}) mm`],
      ["材料", materialLabel(panel.material)],
      ["材质角色", panel.material_role || "—"],
      ["内面 / 外面", `${panel.inner_face || "—"} / ${panel.outer_face || "—"}`],
      ["接触", `${panel.contact_count}`],
    ];
    for (const [key, value] of facts) {
      const dt = document.createElement("dt");
      dt.textContent = key;
      const dd = document.createElement("dd");
      dd.textContent = value;
      list.append(dt, dd);
    }
    // 顺纹方向：这是**板件的属性**，点一下就在竖纹 / 横纹之间切换（不是查看器上的显示开关）。
    // 只读分享的那一页不给改：`panelSave.editor` 缺了就当普通一行文字。
    const grainDt = document.createElement("dt");
    grainDt.textContent = "顺纹方向";
    const grainDd = document.createElement("dd");
    const direction = grainDirectionOf(panel);
    const label = direction
      ? `${GRAIN_DIRECTION_LABEL[direction]}${grainIsPending(panel.id) ? "（待保存）" : ""}`
      : grainLabel(panel.grain.axis);
    if (panelSave.editor && direction) {
      // **点这一行才改纹理**（文字和画面同时变）。点板件只是选中——改数据不能和点选同一个动作。
      const button = document.createElement("span");
      button.className = "grainrow";
      button.setAttribute("role", "button");
      button.tabIndex = 0;
      button.title = "点一下把这块板的纹理翻成另一种（竖纹 ⇄ 横纹）";
      button.textContent = label;
      button.addEventListener("click", () => toggleGrainDirection(panel.id));
      grainDd.append(button);
    } else {
      grainDd.textContent = label;
    }
    list.append(grainDt, grainDd);
    if (panel.panel_type === "door") {
      // 铰链侧：**左开＝铰链在左边，右开＝铰链在右边**，不解释拉手。
      // 对开腔的两扇由几何定死（左扇挂左、右扇挂右），这里只显示结果、不给改；
      // 单开腔没定的时候就给两个按钮让人选——这就是"提示客户选"的那一步。
      const hingeDt = document.createElement("dt");
      hingeDt.textContent = "铰链侧";
      const hingeDd = document.createElement("dd");
      const current = hingeSideOf(panel);
      const label = current === "left" ? "左开" : current === "right" ? "右开" : "还没定";
      if (panel.hinge_locked || !panelSave.editor) {
        hingeDd.textContent = label;
        if (panel.hinge_locked) {
          hingeDd.title = "对开腔由几何决定：左扇挂左、右扇挂右，不能单独改";
        }
      } else {
        const group = document.createElement("span");
        group.className = "hingerow";
        for (const [side, text] of [["left", "左开"], ["right", "右开"]]) {
          const button = document.createElement("button");
          button.type = "button";
          button.textContent = text;
          button.className = "chip";
          button.setAttribute("aria-pressed", String(current === side));
          button.addEventListener("click", () => setHingeSide(panel.id, side));
          group.append(button);
        }
        hingeDd.append(group);
        const hint = document.createElement("span");
        hint.className = "hint-inline";
        hint.textContent = current
          ? hingeIsPending(panel.id) ? "（待保存）" : ""
          : "还没定——选一个，再点「保存并冻结」";
        if (hint.textContent) hingeDd.append(hint);
      }
      list.append(hingeDt, hingeDd);
    }
    detail.append(title, list);
    renderPendingEdits();
  }

  // 铰链侧：先攒着，和顺纹一起点「保存并冻结」才提交。
  const hingeEdits = new Map();

  function hingeIsPending(panelId) {
    return hingeEdits.has(panelId);
  }

  // 当前生效的铰链侧：攒过的看攒的值，否则看板件自己的。空 = 还没定。
  function hingeSideOf(panel) {
    return hingeEdits.has(panel.id) ? hingeEdits.get(panel.id) : (panel.hinge_side || "");
  }

  // 选左开 / 右开。选回板件原本的值就等于撤销这条改动。
  function setHingeSide(panelId, side) {
    const panel = panelById(panelId);
    if (!panel) return;
    if (side === (panel.hinge_side || "")) hingeEdits.delete(panelId);
    else hingeEdits.set(panelId, side);
    if (state.selected === panelId) renderDetail(panel);
    else renderPendingEdits();
    paint();
  }

  // 顺纹编辑：先攒着，点一次「保存并冻结」才提交一次修订。
  // 攒的是「板件 id → 新轴」，只记**和当前不一样**的那些。
  const grainEdits = new Map();

  // 换个顺纹轴之后，六个面怎么摆——**口径由板件阶段给**（`grain_axes` / `grain_cycle_mm`
  // 跟着投影来），这里只照着算，不自己定义规则。缺了那两项（旧投影）就不预览，
  // 直接提交后由服务端算准的。
  //
  // 这条规则我在 Python 那边错过两次（「修好侧板就坏背板」），所以这里刻意做成
  // 「数据驱动」：面是 u 还是 v 由投影说，转不转只看 u 是不是顺纹轴。
  function grainUvFor(axis, panel) {
    const table = panel.grain_axes;
    const cycle = panel.grain_cycle_mm;
    if (!Array.isArray(table) || !cycle) return null;
    const index = { x: 0, y: 1, z: 2 }[axis];
    const size = panel.size_mm;
    const repeat = (span) => Math.min(4.5, Math.max(1, Math.abs(span) / cycle));
    const faces = {};
    let home = "";
    let homeArea = -1;
    for (const [face, [u, v]] of table) {
      const rotate = index !== undefined && u !== index;
      const [first, second] = rotate ? [v, u] : [u, v];
      faces[face] = {
        rotation: rotate ? Math.PI / 2 : 0,
        repeat: [repeat(size[first]), repeat(size[second])],
      };
      const area = Math.abs(size[u]) * Math.abs(size[v]);
      if (area > homeArea) {
        home = face;
        homeArea = area;
      }
    }
    return { axis, rotation: faces[home].rotation, home, faces };
  }

  // 大面的长短边各落在柜体哪根轴上。
  function grainPlaneAxes(panel) {
    const table = panel.grain_axes;
    const pair = Array.isArray(table) ? table.find(([face]) => face === panel.grain.home) : null;
    if (!pair) return null;
    const [, [u, v]] = pair;
    const axisOf = { 0: "x", 1: "y", 2: "z" };
    const spanOf = (index) => Math.abs(Number(panel.size_mm[index])) || 0;
    const first = { axis: axisOf[u], span: spanOf(u) };
    const second = { axis: axisOf[v], span: spanOf(v) };
    return first.span >= second.span
      ? { long: first.axis, short: second.axis }
      : { long: second.axis, short: first.axis };
  }

  // 「竖纹」要的那根轴（长边）、「横纹」要的那根轴（短边）。
  function grainPlaneAxis(panel, direction) {
    const plane = grainPlaneAxes(panel);
    if (!plane) return null;
    return direction === "vertical" ? plane.long : plane.short;
  }

  // 这块板现在是竖纹还是横纹。
  function grainDirectionOf(panel) {
    const plane = grainPlaneAxes(panel);
    if (!plane) return null;
    return grainAxisOf(panel) === plane.long ? "vertical" : "horizontal";
  }

  const GRAIN_DIRECTION_LABEL = { vertical: "竖纹", horizontal: "横纹" };

  function grainIsPending(panelId) {
    return grainEdits.has(panelId);
  }

  function panelById(panelId) {
    return panelList.find((panel) => panel.id === panelId) || null;
  }

  // 当前生效的方向：攒过的看攒的值，否则看板件自己的。
  function grainAxisOf(panel) {
    const edit = grainEdits.get(panel.id);
    return edit ? edit.axis : panel.grain.axis;
  }

  // 点一下就在**竖纹 / 横纹**之间切一次，可以反复切。
  //
  // 「竖纹」= 顺这块板的**长边**、「横纹」= 顺短边。用长边而不是"柜体高"当判据，是因为
  // 水平放的板（顶板 / 层板 / 底板 / 踢脚）大面在水平面里，两根轴都不落在柜体高上——
  // "竖"对它们没有意义；而长边口径正好复现出那张默认表（侧板 580×1000、顶板 764×580、
  // 背板 776×926 的长边分别是高、宽、高）。
  //
  // 攒的是「板件 id → {axis, from}」：`from` 是**切换后**的方向（清单里要显示）。
  function toggleGrainDirection(panelId) {
    const panel = panelById(panelId);
    if (!panel) return;
    const next = grainDirectionOf(panel) === "vertical" ? "horizontal" : "vertical";
    const axis = grainPlaneAxis(panel, next);
    if (axis === null) return;
    if (axis === panel.grain_default) {
      // 切回这种板的默认方向 = 这条改动没必要留着（存下去也是原样）。
      grainEdits.delete(panelId);
    } else {
      grainEdits.set(panelId, { axis, from: next });
    }
    applyGrainAxis(panel);
    if (state.selected === panelId) renderDetail(panel);
    else renderPendingEdits();
    paint();
  }

  // 画面跟着改：把新轴换算成六个面的摆法。
  //
  // **不要动 `panel.grain.axis`**（板件自己的那个值）。它是"改之前"的依据：改一次就把它
  // 覆盖掉的话，再点一次算出来的"下一个方向"还是同一个，看起来就是"只能切一次、再点没反应"。
  // 当前生效的方向一律由 `grainAxisOf()` 决定（攒过看攒的，否则看板件自己的）。
  function applyGrainAxis(panel) {
    const axis = grainAxisOf(panel);
    const faces = grainUvFor(axis, panel);
    if (!faces) return;
    panel.grainView = { axis, faces: faces.faces, rotation: faces.rotation, home: faces.home };
    const record = meshes.find((item) => item.panel.id === panel.id);
    if (record && record.grainFaces) {
      record.grainFaces = faces.faces;
      record.homeFace = faces.home;
      record.woodMap.rotation = faces.rotation;
    }
  }

  // 「待保存」清单 + 保存按钮的可用状态。
  //
  // 这块区域**不属于顺纹**：以后别的板件属性也从这里改、一起存，所以它只显示"还没保存的
  // 改动"和一颗「保存并冻结」，不叫「保存顺纹」。没有"放弃改动"——再点一次就切回去了，
  // 想撤销直接切回原样即可。
  function renderPendingEdits() {
    const { editor, pending, save, status } = panelSave;
    if (!editor) return;
    const total = grainEdits.size + hingeEdits.size;
    editor.hidden = total === 0;
    if (pending) {
      pending.replaceChildren();
      for (const [panelId, edit] of grainEdits) {
        const panel = panelById(panelId);
        const item = document.createElement("li");
        const name = document.createElement("b");
        name.textContent = panel ? panel.name : panelId;
        // 说人话：这块板改成竖纹还是横纹，以及具体落在柜体哪根轴上。
        item.append(
          name,
          document.createTextNode(
            `${GRAIN_DIRECTION_LABEL[edit.from]}（${grainLabel(edit.axis)}）`
          )
        );
        pending.append(item);
      }
      for (const [panelId, side] of hingeEdits) {
        const panel = panelById(panelId);
        const item = document.createElement("li");
        const name = document.createElement("b");
        name.textContent = panel ? panel.name : panelId;
        item.append(name, document.createTextNode(side === "left" ? "左开" : "右开"));
        pending.append(item);
      }
    }
    if (save) save.disabled = total === 0;
    if (status) status.textContent = "";
  }

  // 保存这一页上所有还没落盘的改动，然后重新冻结。现在有两种：顺纹方向、门板铰链侧。
  // 接口本身就是"把攒下的改动一次提交"，再加别的属性也不用改这里。
  async function saveChanges() {
    const { url, version, save, status } = panelSave;
    if (!url || !version || grainEdits.size + hingeEdits.size === 0) return;
    if (save) save.disabled = true;
    if (status) status.textContent = "正在保存…";
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        cache: "no-store",
        body: JSON.stringify({
          expected_version: version,
          axes: Object.fromEntries([...grainEdits].map(([id, edit]) => [id, edit.axis])),
          hinges: Object.fromEntries([...hingeEdits]),
        }),
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        throw new Error(detail.detail?.message || detail.detail || `HTTP ${response.status}`);
      }
      // 存下去的是新的一版冻结板件：这一页读的还是旧的，所以直接刷新把新事实拉回来。
      if (status) status.textContent = "已保存，正在重新载入…";
      window.location.reload();
    } catch (error) {
      if (status) status.textContent = `没保存成功：${error.message}`;
      if (save) save.disabled = false;
    }
  }

  if (panelSave.save) panelSave.save.addEventListener("click", saveChanges);

  function select(panelId) {
    state.selected = panelId;
    if (rows) {
      for (const row of rows.querySelectorAll("tr[data-panel]")) {
        row.setAttribute("aria-selected", String(row.dataset.panel === panelId));
      }
    }
    renderDetail(panelList.find((panel) => panel.id === panelId) || null);
    paint();
  }

  function renderSummary() {    if (!summary) return;
    const materialText = (payload.materials || [])
      .map((item) => `${item.label} ${item.count}`)
      .join(" · ");
    const facts = [
      ["外形 W×D×H", `${triple([width, depth, height])} mm`],
      [
        "内部净空",
        payload.cavity_mm && payload.cavity_mm.width != null
          ? `${triple([payload.cavity_mm.width, payload.cavity_mm.depth, payload.cavity_mm.height])} mm`
          : "—",
      ],
      [
        "料厚 柜体/背/门",
        `${formatMm(payload.thickness_mm?.board)} / ${formatMm(payload.thickness_mm?.back)} / ${formatMm(payload.thickness_mm?.door)} mm`,
      ],
      ["背板安装", `${payload.back_mount?.effective || "—"}（请求 ${payload.back_mount?.requested || "—"}）`],
      ["门 / 抽屉 / 层板", `${payload.n_doors} / ${payload.drawer_count} / ${payload.shelf_count}`],
      ["踢脚高", `${formatMm(payload.toe_kick_height_mm)} mm`],
      ["材料", materialText || "—"],
      ["板件块数", `${panelList.length}`],
    ];
    summary.replaceChildren();
    for (const [key, value] of facts) {
      const dt = document.createElement("dt");
      dt.textContent = key;
      const dd = document.createElement("dd");
      dd.textContent = value;
      summary.append(dt, dd);
    }
  }

  // 点选：按下和抬起在同一处才算点，拖动不算。
  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();
  let downAt = null;

  // 命中记录里的法线是**板件自己的**坐标（raycaster 换算过），盒子又是轴对齐缩放，
  // 所以分量最大的那根轴、加上正负号，就是打在哪个面上。六个名字和 `grain.faces` 一致。
  function faceKey(hit) {
    const normal = hit.face.normal;
    const axes = ["x", "y", "z"];
    let best = 0;
    for (let index = 1; index < 3; index += 1) {
      if (Math.abs(normal[axes[index]]) > Math.abs(normal[axes[best]])) best = index;
    }
    return (normal[axes[best]] >= 0 ? "p" : "n") + axes[best];
  }

  // 返回 { panel, face }；没打到就是 null。面板页只关心这两样。
  function pick(event) {
    const rect = canvas.getBoundingClientRect();
    pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(pointer, camera);
    const hits = raycaster.intersectObjects(
      meshes.filter((record) => record.mesh.visible).map((record) => record.mesh),
      false
    );
    if (!hits.length) return null;
    const hit = hits[0];
    return { panel: hit.object.userData.record.panel, face: faceKey(hit) };
  }

  canvas.addEventListener("pointerdown", (event) => {
    downAt = { x: event.clientX, y: event.clientY };
  });
  canvas.addEventListener("pointerup", (event) => {
    if (!downAt) return;
    const moved = Math.hypot(event.clientX - downAt.x, event.clientY - downAt.y);
    downAt = null;
    if (moved > 4) return;
    const found = pick(event);
    // 点板件**只选中**，不改任何东西。改纹理在右边「顺纹方向」那一行上——
    // 点一下就改数据太容易误伤（点选本来是最常用的动作）。
    select(found ? found.panel.id : null);
  });
  canvas.addEventListener("pointermove", (event) => {
    const found = pick(event);
    const panel = found ? found.panel : null;
    const hoveredId = panel ? panel.id : null;
    const face = found ? found.face : null;
    if (hoveredId !== state.hovered || face !== state.hoverFace) {
      state.hovered = hoveredId;
      state.hoverFace = face;
      paint();
    }
    if (hover) {
      if (panel) {
        const rect = canvas.getBoundingClientRect();
        hover.style.display = "block";
        hover.style.left = `${event.clientX - rect.left}px`;
        hover.style.top = `${event.clientY - rect.top}px`;
        hover.textContent = `${panel.name} · ${triple(panel.size_mm)} mm`;
      } else {
        hover.style.display = "none";
      }
    }
  });
  canvas.addEventListener("pointerleave", () => {
    if (state.hovered !== null || state.hoverFace !== null) {
      state.hovered = null;
      state.hoverFace = null;
      paint();
    }
    if (hover) hover.style.display = "none";
  });

  for (const button of viewButtons) {
    button.addEventListener("click", () => setView(button.dataset.view));
  }
  if (toggles.doors) {
    toggles.doors.addEventListener("click", () => toggle("doors"));
  }
  if (toggles.back) {
    toggles.back.addEventListener("click", () => toggle("back"));
  }
  if (toggles.wire) {
    toggles.wire.addEventListener("click", () => toggle("wire"));
  }
  if (toggles.explode) {
    toggles.explode.addEventListener("input", () => setExplode(toggles.explode.value));
  }
  if (toggles.open) {
    toggles.open.addEventListener("input", () => setOpen(toggles.open.value));
  }
  for (const filter of filters) {
    filter.addEventListener("change", () => {
      const active = new Set(
        [...filters].filter((item) => item.checked).map((item) => item.dataset.assembly)
      );
      state.filter = (panel) => active.has(panel.assembly);
      paint();
    });
  }

  window.addEventListener("resize", () => {
    // 尺寸在 draw() 里每帧重取，这里只负责立刻反映一次。
    renderer.setSize(canvas.clientWidth || 960, canvas.clientHeight || 640, false);
  });


  // 地址栏可以指点初始状态：`?view=front&doors=0&wire=1&explode=60&open=80`。
  // 只影响打开时看哪一面，不改数据——分享一个视角、或者截图核对都靠它。
  const query = new URLSearchParams(window.location.search);
  const requestedView = query.get("view");
  const requestedExplode = Number(query.get("explode"));
  if (query.get("doors") === "0") setDoors(false);
  if (query.get("back") === "0") setBack(false);
  if (query.get("wire") === "1") setWire(true);
  if (query.get("only")) {
    // `?only=white` 之类：只留这一类板件，用来核对某一块到底画在哪。改的是显示，不是数据。
    const groups = new Set(query.get("only").split(","));
    state.filter = (panel) => groups.has(panel.material) || groups.has(panel.assembly);
  }
  if (Number.isFinite(requestedExplode)) setExplode(Math.min(100, Math.max(0, requestedExplode)));
  const requestedOpen = Number(query.get("open"));
  if (Number.isFinite(requestedOpen) && query.get("open") !== null) {
    setOpen(Math.min(100, Math.max(0, requestedOpen)));
  }

  renderSummary();
  renderRows();
  setView(VIEWS[requestedView] ? requestedView : "iso");
  paint();
  draw();

  // `?probe=1`：把每块板当前真实的材质与几何贴回页面标题，供无头浏览器读。
  // 只读画面状态，不改数据——截图核对用，正常打开不会碰它。
  if (query.get("probe") === "1") {
    const dump = meshes.map((record) => ({
      id: record.panel.id,
      material: record.panel.material,
      visible: record.mesh.visible,
      hasMap: Boolean(record.material.map),
      color: record.material.color.hex,
      size: record.mesh.scale.toArray(),
      pos: record.mesh.position.toArray(),
      // 顺纹方向与当前实际用的重复次数：核对「横纹的板有没有转 90°」靠这两个。
      grain: record.panel.grain.axis,
      mapRotation: record.material.map ? record.material.map.rotation : null,
      mapRepeat: record.material.map ? record.material.map.repeat.toArray() : null,
    }));
    document.title = `PROBE ${JSON.stringify({
      camera: camera.position.toArray().map((value) => Math.round(value)),
      size: [canvas.clientWidth, canvas.clientHeight],
      panels: dump,
    })}`;
  }

  return {
    setView,
    select,
    toggle,
    setExplode,
    /** 页面上由指针位置驱动；这里留一个入口，验收脚本才能核对变色。 */
    hover(panelId, face) {
      state.hovered = panelId || null;
      state.hoverFace = face || null;
      paint();
    },
    state,
    /** 验收钩子：样式与几何的换算在 Node 里用桩件核对，见 tests 说明。 */
    __test: { scene, camera, root, meshes },
    dispose() {
      renderer.dispose();
      boxGeometry.dispose();
      edgeGeometry.dispose();
    },
  };
}
