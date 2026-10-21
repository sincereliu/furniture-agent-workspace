import * as THREE from "three";
import { OrbitControls } from "/vendor/three/0.186.0/OrbitControls.js";
import { cameraFov, cameraThreePosition, roomToThree, threeToRoom } from "./layout_frame.js";
import { roomAxes, dimensionAnnotations } from "./layout_annotations.js";
import { ELEVATION_PITCH, wallVisibility } from "./wall_view.js";
import { isFixedChair } from "./chair_solid.js";
import { isFixedCoffeeTable } from "./coffee_table_solid.js";
import { isFixedDesk } from "./desk_solid.js";
import { isFixedSofa } from "./sofa_solid.js";
import { inkViewBiasGlsl } from "./ink_depth.js";
import { INK, addDiorama, addSky, celMaterial, furnitureColor } from "./layout_diorama.js";
import { createLabelOverlay } from "./layout_overlay.js";
import {
  ROOM_LAYER,
  addChair,
  addCoffeeTable,
  addDesk,
  addDimensions,
  addMesh,
  addSofa,
  buildAxes,
  buildOutline,
  buildRoomStage,
  createRotateDialMeshes,
  disposeObject,
  footprintCenter,
  line,
  markRoom,
  prismGeometry,
} from "./layout_meshes.js";

export { cameraThreePosition, roomToThree };

function inkMaterial(color) {
  const material = new THREE.LineBasicMaterial({
    color,
    transparent: true,
  });
  material.customProgramCacheKey = () => "ink-view-bias";
  material.onBeforeCompile = (shader) => {
    shader.vertexShader = shader.vertexShader.replace(
      "#include <project_vertex>",
      inkViewBiasGlsl(),
    );
  };
  return material;
}

function createOutlineMaterial(thickness = 14, color = INK, opacity = 1.0) {
  const mat = new THREE.ShaderMaterial({
    uniforms: {
      uThickness: { value: thickness },
      uColor: { value: new THREE.Color(color) },
      opacity: { value: opacity },
    },
    vertexShader: `
      uniform float uThickness;
      void main() {
        vec4 mv = modelViewMatrix * vec4(position, 1.0);
        vec3 n = normalize(normalMatrix * normal);
        mv.xyz += n * uThickness;
        gl_Position = projectionMatrix * mv;
      }
    `,
    fragmentShader: `
      uniform vec3 uColor;
      uniform float opacity;
      void main() {
        gl_FragColor = vec4(uColor, opacity);
      }
    `,
    side: THREE.BackSide,
    transparent: opacity < 0.999,
    depthWrite: opacity >= 0.999,
  });
  Object.defineProperty(mat, "opacity", {
    get() {
      return this.uniforms.opacity.value;
    },
    set(v) {
      this.uniforms.opacity.value = v;
      this.transparent = v < 0.999;
    },
  });
  return mat;
}

function addInk(mesh, color = INK, thickness = 14) {
  if (mesh.geometry && mesh.geometry.type === "PlaneGeometry") {
    const ink = new THREE.LineSegments(
      new THREE.EdgesGeometry(mesh.geometry, 25),
      inkMaterial(color),
    );
    ink.raycast = () => {};
    mesh.add(ink);
    mesh.userData.ink = ink;
    return ink;
  }
  const outline = new THREE.Mesh(
    mesh.geometry,
    createOutlineMaterial(thickness, color),
  );
  outline.castShadow = false;
  outline.receiveShadow = false;
  outline.raycast = () => {};
  if (mesh.layers) outline.layers.mask = mesh.layers.mask;
  mesh.add(outline);
  mesh.userData.ink = outline;
  return outline;
}

export function mountLayout(canvas) {
  const renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: true,
    logarithmicDepthBuffer: true,
  });
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.setClearColor(0xf2efe9, 1);
  const camera = new THREE.PerspectiveCamera(48, 1, 10, 500000);
  camera.up.set(0, 1, 0);
  const LENS_BASE = 48;
  const ELEVATION_PULL = 8;
  const scene = new THREE.Scene();
  const sky = addSky();
  scene.add(sky);
  const nightFill = new THREE.HemisphereLight(0xffffff, 0xe2ddd5, 0.92);
  nightFill.layers.set(0);
  const moon = new THREE.DirectionalLight(0xfffcf5, 0.48);
  moon.layers.set(0);
  const roomFill = new THREE.HemisphereLight(0xfffdfa, 0xdcd5c9, 0.76);
  roomFill.layers.set(ROOM_LAYER);
  const roomKey = new THREE.DirectionalLight(0xfffaf0, 0.95);
  roomKey.layers.set(ROOM_LAYER);
  roomKey.castShadow = true;
  roomKey.shadow.mapSize.set(2048, 2048);
  roomKey.shadow.bias = -0.0004;
  roomKey.shadow.normalBias = 0.02;
  scene.add(nightFill, moon, roomFill, roomKey);

  // 分层缓存：房间舞台（围墙/地板/城市底座/坐标轴）、家具网格池（按 id 增量更新）、动态标注与手柄
  const content = new THREE.Group();
  const stageGroup = new THREE.Group();
  const itemsGroup = new THREE.Group();
  const annotationsGroup = new THREE.Group();
  content.add(stageGroup, itemsGroup, annotationsGroup);
  scene.add(content);

  let stageKey = "";
  let stageAxisLabels = [];
  const itemCache = new Map();

  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = false;
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
  const overlay = createLabelOverlay(canvas, camera);
  let pickables = [];
  let wallShells = [];
  const WALL_FADE_MS = 150;
  let wallFade = [];
  let wallFadeFrom = [];
  let wallFadeTargets = [];
  let wallFadeStarted = 0;

  function setLens(fovDeg) {
    const next = Math.max(0.1, Math.min(150, Number(fovDeg) || LENS_BASE));
    if (Math.abs(camera.fov - next) < 1e-6) return;
    camera.fov = next;
    camera.updateProjectionMatrix();
  }

  function isElevation() {
    const [x, y, z] = threeToRoom(...camera.position.clone().sub(controls.target).toArray());
    return Math.abs(Math.atan2(z, Math.hypot(x, y))) < ELEVATION_PITCH;
  }

  function refreshWalls() {
    if (!wallShells.length) return;
    const geometry = wallShells.map((wall) => ({
      id: wall.userData.wallId,
      center: [wall.userData.wallCenter.x, wall.userData.wallCenter.y, wall.userData.wallCenter.z],
      normal: [wall.userData.wallNormal.x, wall.userData.wallNormal.y, wall.userData.wallNormal.z],
    }));
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
      wallFade = [...targets];
      wallFadeTargets = [...targets];
      wallFadeStarted = 0;
    } else {
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
      wall.visible = opacity > 0.002;
      wall.userData.material.opacity = opacity;
      wall.userData.material.depthWrite = opacity >= 0.999;
      wall.userData.material.color.setHex(state.color === null ? wall.userData.baseColor : state.color);
      for (const ink of wall.userData.inks) {
        ink.visible = wall.visible;
        ink.material.opacity = Math.min(1, opacity * 1.35);
        ink.material.depthWrite = opacity >= 0.999;
      }
    });
  }

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
    overlay.refresh();
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

  function draw() {
    sky.position.copy(controls.target);
    renderer.autoClear = true;
    renderer.render(scene, camera);
  }

  function setFovForZoom(zoom) {
    const z = Math.max(0.02, Number(zoom) || 1);
    setLens(cameraFov(z));
  }

  function elevationPull() {
    return ELEVATION_PULL;
  }

  function ensureRoomStage(data) {
    const nextStageKey = JSON.stringify([data.room, data.openings || [], data.obstacles || []]);
    if (nextStageKey === stageKey) {
      for (const spec of stageAxisLabels) overlay.addLabel(spec);
      return;
    }
    stageKey = nextStageKey;
    disposeObject(stageGroup);
    stageGroup.clear();
    stageAxisLabels = [];
    wallFade = [];
    wallFadeFrom = [];
    wallFadeTargets = [];
    wallFadeStarted = 0;

    const room = data.room;
    const width = room.width_mm;
    const depth = room.depth_mm;
    const height = room.height_mm;
    roomKey.position.set(...roomToThree(width * 0.25, depth * 1.35, height * 2.8));
    roomKey.target.position.set(...roomToThree(width / 2, depth / 2, 0));
    if (!roomKey.target.parent) scene.add(roomKey.target);
    const d = Math.max(width, depth) * 0.95;
    roomKey.shadow.camera.left = -d;
    roomKey.shadow.camera.right = d;
    roomKey.shadow.camera.top = d;
    roomKey.shadow.camera.bottom = -d;
    roomKey.shadow.camera.near = 100;
    roomKey.shadow.camera.far = height * 7;
    roomKey.shadow.camera.updateProjectionMatrix();
    moon.position.set(...roomToThree(-width, -depth * 0.4, height * 4));
    addDiorama(stageGroup, width, depth, addInk);
    stageGroup.userData.outline = {
      width, depth, height, axes: roomAxes(room),
    };
    content.userData.roomDiagonal = Math.hypot(width, depth, height);
    wallShells = buildRoomStage(
      stageGroup, width, depth, height,
      data.openings || [], data.obstacles || [],
      addInk,
    );
    buildOutline(stageGroup);
    buildAxes(stageGroup, (spec) => {
      stageAxisLabels.push(spec);
      overlay.addLabel(spec);
    });
  }

  function sync(data, options) {
    const selectedId = options.selectedId;
    const readOnly = options.readOnly;
    const dimsMode = options.dims === false ? "off" : (options.dims || "selected");
    disposeObject(annotationsGroup);
    annotationsGroup.clear();
    pickables = [];
    overlay.clear();

    ensureRoomStage(data);

    const activeIds = new Set();
    for (const item of data.items || []) {
      activeIds.add(item.id);
      const selected = item.id === selectedId;
      const blocked = selected && options.blockedId === item.id;
      const itemZStart = item.z_start, itemZEnd = item.z_end;
      const itemSig = JSON.stringify([
        item.footprint, itemZStart, itemZEnd,
        item.width, item.depth, item.height,
        item.category, item.manufacture,
        selected, blocked,
      ]);
      let cached = itemCache.get(item.id);
      if (!cached || cached.signature !== itemSig) {
        if (cached) {
          itemsGroup.remove(cached.group);
          disposeObject(cached.group);
        }
        const itemGroup = new THREE.Group();
        const itemPickables = [];
        const drewShape = (isFixedSofa(item) && addSofa(itemGroup, itemPickables, item, selected, blocked, addInk))
          || (isFixedCoffeeTable(item) && addCoffeeTable(itemGroup, itemPickables, item, selected, blocked, addInk))
          || (isFixedChair(item) && addChair(itemGroup, itemPickables, item, selected, blocked, addInk))
          || (isFixedDesk(item) && addDesk(itemGroup, itemPickables, item, selected, blocked, addInk));
        if (!drewShape) {
          const mesh = markRoom(new THREE.Mesh(
            prismGeometry(item.footprint, itemZStart, itemZEnd),
            celMaterial(furnitureColor(item, selected, blocked)),
          ));
          mesh.castShadow = true;
          mesh.receiveShadow = true;
          const outlineColor = blocked ? 0xd93838 : (selected ? 0xf59e0b : INK);
          const outlineThick = (selected || blocked) ? 22 : 14;
          addInk(mesh, outlineColor, outlineThick);
          mesh.userData = { kind: "item", itemId: item.id };
          addMesh(itemGroup, mesh, itemPickables);
        }
        if (item.footprint.length >= 4) {
          const frontZ = (itemZStart + itemZEnd) / 2;
          const a = item.footprint[3];
          const b = item.footprint[2];
          itemGroup.add(line([
            roomToThree(a[0], a[1], frontZ),
            roomToThree(b[0], b[1], frontZ),
          ], 0x047857));
        }
        itemsGroup.add(itemGroup);
        cached = { signature: itemSig, group: itemGroup, pickables: itemPickables };
        itemCache.set(item.id, cached);
      }
      pickables.push(...cached.pickables);

      const dimMode = dimsMode === "off" ? "off" : (dimsMode === "all" ? "all" : (selected ? "selected" : "off"));
      if (dimMode !== "off" && (dimMode === "all" || selected)) {
        addDimensions(annotationsGroup, dimensionAnnotations(data.room, item), overlay.addLabel);
      }
      if (!selected) continue;
      const center = footprintCenter(item.footprint);
      if (!readOnly) {
        const fillsWall = item.placement && item.placement.fill;
        if (!fillsWall && item.footprint.length >= 4) {
          const dial = createRotateDialMeshes(item, (itemZStart + itemZEnd) / 2);
          dial.arrow.userData = { kind: "rotate", itemId: item.id };
          dial.grab.userData = { kind: "ring", itemId: item.id };
          addMesh(annotationsGroup, dial.arrow, pickables);
          addMesh(annotationsGroup, dial.grab, pickables);
        }
        const heightHandle = new THREE.Mesh(
          new THREE.SphereGeometry(26, 16, 12),
          new THREE.MeshBasicMaterial({ color: 0x3b82f6 }),
        );
        heightHandle.position.set(...roomToThree(center[0], center[1], itemZEnd + 72));
        heightHandle.userData = { kind: "height", itemId: item.id };
        addMesh(annotationsGroup, heightHandle, pickables);
      }
    }

    for (const [id, cached] of itemCache.entries()) {
      if (!activeIds.has(id)) {
        itemsGroup.remove(cached.group);
        disposeObject(cached.group);
        itemCache.delete(id);
      }
    }

    refreshWalls();
    applyRoomLimits();
    overlay.refresh();
    draw();
  }

  function setEnabled(enabled) {
    controls.enabled = enabled;
  }

  function setShiftPan(enabled) {
    controls.mouseButtons.LEFT = enabled ? THREE.MOUSE.PAN : THREE.MOUSE.ROTATE;
  }

  resize();
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
      overlay.refresh();
      draw();
    } else if (wallFadeRunning()) {
      refreshWalls();
      draw();
    }
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);

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

  window.__diag = {
    scene, camera, controls, content, stageGroup, itemsGroup, annotationsGroup,
    itemCache, renderer, syncCached,
  };
  return {
    controls, resize, setView, readView, basis, project, ground, pick, sync: syncCached, draw, setEnabled, setShiftPan,
    setFovForZoom, elevationPull,
  };
}
