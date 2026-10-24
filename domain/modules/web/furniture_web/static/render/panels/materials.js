import * as THREE from "three";

// 材质：整台柜子只有两种材料——柜体一种木纹，门板白色纯色。
// 木纹是画出来的（画布程序纹理），不从服务器取图：这一页的 CSP 只允许 'self'。
const WOOD_BASE = 0xdcc09a;
const WOOD_SHELL = 0xc9ab86;
const WHITE_FACE = 0xf7f8fa;
// 板件轮廓线：深棕、不透明度 0.7。浅木色底上要看得清板与板的缝，靠的就是它。
const EDGE_COLOR = 0x5b4327;
const EDGE_OPACITY = 0.7;
const SELECT_COLOR = 0x1d4ed8;
const HOVER_COLOR = 0xf59e0b;
const FLOOR_COLOR = 0xdfe5ee;

// 木纹图：纹路是**沿贴图 u 轴**的一条条细线（y 固定，x 从画布左外连到右外）。
//
// 这条约定和板件阶段的 `_grain_uv()` 绑死：那个函数按「这个面的 u 轴是不是顺纹轴」
// 逐个面决定转不转。两边任何一个翻转，症状都是某一类板「纹理横竖不对」：
//   * 只翻贴图方向 → 顺着高的板件（侧板 / 背板）先错；
//   * 只翻旋转方向 → 顺着宽的板件（顶底 / 层板 / 踢脚）先错。
// 所以两处都各有一条测试钉住，改一处必须同步改另一处，并在页面上量一遍：
// 侧板与背板该是竖纹，顶底板 / 层板 / 踢脚板该是横纹。量法见
// `test_wood_grain_is_drawn_along_the_texture_u_axis` 的说明。
//
// 纹理外观是**固定的几张常量**，页面上不提供调节（预设、深浅、粗细那些只是看效果用的，
// 真正要改的是每块板的**顺纹方向**——那是板件的属性，见下面的 `grainEdits`）。
const GRAIN_CYCLE_MM = 220; // 与板件阶段的 `GRAIN_CYCLE_MM` 一致：一张图铺多长
const GRAIN_SIZE = 256; // 贴图边长（像素）。木纹是噪声，256 够用；调大更细也更费显存
const GRAIN_LINES = 12; // 220 / 12 ≈ 18mm 一道：有木纹的样子，也不至于糊成一团
const GRAIN_TONE = "#ddc19b"; // 底色（浅木）
const GRAIN_WIDTH = [2.4, 6.8]; // [最细, 最粗] 线宽（像素）
const GRAIN_DARK_INK = ["158,120,80", 0.16]; // 深纹：颜色 + 基础不透明度
const GRAIN_LIGHT_INK = ["255,248,234", 0.16]; // 浅纹：同上
const GRAIN_DARK_SHARE = 0.68; // 深色线占比
const GRAIN_JITTER = [5, 7, 24, 72]; // 横向 ±px、纵向 ±px、折点步长 [min, max] px
//: 随机种子。固定住 = 每次刷新画出同一张纹理，截图核对才对得上（别换回 `Math.random()`）。
const GRAIN_SEED = 20261016;

// 固定种子的伪随机：同一个种子永远画出同一张纹理（截图核对靠它）。
// 不用 `Math.random()`——那样每次刷新纹理都不同，两张截图对不上。
function makeRandom(seed) {
  let state = (seed >>> 0) || 1;
  return () => {
    state ^= state << 13;
    state >>>= 0;
    state ^= state >> 17;
    state ^= state << 5;
    state >>>= 0;
    return state / 4294967296;
  };
}

// 往画布上画木纹。纹路是**沿贴图 u 轴**的一条条横线（y 固定、x 一路延伸），
// 面转不转由板件阶段按「这个面的 u 是不是顺纹轴」定（`_grain_uv()`）。
function paintGrain(canvas) {
  const context = canvas.getContext("2d");
  if (!context) throw new Error("2d context unavailable");
  const random = makeRandom(GRAIN_SEED);
  context.fillStyle = GRAIN_TONE;
  context.fillRect(0, 0, GRAIN_SIZE, GRAIN_SIZE);
  for (let index = 0; index < GRAIN_LINES; index += 1) {
    const y = ((index + 0.5) * GRAIN_SIZE) / GRAIN_LINES + (random() - 0.5) * GRAIN_JITTER[0];
    const ink = random() < GRAIN_DARK_SHARE ? GRAIN_DARK_INK : GRAIN_LIGHT_INK;
    context.strokeStyle = `rgba(${ink[0]},${(ink[1] + random() * 0.2).toFixed(3)})`;
    context.lineWidth = GRAIN_WIDTH[0] + random() * (GRAIN_WIDTH[1] - GRAIN_WIDTH[0]);
    context.beginPath();
    context.moveTo(-10, y + (random() - 0.5) * 2);
    let x = 0;
    while (x < GRAIN_SIZE + 10) {
      x += GRAIN_JITTER[2] + random() * (GRAIN_JITTER[3] - GRAIN_JITTER[2]);
      context.lineTo(x, y + (random() - 0.5) * GRAIN_JITTER[1]);
    }
    context.stroke();
  }
}

function makeWoodTexture() {
  const canvas = document.createElement("canvas");
  canvas.width = GRAIN_SIZE;
  canvas.height = GRAIN_SIZE;
  paintGrain(canvas);
  return canvas;
}

function textureFromCanvas(canvas) {
  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 4;
  texture.center.set(0.5, 0.5); // 每个面的旋转都绕贴图中心，转完还铺满整面
  return texture;
}

function materialFor(kind, texture) {
  // **不要 DoubleSide**：板件之间的接缝面本来就是共面的（层板端面贴着中立板、
  // 底板贴着侧板……），双面渲染会让这对共面三角形同时参与深度测试，转一下就闪。
  // 盒子是闭合体，只看外面用默认的 FrontSide 就够。
  // `polygonOffset` 往后退一点，让描边线（贴着板面画的那圈）稳稳压在上面，
  // 否则线与面同深度，也会闪。
  const base = {
    roughness: 0.72,
    metalness: 0.0,
    polygonOffset: true,
    polygonOffsetFactor: 1,
    polygonOffsetUnits: 1,
  };
  if (kind === "white") {
    return new THREE.MeshStandardMaterial({
      ...base,
      color: WHITE_FACE,
      roughness: 0.34,
    });
  }
  return new THREE.MeshStandardMaterial({ ...base, color: WOOD_BASE, map: texture });
}


export {WOOD_BASE, WHITE_FACE, EDGE_COLOR, EDGE_OPACITY, SELECT_COLOR, HOVER_COLOR, FLOOR_COLOR, GRAIN_SEED, makeRandom, makeWoodTexture, textureFromCanvas, materialFor};
