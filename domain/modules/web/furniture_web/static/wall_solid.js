/**
 * 预览围墙的实体（房间坐标，毫米）。纯几何，不依赖 three。
 *
 * 厚度与 room_shell.WALL_THICKNESS_MM 相同。墙在室内边界外侧，
 * 家具仍贴着内墙面。北墙和南墙向两端各伸出一个墙厚，补上转角；
 * 东墙和西墙夹在这两段之间，四段不重叠。门窗从所在墙上挖掉。
 */

export const WALL_THICKNESS_MM = 100;

const MIN_MM = 0.5;

/** 从一批 [along0, z0, along1, z1] 里挖掉一个洞。洞可以互相重叠。 */
function subtractRects(rects, hole) {
  const [a, c, b, d] = hole;
  const next = [];
  for (const rect of rects) {
    const [x0, z0, x1, z1] = rect;
    if (b <= x0 + MIN_MM || a >= x1 - MIN_MM || d <= z0 + MIN_MM || c >= z1 - MIN_MM) {
      next.push(rect);
      continue;
    }
    if (a > x0 + MIN_MM) next.push([x0, z0, Math.min(a, x1), z1]);
    if (b < x1 - MIN_MM) next.push([Math.max(b, x0), z0, x1, z1]);
    const ix0 = Math.max(x0, a);
    const ix1 = Math.min(x1, b);
    if (ix1 - ix0 >= MIN_MM) {
      if (c > z0 + MIN_MM) next.push([ix0, z0, ix1, Math.min(c, z1)]);
      if (d < z1 - MIN_MM) next.push([ix0, Math.max(d, z0), ix1, z1]);
    }
  }
  return next;
}

function openingHole(opening, alongOf) {
  const along0 = alongOf(opening);
  const z0 = opening.sill_height_mm || 0;
  return [along0, z0, along0 + opening.width_mm, z0 + opening.height_mm];
}

/**
 * 四面墙挖掉门窗之后的实体。
 * 每块盒子是房间坐标 [x0, y0, z0, x1, y1, z1]。
 * `center` / `normal` 用房间坐标：法线朝外，中心在墙厚中面。
 * 顺序固定为北、东、南、西。
 */
export function wallSolids(width, depth, height, openings = [], thickness = WALL_THICKNESS_MM) {
  const t = thickness;
  const on = (wall) => openings.filter((opening) => opening.wall === wall);
  const specs = [
    {
      id: "north",
      normal: [0, -1, 0],
      center: [width / 2, -t / 2, height / 2],
      along0: -t,
      along1: width + t,
      holes: on("north").map((opening) => openingHole(opening, (item) => item.offset_mm)),
      toBox: (a, z0, b, z1) => [a, -t, z0, b, 0, z1],
    },
    {
      id: "east",
      normal: [1, 0, 0],
      center: [width + t / 2, depth / 2, height / 2],
      along0: 0,
      along1: depth,
      holes: on("east").map((opening) => openingHole(opening, (item) => item.offset_mm)),
      toBox: (a, z0, b, z1) => [width, a, z0, width + t, b, z1],
    },
    {
      id: "south",
      normal: [0, 1, 0],
      center: [width / 2, depth + t / 2, height / 2],
      along0: -t,
      along1: width + t,
      holes: on("south").map((opening) => openingHole(
        opening,
        (item) => width - item.offset_mm - item.width_mm,
      )),
      toBox: (a, z0, b, z1) => [a, depth, z0, b, depth + t, z1],
    },
    {
      id: "west",
      normal: [-1, 0, 0],
      center: [-t / 2, depth / 2, height / 2],
      along0: 0,
      along1: depth,
      holes: on("west").map((opening) => openingHole(
        opening,
        (item) => depth - item.offset_mm - item.width_mm,
      )),
      toBox: (a, z0, b, z1) => [-t, a, z0, 0, b, z1],
    },
  ];
  return specs.map((spec) => {
    let rects = [[spec.along0, 0, spec.along1, height]];
    for (const hole of spec.holes) rects = subtractRects(rects, hole);
    return {
      id: spec.id,
      normal: spec.normal,
      center: spec.center,
      boxes: rects.map((rect) => spec.toBox(...rect)),
    };
  });
}

/** 门窗填在墙厚里的盒子，房间坐标 [x0, y0, z0, x1, y1, z1]。 */
export function openingSolids(width, depth, openings = [], thickness = WALL_THICKNESS_MM) {
  const t = thickness;
  return openings.map((opening) => {
    const span = opening.offset_mm;
    const end = span + opening.width_mm;
    const z0 = opening.sill_height_mm || 0;
    const z1 = z0 + opening.height_mm;
    let box;
    if (opening.wall === "north") box = [span, -t, z0, end, 0, z1];
    else if (opening.wall === "south") box = [width - end, depth, z0, width - span, depth + t, z1];
    else if (opening.wall === "east") box = [width, span, z0, width + t, end, z1];
    else box = [-t, depth - end, z0, 0, depth - span, z1];
    return { wall: opening.wall, kind: opening.kind, box };
  });
}
