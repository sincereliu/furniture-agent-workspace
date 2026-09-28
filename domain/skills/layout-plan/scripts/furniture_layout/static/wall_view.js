/**
 * 墙的显隐判据（纯几何，不依赖 three，可直接在 node 里断言，见 wall_view_check.mjs）。
 *
 * 人眼习惯：站在房间外面看时，离你最近的那面墙不会挡在你和房间之间——它"不存在"。
 * 一个判据管住两种情况：**这面墙在房间中心和你之间**（朝外的法线与"中心→相机"同向），
 * 它就在你和房间之间，不画。
 *   · 相机在房间外：朝相机的那一两面被剔掉，剩下的当背景/侧墙。
 *   · 相机在房间内：四面墙的法线都不指向相机 → 一面都不剔（你背后那面本来也在视野外）。
 * 立面视图例外：只留正对相机的那面墙。
 */

// 三档要**渐变**而不是跳变：背景墙 > 立面墙 > 侧墙，数值彼此靠近。
// 另外浅灰(0xdbe3ee)压浅底(0xeef1f6)只差约 8 个色阶，所以背景墙必须用中灰才读得出来。
export const WALL_SIDE_OPACITY = 0.25;        // 侧墙：轻，但不至于消失
export const WALL_BACK_OPACITY = 0.55;        // 背景墙：读得出门窗，又不是一堵实墙
export const WALL_BACK_COLOR = 0xc2ccd9;      // 背景墙用中灰
export const WALL_ELEVATION_OPACITY = 0.45;   // 立面视图：正对那面
export const WALL_ELEVATION_COLOR = 0xbfc9d6; // 立面视图墙面：与背景墙同一档
export const ELEVATION_PITCH = 0.12;          // 与 room_page.html 的 ELEVATION_MAX_PITCH 一致

const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];

/**
 * @param walls  [{id, center:[x,y,z], normal:[x,y,z]}] normal 是墙面**朝房间外**的法线
 * @param cameraPosition [x,y,z]（three 坐标，y 向上）
 * @param viewDirection  相机朝向单位向量（只有立面判定用得上）
 * @param options.elevation 是否立面视图
 * @returns {elevation, walls:[{id, visible, opacity}]}
 */
export function wallVisibility(walls, cameraPosition, viewDirection, options = {}) {
  const elevation = options.elevation === true;
  const states = walls.map((wall) => {
    // 水平分量：墙是竖直平面，朝向不能被相机高度带偏
    const rel = [
      cameraPosition[0] - wall.center[0],
      0,
      cameraPosition[2] - wall.center[2],
    ];
    const cameraOutside = dot(wall.normal, rel) > 0;      // 相机在这面墙的外侧
    // 立面视图里要画的是**对面**那面墙（窗和门在它上面）：法线与视线同向，
    // 也就是"墙不在相机与房间中心之间"的严格版。
    const facingAway = dot(wall.normal, [viewDirection[0], 0, viewDirection[2]]) > 0.7;
    return {
      id: wall.id,
      visible: elevation ? facingAway : !cameraOutside,
      distance: Math.hypot(
        cameraPosition[0] - wall.center[0],
        cameraPosition[1] - wall.center[1],
        cameraPosition[2] - wall.center[2],
      ),
    };
  });

  // 可见的墙里，离相机最远的那面当背景墙（更实），同屏其它可见墙当侧墙（更淡）
  const shown = states.filter((state) => state.visible);
  const farthest = shown.reduce((max, state) => Math.max(max, state.distance), -Infinity);

  return {
    elevation,
    walls: states.map((state) => ({
      id: state.id,
      visible: state.visible,
      // 背景墙 / 侧墙 / 立面墙三档，颜色与不透明度一起给（浅色 + 低透明度等于看不见）
      opacity: elevation
        ? WALL_ELEVATION_OPACITY
        : (state.distance === farthest ? WALL_BACK_OPACITY : WALL_SIDE_OPACITY),
      color: elevation
        ? WALL_ELEVATION_COLOR
        : (state.distance === farthest ? WALL_BACK_COLOR : null),
    })),
  };
}
