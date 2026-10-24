import assert from "node:assert/strict";
import { createDragTransaction, poseOperation } from "./layout_interaction.js";
import { heightProbe, localFootprint, resolveInteger, setItemHeight, solveRotation } from "./layout_solver.js";

const basis = { right: [1, 0, 0], forward: [0, -Math.SQRT1_2, -Math.SQRT1_2], up: [0, 0, Math.SQRT1_2] };
const room = { id: "room", width_mm: 3600, depth_mm: 3000, height_mm: 2800 };
const walls = {
  north: { origin: [700, 0], angle: 0, normal: [0, 1], tangent: [1, 0] },
  east: { origin: [3600, 700], angle: 90, normal: [-1, 0], tangent: [0, 1] },
  south: { origin: [2900, 3000], angle: 180, normal: [0, -1], tangent: [-1, 0] },
  west: { origin: [0, 2300], angle: 270, normal: [1, 0], tangent: [0, -1] },
};
function itemFor(wall, changes = {}) {
  const w = walls[wall];
  const item = { id: "cab", label: "cab", category: "bookcase", furniture_category: "floor_cabinet",
    width: 900, depth: 400, height: 1000, z_start: 0, z_end: 1000, manufacture: true,
    placement: { mode: "wall", host_wall: wall, origin_x_mm: w.origin[0], origin_y_mm: w.origin[1],
      origin_z_mm: 0, rotation_z_deg: w.angle, fill: false }, ...changes };
  item.footprint = localFootprint(item, item.placement.origin_x_mm, item.placement.origin_y_mm, item.placement.rotation_z_deg);
  return item;
}
function gesture(item, options = {}) {
  const scene = { room, items: [item], obstacles: [], openings: [] };
  const projectWallNormal = wall => ({ x: walls[wall].normal[0], y: walls[wall].normal[1] });
  return { scene, tx: createDragTransaction({ scene, item, kind: "move", pointerId: 1,
    screen: [0, 0], basis, scale: Math.SQRT1_2,
    wallScreenNormal: item.placement.host_wall ? projectWallNormal(item.placement.host_wall) : null,
    projectWallNormal, ...options }) };
}
const screen = (x, y) => [x / Math.SQRT1_2, y];
const fixtures = [];
function addFixture(item, candidate) {
  const source = { id: item.id, category: item.category, furniture_category: item.furniture_category,
    width: item.width, depth: item.depth, height: item.height,
    placement: { ...poseOperation(item), mode: "free" } };
  delete source.placement.op;delete source.placement.item_id;delete source.placement.host_wall;
  fixtures.push({ room, source, operation: poseOperation(candidate), expected: {
    placement: candidate.placement, footprint: candidate.footprint } });
}
for (const [wall, w] of Object.entries(walls)) {
  const item = itemFor(wall), original = structuredClone(item);
  const { tx, scene } = gesture(item);
  const at = (away, along) => screen(w.normal[0] * away + w.tangent[0] * along,
    w.normal[1] * away + w.tangent[1] * along);
  tx.update(at(120, 0));
  tx.update(at(120, 200));
  tx.update(at(0, 200));
  assert.equal(tx.item.placement.mode, "wall");
  assert.equal(tx.item.placement.host_wall, wall);
  const snapped = structuredClone(tx.item);
  tx.update(at(120, 200));
  assert.equal(tx.item.placement.mode, "free");
  assert.equal(tx.item.placement.origin_x_mm, w.origin[0] + w.normal[0] * 120 + w.tangent[0] * 200);
  assert.equal(tx.item.placement.origin_y_mm, w.origin[1] + w.normal[1] * 120 + w.tangent[1] * 200);
  assert.deepEqual(item, original, "preview cannot mutate the input scene");
  assert.equal(tx.preview(scene).items[0], tx.item);
  const finished = tx.finish();
  assert.equal(finished.changed, true);
  assert.throws(() => tx.update([0, 0]));
  for (const candidate of [snapped, finished.item]) {
    // Start the Python consumer from the same absolute pose, expressed as free planning input.
    addFixture(item, candidate);
  }
}

// A newly attached cabinet must support leaving again during the same gesture.
{
  const item = itemFor("north");item.placement.mode = "free";item.placement.host_wall = null;
  item.placement.origin_y_mm = 120;item.footprint = localFootprint(item, 700, 120, 0);
  const { tx } = gesture(item);
  tx.update(screen(200, -120));
  assert.equal(tx.item.placement.mode, "wall");
  tx.update(screen(200, 0));
  assert.equal(tx.item.placement.mode, "free");
  assert.equal(tx.item.placement.origin_x_mm, 900);
  assert.equal(tx.item.placement.origin_y_mm, 120);
}
for (const category of ["sofa", "chair"]) {
  const item = itemFor("east", { category, manufacture: false });
  const before = structuredClone(item), { tx } = gesture(item);
  tx.update(screen(-120, 200));
  assert.equal(tx.item.placement.rotation_z_deg, 90);
  tx.update(screen(0, 200));
  assert.equal(tx.item.placement.mode, "free", "movable furniture never attaches");
  tx.cancel();
  assert.deepEqual(item, before);
  assert.throws(() => tx.finish());
}
// Clicks and sub-threshold motion do not commit a mode change.
{
  const { tx } = gesture(itemFor("north"));tx.update([1, 1]);
  assert.equal(tx.finish().changed, false);
}
// Height candidates preserve fractional untouched coordinates; operations serialize the same pose.
{
  const item = itemFor("north");
  const { tx } = gesture(item, { kind: "height" });
  tx.update([0, -100]);
  assert.equal(tx.item.z_start, 100);
  assert.equal(tx.item.placement.mode, "wall");
  const result = tx.finish();
  assert.equal(result.operation.origin_z_mm, 100);
  addFixture(item, result.item);
  assert.equal(item.z_start, 0);
}
{
  const item = itemFor("north");
  item.placement.mode = "free";item.placement.host_wall = null;item.placement.origin_y_mm = 800;
  item.footprint = localFootprint(item, 700, 800, 0);
  const { tx } = gesture(item, { kind: "rotate", screen: [100, 0], rotationOrigin: { x: 0, y: 0 } });
  tx.update([0, 100]);
  assert.equal(tx.item.placement.rotation_z_deg, 90);
  const result = tx.finish();
  addFixture(item, result.item);
  assert.equal(item.placement.rotation_z_deg, 0);
}
if (process.argv.includes("--scenes")) {
  let input = "";
  for await (const chunk of process.stdin) input += chunk;
  const results = JSON.parse(input).map(({ scene, action, screen = [0, 120], value }) => {
    scene.items = scene.items.map(item => ({ ...item,
      footprint: item.footprint.map(point => [point.x_mm, point.y_mm]),
      z_start: item.placement.origin_z_mm, z_end: item.placement.origin_z_mm + item.height }));
    const original = structuredClone(scene);
    const item = scene.items[0];
    let candidate, operation, blocker;
    if (action === "numericHeight" || action === "numericRotation") {
      candidate = structuredClone(item);
      if (action === "numericHeight") {
        const solved = resolveInteger(candidate.z_start, value, heightProbe(scene, candidate, candidate.footprint));
        blocker = solved.blocker;
        setItemHeight(candidate, solved.value);
      } else {
        const result = solveRotation(scene, candidate,
          [candidate.footprint.reduce((sum, point) => sum + point[0], 0) / 4,
           candidate.footprint.reduce((sum, point) => sum + point[1], 0) / 4], value);
        blocker = result.blocker;
      }
      operation = poseOperation(candidate);
    } else {
      const transaction = createDragTransaction({ scene, item, kind: action || "move", pointerId: 1,
        screen: action === "rotate" ? [100, 0] : [0, 0], basis, scale: Math.SQRT1_2,
        wallScreenNormal: item.placement.host_wall ? { x: walls[item.placement.host_wall].normal[0],
          y: walls[item.placement.host_wall].normal[1] } : null,
        projectWallNormal: wall => ({ x: walls[wall].normal[0], y: walls[wall].normal[1] }),
        rotationOrigin: { x: 0, y: 0 } });
      blocker = transaction.update(screen).blocker;
      const result = transaction.finish();candidate = result.item;operation = result.operation;
    }
    assert.deepEqual(scene, original, "constraint checks cannot mutate the committed document");
    return { operation, blocker, placement: candidate.placement };
  });
  process.stdout.write(JSON.stringify(results));
} else if (process.argv.includes("--fixtures")) process.stdout.write(JSON.stringify(fixtures));
else console.log("Drag transactions pass: four-wall detach/attach continuity, isolated previews, cancel and exact operations.");
