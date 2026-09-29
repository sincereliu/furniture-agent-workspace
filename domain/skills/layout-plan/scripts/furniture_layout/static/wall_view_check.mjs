/**
 * 墙显隐判据的断言：横在人和房间之间的那面墙不画、背景墙最实、侧墙最淡；
 * 立面视图只留正对相机那面。
 * 运行：node domain/skills/layout-plan/scripts/furniture_layout/static/wall_view_check.mjs
 * （与 frame_check.mjs 同类：纯几何，不需要浏览器）
 */
import {
  WALL_BACK_COLOR,
  WALL_BACK_OPACITY,
  WALL_ELEVATION_OPACITY,
  WALL_SIDE_OPACITY,
  wallVisibility,
} from "./wall_view.js";

// 2400 × 3000 × 2800 的房间；three 坐标 x=东, y=高, z=南。法线朝房间外。
const W = 2400;
const D = 3000;
const walls = [
  { id: "north", center: [W / 2, 0, 0], normal: [0, 0, -1] },
  { id: "east", center: [W, 0, D / 2], normal: [1, 0, 0] },
  { id: "south", center: [W / 2, 0, D], normal: [0, 0, 1] },
  { id: "west", center: [0, 0, D / 2], normal: [-1, 0, 0] },
];

const state = (result, id) => result.walls.find((wall) => wall.id === id);
const visibleIds = (result) => result.walls.filter((wall) => wall.visible).map((wall) => wall.id).join(",");

function expect(condition, message) {
  if (!condition) throw new Error(message);
}

// 1) 默认那一眼：相机在房间外东南上方看向西北 → 南墙、东墙横在人和房间之间，不画
{
  const position = [1200 + 2100, 1100 + 800, 1260 + 2000];
  const result = wallVisibility(walls, position, [-0.62, -0.24, -0.75], { elevation: false });
  expect(result.elevation === false, "透视视角不该被判成立面");
  expect(visibleIds(result) === "north,west", `应只留北墙与西墙，实际 ${visibleIds(result)}`);
  expect(state(result, "north").opacity === WALL_BACK_OPACITY, "北墙是背景墙，应最实");
  expect(state(result, "north").color === WALL_BACK_COLOR, "背景墙要用中灰，不能用浅灰（浅灰压浅底看不见）");
  expect(state(result, "west").opacity === WALL_SIDE_OPACITY, "西墙是侧墙，应最淡");
  expect(state(result, "west").color === null, "侧墙沿用默认浅灰");
}

// 2) 相机在房间内部靠南：四面墙都不在"中心与相机之间"，一面都不剔
{
  const position = [W / 2, 1600, D - 200];
  const result = wallVisibility(walls, position, [0, 0, -1], { elevation: false });
  expect(visibleIds(result) === "north,east,south,west", `房间内不该剔墙，实际 ${visibleIds(result)}`);
  expect(state(result, "north").opacity === WALL_BACK_OPACITY, "北墙离相机最远，当背景墙");
  expect(state(result, "south").opacity === WALL_SIDE_OPACITY, "南墙贴脸，当侧墙提示");
}

// 3) 相机在房间外南侧高处：只有南墙横在中间 → 剔南墙，其余三面都在
{
  const position = [W / 2, 1600, D + 1200];
  const result = wallVisibility(walls, position, [0, 0, -1], { elevation: false });
  expect(visibleIds(result) === "north,east,west", `只该剔南墙，实际 ${visibleIds(result)}`);
  expect(state(result, "north").opacity === WALL_BACK_OPACITY, "北墙最远，是背景墙");
  expect(state(result, "east").opacity === WALL_SIDE_OPACITY, "东西墙是侧墙");
}

// 4) 立面视图：只留**正面对着相机**的那面墙。
//    相机在南边往北看时，被画的是北墙（它的正面朝南、正对相机）；
//    相机身后的南墙**不能画**——它的顶边会变成"房间上方多出来的一条水平线"。
{
  const position = [W / 2, 1400, D + 6000];
  const result = wallVisibility(walls, position, [0, 0, -1], { elevation: true });
  expect(result.elevation === true, "应被判定为立面视图");
  expect(visibleIds(result) === "north", `立面视图应只画北墙，实际 ${visibleIds(result)}`);
  expect(state(result, "south").visible === false, "相机身后的南墙不该画（顶边会跑到房间上方）");
  expect(
    state(result, "north").opacity === WALL_ELEVATION_OPACITY,
    `立面视图那面墙要用 ${WALL_ELEVATION_OPACITY} 的透明度，实际 ${state(result, "north").opacity}`,
  );
}

// 4b) 反方向同理：相机在北边往南看 → 只画南墙，身后的北墙不画
{
  const position = [W / 2, 1400, -6000];
  const result = wallVisibility(walls, position, [0, 0, 1], { elevation: true });
  expect(visibleIds(result) === "south", `从北往南看应只画南墙，实际 ${visibleIds(result)}`);
  expect(state(result, "north").visible === false, "相机身后的北墙不该画");
}

// 4c) 东西两个立面：相机在东边往西看只画西墙；反之只画东墙
{
  const east = wallVisibility(walls, [W + 6000, 1400, D / 2], [-1, 0, 0], { elevation: true });
  expect(visibleIds(east) === "west", `从东往西看应只画西墙，实际 ${visibleIds(east)}`);
  const west = wallVisibility(walls, [-6000, 1400, D / 2], [1, 0, 0], { elevation: true });
  expect(visibleIds(west) === "east", `从西往东看应只画东墙，实际 ${visibleIds(west)}`);
}

// 5) 相机绕房间一圈（房间外）：可见墙恰好是"墙不在中心与相机之间"的那些；背景墙只有一面
{
  for (let step = 0; step < 24; step += 1) {
    const angle = (step / 24) * Math.PI * 2;
    const position = [W / 2 + Math.cos(angle) * 7000, 1800, D / 2 + Math.sin(angle) * 7000];
    const result = wallVisibility(walls, position, [-Math.cos(angle), -0.15, -Math.sin(angle)], {
      elevation: false,
    });
    for (const wall of walls) {
      const rel = [position[0] - wall.center[0], 0, position[2] - wall.center[2]];
      const cameraOutside = wall.normal[0] * rel[0] + wall.normal[2] * rel[2] > 0;
      expect(
        state(result, wall.id).visible === !cameraOutside,
        `第 ${step} 步：${wall.id} 的可见性与"是否在中心与相机之间"不一致`,
      );
    }
    const shown = result.walls.filter((wall) => wall.visible);
    expect(shown.length >= 2, `第 ${step} 步：外围视角至少该看到两面墙，实际 ${shown.length} 面`);
    const backs = shown.filter((wall) => wall.opacity === WALL_BACK_OPACITY);
    expect(backs.length === 1, `第 ${step} 步：背景墙应恰好一面，实际 ${backs.length} 面`);
  }
}

console.log("wall view ok");
