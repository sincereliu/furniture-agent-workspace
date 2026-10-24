import assert from "node:assert/strict";
import { normalizeItems } from "../../furniture_web/static/pages/room/layout_payload.js";
import { createLayoutPersistence, LayoutWriteError, placementChanged } from "../../furniture_web/static/pages/room/layout_persistence.js";

const turn = () => new Promise(resolve => setImmediate(resolve));
const item = (id, x, y) => ({
  id, label: id, height: 800,
  placement: { mode: "free", host_wall: null, origin_x_mm: x, origin_y_mm: y, origin_z_mm: 0, rotation_z_deg: 0 },
  footprint: [{ x_mm: x, y_mm: y }, { x_mm: x + 400, y_mm: y }, { x_mm: x + 400, y_mm: y + 400 }, { x_mm: x, y_mm: y + 400 }],
});
const document = (version, cabinetX, chairY) => ({
  version, rooms: [{ id: "study", scene: { room: { id: "study" }, items: [item("cabinet", cabinetX, 0), item("chair", 1500, chairY)] } }],
});
const setPose = (id,x,y=0) => ({ op: "set_pose", item_id: id, mode: "free", origin_x_mm:x, origin_y_mm:y, origin_z_mm:0, rotation_z_deg:0 });
const move = source => setPose(source.id,source.placement.origin_x_mm,source.placement.origin_y_mm);
function harness({ versioned = true } = {}) {
  const calls = [];
  const shown = [];
  const h = { interacting: false, scene: { items: normalizeItems(document("v0", 100, 200).rooms[0].scene.items) } };
  const controller = createLayoutPersistence({
    readUrl: "/layout", editUrl: "/edit", version: "v0", versioned,
    getLeaseToken: () => "lease", isInteracting: () => h.interacting,
    onMetadata() {},
    onDocument(payload) {
      shown.push(payload);
      h.scene.items = normalizeItems(payload.rooms ? payload.rooms[0].scene.items : payload.items);
    },
    request(url, options) {
      return new Promise((resolve, reject) => calls.push({
        url, options, op: options?.body ? JSON.parse(options.body) : null, reject,
        reply(payload, status = 200) { resolve({ ok: status === 200, status, json: async () => payload }); },
      }));
    },
  });
  return { h, controller, calls, shown };
}

// Moving along the same wall is a change; equivalent rotations are not.
{
  const before = item("cabinet", 0, 100).placement;
  before.mode = "wall"; before.host_wall = "west";
  assert.equal(placementChanged(before, { ...before }), false);
  assert.equal(placementChanged(before, { ...before, origin_y_mm: 200 }), true);
  assert.equal(placementChanged(before, { ...before, origin_z_mm: 50 }), true);
  assert.equal(placementChanged(before, { ...before, rotation_z_deg: 360 }), false);
  assert.equal(placementChanged(before, { ...before, rotation_z_deg: -90 }), true);
}

// A cabinet response must not erase the chair currently being dragged.
{
  const { h, controller: c, calls } = harness();
  h.scene.items[0].placement.origin_x_mm = 900;
  const first = c.write(move(h.scene.items[0]));
  await turn();
  const chair = h.scene.items[1];
  h.interacting = true;
  chair.placement.origin_y_mm = 800;
  calls[0].reply(document("v1", 900, 200));
  await first;
  assert.equal(h.scene.items[1], chair);
  assert.equal(h.scene.items[1].placement.origin_y_mm, 800);
  h.interacting = false;
  const second = c.write(move(chair));
  await turn();
  assert.equal(calls[1].op.expected_version, "v1");
  assert.equal(calls[1].op.origin_y_mm, 800);
  calls[1].reply(document("v2", 900, 800));
  await second;
  assert.equal(h.scene.items[0].placement.origin_x_mm, 900);
  assert.equal(h.scene.items[1].placement.origin_y_mm, 800);
}

// Rapid releases are serialized and capture each submitted operation by value.
{
  const { h, controller: c, calls } = harness();
  const first = c.write(setPose("cabinet",900));
  const op = setPose("chair",1500,800);
  const second = c.write(op);
  op.origin_y_mm = 99;
  await turn();
  assert.equal(c.busy, true);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].options.headers["X-Edit-Lease"], "lease");
  calls[0].reply(document("v1", 900, 200));
  await first;
  await turn();
  assert.equal(calls[1].op.expected_version, "v1");
  assert.equal(calls[1].op.origin_y_mm, 800);
  calls[1].reply(document("v2", 900, 800));
  await second;
  assert.equal(c.version, "v2");
  assert.equal(c.busy, false);
  assert.equal(h.scene.items[0].placement.origin_x_mm, 900);
}

// A GET started before a write cannot roll back the acknowledged result.
{
  const { h, controller: c, calls } = harness();
  const oldRead = c.refresh();
  const saved = c.write(setPose("cabinet",900));
  await turn();
  calls[1].reply(document("v1", 900, 200));
  await saved;
  calls[0].reply(document("v0", 100, 200));
  assert.equal(await oldRead, false);
  assert.equal(c.version, "v1");
  assert.equal(h.scene.items[0].placement.origin_x_mm, 900);
}

// Two reads can finish in reverse order; only the newest requested snapshot applies.
{
  const { controller: c, calls, shown } = harness();
  const older = c.refresh();
  const newer = c.refresh();
  calls[1].reply(document("v2", 900, 800));
  assert.equal(await newer, true);
  calls[0].reply(document("v1", 100, 200));
  assert.equal(await older, false);
  assert.equal(shown.length, 1);
  assert.equal(c.version, "v2");
}

// A refresh during interaction owns its snapshot and installs it only after release.
{
  const { h, controller: c, calls, shown } = harness();
  h.interacting = true;
  const read = c.refresh();
  const payload = document("v1", 900, 200);
  calls[0].reply(payload);
  await read;
  payload.rooms[0].scene.items[0].placement.origin_x_mm = 99;
  assert.equal(shown.length, 0);
  h.interacting = false;
  c.flush();
  assert.equal(h.scene.items[0].placement.origin_x_mm, 900);
}

// A notice arriving during an existing notification read must trigger a newer read.
{
  const { controller: c, calls, shown } = harness();
  c.notice({ version: "v1" });
  assert.equal(calls.length, 1);
  c.notice({ version: "v2" });
  calls[0].reply(document("v1", 100, 200));
  await turn();
  assert.equal(calls.length, 2);
  assert.equal(shown.length, 0);
  calls[1].reply(document("v2", 900, 800));
  await turn();
  assert.equal(c.version, "v2");
  assert.equal(shown.length, 1);
}

// External notices wait until interaction ends; duplicate notices do not reread.
{
  const { h, controller: c, calls } = harness();
  h.interacting = true;
  c.notice({ version: "v1" });
  assert.equal(calls.length, 0);
  h.interacting = false;
  c.flush();
  calls[0].reply(document("v1", 900, 800));
  await turn();
  c.notice({ version: "v1" });
  assert.equal(calls.length, 1);
}

// Version conflicts, collisions, denied permission and lease loss all recover from the server.
for (const status of [409, 422, 403, 423]) {
  const { h, controller: c, calls } = harness();
  h.scene.items[0].placement.origin_x_mm = 900;
  const rejected = assert.rejects(c.write(move(h.scene.items[0])), error => error instanceof LayoutWriteError && error.status === status);
  await turn();
  calls[0].reply({ detail: "rejected" }, status);
  await turn();
  calls[1].reply(document("v0", 100, 200));
  await rejected;
  assert.equal(h.scene.items[0].placement.origin_x_mm, 100);
  assert.equal(c.busy, false);
  const next = c.write(setPose("chair",1500,800));
  await turn();
  calls[2].reply(document("v1", 100, 800));
  await next;
  assert.equal(h.scene.items[1].placement.origin_y_mm, 800);
}

// A lost response may hide a committed write. Recovery must adopt its real server version.
{
  const { h, controller: c, calls } = harness();
  const failed = assert.rejects(c.write(setPose("cabinet",900)), /connection lost/);
  await turn();
  calls[0].reject(new Error("connection lost"));
  await turn();
  calls[1].reply(document("v1", 900, 200));
  await failed;
  assert.equal(c.version, "v1");
  assert.equal(h.scene.items[0].placement.origin_x_mm, 900);
}

// Decision updates share the write queue and version, without replacing scene geometry.
{
  const { controller: c, calls, shown } = harness();
  const save = c.write(setPose("cabinet",900));
  const decision = c.write({ action: "confirm", target: "d1" }, "/decisions");
  await turn();
  assert.equal(calls.length, 1);
  calls[0].reply(document("v1", 900, 200));
  await save;
  await turn();
  assert.equal(calls[1].url, "/decisions");
  assert.equal(calls[1].op.expected_version, "v1");
  calls[1].reply({ version: "v2", decisions: { pending: [] } });
  await decision;
  assert.equal(c.version, "v2");
  assert.equal(shown.length, 1);
}

// Standalone rooms use the same ordering without adding project version fields.
{
  const { controller: c, calls, shown } = harness({ versioned: false });
  const save = c.write(setPose("cabinet",900));
  await turn();
  assert.equal("expected_version" in calls[0].op, false);
  calls[0].reply({ items: [item("cabinet", 900, 0)] });
  await save;
  assert.equal(shown[0].items[0].placement.origin_x_mm, 900);
}
console.log("Layout persistence checks pass: ordering, drag isolation, notices, failures, decisions and standalone rooms.");
