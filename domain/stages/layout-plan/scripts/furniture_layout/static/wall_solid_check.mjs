/**
 * 围墙要有厚度，并且挖得开门窗。
 * 运行：node domain/stages/layout-plan/scripts/furniture_layout/static/wall_solid_check.mjs
 */
import { WALL_THICKNESS_MM, openingSolids, wallSolids } from "./wall_solid.js";

const W = 4000;
const D = 3000;
const H = 2800;
const T = WALL_THICKNESS_MM;

function expect(condition, message) {
  if (!condition) throw new Error(message);
}

function overlaps(a, b) {
  return a[0] < b[3] - 1e-6 && a[3] > b[0] + 1e-6
    && a[1] < b[4] - 1e-6 && a[4] > b[1] + 1e-6
    && a[2] < b[5] - 1e-6 && a[5] > b[2] + 1e-6;
}

function contains(box, x, y, z) {
  return x > box[0] && x < box[3] && y > box[1] && y < box[4] && z > box[2] && z < box[5];
}

function boxesOf(walls, id) {
  return walls.find((wall) => wall.id === id).boxes;
}

expect(T === 100, "墙厚与房间外壳一致，为 100 mm");

{
  const walls = wallSolids(W, D, H, []);
  expect(walls.map((wall) => wall.id).join(",") === "north,east,south,west", "墙的顺序");
  const north = boxesOf(walls, "north")[0];
  const east = boxesOf(walls, "east")[0];
  const south = boxesOf(walls, "south")[0];
  const west = boxesOf(walls, "west")[0];
  expect(JSON.stringify(north) === JSON.stringify([-T, -T, 0, W + T, 0, H]), `北墙 ${north}`);
  expect(JSON.stringify(east) === JSON.stringify([W, 0, 0, W + T, D, H]), `东墙 ${east}`);
  expect(JSON.stringify(south) === JSON.stringify([-T, D, 0, W + T, D + T, H]), `南墙 ${south}`);
  expect(JSON.stringify(west) === JSON.stringify([-T, 0, 0, 0, D, H]), `西墙 ${west}`);
  const all = [north, east, south, west];
  for (let i = 0; i < all.length; i += 1) {
    for (let j = i + 1; j < all.length; j += 1) {
      expect(!overlaps(all[i], all[j]), "四段墙不能叠在一起");
    }
  }
  expect(!all.some((box) => contains(box, W / 2, D / 2, H / 2)), "室内不能被墙占掉");
  expect(all.some((box) => contains(box, -T / 2, -T / 2, H / 2)), "西北转角要有墙");
  expect(walls[0].normal.join(",") === "0,-1,0", "北墙法线朝外");
  expect(walls[0].center[1] === -T / 2, "显隐用的中心落在墙厚中面");
}

{
  const door = {
    wall: "north",
    kind: "door",
    offset_mm: 1000,
    width_mm: 900,
    height_mm: 2100,
    sill_height_mm: 0,
  };
  const walls = wallSolids(W, D, H, [door]);
  const north = boxesOf(walls, "north");
  expect(north.length === 3, `门洞应留下左右垛和门梁，实际 ${north.length} 块`);
  const hole = [1000, -T, 0, 1900, 0, 2100];
  expect(!north.some((box) => overlaps(box, hole)), "门洞里不能还有墙");
  expect(north.some((box) => contains(box, 500, -T / 2, 1000)), "门西侧要留墙垛");
  expect(north.some((box) => contains(box, 1400, -T / 2, 2400)), "门上方要留门梁");
  const plug = openingSolids(W, D, [door])[0];
  expect(JSON.stringify(plug.box) === JSON.stringify(hole), `门要填在墙厚里 ${plug.box}`);
}

{
  const window = {
    wall: "south",
    kind: "window",
    offset_mm: 500,
    width_mm: 900,
    height_mm: 1200,
    sill_height_mm: 900,
  };
  const hole = [W - 1400, D, 900, W - 500, D + T, 2100];
  const south = boxesOf(wallSolids(W, D, H, [window]), "south");
  expect(!south.some((box) => overlaps(box, hole)), "南墙窗洞按顺时针偏移挖在东侧");
  expect(south.some((box) => contains(box, W - 950, D + T / 2, 400)), "窗下要留窗台");
  expect(JSON.stringify(openingSolids(W, D, [window])[0].box) === JSON.stringify(hole), "窗洞盒子");
}

{
  const door = {
    wall: "west",
    kind: "door",
    offset_mm: 200,
    width_mm: 800,
    height_mm: 2000,
    sill_height_mm: 0,
  };
  const hole = [-T, D - 1000, 0, 0, D - 200, 2000];
  const west = boxesOf(wallSolids(W, D, H, [door]), "west");
  expect(!west.some((box) => overlaps(box, hole)), "西墙门洞从南端起算");
  expect(JSON.stringify(openingSolids(W, D, [door])[0].box) === JSON.stringify(hole), "西墙门盒子");
}

{
  const door = {
    wall: "east",
    kind: "door",
    offset_mm: 400,
    width_mm: 900,
    height_mm: 2100,
    sill_height_mm: 0,
  };
  const transom = {
    wall: "east",
    kind: "window",
    offset_mm: 500,
    width_mm: 700,
    height_mm: 400,
    sill_height_mm: 1900,
  };
  const east = boxesOf(wallSolids(W, D, H, [door, transom]), "east");
  expect(!east.some((box) => contains(box, W + T / 2, 800, 1000)), "重叠的门洞里不能有墙");
  expect(!east.some((box) => contains(box, W + T / 2, 900, 2000)), "压在门上的气窗也要挖掉");
  expect(east.some((box) => contains(box, W + T / 2, 800, 2500)), "气窗上方仍留墙");
}

console.log("walls are 100 mm thick outside the room, with openings cut out");
