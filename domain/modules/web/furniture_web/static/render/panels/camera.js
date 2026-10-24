import * as THREE from "three";

// 环顾一圈的方向（three.js 坐标，已经含 Z 朝上 → Y 朝上的那次旋转）。
//
// 换算关系是 `世界 = (柜宽 − 柜X, 柜Z, -柜Y)`，其中 x 那次**镜像**是必须的：
// 柜体坐标是「X 宽向右、Y 朝门、Z 朝上」，而站在门前看（门朝你），右手系里
// 柜体 +X 必然落在人的**左手边**——数据却把低 X 叫 `left_side_panel`。不镜像的话
// 整台柜子在页面上是反的：左侧板画在右边，`hinge_side="left"` 的门开到右边。
// 所以这里按「低 X = 屏幕左」渲染；柜宽中点是不动点，取景中心不受影响。
//
// **柜体 +Y（门那一面）在世界里是 -Z**：「正面（门）」必须站在 -Z 看，站到 +Z
// 看到的是背板。这两个弄反的话，人会以为门板没画出来（实测踩过）。
// 镜像之后，「左侧」= 从 +X 看、「右侧」= 从 -X 看。
const VIEWS = {
  iso: [-0.78, 0.62, -0.86],
  front: [0, 0.22, -1.25],
  back: [0, 0.22, 1.25],
  left: [1.25, 0.22, -0.08],
  right: [-1.25, 0.22, -0.08],
  top: [0, 1.35, -0.28],
};


export function createPanelCamera({canvas, camera, controls, width, depth, height, viewButtons}){
  // 整台柜子进镜头要多少距离：把八个角投到「右 / 上 / 沿视线」三个轴上再解。
  // 用外接球（半径 × 常数）会算得过远——球把柜子外面的空处也算进去了。
  //
  // **取景一律用世界坐标**（`world = (柜宽−柜X, 柜Z, -柜Y)`，含那次镜像），和 VIEWS
  // 同一套；柜体坐标和世界坐标差着一次镜像加一次 Z→Y 的旋转，混着用会瞄错方向（实测踩过）。
  // 柜宽中点是镜像的不动点，所以取景中心还是 (宽/2, 高/2, -深/2)。
  const centerWorld = new THREE.Vector3(width / 2, height / 2, -depth / 2);
  const CORNERS = [];
  for (const x of [0, width]) {
    for (const y of [0, depth]) {
      for (const z of [0, height]) {
        CORNERS.push(new THREE.Vector3(width - x, z, -y));
      }
    }
  }
  const MIN_ASPECT = 1.0;
  // 画面基向量。所有预设视角都不是正俯视（Y 分量远小于 1），所以上方向稳定取世界 +Y。
  const HALF_TAN_V = Math.tan(((38 * Math.PI) / 180) / 2);
  const FIT_UP = [0, 1, 0];

  // 每个角单独解：「相机要退到多远，这个角才落在画面里」。
  // `direction` 是相机→目标的单位向量，所以角在相机前方时 `-(角·direction)` 为正；
  // 这个数越小说明角离相机越近、张角越大，要的余量也越多。取八个角里最大的。
  // 判据是 `|右分量| ≤ halfTanH · (distance − depth)`，上分量同理。
  function fitDistanceFor(direction, aspect) {
    const right = [
      FIT_UP[1] * direction[2] - FIT_UP[2] * direction[1],
      FIT_UP[2] * direction[0] - FIT_UP[0] * direction[2],
      FIT_UP[0] * direction[1] - FIT_UP[1] * direction[0],
    ];
    const rightLength = Math.hypot(right[0], right[1], right[2]) || 1;
    for (let index = 0; index < 3; index += 1) right[index] /= rightLength;
    const up = [
      direction[1] * right[2] - direction[2] * right[1],
      direction[2] * right[0] - direction[0] * right[2],
      direction[0] * right[1] - direction[1] * right[0],
    ];
    const halfTanH = HALF_TAN_V * Math.max(aspect, MIN_ASPECT);
    let needed = 0;
    for (const corner of CORNERS) {
      const depth = -(
        corner.x * direction[0] + corner.y * direction[1] + corner.z * direction[2]
      );
      const horizontal = Math.abs(
        corner.x * right[0] + corner.y * right[1] + corner.z * right[2]
      );
      const vertical = Math.abs(
        corner.x * up[0] + corner.y * up[1] + corner.z * up[2]
      );
      needed = Math.max(
        needed,
        depth + vertical / HALF_TAN_V,
        depth + horizontal / halfTanH
      );
    }
    return needed * 1.04;
  }

  function setView(name) {
    name = VIEWS[name] ? name : "iso";
    const raw = VIEWS[name] || VIEWS.iso;
    // 方向只取朝向，距离由 distance 单独定——不归一化的话每个视角离得远近会不一样。
    const length = Math.hypot(raw[0], raw[1], raw[2]) || 1;
    const direction = [raw[0] / length, raw[1] / length, raw[2] / length];
    const canvasAspect =
      (canvas.clientWidth || 960) / Math.max(canvas.clientHeight || 640, 1);
    const distance = fitDistanceFor(direction, canvasAspect);
    camera.position.set(
      centerWorld.x + direction[0] * distance,
      centerWorld.y + direction[1] * distance,
      centerWorld.z + direction[2] * distance
    );
    // 近平面跟着取景距离走。固定 `near = 1` 而 `far` 是几万，深度精度全耗在近处，
    // 远处相邻两张面就会打架——转起来是"闪烁/起条纹"。按距离给 near，精度能好几倍。
    camera.near = Math.max(1, distance / 1000);
    camera.far = distance * 6;
    camera.updateProjectionMatrix();
    controls.target.copy(centerWorld);
    controls.update();
    for (const button of viewButtons) {
      button.setAttribute("aria-pressed", String(button.dataset.view === name));
    }
  }


  return {setView};
}
