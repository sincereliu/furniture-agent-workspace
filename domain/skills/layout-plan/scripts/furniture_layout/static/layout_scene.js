import * as THREE from "three";
import { OrbitControls } from "/vendor/three/0.186.0/OrbitControls.js";
import { cameraThreePosition, roomToThree } from "./layout_frame.js";
import { ELEVATION_PITCH, wallVisibility } from "./wall_view.js";

export { cameraThreePosition, roomToThree };

function disposeObject(object) {
  const materials = new Set();
  object.traverse((node) => {
    if (node.geometry) node.geometry.dispose();
    const list = node.material
      ? (Array.isArray(node.material) ? node.material : [node.material])
      : [];
    for (const material of list) materials.add(material);
  });
  for (const material of materials) {
    if (material.map) material.map.dispose();
    material.dispose();
  }
}

function prismGeometry(footprint, z0, z1) {
  const positions = [];
  const n = footprint.length;
  const bottom = footprint.map(([x, y]) => roomToThree(x, y, z0));
  const top = footprint.map(([x, y]) => roomToThree(x, y, z1));
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

function lineSegments(values, color) {
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(values, 3));
  return new THREE.LineSegments(geometry, new THREE.LineBasicMaterial({ color }));
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
    `color:#${label.color.toString(16).padStart(6, "0")}`,
    "background:rgba(255,255,255,.82)",
    "border-radius:4px",
    "padding:1px 4px",
    "white-space:nowrap",
    "text-shadow:0 1px 0 rgba(255,255,255,.9)",
    "transform:translate(0,0)",
    "will-change:transform",
  ].join(";");
  layer.appendChild(el);
  return el;
}

/**
 * 屏幕空间的方位指示器：右下角一个小三脚架，红 X 东 / 绿 Y 南 / 蓝 Z 上。
 *
 * 为什么需要它：3D 投影会把"Y 沿西墙向南（远近方向）"和"Z 竖直向上"压成两条几乎重合的
 * 竖线，几何再正确也读不出来。指示器用固定的屏幕方向绘制，永远一眼可辨。
 */
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

function addMesh(parent, mesh, pickables) {
  parent.add(mesh);
  if (mesh.userData && mesh.userData.kind) pickables.push(mesh);
  return mesh;
}

export function mountLayout(canvas) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setClearColor(0xeef1f6, 1);
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
  scene.add(new THREE.HemisphereLight(0xffffff, 0xc5d0dc, 1.2));
  const sun = new THREE.DirectionalLight(0xffffff, 0.85);
  sun.position.set(4000, 8000, 2000);
  scene.add(sun);
  const content = new THREE.Group();
  scene.add(content);
  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = false;
  controls.screenSpacePanning = true;
  controls.mouseButtons = {
    LEFT: THREE.MOUSE.ROTATE,
    MIDDLE: THREE.MOUSE.PAN,
    RIGHT: THREE.MOUSE.PAN,
  };
  controls.minPolarAngle = 0.02;
  controls.maxPolarAngle = Math.PI - 0.02;
  const raycaster = new THREE.Raycaster();
  const ndc = new THREE.Vector2();
  const floor = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
  const hitPoint = new THREE.Vector3();
  const wallViewDirection = new THREE.Vector3();
  let pickables = [];
  let wallShells = [];
  let labelLayer = null;
  let labelEntries = [];
  let axisGizmo = null;
  let axesGroup = null;      // 坐标轴的可复用容器：每帧清空重建，避免往 content 里累积
  const WALL_FADE_MS = 150;  // 墙显隐/透明度的过渡时长：判据是二值的，靠它摊开突变
  let wallFade = [];         // 每面墙当前的渐变透明度
  let wallFadeFrom = [];     // 本趟渐变的起点
  let wallFadeTargets = [];  // 本趟渐变的目标
  let wallFadeStarted = 0;   // 本趟渐变的开始时刻（0 = 没有在跑的渐变）
  function setLens(fovDeg) {
    const next = Math.max(2, Math.min(90, Number(fovDeg) || LENS_BASE));
    if (Math.abs(camera.fov - next) < 0.01) return;
    camera.fov = next;
    camera.updateProjectionMatrix();
  }

  /** DOM 标注：每帧把锚点投影到屏幕像素，写 transform。字号恒定，不随缩放变小。 */
  function refreshLabels() {
    if (!labelLayer || !labelEntries.length) return;
    const rect = canvas.getBoundingClientRect();
    camera.updateMatrixWorld(true);
    for (const entry of labelEntries) {
      const projected = new THREE.Vector3(...entry.anchor).project(camera);
      const x = (projected.x * 0.5 + 0.5) * rect.width;
      const y = (-projected.y * 0.5 + 0.5) * rect.height;
      const visible = projected.z < 1 && x > -80 && y > -20 && x < rect.width + 80 && y < rect.height + 20;
      entry.el.style.display = visible ? "block" : "none";
      if (visible) entry.el.style.transform = `translate(${Math.round(x)}px, ${Math.round(y)}px) translate(-50%,-50%)`;
    }
    // 简单防重叠：同类标签挨太近就整体下推。
    const shown = labelEntries.filter((entry) => entry.el.style.display !== "none");
    for (let i = 0; i < shown.length; i += 1) {
      for (let j = i + 1; j < shown.length; j += 1) {
        const a = shown[i].el.getBoundingClientRect();
        const b = shown[j].el.getBoundingClientRect();
        if (Math.abs(a.top - b.top) < 16 && a.left < b.right && b.left < a.right) {
          shown[j].el.style.transform += " translateY(16px)";
        }
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
    camera.updateMatrixWorld(true);
    // 相机的屏幕基：right / up（用真实矩阵列，不手写映射）
    const m = camera.matrixWorld;
    const col = (i) => new THREE.Vector3(m.elements[i * 4], m.elements[i * 4 + 1], m.elements[i * 4 + 2]).normalize();
    const right = col(0);
    const camUp = col(1);
    const toScreen = (dir) => ({ dx: dir.dot(right) * R, dy: -dir.dot(camUp) * R });
    const dirs = [
      { key: "X 宽", dir: new THREE.Vector3(1, 0, 0), color: "#dc2626", anchor: 0 },
      { key: "Y 深", dir: new THREE.Vector3(0, 0, 1), color: "#047857", anchor: 0.42 },
      { key: "Z 高", dir: new THREE.Vector3(0, 1, 0), color: "#2563eb", anchor: 0.82 },
    ];
    ctx.lineWidth = 2.4;
    ctx.font = "700 11px Inter,Microsoft YaHei,sans-serif";
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    for (const item of dirs) {
      const { dx, dy } = toScreen(item.dir);
      ctx.strokeStyle = item.color;
      ctx.fillStyle = item.color;
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.lineTo(dx, dy);
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(dx, dy, 3.4, 0, Math.PI * 2);
      ctx.fill();
      // 标签沿箭头方向错开，避免三条挤在原点处
      ctx.fillText(item.key, dx + item.anchor * 26 + 5, dy + item.anchor * 26);
    }
    ctx.fillStyle = "#0f172a";
    ctx.beginPath();
    ctx.arc(0, 0, 2.8, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  function isElevation() {
    const up = camera.position.y - controls.target.y;
    const flat = Math.hypot(camera.position.x - controls.target.x, camera.position.z - controls.target.z);
    return Math.abs(Math.atan2(up, flat)) < ELEVATION_PITCH;
  }

  /**
   * 房间**边线**：只画地板北边（远端）一条中性灰边界线，别的一律不画。
   *
   * 走过的弯路值得记下来：地板是个**面**，把它的四条边都画出来就等于给地板勾了轮廓。
   * 从房间外面看时，近端两条边（东、南）会投影到墙面之外——透视下甚至落在北墙顶边之上，
   * 看起来就像"北墙上又被画了一个矩形框"。实测（5 种窗口尺寸都复现）：
   *   #64748b  世界 [2400,0,0]->[2400,3000,0]（东边）
   *            世界 [0,3000,0]->[2400,3000,0]（南边）
   *            世界 [0,0,0]->[0,3000,0]（西边）
   * 三条都落在画布上半部、越出墙面。近端边没有任何信息量（地板填充已经表达了范围），
   * 所以直接去掉：只留北边一条做"房间尽头"的界定。
   */
  function refreshOutline() {
    const outline = content.userData.outline;
    if (!outline || !wallShells.length) return;
    const { x0, x1, z0 } = outline;
    const at = (x, y, z) => roomToThree(x, y, z);
    const segments = [
      ...at(x0, 0, z0), ...at(x1, 0, z0),      // 北边（房间远端的界定线）
    ];
    let entry = outline.lines.find((item) => item.key === "neutral");
    if (!entry) {
      entry = { key: "neutral", line: lineSegments([], 0x64748b) };
      content.add(entry.line);
      outline.lines.push(entry);
    }
    entry.line.geometry.dispose();
    entry.line.geometry = new THREE.BufferGeometry();
    entry.line.geometry.setAttribute("position", new THREE.Float32BufferAttribute(segments, 3));
  }

  /**
   * 坐标轴。**约定对照表（房间 ↔ three.js）**：
   *
   * | 房间轴 | 含义 | 正方向 | 长度 | three.js 分量 |
   * |--------|------|--------|------|----------------|
   * | X      | 宽度 | 西 → 东 | 总宽 | three.x（东）|
   * | Y      | 深度 | 北 → 南 | 总深 | three.z（three 的 z 指向南/屏幕外）|
   * | Z      | 高度 | 下 → 上 | 总高 | three.y（three 的 y 就是上）|
   *
   * 映射只有一处：`roomToThree(x, y, z) = [x, z, y]`。
   * 原点 = 房间 (0,0,0) = 西墙 ∩ 北墙 ∩ 地面 = `roomToThree(0,0,0) = three(0,0,0)`。
   *
   * 三条轴都**沿房间边界**铺设、长度**严格等于房间对应尺寸**，末端带箭头锥指明正方向。
   */
  function refreshAxes() {
    const outline = content.userData.outline;
    if (!outline || !wallShells.length) return;
    // 轴每帧重建（相机一动就要重画），所以必须**清掉上一帧的轴**再画。
    // 曾经直接 content.add(...) 且从不清理：动画期间每帧加 6 个网格，
    // 实测一次切换后 content 子对象从 27 涨到 3183（真·内存泄漏 + 掉帧）。
    // 这里用一个**可复用的组**：组本身属于 content（跟随 sync 重建），组内每次清空。
    if (!axesGroup) {
      axesGroup = new THREE.Group();
      content.add(axesGroup);
    }
    disposeObject(axesGroup);
    axesGroup.clear();
    const { x1, z1, height } = outline;                 // x0 = z0 = 0（原点是房间角落）
    const nudge = 25;                                    // 标签离轴让开的距离（mm）：贴着轴，读起来才归属明确
    // 端点直接写 **three.js 坐标**，映射只在这一处发生，不再经 roomToThree 的参数位次：
    //   房间 X（宽，向东）  → three.x = 0 … x1
    //   房间 Y（深，向南）  → three.z = 0 … z1   ← 深度落在 three 的 z 上
    //   房间 Z（高，向上）  → three.y = 0 … height ← 高度落在 three 的 y 上
    // 曾经写成 at(0, 0, z1) / at(0, height, 0)（按 three 分量顺序传参）→
    // 绿轴拿到了 3000 的"高度"、蓝轴拿到了 2800 的"深度"，两条轴正好互换。
    const axes = [
      { key: "x", from: [0, 0, 0], to: [x1, 0, 0], color: 0xdc2626 },
      { key: "y", from: [0, 0, 0], to: [0, 0, z1], color: 0x047857 },
      { key: "z", from: [0, 0, 0], to: [0, height, 0], color: 0x2563eb },
    ];

    // 轴杆用**实体圆柱**（细线在多数驱动上宽不出 1px，看不清），末端接同色锥形箭头。
    const radius = Math.max(12, Math.min(x1, z1, height) * 0.006);
    const head = Math.max(70, Math.min(x1, z1, height) * 0.032);
    axes.forEach((axis, index) => {
      const from = new THREE.Vector3(...axis.from);
      const to = new THREE.Vector3(...axis.to);
      const dir = to.clone().sub(from).normalize();
      const material = new THREE.MeshBasicMaterial({ color: axis.color });
      // 杆：从起点到"终点 - 箭头长度"
      const shaftEnd = to.clone().addScaledVector(dir, -head);
      const shaftLength = from.distanceTo(shaftEnd);
      const shaft = new THREE.Mesh(new THREE.CylinderGeometry(radius, radius, shaftLength, 12), material);
      shaft.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir);
      shaft.position.copy(from).addScaledVector(dir, shaftLength / 2);
      shaft.userData.kind = null;                        // 轴杆不参与拾取
      axesGroup.add(shaft);
      // 箭头：锥尖落在轴的终点（= 房间边界）
      const cone = new THREE.Mesh(new THREE.ConeGeometry(head * 0.45, head, 18), material);
      cone.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir);   // 锥尖默认朝 +Y
      cone.position.copy(to).addScaledVector(dir, -head * 0.5);
      cone.userData.kind = null;
      axesGroup.add(cone);
    });

    outline.axisLength = { x: x1, y: z1, z: height };
    // 标签锚点也用 **three.js 坐标**（与上面的轴端点同一套，不再经 roomToThree 的参数位次）：
    //   X 轴中点 (x1/2, 0, 0)      往北墙外让开 → three.z = -nudge
    //   Y 轴中点 (0, 0, z1/2)      往西墙外让开 → three.x = -nudge
    //   Z 轴中点 (0, height/2, 0)  往西北外让开 → three.x = -nudge
    outline.labelAnchors = {
      x: [x1 / 2, 0, -nudge],
      y: [-nudge, 0, z1 / 2],
      z: [-nudge, height / 2, 0],
    };
  }

  /**
   * 把当前的墙与相机喂给纯函数 wallVisibility()，再把结果写回材质。
   *
   * **加一层短时渐变**（约 150ms）：判据本身是二值的（`visible: !cameraOutside`），
   * 相机一越过阈值，墙就会在**某一帧**瞬间出现/消失，同时透明度从侧墙 0.25 跳到背景墙 0.55。
   * 实测这一步没有掉帧（变化帧 16.4~17.0ms，与其它帧一致，着色器程序数恒为 5），
   * 所以那个"顿"是**画面突变**而不是卡顿。把突变摊成 150ms 的过渡即可。
   * 墙一律用 `opacity` 表达（不靠 visible 开关），这样渐变过程中不会出现"半透明突然变实"。
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
      wall.material.opacity = opacity;
      // 颜色由判据一起给：背景墙用中灰。浅灰压浅色背景等于看不见。
      wall.material.color.setHex(state.color === null ? wall.userData.baseColor : state.color);
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
    controls.target.set(target[0], target[2], target[1]);
    camera.up.set(0, 1, 0);
    camera.lookAt(controls.target);
    controls.maxDistance = Math.max(distance * 6, 8000);
    applyRoomLimits();
    controls.update();
    refreshWalls();
    refreshOutline();
    refreshAxes();
    refreshLabels();
  }

  function readView() {
    const offset = camera.position.clone().sub(controls.target);
    const east = offset.x;
    const up = offset.y;
    const south = offset.z;
    const horizontal = Math.hypot(east, south);
    return {
      yaw: Math.atan2(south, east),
      pitch: Math.atan2(up, horizontal),
      distance: offset.length(),
      target: [controls.target.x, controls.target.z, controls.target.y],
    };
  }

  function basis() {
    camera.updateMatrixWorld(true);
    const right = new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 0);
    const up = new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 1);
    const forward = new THREE.Vector3();
    camera.getWorldDirection(forward);
    const position = camera.position;
    const room = (vector) => [vector.x, vector.z, vector.y];
    return {
      position: [position.x, position.z, position.y],
      forward: room(forward),
      right: room(right),
      up: room(up),
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
    return [hit.x, hit.z];
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
    renderer.autoClear = true;
    renderer.render(scene, camera);
  }

  /**
   * 设 fov。**关系只有一条**：`fov = LENS_BASE ÷ (用户缩放 × 收窄倍数)`。
   *
   * 为什么与距离无关：投影到屏幕的高度 = 距离 × tan(fov/2)。要让"观感尺寸"只由缩放决定，
   * 就必须让 `距离 × tan(fov/2)` 恒定 —— 也就是 **距离拉远多少、tan(fov/2) 就同比例缩小**。
   * 正视图把相机拉远 8 倍，fov 就按同一比例收窄（调用方传 zoom×pull），于是：
   *   · 观感尺寸 = 基准取景 ÷ 用户缩放（切视角不改画面大小）；
   *   · 透视收敛被压平 8 倍（立面的竖直棱线接近平行）。
   *
   * 曾经的错误：把"基准距离 ÷ 当前距离"当作 fov 系数（`48 × ref/dist`）。
   * 那个式子让 fov 随距离变小，而屏幕高度 = 距离×tan(fov/2) 反而随距离**变大**，
   * 于是切到正视图时画面暴涨 68 倍（就是"俯视图缩放比例太大、切换抖动"的根源）。
   */
  function setFovForZoom(zoom) {
    const z = Math.max(0.02, Number(zoom) || 1);
    setLens(LENS_BASE / z);
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
    axesGroup = null;            // 旧组随 content 一起被清掉，引用必须失效，否则下一帧往孤儿组里加
    // outline.lines 里存的是复用用的线段对象；content 已清空，这些引用成了孤儿（不可见且泄漏），
    // 所以一并清掉，让 refreshOutline() 下一帧重新建线并挂到新的 content 上。
    if (content.userData.outline) content.userData.outline.lines = [];
    wallFade = [];               // 墙是新对象，旧的渐变状态作废
    wallFadeFrom = [];
    wallFadeTargets = [];
    wallFadeStarted = 0;
    pickables = [];
    // 标注层也要跟着重建：DOM 元素不是 three 对象，content.clear() 不会清掉它们
    for (const entry of labelEntries) entry.el.remove();
    labelEntries = [];
    labelLayer = labelLayer || ensureLabelLayer(canvas);
    if (!axisGizmo && labelLayer) {
      axisGizmo = makeAxisGizmo();
      labelLayer.parentElement.appendChild(axisGizmo.el);
    }
    const addDimLabel = (label) => {
      if (!labelLayer) return;
      labelEntries.push({ ...label, el: makeLabelElement(labelLayer, { ...label, color: 0x334155 }) });
    };
    const width = room.width_mm;
    const depth = room.depth_mm;
    const height = room.height_mm;
    const floorMesh = new THREE.Mesh(
      new THREE.PlaneGeometry(width, depth),
      new THREE.MeshStandardMaterial({ color: 0xf8fafc, roughness: 1, metalness: 0, side: THREE.DoubleSide }),
    );
    floorMesh.rotation.x = -Math.PI / 2;
    floorMesh.position.set(width / 2, 0, depth / 2);
    content.add(floorMesh);
    const step = [200, 250, 500, 1000, 2000, 5000].find((value) => Math.max(width, depth) / value <= 14) || 5000;
    const grid = [];
    for (let x = step; x < width; x += step) grid.push(...roomToThree(x, 0, 0.4), ...roomToThree(x, depth, 0.4));
    for (let y = step; y < depth; y += step) grid.push(...roomToThree(0, y, 0.4), ...roomToThree(width, y, 0.4));
    if (grid.length) content.add(lineSegments(grid, 0xcbd5e1));
    // 房间边线按"可见墙"和"坐标轴分色"逐帧重建，见 refreshOutline()。
    content.userData.outline = {
      x0: 0,
      x1: width,
      z0: 0,
      z1: depth,
      height,
      lines: [],
    };
    // 相机到目标的距离下限用房间对角线：保证相机始终在房间外（见 applyRoomLimits）。
    content.userData.roomDiagonal = Math.hypot(width, depth, height);
    const wallMaterial = new THREE.MeshStandardMaterial({
      color: 0xdbe3ee,
      transparent: true,
      opacity: 0.22,
      roughness: 1,
      metalness: 0,
      side: THREE.DoubleSide,
      depthWrite: false,
    });
    // 墙的显隐与透明度按人眼习惯逐帧算（见 wall_view.js）
    const shells = [];
    const addWall = (mesh, center, normal, wallId) => {
      mesh.material = wallMaterial.clone();     // 每面墙单独一份材质，透明度各算各的
      mesh.userData.wallCenter = center;
      mesh.userData.wallNormal = normal.normalize();
      mesh.userData.wallId = wallId;
      mesh.userData.baseColor = wallMaterial.color.getHex();
      shells.push(mesh);
      content.add(mesh);
    };
    // 北墙：先设 position 再 addWall。漏掉 position 会让它落在世界原点（房间中心）——
    // 表现就是"北墙跑到房间中间、只有一半落在地板上"。
    const north = new THREE.Mesh(new THREE.PlaneGeometry(width, height), wallMaterial);
    north.position.set(width / 2, height / 2, 0);
    addWall(north, new THREE.Vector3(width / 2, 0, 0), new THREE.Vector3(0, 0, -1), "north");
    const east = new THREE.Mesh(new THREE.PlaneGeometry(depth, height), wallMaterial);
    east.rotation.y = Math.PI / 2;
    east.position.set(width, height / 2, depth / 2);
    addWall(east, new THREE.Vector3(width, 0, depth / 2), new THREE.Vector3(1, 0, 0), "east");
    const south = new THREE.Mesh(new THREE.PlaneGeometry(width, height), wallMaterial);
    south.rotation.y = Math.PI;
    south.position.set(width / 2, height / 2, depth);
    addWall(south, new THREE.Vector3(width / 2, 0, depth), new THREE.Vector3(0, 0, 1), "south");
    const west = new THREE.Mesh(new THREE.PlaneGeometry(depth, height), wallMaterial);
    west.rotation.y = -Math.PI / 2;
    west.position.set(0, height / 2, depth / 2);
    addWall(west, new THREE.Vector3(0, 0, depth / 2), new THREE.Vector3(-1, 0, 0), "west");
    wallShells = shells;
    for (const opening of data.openings || []) {
      const span = opening.offset_mm;
      const end = span + opening.width_mm;
      const z0 = opening.sill_height_mm || 0;
      const z1 = z0 + opening.height_mm;
      let box;
      if (opening.wall === "north") box = [span, 0, z0, end, 30, z1];
      else if (opening.wall === "south") box = [width - end, depth - 30, z0, width - span, depth, z1];
      else if (opening.wall === "east") box = [width - 30, span, z0, width, end, z1];
      else box = [0, depth - end, z0, 30, depth - span, z1];
      const mesh = new THREE.Mesh(
        new THREE.BoxGeometry(box[3] - box[0], box[5] - box[2], box[4] - box[1]),
        new THREE.MeshStandardMaterial({ color: 0x38bdf8, transparent: true, opacity: 0.55, roughness: 0.4, metalness: 0, side: THREE.DoubleSide }),
      );
      mesh.position.set((box[0] + box[3]) / 2, (box[2] + box[5]) / 2, (box[1] + box[4]) / 2);
      content.add(mesh);
    }
    for (const obstacle of data.obstacles || []) {
      content.add(new THREE.Mesh(
        prismGeometry(obstacle.footprint, obstacle.z_start, obstacle.z_end),
        new THREE.MeshStandardMaterial({ color: 0xdc6b6b, roughness: 0.7, metalness: 0, side: THREE.DoubleSide }),
      ));
    }
    for (const item of data.items || []) {
      const selected = item.id === selectedId;
      const blocked = selected && options.blockedId === item.id;
      // 竖向范围统一由 itemZRange() 推导：payload 不保证带 z_start / z_end
      const [itemZStart, itemZEnd] = itemZRange(item);
      const mesh = new THREE.Mesh(
        prismGeometry(item.footprint, itemZStart, itemZEnd),
        new THREE.MeshStandardMaterial({
          color: blocked ? 0xdc2626 : (selected ? 0x1d4ed8 : 0x3b6fd8),
          roughness: 0.55,
          metalness: 0.02,
          side: THREE.DoubleSide,
        }),
      );
      mesh.userData = { kind: "item", itemId: item.id };
      addMesh(content, mesh, pickables);
      if (item.footprint.length >= 4) {
        const frontZ = (itemZStart + itemZEnd) / 2;
        const a = footprintPoint(item.footprint[3]);
        const b = footprintPoint(item.footprint[2]);
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
        addDimensions(content, data, item, addDimLabel);
      }
      if (!selected) continue;
      const center = footprintCenter(item.footprint);
      const midZ = (itemZStart + itemZEnd) / 2;
      if (!readOnly) {
        const ring = new THREE.Mesh(
          new THREE.TorusGeometry(Math.max(180, width * 0.06), 14, 8, 48),
          new THREE.MeshStandardMaterial({ color: 0xf59e0b, roughness: 0.4, metalness: 0 }),
        );
        ring.rotation.x = Math.PI / 2;
        ring.position.set(center[0], midZ, center[1]);
        ring.userData = { kind: "ring", itemId: item.id };
        addMesh(content, ring, pickables);
        const rotateHandle = new THREE.Mesh(
          new THREE.SphereGeometry(70, 16, 12),
          new THREE.MeshStandardMaterial({ color: 0xf59e0b, roughness: 0.35, metalness: 0 }),
        );
        rotateHandle.position.set(center[0] + 220, itemZEnd + 160, center[1]);
        rotateHandle.userData = { kind: "rotate", itemId: item.id };
        addMesh(content, rotateHandle, pickables);
        const heightHandle = new THREE.Mesh(
          new THREE.SphereGeometry(64, 16, 12),
          new THREE.MeshStandardMaterial({ color: 0x3b82f6, roughness: 0.35, metalness: 0 }),
        );
        heightHandle.position.set(center[0] - 220, itemZEnd + 160, center[1]);
        heightHandle.userData = { kind: "height", itemId: item.id };
        addMesh(content, heightHandle, pickables);
      }
    }
    refreshWalls();
    refreshOutline();
    refreshAxes();
    applyRoomLimits();
    // 轴标：几何由 refreshAxes() 重建；标签锚点直接取它交接的 three.js 坐标，
    // 与轴端点同一套（曾经这里改用 roomToThree 的房间参数位次，正好又反一次，
    // 表现为"颜色对了、数字落在对方轴上"）。
    if (labelLayer) {
      const addLabelAt = (anchor, text, color) => labelEntries.push({
        anchor, text, color, el: makeLabelElement(labelLayer, { text, color }),
      });
      const anchors = content.userData.outline?.labelAnchors;
      if (anchors) {
        // 三个数字标签（轴名 + 房间真尺寸），各自贴在自己那条轴上，正方向由箭头表示。
        addLabelAt(anchors.x, `X ${Math.round(width)}`, 0xdc2626);
        addLabelAt(anchors.y, `Y ${Math.round(depth)}`, 0x047857);
        addLabelAt(anchors.z, `Z ${Math.round(height)}`, 0x2563eb);
      }
    }
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
      refreshOutline();
      refreshAxes();
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

/** footprint 的点有两种写法：`{x_mm, y_mm}`（布局阶段）或 `[x, y]`。统一成 [x, y]。 */
function footprintPoint(point) {
  return Array.isArray(point) ? [point[0], point[1]] : [point.x_mm, point.y_mm];
}

function footprintCenter(footprint) {
  const count = footprint.length || 1;
  const points = footprint.map(footprintPoint);
  return [
    points.reduce((sum, point) => sum + point[0], 0) / count,
    points.reduce((sum, point) => sum + point[1], 0) / count,
  ];
}

/**
 * 一件家具的竖向范围 [z_start, z_end]。
 *
 * `room_page_payload` 给的是 `{placement, width, depth, height}`，
 * 不保证带 `z_start` / `z_end`（那是另一个入口的形状）——两种都认，缺了就按
 * placement.origin_z_mm + height 推，避免算出 NaN 让整段标注静默失效。
 */
function itemZRange(item) {
  if (Number.isFinite(item.z_start) && Number.isFinite(item.z_end)) {
    return [item.z_start, item.z_end];
  }
  const base = item.placement && Number.isFinite(item.placement.origin_z_mm)
    ? item.placement.origin_z_mm
    : 0;
  return [base, base + (Number.isFinite(item.height) ? item.height : 0)];
}

/**
 * 家具尺寸与离墙净距的标注。
 *
 * 线用 three 画（`parent`），**数字用 DOM 标注层**（`onLabel` 回调）——sprite 文字在缩小时
 * 会糊成一片（实测 10px 高、汉字 7px），DOM 是屏幕空间，字号恒定。
 * 尺寸取局部轴（跟着朝向走，不是 AABB）；净距取自摆放检查算出的六向净空。
 */
function addDimensions(parent, data, item, onLabel) {
  // footprint 的元素是 {x_mm, y_mm}（布局阶段的数据结构），不是 [x, y] 数组对——
  // 之前按数组取 point[0] 拿到 undefined，整段尺寸标注静默失效。两种格式都认。
  const points = item.footprint.map(footprintPoint);
  const xs = points.map((point) => point[0]);
  const ys = points.map((point) => point[1]);
  const box = { x0: Math.min(...xs), x1: Math.max(...xs), y0: Math.min(...ys), y1: Math.max(...ys) };
  const [zStart, zEnd] = itemZRange(item);
  const midX = (box.x0 + box.x1) / 2;
  const midY = (box.y0 + box.y1) / 2;
  const z = zStart + 8;
  const zMid = (zStart + zEnd) / 2;
  const fmt = (value) => `${Math.round(value)}`;

  // 本体宽 / 深：画在 footprint 的边外侧，数字贴在线中点
  const sizeGap = 90;
  const specs = [
    { label: `宽 ${fmt(box.x1 - box.x0)}`, from: [box.x0, box.y0 - sizeGap], to: [box.x1, box.y0 - sizeGap], textAt: [midX, z, box.y0 - sizeGap] },
    { label: `深 ${fmt(box.y1 - box.y0)}`, from: [box.x0 - sizeGap, box.y0], to: [box.x0 - sizeGap, box.y1], textAt: [box.x0 - sizeGap, z, midY] },
  ];
  for (const spec of specs) {
    parent.add(line([roomToThree(spec.from[0], spec.from[1], z), roomToThree(spec.to[0], spec.to[1], z)], 0x334155));
    onLabel({ anchor: roomToThree(spec.textAt[0], spec.textAt[1], spec.textAt[2]), text: spec.label, color: 0x334155 });
  }
  // 高：画在 footprint 某个竖向棱边外侧
  const hx = box.x1 + sizeGap;
  parent.add(line([roomToThree(hx, box.y1, zStart), roomToThree(hx, box.y1, zEnd)], 0x334155));
  onLabel({
    anchor: roomToThree(hx, zMid, zEnd),
    text: `高 ${fmt(zEnd - zStart)}`,
    color: 0x334155,
  });

  // 离墙净距：只画选中件的四向，数字用紫色（与净距线同色）
  const gaps = item.clearances_mm || {};
  const gapSpecs = [
    { key: "west", from: [0, midY], to: [box.x0, midY], at: [box.x0 / 2, z, midY] },
    { key: "east", from: [box.x1, midY], to: [data.room.width_mm, midY], at: [(box.x1 + data.room.width_mm) / 2, z, midY] },
    { key: "north", from: [midX, 0], to: [midX, box.y0], at: [midX, z, box.y0 / 2] },
    { key: "south", from: [midX, box.y1], to: [midX, data.room.depth_mm], at: [midX, z, (box.y1 + data.room.depth_mm) / 2] },
  ];
  for (const spec of gapSpecs) {
    // clearances_mm 的值可能是纯数字（{west: 802}），也可能是 {gap, blocker} —— 两种都认
    const raw = gaps[spec.key];
    const gap = typeof raw === "number" ? raw : (raw && typeof raw.gap === "number" ? raw.gap : null);
    if (gap === null || gap <= 0.5) continue;
    parent.add(line([roomToThree(spec.from[0], spec.from[1], z), roomToThree(spec.to[0], spec.to[1], z)], 0x7c3aed));
    onLabel({ anchor: roomToThree(spec.at[0], spec.at[1], spec.at[2]), text: `离墙 ${fmt(gap)}`, color: 0x7c3aed });
  }
}
