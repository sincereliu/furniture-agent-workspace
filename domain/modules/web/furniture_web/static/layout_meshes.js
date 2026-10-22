import * as THREE from "three";
import { roomToThree } from "./layout_frame.js";
import { openingSolids, wallSolids } from "./wall_solid.js";
import { wallSurfacePositions } from "./wall_surface.js";
import { chairParts } from "./chair_solid.js";
import { coffeeTableParts } from "./coffee_table_solid.js";
import { deskParts } from "./desk_solid.js";
import { sofaFrame, sofaLocalBox, sofaMount, sofaParts } from "./sofa_solid.js";
import { INK, celMaterial, furnitureColor, woodTexture } from "./layout_diorama.js";

export const ROOM_LAYER = 1;
const DIAL_COLOR = 0xf5c400;

export function markRoom(mesh) {
  mesh.layers.set(ROOM_LAYER);
  return mesh;
}

export function disposeObject(object) {
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

export function prismGeometry(footprint, z0, z1) {
  const positions = [];
  const n = footprint.length;
  const bottom = footprint.map(([x, y]) => roomToThree(x, y, z0));
  const top = footprint.map(([x, y]) => roomToThree(x, y, z1));
  const push = (a, b, c) => positions.push(...a, ...b, ...c);
  for (let i = 0; i < n; i += 1) {
    const j = (i + 1) % n;
    push(bottom[i], top[j], bottom[j]);
    push(bottom[i], top[i], top[j]);
  }
  for (let i = 1; i < n - 1; i += 1) {
    push(top[0], top[i + 1], top[i]);
    push(bottom[0], bottom[i], bottom[i + 1]);
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.computeVertexNormals();
  geometry.userData = { footprint, z0, z1 };
  return geometry;
}

export function wallGeometry(boxes, padding = 0) {
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(wallSurfacePositions(boxes, padding), 3));
  geometry.computeVertexNormals();
  geometry.userData.wallBoxes = boxes;
  return geometry;
}

export function line(points, color) {
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(points.flat(), 3));
  const material = new THREE.LineBasicMaterial({
    color,
    polygonOffset: true,
    polygonOffsetFactor: -2,
    polygonOffsetUnits: -2,
  });
  return new THREE.Line(geometry, material);
}

export function lineSegments(values, color, opacity = 1) {
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(values, 3));
  return new THREE.LineSegments(geometry, new THREE.LineBasicMaterial({
    color,
    transparent: opacity < 1,
    opacity,
  }));
}

export function addRoomBox(parent, box, material) {
  const [x0, y0, z0, x1, y1, z1] = box;
  const mesh = new THREE.Mesh(
    new THREE.BoxGeometry(x1 - x0, z1 - z0, y1 - y0),
    material,
  );
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  mesh.position.set(...roomToThree((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2));
  parent.add(mesh);
  return mesh;
}

export function insetOpening(wall, box) {
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

export function addMesh(parent, mesh, pickables) {
  parent.add(mesh);
  if (mesh.userData && mesh.userData.kind) pickables.push(mesh);
  return mesh;
}

function addShapedItem(parent, pickables, item, parts, materials, selected, addInk, blocked) {
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
  const ink = blocked ? 0xd93838 : (selected ? 0xf59e0b : INK);
  const thick = (selected || blocked) ? 22 : 14;
  for (const part of parts) {
    const local = sofaLocalBox(part.box);
    const mesh = markRoom(new THREE.Mesh(
      new THREE.BoxGeometry(...local.size),
      materials[part.role],
    ));
    mesh.position.set(...local.center);
    mesh.userData = { kind: "item", itemId: item.id };
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    addInk(mesh, ink, thick);
    group.add(mesh);
    pickables.push(mesh);
  }
  return true;
}

export function addSofa(parent, pickables, item, selected, blocked, addInk) {
  const parts = sofaParts(item.width, item.depth, item.height);
  const base = furnitureColor(item, selected, blocked);
  const fabric = celMaterial(base);
  const materials = selected || blocked
    ? { fabric, deck: fabric, cushion: fabric, wood: fabric }
    : {
        fabric,
        deck: celMaterial(0x776e64),
        cushion: celMaterial(0xd4c9bb),
        wood: celMaterial(0x3a312b),
      };
  return addShapedItem(parent, pickables, item, parts, materials, selected, addInk, blocked);
}

export function addCoffeeTable(parent, pickables, item, selected, blocked, addInk) {
  const parts = coffeeTableParts(item.width, item.depth, item.height);
  const base = furnitureColor(item, selected, blocked);
  const top = celMaterial(base);
  const materials = selected || blocked
    ? { top, leg: top, shelf: top }
    : {
        top,
        leg: celMaterial(0x3a322c),
        shelf: celMaterial(0xc9bfb0),
      };
  return addShapedItem(parent, pickables, item, parts, materials, selected, addInk, blocked);
}

export function addChair(parent, pickables, item, selected, blocked, addInk) {
  const parts = chairParts(item.width, item.depth, item.height);
  const base = furnitureColor(item, selected, blocked);
  const cushion = celMaterial(base);
  const materials = selected || blocked
    ? { seat: cushion, back: cushion, leg: cushion }
    : {
        seat: celMaterial(0xd4c9bb),
        back: cushion,
        leg: celMaterial(0x3a322c),
      };
  return addShapedItem(parent, pickables, item, parts, materials, selected, addInk, blocked);
}

export function addDesk(parent, pickables, item, selected, blocked, addInk) {
  const parts = deskParts(item.width, item.depth, item.height);
  const base = furnitureColor(item, selected, blocked);
  const top = celMaterial(base);
  const materials = selected || blocked
    ? { top, leg: top, apron: top }
    : {
        top,
        leg: celMaterial(0x3a322c),
        apron: celMaterial(0xc9bfb0),
      };
  return addShapedItem(parent, pickables, item, parts, materials, selected, addInk, blocked);
}

export function footprintCenter(footprint) {
  const count = footprint.length || 1;
  return [
    footprint.reduce((sum, point) => sum + point[0], 0) / count,
    footprint.reduce((sum, point) => sum + point[1], 0) / count,
  ];
}

export function createRotateDialMeshes(item, z) {
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
  const grab = new THREE.Mesh(
    new THREE.TorusGeometry(radius, band, 6, 64),
    new THREE.MeshBasicMaterial({ transparent: true, opacity: 0, depthWrite: false }),
  );
  grab.rotation.x = Math.PI / 2;
  grab.position.set(...roomToThree(center[0], center[1], z));
  return { arrow, grab };
}

export function buildRoomStage(content, width, depth, height, openings, obstacles, addInk) {
  const boards = woodTexture();
  boards.repeat.set(Math.max(width / 1200, 1), Math.max(depth / 1200, 1));
  const floorMesh = markRoom(new THREE.Mesh(
    new THREE.PlaneGeometry(width, depth),
    celMaterial(0xffffff, { map: boards }),
  ));
  floorMesh.rotation.x = -Math.PI / 2;
  floorMesh.position.set(...roomToThree(width / 2, depth / 2, 0));
  floorMesh.receiveShadow = true;
  content.add(floorMesh);
  addInk(floorMesh, 0xb8b0a4);

  const step = [200, 250, 500, 1000, 2000, 5000].find((value) => Math.max(width, depth) / value <= 14) || 5000;
  const grid = [];
  for (let x = step; x < width; x += step) grid.push(...roomToThree(x, 0, 2), ...roomToThree(x, depth, 2));
  for (let y = step; y < depth; y += step) grid.push(...roomToThree(0, y, 2), ...roomToThree(width, y, 2));
  if (grid.length) content.add(lineSegments(grid, 0xb5aea2, 0.22));

  const wallMaterial = celMaterial(0xede8df, {
    transparent: true,
    opacity: 1,
    depthWrite: true,
  });
  const shells = [];
  for (const solid of wallSolids(width, depth, height, openings)) {
    const material = wallMaterial.clone();
    const group = new THREE.Group();
    const inks = [];
    if (solid.boxes.length) {
      const mesh = markRoom(new THREE.Mesh(wallGeometry(solid.boxes), material));
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      group.add(mesh);
      inks.push(addInk(mesh, 0x4a433b, 12));
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

  for (const opening of openingSolids(width, depth, openings)) {
    const windowGlow = opening.kind === "window";
    addRoomBox(
      content,
      insetOpening(opening.wall, opening.box),
      new THREE.MeshBasicMaterial({
        color: windowGlow ? 0xc8e6f5 : 0xd7be9e,
        transparent: true,
        opacity: windowGlow ? 0.76 : 0.90,
        side: THREE.DoubleSide,
      }),
    );
  }

  for (const obstacle of obstacles) {
    const obstacleMesh = markRoom(new THREE.Mesh(
      prismGeometry(obstacle.footprint, obstacle.z_start, obstacle.z_end),
      celMaterial(0xd98986),
    ));
    obstacleMesh.castShadow = true;
    obstacleMesh.receiveShadow = true;
    addInk(obstacleMesh, 0x6a3030, 16);
    content.add(obstacleMesh);
  }

  return shells;
}

export function buildOutline(content) {
  const { width } = content.userData.outline;
  content.add(lineSegments([
    ...roomToThree(0, 0, 0), ...roomToThree(width, 0, 0),
  ], 0xb8b0a4));
}

export function buildAxes(content, onLabel) {
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
    onLabel(axis);
  }
}

export function addDimensions(parent, annotations, onLabel) {
  for (const annotation of annotations) {
    const dimension = line([
      roomToThree(...annotation.from), roomToThree(...annotation.to),
    ], annotation.color);
    dimension.material.depthTest = false;
    dimension.material.depthWrite = false;
    dimension.material.transparent = true;
    dimension.material.opacity = .8;
    dimension.renderOrder = 10;
    parent.add(dimension);
    onLabel(annotation);
  }
}
