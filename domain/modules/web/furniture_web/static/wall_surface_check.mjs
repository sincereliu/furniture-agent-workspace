import assert from "node:assert/strict";
import { wallSolids } from "./wall_solid.js";
import { wallSurfacePositions } from "./wall_surface.js";

const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const dot = (a, b) => a.reduce((sum, v, i) => sum + v * b[i], 0);
const sub = (a, b) => a.map((v, i) => v - b[i]);

function checkSurface(boxes, padding = 0) {
  const positions = wallSurfacePositions(boxes, padding);
  const padded = boxes.map(([x0, y0, z0, x1, y1, z1]) => [
    [x0 - padding, z0 - padding, y0 - padding],
    [x1 + padding, z1 + padding, y1 + padding],
  ]);
  const inside = (point) => padded.some(([lo, hi]) => (
    point.every((value, axis) => value > lo[axis] && value < hi[axis])
  ));
  const edges = new Map();
  let volume = 0;
  for (let i = 0; i < positions.length; i += 9) {
    const triangle = [0, 3, 6].map((offset) => positions.slice(i + offset, i + offset + 3));
    const [a, b, c] = triangle;
    const normal = cross(sub(b, a), sub(c, a));
    const length = Math.hypot(...normal);
    assert.ok(length > 0, "no degenerate triangles");
    const center = a.map((v, axis) => (v + b[axis] + c[axis]) / 3);
    const offset = normal.map((v) => v / length * 0.001);
    assert.ok(inside(sub(center, offset)), "each face has solid wall immediately behind it");
    assert.ok(!inside(center.map((v, axis) => v + offset[axis])), "no faces remain inside the wall union");
    volume += dot(a, cross(b, c)) / 6;
    for (let e = 0; e < 3; e += 1) {
      const from = triangle[e].join(",");
      const to = triangle[(e + 1) % 3].join(",");
      const key = [from, to].sort().join("/");
      const record = edges.get(key) || { count: 0, direction: 0 };
      record.count += 1;
      record.direction += from < to ? 1 : -1;
      edges.set(key, record);
    }
  }
  for (const edge of edges.values()) {
    assert.equal(edge.count, 2, "surface has no cracks or T junctions");
    assert.equal(edge.direction, 0, "adjacent faces wind consistently");
  }
  return volume;
}

const door = { kind: "door", offset_mm: 1000, width_mm: 900, height_mm: 2100, sill_height_mm: 0 };
const window = { kind: "window", offset_mm: 600, width_mm: 1200, height_mm: 1200, sill_height_mm: 900 };
for (const wall of ["north", "east", "south", "west"]) {
  for (const openings of [[], [door], [window], [door, window]]) {
    const solids = wallSolids(4000, 3000, 2800, openings.map((o) => ({ ...o, wall })));
    for (const solid of solids) {
      const expected = solid.boxes.reduce((sum, [x0, y0, z0, x1, y1, z1]) => (
        sum + (x1 - x0) * (y1 - y0) * (z1 - z0)
      ), 0);
      const volume = checkSurface(solid.boxes);
      assert.ok(Math.abs(volume - expected) < expected * 1e-10, "wall and opening volumes are unchanged");
      checkSurface(solid.boxes, 8);
    }
  }
}

// A single padded hull surrounds a door/window without the internal surfaces of
// the overlapping, individually inflated wall blocks.
for (const opening of [door, window]) {
  const north = wallSolids(4000, 3000, 2800, [{ ...opening, wall: "north" }])[0];
  const p = 8;
  const holeHeight = opening.height_mm - (opening.kind === "window" ? 2 * p : 0);
  const expected = ((4200 + 2 * p) * (2800 + 2 * p)
    - (opening.width_mm - 2 * p) * holeHeight) * (100 + 2 * p);
  assert.ok(Math.abs(checkSurface(north.boxes, p) - expected) < expected * 1e-10);
}

// Fractional coordinates and very narrow residual strips must stay watertight.
for (const solid of wallSolids(4000.25, 3000.75, 2800.5, [
  { ...window, wall: "east", offset_mm: 600.25 },
  { ...door, wall: "east", offset_mm: 1800.5 },
])) {
  checkSurface(solid.boxes);
  checkSurface(solid.boxes, 8);
}
assert.deepEqual(wallSurfacePositions([]), []);
assert.deepEqual(wallSurfacePositions([], 8), []);
const openEast = wallSolids(4000, 3000, 2800, [
  { ...door, wall: "east", offset_mm: 0, width_mm: 3000, height_mm: 2800 },
]).find((solid) => solid.id === "east");
assert.deepEqual(wallSurfacePositions(openEast.boxes), []);
console.log("wall surfaces are closed unions without internal seams, including padded outlines");
