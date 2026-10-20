import assert from "node:assert/strict";
import { placeLabels } from "./layout_labels.js";

const labels = Array.from({ length: 9 }, () => ({ x: 400, y: 300, width: 125, height: 18 }));
const result = placeLabels(labels, 800, 600);
for (const [i, rect] of result.entries()) {
  assert.ok(rect.x - rect.width / 2 >= 0 && rect.x + rect.width / 2 <= 800);
  assert.ok(rect.y - rect.height / 2 >= 0 && rect.y + rect.height / 2 <= 600);
  for (const other of result.slice(i + 1)) {
    assert.ok(Math.abs(rect.x - other.x) >= (rect.width + other.width) / 2 ||
      Math.abs(rect.y - other.y) >= (rect.height + other.height) / 2);
  }
}
assert.deepEqual(placeLabels(labels.map((label, i) => ({ ...label, offset: result[i].offset })), 800, 600), result);

const edge = placeLabels([
  { x: 1, y: 1, width: 125, height: 18 },
  { x: 2, y: 2, width: 90, height: 18 },
  { x: 799, y: 599, width: 125, height: 18 },
], 800, 600);
for (const rect of edge) {
  assert.ok(rect.x - rect.width / 2 >= 0 && rect.x + rect.width / 2 <= 800);
  assert.ok(rect.y - rect.height / 2 >= 0 && rect.y + rect.height / 2 <= 600);
}
assert.ok(Math.abs(edge[0].y - edge[1].y) >= 18);
assert.deepEqual(placeLabels([], 800, 600), []);
console.log("labels avoid overlap, stay inside the canvas, and keep stable offsets");
