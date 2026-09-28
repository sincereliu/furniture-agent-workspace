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
    // 简单防重叠：同类标签挨太近就整体下推
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

  /** 右下角方位指示器：跟随视角旋转，但以固定的屏幕尺寸绘制，永远读得清。 */
  function drawAxisGizmo() {
    if (!axisGizmo) return;
    const { ctx } = axisGizmo;
    const S = 96;
    ctx.clearRect(0, 0, S, S);
    ctx.save();
    ctx.translate(S * 0.45, S * 0.58);
    // 世界方向 → 屏幕方向：只取水平分量，避免俯仰把两条地面轴压成一条
    camera.updateMatrixWorld(true);
    const right = new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 0);
    const east = new THREE.Vector3(right.x, 0, right.z).normalize();           // 房间 +X（东）
    const south = new THREE.Vector3().crossVectors(new THREE.Vector3(0, 1, 0), east).normalize(); // 房间 +Y（南）
    const R = 30;
    const arrows = [
      { dir: east, up: 0, color: "#dc2626", text: "X 东" },
      { dir: south, up: 0, color: "#047857", text: "Y 南" },
      { dir: null, up: 1, color: "#2563eb", text: "Z 上" },
    ];
    ctx.lineWidth = 2.2;
    ctx.font = "700 11px Inter,Microsoft YaHei,sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    for (const a of arrows) {
      const dx = a.up ? 0 : a.dir.x * R;
      const dy = a.up ? -R : a.dir.z * R;
      ctx.strokeStyle = a.color;
      ctx.fillStyle = a.color;
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.lineTo(dx, dy);
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(dx, dy, 3.2, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillText(a.text, dx + (dx >= 0 ? 16 : -16) * 0.2 + dx * 0.35, dy + (dy >= 0 ? 10 : -10));
    }
    ctx.fillStyle = "#0f172a";
    ctx.beginPath();
    ctx.arc(0, 0, 2.6, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  function isElevation() {
    const up = camera.position.y - controls.target.y;
    const flat = Math.hypot(camera.position.x - controls.target.x, camera.position.z - controls.target.z);
    return Math.abs(Math.atan2(up, flat)) < ELEVATION_PITCH;
  }

  /**
   * 房间坐标三脚架：从房间原点（西北地面角）引出，**整体在房间内部**。
   *
   * 之前把轴画在"房间边界的外侧"（Y 沿西边界外墙、Z 沿东端外墙），结果那两条线在地面上
   * 没有对应的底边，看起来就是"房间里凭空多出来的悬空线"。现在改成室内三脚架：
   *   X → 沿北墙（东向）  Y → 沿西墙（南向）  Z → 竖直向上
   * 三条长度相等（取短边与层高的较小值），颜色红/绿/蓝，标签贴在线中点。
   */
  function refreshOutline() {
    const outline = content.userData.outline;
    if (!outline || !wallShells.length) return;
    const { x0, x1, z0, z1, height } = outline;
    const at = (x, y, z) => roomToThree(x, y, z);
    const groups = { neutral: [], x: [], y: [], z: [] };
    const edge = (bucket, a, b) => { bucket.push(...a, ...b); };

    // 地板一圈：中性灰底边（房间占地轮廓）
    edge(groups.neutral, at(x0, 0, z0), at(x1, 0, z0));
    edge(groups.neutral, at(x1, 0, z0), at(x1, 0, z1));
    edge(groups.neutral, at(x0, 0, z1), at(x1, 0, z1));
    edge(groups.neutral, at(x0, 0, z0), at(x0, 0, z1));

    // 三脚架：X/Y 取房间的宽与深（贴地、沿北墙与西墙），Z 取**短轴**。
    // 为什么 Z 不取全高 2800：透视下"沿西墙向南（3000）"与"竖直向上（2800）"会被压成两条
    // 近乎竖直、方向相反的线，几何再对也读不出来。Z 取短轴后三条轴各占一个方向，一眼可辨。
    const zShaft = Math.max(500, height * 0.3);
    edge(groups.x, at(x0, 0, z0), at(x1, 0, z0));              // X 东：沿北墙脚，长 = 房间宽
    edge(groups.y, at(x0, 0, z0), at(x0, 0, z1));              // Y 南：沿西墙脚，长 = 房间深
    edge(groups.z, at(x0, 0, z0), at(x0, zShaft, z0));         // Z 上：原点上方短轴

    const palette = [["neutral", 0x64748b], ["x", 0xdc2626], ["y", 0x047857], ["z", 0x2563eb]];
    for (const [key, color] of palette) {
      let entry = outline.lines.find((item) => item.key === key);
      if (!entry) {
        entry = { key, line: lineSegments([], color) };
        content.add(entry.line);
        outline.lines.push(entry);
      }
      entry.line.geometry.dispose();
      entry.line.geometry = new THREE.BufferGeometry();
      entry.line.geometry.setAttribute("position", new THREE.Float32BufferAttribute(groups[key], 3));
    }
    // 轴端点圆点：让"这条轴到哪为止、朝哪个方向"一眼可辨（三条轴在屏幕上会被透视压得很近）
    const tips = [
      { key: "x", at: at(x1, 0, z0), color: 0xdc2626 },
      { key: "y", at: at(x0, 0, z1), color: 0x047857 },
      { key: "z", at: at(x0, zShaft, z0), color: 0x2563eb },
    ];
    outline.tips = outline.tips || [];
    tips.forEach((tip, index) => {
      if (!outline.tips[index]) {
        const dot = new THREE.Mesh(
          new THREE.SphereGeometry(1, 12, 8),
          new THREE.MeshBasicMaterial({ color: tip.color }),
        );
        content.add(dot);
        outline.tips.push(dot);
      }
      const dot = outline.tips[index];
      dot.material.color.setHex(tip.color);
      dot.position.set(tip.at[0], tip.at[1], tip.at[2]);
      dot.scale.setScalar(Math.max(60, Math.min(x1 - x0, z1 - z0, height) * 0.035));
      dot.userData.kind = null;               // 端点不参与拾取
    });
    outline.axisLength = { x: x1 - x0, y: z1 - z0, z: zShaft };
  }

  /** 把当前的墙与相机喂给纯函数 wallVisibility()，再把结果写回材质。 */
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
    result.walls.forEach((state, index) => {
      const wall = wallShells[index];
      wall.visible = state.visible;
      wall.material.opacity = state.opacity;
      // 颜色由判据一起给：背景墙用中灰。浅灰压浅色背景等于看不见。
      wall.material.color.setHex(state.color === null ? wall.userData.baseColor : state.color);
    });
  }

  function resize() {
    const width = canvas.clientWidth || 960;
    const height = canvas.clientHeight || 600;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(width, height, false);
    camera.aspect = width / Math.max(height, 1);
    camera.updateProjectionMatrix();
  }

  function clientNdc(clientX, clientY) {
    const rect = canvas.getBoundingClientRect();
    ndc.x = ((clientX - rect.left) / rect.width) * 2 - 1;
    ndc.y = -((clientY - rect.top) / rect.height) * 2 + 1;
  }

  function setView(yaw, pitch, distance, target) {
    const position = cameraThreePosition(yaw, pitch, distance, target);
    camera.position.set(position[0], position[1], position[2]);
    controls.target.set(target[0], target[2], target[1]);
    camera.up.set(0, 1, 0);
    camera.lookAt(controls.target);
    const span = Math.hypot(target[0], target[1], target[2]) + distance;
    controls.minDistance = Math.max(200, span * 0.02);
    controls.maxDistance = Math.max(distance * 6, 8000);
    controls.update();
    refreshWalls();
    refreshOutline();
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

  function draw() {
    renderer.render(scene, camera);
  }

  function sync(data, options) {
    const room = data.room;
    const selectedId = options.selectedId;
    const readOnly = options.readOnly;
    const showDims = options.dims !== false;
    disposeObject(content);
    content.clear();
    pickables = [];
    // 标注层也要跟着重建：DOM 元素不是 three 对象，content.clear() 不会清掉它们
    for (const entry of labelEntries) entry.el.remove();
    labelEntries = [];
    labelLayer = labelLayer || ensureLabelLayer(canvas);
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
      const mesh = new THREE.Mesh(
        prismGeometry(item.footprint, item.z_start, item.z_end),
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
        const frontZ = (item.z_start + item.z_end) / 2;
        const a = item.footprint[3];
        const b = item.footprint[2];
        content.add(line([
          roomToThree(a[0], a[1], frontZ),
          roomToThree(b[0], b[1], frontZ),
        ], 0x047857));
      }
      if (!selected) continue;
      const center = footprintCenter(item.footprint);
      const midZ = (item.z_start + item.z_end) / 2;
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
        rotateHandle.position.set(center[0] + 220, item.z_end + 160, center[1]);
        rotateHandle.userData = { kind: "rotate", itemId: item.id };
        addMesh(content, rotateHandle, pickables);
        const heightHandle = new THREE.Mesh(
          new THREE.SphereGeometry(64, 16, 12),
          new THREE.MeshStandardMaterial({ color: 0x3b82f6, roughness: 0.35, metalness: 0 }),
        );
        heightHandle.position.set(center[0] - 220, item.z_end + 160, center[1]);
        heightHandle.userData = { kind: "height", itemId: item.id };
        addMesh(content, heightHandle, pickables);
      }
      if (showDims) addDimensions(content, data, item);
    }
    refreshWalls();
    refreshOutline();
    // 轴标只是文字：几何（三脚架 + 地板轮廓）由 refreshOutline() 重建；
    // 标签锚点取 outline.axisLength，所以必须放在 refreshOutline() 之后
    if (labelLayer) {
      const addLabelAt = (anchor, text, color) => labelEntries.push({
        anchor, text, color, el: makeLabelElement(labelLayer, { text, color }),
      });
      const len = content.userData.outline?.axisLength || { x: width, y: depth, z: height };
      const nudge = 60;
      // 标签：X/Y 放在各自长轴上约 62% 处；Z 短轴标签放在其端点外侧
      addLabelAt(roomToThree(len.x * 0.62, 0, -nudge), `X 东 · 总宽 ${Math.round(width)}`, 0xdc2626);
      addLabelAt(roomToThree(-nudge, 0, len.y * 0.62), `Y 南 · 总深 ${Math.round(depth)}`, 0x047857);
      addLabelAt(roomToThree(-nudge * 2, len.z * 1.15, -nudge * 2), `Z 上 · 总高 ${Math.round(height)}`, 0x2563eb);
      addLabelAt(roomToThree(-nudge * 2.2, 0, -nudge * 2.2), "O (0,0,0)", 0x0f172a);
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
      refreshLabels();
      draw();
    }
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
  return {
    controls, resize, setView, readView, basis, project, ground, pick, sync, draw, setEnabled, setShiftPan,
  };
}

function footprintCenter(footprint) {
  const count = footprint.length || 1;
  return [
    footprint.reduce((sum, point) => sum + point[0], 0) / count,
    footprint.reduce((sum, point) => sum + point[1], 0) / count,
  ];
}

function addDimensions(parent, data, item) {
  const xs = item.footprint.map((point) => point[0]);
  const ys = item.footprint.map((point) => point[1]);
  const box = { x0: Math.min(...xs), x1: Math.max(...xs), y0: Math.min(...ys), y1: Math.max(...ys) };
  const midX = (box.x0 + box.x1) / 2;
  const midY = (box.y0 + box.y1) / 2;
  const z = item.z_start + 8;
  const specs = [
    [box.x0, midY, 0, midY],
    [box.x1, midY, data.room.width_mm, midY],
    [midX, box.y0, midX, 0],
    [midX, box.y1, midX, data.room.depth_mm],
  ];
  for (const spec of specs) {
    if (Math.hypot(spec[2] - spec[0], spec[3] - spec[1]) < 1) continue;
    parent.add(line([
      roomToThree(spec[0], spec[1], z),
      roomToThree(spec[2], spec[3], z),
    ], 0x7c3aed));
  }
}
