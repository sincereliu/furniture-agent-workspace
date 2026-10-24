import { grainLabel } from "./labels.js";
export function createPanelEditor({panelList, meshes, state, panelSave, renderDetail, paint}){
  // 铰链侧：先攒着，和顺纹一起点「保存并冻结」才提交。
  const hingeEdits = new Map();

  function hingeIsPending(panelId) {
    return hingeEdits.has(panelId);
  }

  // 当前生效的铰链侧：攒过的看攒的值，否则看板件自己的。空 = 还没定。
  function hingeSideOf(panel) {
    return hingeEdits.has(panel.id) ? hingeEdits.get(panel.id) : (panel.hinge_side || "");
  }

  // 选左开 / 右开。选回板件原本的值就等于撤销这条改动。
  function setHingeSide(panelId, side) {
    const panel = panelById(panelId);
    if (!panel) return;
    if (side === (panel.hinge_side || "")) hingeEdits.delete(panelId);
    else hingeEdits.set(panelId, side);
    if (state.selected === panelId) renderDetail(panel);
    else renderPendingEdits();
    paint();
  }

  // 顺纹编辑：先攒着，点一次「保存并冻结」才提交一次修订。
  // 攒的是「板件 id → 新轴」，只记**和当前不一样**的那些。
  const grainEdits = new Map();

  // 换个顺纹轴之后，六个面怎么摆——**口径由板件阶段给**（`grain_axes` / `grain_cycle_mm`
  // 跟着投影来），这里只照着算，不自己定义规则。缺了那两项（旧投影）就不预览，
  // 直接提交后由服务端算准的。
  //
  // 这条规则我在 Python 那边错过两次（「修好侧板就坏背板」），所以这里刻意做成
  // 「数据驱动」：面是 u 还是 v 由投影说，转不转只看 u 是不是顺纹轴。
  function grainUvFor(axis, panel) {
    const table = panel.grain_axes;
    const cycle = panel.grain_cycle_mm;
    if (!Array.isArray(table) || !cycle) return null;
    const index = { x: 0, y: 1, z: 2 }[axis];
    const size = panel.size_mm;
    const repeat = (span) => Math.min(4.5, Math.max(1, Math.abs(span) / cycle));
    const faces = {};
    let home = "";
    let homeArea = -1;
    for (const [face, [u, v]] of table) {
      const rotate = index !== undefined && u !== index;
      const [first, second] = rotate ? [v, u] : [u, v];
      faces[face] = {
        rotation: rotate ? Math.PI / 2 : 0,
        repeat: [repeat(size[first]), repeat(size[second])],
      };
      const area = Math.abs(size[u]) * Math.abs(size[v]);
      if (area > homeArea) {
        home = face;
        homeArea = area;
      }
    }
    return { axis, rotation: faces[home].rotation, home, faces };
  }

  // 大面的长短边各落在柜体哪根轴上。
  function grainPlaneAxes(panel) {
    const table = panel.grain_axes;
    const pair = Array.isArray(table) ? table.find(([face]) => face === panel.grain.home) : null;
    if (!pair) return null;
    const [, [u, v]] = pair;
    const axisOf = { 0: "x", 1: "y", 2: "z" };
    const spanOf = (index) => Math.abs(Number(panel.size_mm[index])) || 0;
    const first = { axis: axisOf[u], span: spanOf(u) };
    const second = { axis: axisOf[v], span: spanOf(v) };
    return first.span >= second.span
      ? { long: first.axis, short: second.axis }
      : { long: second.axis, short: first.axis };
  }

  // 「竖纹」要的那根轴（长边）、「横纹」要的那根轴（短边）。
  function grainPlaneAxis(panel, direction) {
    const plane = grainPlaneAxes(panel);
    if (!plane) return null;
    return direction === "vertical" ? plane.long : plane.short;
  }

  // 这块板现在是竖纹还是横纹。
  function grainDirectionOf(panel) {
    const plane = grainPlaneAxes(panel);
    if (!plane) return null;
    return grainAxisOf(panel) === plane.long ? "vertical" : "horizontal";
  }

  const GRAIN_DIRECTION_LABEL = { vertical: "竖纹", horizontal: "横纹" };

  function grainIsPending(panelId) {
    return grainEdits.has(panelId);
  }

  function panelById(panelId) {
    return panelList.find((panel) => panel.id === panelId) || null;
  }

  // 当前生效的方向：攒过的看攒的值，否则看板件自己的。
  function grainAxisOf(panel) {
    const edit = grainEdits.get(panel.id);
    return edit ? edit.axis : panel.grain.axis;
  }

  // 点一下就在**竖纹 / 横纹**之间切一次，可以反复切。
  //
  // 「竖纹」= 顺这块板的**长边**、「横纹」= 顺短边。用长边而不是"柜体高"当判据，是因为
  // 水平放的板（顶板 / 层板 / 底板 / 踢脚）大面在水平面里，两根轴都不落在柜体高上——
  // "竖"对它们没有意义；而长边口径正好复现出那张默认表（侧板 580×1000、顶板 764×580、
  // 背板 776×926 的长边分别是高、宽、高）。
  //
  // 攒的是「板件 id → {axis, from}」：`from` 是**切换后**的方向（清单里要显示）。
  function toggleGrainDirection(panelId) {
    const panel = panelById(panelId);
    if (!panel) return;
    const next = grainDirectionOf(panel) === "vertical" ? "horizontal" : "vertical";
    const axis = grainPlaneAxis(panel, next);
    if (axis === null) return;
    if (axis === panel.grain_default) {
      // 切回这种板的默认方向 = 这条改动没必要留着（存下去也是原样）。
      grainEdits.delete(panelId);
    } else {
      grainEdits.set(panelId, { axis, from: next });
    }
    applyGrainAxis(panel);
    if (state.selected === panelId) renderDetail(panel);
    else renderPendingEdits();
    paint();
  }

  // 画面跟着改：把新轴换算成六个面的摆法。
  //
  // **不要动 `panel.grain.axis`**（板件自己的那个值）。它是"改之前"的依据：改一次就把它
  // 覆盖掉的话，再点一次算出来的"下一个方向"还是同一个，看起来就是"只能切一次、再点没反应"。
  // 当前生效的方向一律由 `grainAxisOf()` 决定（攒过看攒的，否则看板件自己的）。
  function applyGrainAxis(panel) {
    const axis = grainAxisOf(panel);
    const faces = grainUvFor(axis, panel);
    if (!faces) return;
    panel.grainView = { axis, faces: faces.faces, rotation: faces.rotation, home: faces.home };
    const record = meshes.find((item) => item.panel.id === panel.id);
    if (record && record.grainFaces) {
      record.grainFaces = faces.faces;
      record.homeFace = faces.home;
      record.woodMap.rotation = faces.rotation;
    }
  }

  // 「待保存」清单 + 保存按钮的可用状态。
  //
  // 这块区域**不属于顺纹**：以后别的板件属性也从这里改、一起存，所以它只显示"还没保存的
  // 改动"和一颗「保存并冻结」，不叫「保存顺纹」。没有"放弃改动"——再点一次就切回去了，
  // 想撤销直接切回原样即可。
  function renderPendingEdits() {
    const { editor, pending, save, status } = panelSave;
    if (!editor) return;
    const total = grainEdits.size + hingeEdits.size;
    editor.hidden = total === 0;
    if (pending) {
      pending.replaceChildren();
      for (const [panelId, edit] of grainEdits) {
        const panel = panelById(panelId);
        const item = document.createElement("li");
        const name = document.createElement("b");
        name.textContent = panel ? panel.name : panelId;
        // 说人话：这块板改成竖纹还是横纹，以及具体落在柜体哪根轴上。
        item.append(
          name,
          document.createTextNode(
            `${GRAIN_DIRECTION_LABEL[edit.from]}（${grainLabel(edit.axis)}）`
          )
        );
        pending.append(item);
      }
      for (const [panelId, side] of hingeEdits) {
        const panel = panelById(panelId);
        const item = document.createElement("li");
        const name = document.createElement("b");
        name.textContent = panel ? panel.name : panelId;
        item.append(name, document.createTextNode(side === "left" ? "左开" : "右开"));
        pending.append(item);
      }
    }
    if (save) save.disabled = total === 0;
    if (status) status.textContent = "";
  }

  // 保存这一页上所有还没落盘的改动，然后重新冻结。现在有两种：顺纹方向、门板铰链侧。
  // 接口本身就是"把攒下的改动一次提交"，再加别的属性也不用改这里。
  async function saveChanges() {
    const { url, version, save, status } = panelSave;
    if (!url || !version || grainEdits.size + hingeEdits.size === 0) return;
    if (save) save.disabled = true;
    if (status) status.textContent = "正在保存…";
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        cache: "no-store",
        body: JSON.stringify({
          expected_version: version,
          axes: Object.fromEntries([...grainEdits].map(([id, edit]) => [id, edit.axis])),
          hinges: Object.fromEntries([...hingeEdits]),
        }),
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        throw new Error(detail.detail?.message || detail.detail || `HTTP ${response.status}`);
      }
      // 存下去的是新的一版冻结板件：这一页读的还是旧的，所以直接刷新把新事实拉回来。
      if (status) status.textContent = "已保存，正在重新载入…";
      window.location.reload();
    } catch (error) {
      if (status) status.textContent = `没保存成功：${error.message}`;
      if (save) save.disabled = false;
    }
  }

  if (panelSave.save) panelSave.save.addEventListener("click", saveChanges);


  return {hingeIsPending, hingeSideOf, setHingeSide, grainDirectionOf, grainIsPending, toggleGrainDirection, renderPendingEdits, GRAIN_DIRECTION_LABEL};
}
