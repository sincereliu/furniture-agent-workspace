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

function makeWoodTexture() {
  const canvas = document.createElement("canvas");
  canvas.width = 256;
  canvas.height = 256;
  const context = canvas.getContext("2d");
  if (!context) return null;
  context.fillStyle = "#ddc19b";
  context.fillRect(0, 0, 256, 256);
  // 细密顺纹 + 几道浅色宽纹：浅木（白橡之类）的样子，纹路对比不能太大。
  for (let index = 0; index < 220; index += 1) {
    const x = Math.random() * 256;
    const width = 0.5 + Math.random() * 1.7;
    const dark = Math.random() < 0.68;
    context.strokeStyle = dark
      ? `rgba(160,124,84,${0.05 + Math.random() * 0.11})`
      : `rgba(255,247,232,${0.05 + Math.random() * 0.11})`;
    context.lineWidth = width;
    context.beginPath();
    context.moveTo(x, -10);
    let y = 0;
    while (y < 266) {
      const step = 8 + Math.random() * 20;
      y += step;
      context.lineTo(x + (Math.random() - 0.5) * 8, y);
    }
    context.stroke();
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 4;
  return texture;
}

function materialFor(kind, texture) {
  if (kind === "white") {
    return new THREE.MeshStandardMaterial({
      color: WHITE_FACE,
      roughness: 0.34,
      metalness: 0.0,
      side: THREE.DoubleSide,
    });
  }
  return new THREE.MeshStandardMaterial({
    color: WOOD_BASE,
    map: texture,
    roughness: 0.72,
    metalness: 0.0,
    side: THREE.DoubleSide,
  });
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
    counts[panel.group] = (counts[panel.group] || 0) + 1;
  }
  return counts;
}

// 页面上材料只有两种，图例也照这个来。
const MATERIAL_LABELS = { wood: "柜体木纹", white: "门板白色" };

export function materialLabel(material) {
  return MATERIAL_LABELS[material] || "柜体木纹";
}

// 环顾一圈的方向（three.js 坐标，已经含 Z 朝上 → Y 朝上的那次旋转）。
//
// 换算关系是 `世界 = (柜X, 柜Z, -柜Y)`，所以**柜体 +Y（门那一面）在世界里是 -Z**：
// 「正面（门）」必须站在 -Z 看，站到 +Z 看到的是背板。这两个弄反的话，人会以为
// 门板没画出来（实测踩过）。左右同理：站在门前看，柜体 +X 在人右手边，所以
// 「左侧」= 从 -X 看、「右侧」= 从 +X 看。
const VIEWS = {
  iso: [0.78, 0.62, -0.86],
  front: [0, 0.22, -1.25],
  back: [0, 0.22, 1.25],
  left: [-1.25, 0.22, -0.08],
  right: [1.25, 0.22, -0.08],
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
  // **取景一律用世界坐标**（`world = (柜X, 柜Z, -柜Y)`），和 VIEWS 同一套；
  // 柜体坐标和世界坐标差着那次 Z→Y 的旋转，混着用会瞄错方向（实测踩过）。
  const centerWorld = new THREE.Vector3(width / 2, height / 2, -depth / 2);
  const CORNERS = [];
  for (const x of [0, width]) {
    for (const y of [0, depth]) {
      for (const z of [0, height]) {
        CORNERS.push(new THREE.Vector3(x, z, -y));
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

  const woodTexture = makeWoodTexture();
  const meshes = [];
  for (const panel of panelList) {
    const [sx, sy, sz] = panel.size_mm.map(Number);
    const [px, py, pz] = panel.pos_mm.map(Number);
    const white = panel.material === "white";
    const material = materialFor(panel.material, woodTexture);
    if (!white && material.map) {
      // 一块板一份贴图：整台柜子共用一张图的话，每块板的花纹位置会一模一样。
      // 盒子几何的 UV 每面都是 0–1，重复次数按长边给，木纹才不会被拉成条纹。
      const map = material.map.clone();
      map.needsUpdate = true;
      const along = Math.max(sx, sy, sz);
      const repeat = Math.min(4.5, Math.max(1, along / 220));
      map.repeat.set(repeat, repeat);
      map.offset.set(Math.random() * 0.5, Math.random() * 0.5);
      material.map = map;
    }
    const mesh = new THREE.Mesh(boxGeometry, material);
    mesh.scale.set(sx, sy, sz);
    const home = new THREE.Vector3(px + sx / 2, py + sy / 2, pz + sz / 2);
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
    hovered: null,
    selected: null,
  };

  const isFrontPanel = (panel) =>
    panel.group === "door" || panel.group === "drawer_front";

  // 材料只有两种，所以「透视」只用材质名判断；旧数据没有 material 时退回角色判断。
  const isWhitePanel = (panel) =>
    panel.material ? panel.material === "white" : isFrontPanel(panel);

  const isSuppressed = (panel) =>
    (!state.doors && isFrontPanel(panel)) ||
    (!state.back && (panel.group === "back" || panel.group === "rail"));

  // 三种状态：本色（木纹或白门）、悬停（琥珀色）、选中（蓝）。悬停/选中都把纹理压掉，
  // 只留下纯色 + 自发光，鼠标扫到哪里一眼就能看出来。
  const LOOK = {
    normal: { emissive: 0x000000, emissiveIntensity: 1, edge: EDGE_COLOR, edgeOpacity: EDGE_OPACITY },
    hover: { color: HOVER_COLOR, emissive: 0x8a4d00, emissiveIntensity: 0.85, edge: HOVER_COLOR, edgeOpacity: 1 },
    select: { color: SELECT_COLOR, emissive: SELECT_COLOR, emissiveIntensity: 0.5, edge: SELECT_COLOR, edgeOpacity: 1 },
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

      record.material.map = highlighted || isWhitePanel(panel) ? null : record.woodMap;
      record.material.color.setHex(highlighted ? look.color : record.baseColor);
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
    detail.append(title, list);
  }

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

  function pick(event) {
    const rect = canvas.getBoundingClientRect();
    pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(pointer, camera);
    const hits = raycaster.intersectObjects(
      meshes.filter((record) => record.mesh.visible).map((record) => record.mesh),
      false
    );
    return hits.length ? hits[0].object.userData.record.panel : null;
  }

  canvas.addEventListener("pointerdown", (event) => {
    downAt = { x: event.clientX, y: event.clientY };
  });
  canvas.addEventListener("pointerup", (event) => {
    if (!downAt) return;
    const moved = Math.hypot(event.clientX - downAt.x, event.clientY - downAt.y);
    downAt = null;
    if (moved > 4) return;
    const panel = pick(event);
    select(panel && panel.id !== state.selected ? panel.id : null);
  });
  canvas.addEventListener("pointermove", (event) => {
    const panel = pick(event);
    const hoveredId = panel ? panel.id : null;
    if (hoveredId !== state.hovered) {
      state.hovered = hoveredId;
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
    if (state.hovered !== null) {
      state.hovered = null;
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

  // 地址栏可以指点初始状态：`?view=front&doors=0&wire=1&explode=60`。
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
    hover(panelId) {
      state.hovered = panelId || null;
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
