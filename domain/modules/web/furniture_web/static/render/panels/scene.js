import * as THREE from "three";
import {OrbitControls} from "/vendor/three/0.186.0/OrbitControls.js";
import {createPanelCamera} from "./camera.js";
import {WOOD_BASE,WHITE_FACE,EDGE_COLOR,EDGE_OPACITY,SELECT_COLOR,HOVER_COLOR,FLOOR_COLOR,GRAIN_SEED,makeRandom,makeWoodTexture,textureFromCanvas,materialFor} from "./materials.js";

export function createPanelScene({canvas,panelList,width,depth,height,state,viewButtons,hingeSideOf}){
  const center = new THREE.Vector3(width / 2, depth / 2, height / 2);
  const modelRadius = 0.5 * Math.hypot(width, depth, height);
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

  const {setView}=createPanelCamera({canvas,camera,controls,width,depth,height,viewButtons});
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

  const raycaster=new THREE.Raycaster();
  const pointer=new THREE.Vector2();
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

function dispose(){renderer.dispose();boxGeometry.dispose();edgeGeometry.dispose()}

return {renderer,scene,camera,root,meshes,paint,draw,pick,setView,dispose};
}
