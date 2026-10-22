import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import { normalizeItems } from "./layout_payload.js";

// Exercise the page's actual persistence code with delayed HTTP responses.
const page = readFileSync(new URL("../templates/room_page.js", import.meta.url), "utf8");
const syncBlock = page.slice(page.indexOf("async function reload()"), page.indexOf('canvas.addEventListener("pointerup",event=>{'));
const busyBlock = page.slice(page.indexOf("function sceneBusy()"), page.indexOf("function applyLayoutNotice("));
const flushBlock = page.slice(page.indexOf("function flushLayoutNotice()"), page.indexOf("function watchLayout()"));
const storeBlock = page.slice(page.indexOf("const syncStore="), page.indexOf("const pullStore=")).replace("const syncStore=", "var syncStore=");
const turn = () => new Promise(resolve => setImmediate(resolve));
const item = (id, x, y) => ({
  id, label: id, height: 800,
  placement: { mode: "free", host_wall: null, origin_x_mm: x, origin_y_mm: y, origin_z_mm: 0, rotation_z_deg: 0 },
  footprint: [{ x_mm: x, y_mm: y }, { x_mm: x + 400, y_mm: y }, { x_mm: x + 400, y_mm: y + 400 }, { x_mm: x, y_mm: y + 400 }],
});
const document = (version, cabinetX, chairY) => ({
  version, rooms: [{ id: "study", scene: { room: { id: "study" }, items: [item("cabinet", cabinetX, 0), item("chair", 1500, chairY)] } }],
});
function harness() {
  const calls = [];
  const context = vm.createContext({
    Promise, Math, String, Number, Boolean, Object, JSON, console,
    PROJECT_EDIT_URL: "/edit", LAYOUT_URL: "/layout", SCENE_ID: "study", READ_ONLY: false,
    layoutVersion: "v0", rooms: [], drag: null, state: { orbiting: false, panning: false },
    leaseStore: { token: "lease" }, normalizeItems, fillsWall: () => false,
    normalizeAngle: value => value, applyLease() {}, applyWorking() {}, applyDecisions() {}, setStatus() {},
    scene: { room: { id: "study" }, items: normalizeItems(document("v0", 100, 200).rooms[0].scene.items) },
    fetch(url, options) {
      return new Promise(resolve => calls.push({
        url, op: options?.body ? JSON.parse(options.body) : null,
        reply(payload, status = 200) { resolve({ ok: status === 200, status, json: async () => payload }); },
      }));
    },
  });
  context.showRoom = index => { context.scene.items = normalizeItems(context.rooms[index].scene.items); };
  vm.runInContext(storeBlock + busyBlock + syncBlock + flushBlock, context);
  return { context, calls };
}

// Returning to the same wall with a different position still needs a save.
{
  const { context: c } = harness();
  const cabinet = c.scene.items[0];
  cabinet.placement.mode = "wall";
  cabinet.placement.host_wall = "west";
  const activeDrag = { item: cabinet, startPlacement: { ...cabinet.placement } };
  assert.equal(c.dragChanged(activeDrag), false);
  cabinet.placement.origin_y_mm += 100;
  assert.equal(c.dragChanged(activeDrag), true, "same-wall along-position change must not skip saving");
}

// A cabinet response must not erase the chair currently being dragged.
{
  const { context: c, calls } = harness();
  c.scene.items[0].placement.origin_x_mm = 900;
  const savedCabinet = c.persist(c.scene.items[0], "move");
  await turn();
  const chair = c.scene.items[1];
  c.drag = { item: chair };
  chair.placement.origin_y_mm = 800;
  calls[0].reply(document("v1", 900, 200));
  await savedCabinet;
  assert.equal(c.scene.items[1].placement.origin_y_mm, 800, "save response erased an active drag");
  c.drag = null;
  const savedChair = c.persist(chair, "move");
  await turn();
  assert.equal(calls[1].op.expected_version, "v1");
  assert.equal(calls[1].op.origin_y_mm, 800);
  calls[1].reply(document("v2", 900, 800));
  await savedChair;
  assert.equal(c.scene.items[0].placement.origin_x_mm, 900);
  assert.equal(c.scene.items[1].placement.origin_y_mm, 800);
}

// Rapid releases save in order, each using the preceding acknowledged version.
{
  const { context: c, calls } = harness();
  c.scene.items[0].placement.origin_x_mm = 900;
  const first = c.persist(c.scene.items[0], "move");
  c.scene.items[1].placement.origin_y_mm = 800;
  const second = c.persist(c.scene.items[1], "move");
  await turn();
  assert.equal(calls.length, 1, "writes raced with the same expected_version");
  calls[0].reply(document("v1", 900, 200));
  await first;
  await turn();
  assert.equal(calls[1].op.expected_version, "v1");
  assert.equal(c.scene.items[1].placement.origin_y_mm, 800);
  calls[1].reply(document("v2", 900, 800));
  await second;
  assert.equal(c.layoutVersion, "v2");
  assert.equal(c.scene.items[0].placement.origin_x_mm, 900);
}

// A GET started before a write must never roll back the successful result.
{
  const { context: c, calls } = harness();
  const oldRead = c.refreshProjectDocument();
  c.scene.items[0].placement.origin_x_mm = 900;
  const saved = c.persist(c.scene.items[0], "move");
  await turn();
  calls[1].reply(document("v1", 900, 200));
  await saved;
  calls[0].reply(document("v0", 100, 200));
  assert.equal(await oldRead, false);
  assert.equal(c.layoutVersion, "v1");
  assert.equal(c.scene.items[0].placement.origin_x_mm, 900);
}

// Rejected writes release the queue and restore the authoritative document.
{
  const { context: c, calls } = harness();
  c.scene.items[0].placement.origin_x_mm = 900;
  const saved = c.persist(c.scene.items[0], "move");
  await turn();
  calls[0].reply({ detail: "collision" }, 422);
  await turn();
  calls[1].reply(document("v0", 100, 200));
  assert.equal(await saved, false);
  assert.equal(c.scene.items[0].placement.origin_x_mm, 100);
  assert.equal(c.sceneBusy(), false);
}
console.log("Delayed saves, serial versions, active drags, stale reads and rejection recovery pass.");
