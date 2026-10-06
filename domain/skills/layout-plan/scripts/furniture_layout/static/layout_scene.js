import * as THREE from "three";
import { OrbitControls } from "/vendor/three/0.186.0/OrbitControls.js";
import { cameraFov, cameraThreePosition, roomToThree, threeToRoom } from "./layout_frame.js";
import { ROOM_AXES, roomAxes, dimensionAnnotations } from "./layout_annotations.js";
import { placeLabels } from "./layout_labels.js";
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
  sun.position.set(...roomToThree(4000, 2000, 8000));
  scene.add(sun);
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
  const raycaster = new THREE.Raycaster();
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
    ctx.fillStyle = "#0f172a";
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
    ], 0x64748b));
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
    const floorMesh = new THREE.Mesh(
      new THREE.PlaneGeometry(width, depth),
      new THREE.MeshStandardMaterial({ color: 0xf8fafc, roughness: 1, metalness: 0, side: THREE.DoubleSide }),
    );
    floorMesh.rotation.x = -Math.PI / 2;
    floorMesh.position.set(...roomToThree(width / 2, depth / 2, 0));
    content.add(floorMesh);
    const step = [200, 250, 500, 1000, 2000, 5000].find((value) => Math.max(width, depth) / value <= 14) || 5000;
    const grid = [];
    for (let x = step; x < width; x += step) grid.push(...roomToThree(x, 0, 0.4), ...roomToThree(x, depth, 0.4));
    for (let y = step; y < depth; y += step) grid.push(...roomToThree(0, y, 0.4), ...roomToThree(width, y, 0.4));
    if (grid.length) content.add(lineSegments(grid, 0xcbd5e1));
    // outline 内的几何和标注定义都使用房间坐标。
    content.userData.outline = {
      width, depth, height, axes: roomAxes(room),
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
      mesh.userData.wallCenter = new THREE.Vector3(...roomToThree(...center));
      mesh.userData.wallNormal = new THREE.Vector3(...roomToThree(...normal)).normalize();
      mesh.userData.wallId = wallId;
      mesh.userData.baseColor = wallMaterial.color.getHex();
      shells.push(mesh);
      content.add(mesh);
    };
    // 北墙：先设 position 再 addWall。漏掉 position 会让它落在世界原点（房间中心）——
    // 表现就是"北墙跑到房间中间、只有一半落在地板上"。
    const north = new THREE.Mesh(new THREE.PlaneGeometry(width, height), wallMaterial);
    north.position.set(...roomToThree(width / 2, 0, height / 2));
    addWall(north, [width / 2, 0, 0], [0, -1, 0], "north");
    const east = new THREE.Mesh(new THREE.PlaneGeometry(depth, height), wallMaterial);
    east.rotation.y = Math.PI / 2;
    east.position.set(...roomToThree(width, depth / 2, height / 2));
    addWall(east, [width, depth / 2, 0], [1, 0, 0], "east");
    const south = new THREE.Mesh(new THREE.PlaneGeometry(width, height), wallMaterial);
    south.rotation.y = Math.PI;
    south.position.set(...roomToThree(width / 2, depth, height / 2));
    addWall(south, [width / 2, depth, 0], [0, 1, 0], "south");
    const west = new THREE.Mesh(new THREE.PlaneGeometry(depth, height), wallMaterial);
    west.rotation.y = -Math.PI / 2;
    west.position.set(...roomToThree(0, depth / 2, height / 2));
    addWall(west, [0, depth / 2, 0], [-1, 0, 0], "west");
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
        new THREE.BoxGeometry(...roomToThree(box[3] - box[0], box[4] - box[1], box[5] - box[2])),
        new THREE.MeshStandardMaterial({ color: 0x38bdf8, transparent: true, opacity: 0.55, roughness: 0.4, metalness: 0, side: THREE.DoubleSide }),
      );
      mesh.position.set(...roomToThree((box[0] + box[3]) / 2, (box[1] + box[4]) / 2, (box[2] + box[5]) / 2));
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
      // 页面边界已把规范字段转换成画布模型。
      const itemZStart = item.z_start, itemZEnd = item.z_end;
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
      const midZ = (itemZStart + itemZEnd) / 2;
      if (!readOnly) {
        const fillsWall = item.placement && item.placement.fill;
        if (!fillsWall) {
          const ring = new THREE.Mesh(
            new THREE.TorusGeometry(Math.max(180, width * 0.06), 14, 8, 48),
            new THREE.MeshStandardMaterial({ color: 0xf59e0b, roughness: 0.4, metalness: 0 }),
          );
          ring.rotation.x = Math.PI / 2;
          ring.position.set(...roomToThree(center[0], center[1], midZ));
          ring.userData = { kind: "ring", itemId: item.id };
          addMesh(content, ring, pickables);
          const rotateHandle = new THREE.Mesh(
            new THREE.SphereGeometry(70, 16, 12),
            new THREE.MeshStandardMaterial({ color: 0xf59e0b, roughness: 0.35, metalness: 0 }),
          );
          rotateHandle.position.set(...roomToThree(center[0] + 220, center[1], itemZEnd + 160));
          rotateHandle.userData = { kind: "rotate", itemId: item.id };
          addMesh(content, rotateHandle, pickables);
        }
        const heightHandle = new THREE.Mesh(
          new THREE.SphereGeometry(64, 16, 12),
          new THREE.MeshStandardMaterial({ color: 0x3b82f6, roughness: 0.35, metalness: 0 }),
        );
        heightHandle.position.set(...roomToThree(center[0] - 220, center[1], itemZEnd + 160));
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
