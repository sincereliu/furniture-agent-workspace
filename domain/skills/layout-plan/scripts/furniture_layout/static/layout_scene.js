import * as THREE from "three";
import { OrbitControls } from "./OrbitControls.js";
import { cameraThreePosition, roomToThree } from "./layout_frame.js";

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
  return new THREE.Line(geometry, new THREE.LineBasicMaterial({ color }));
}

function lineSegments(values, color) {
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(values, 3));
  return new THREE.LineSegments(geometry, new THREE.LineBasicMaterial({ color }));
}

function labelSprite(text, color) {
  const board = document.createElement("canvas");
  board.width = 512;
  board.height = 64;
  const ctx = board.getContext("2d");
  ctx.clearRect(0, 0, board.width, board.height);
  ctx.font = "700 28px Microsoft YaHei, sans-serif";
  ctx.fillStyle = color;
  ctx.textBaseline = "middle";
  ctx.fillText(text, 8, 32);
  const material = new THREE.SpriteMaterial({
    map: new THREE.CanvasTexture(board),
    transparent: true,
    depthTest: false,
  });
  const sprite = new THREE.Sprite(material);
  sprite.scale.set(980, 122, 1);
  sprite.renderOrder = 4;
  return sprite;
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
  let pickables = [];

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
    const shell = new THREE.BoxGeometry(width, height, depth);
    shell.translate(width / 2, height / 2, depth / 2);
    content.add(new THREE.LineSegments(
      new THREE.EdgesGeometry(shell),
      new THREE.LineBasicMaterial({ color: 0x64748b }),
    ));
    const wallMaterial = new THREE.MeshStandardMaterial({
      color: 0xdbe3ee,
      transparent: true,
      opacity: 0.28,
      roughness: 1,
      metalness: 0,
      side: THREE.DoubleSide,
      depthWrite: false,
    });
    const northWall = new THREE.Mesh(new THREE.PlaneGeometry(width, height), wallMaterial);
    northWall.position.set(width / 2, height / 2, 0);
    content.add(northWall);
    const east = new THREE.Mesh(new THREE.PlaneGeometry(depth, height), wallMaterial);
    east.rotation.y = Math.PI / 2;
    east.position.set(width, height / 2, depth / 2);
    content.add(east);
    const south = new THREE.Mesh(new THREE.PlaneGeometry(width, height), wallMaterial);
    south.rotation.y = Math.PI;
    south.position.set(width / 2, height / 2, depth);
    content.add(south);
    const west = new THREE.Mesh(new THREE.PlaneGeometry(depth, height), wallMaterial);
    west.rotation.y = -Math.PI / 2;
    west.position.set(0, height / 2, depth / 2);
    content.add(west);
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
    addAxes(content, width, depth, height);
    draw();
  }

  function setEnabled(enabled) {
    controls.enabled = enabled;
  }

  function setShiftPan(enabled) {
    controls.mouseButtons.LEFT = enabled ? THREE.MOUSE.PAN : THREE.MOUSE.ROTATE;
  }

  resize();
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

function addAxes(parent, width, depth, height) {
  const gap = Math.max(120, Math.min(width, depth) * 0.04);
  const arms = [
    { from: roomToThree(0, -gap, 0), to: roomToThree(width, -gap, 0), color: 0xdc2626, text: `X 东 · 总宽 ${Math.round(width)}` },
    { from: roomToThree(-gap, 0, 0), to: roomToThree(-gap, depth, 0), color: 0x047857, text: `Y 南 · 总深 ${Math.round(depth)}` },
    { from: roomToThree(-gap, -gap, 0), to: roomToThree(-gap, -gap, height), color: 0x2563eb, text: `Z 上 · 总高 ${Math.round(height)}` },
  ];
  for (const arm of arms) {
    parent.add(line([arm.from, arm.to], arm.color));
    const sprite = labelSprite(arm.text, `#${arm.color.toString(16).padStart(6, "0")}`);
    sprite.position.set((arm.from[0] + arm.to[0]) / 2, (arm.from[1] + arm.to[1]) / 2, (arm.from[2] + arm.to[2]) / 2);
    parent.add(sprite);
  }
  const origin = labelSprite("O (0,0,0)", "#0f172a");
  origin.position.set(-gap, 0, -gap);
  parent.add(origin);
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
