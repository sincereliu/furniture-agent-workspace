import { formatMm, triple, materialLabel, grainLabel } from "./labels.js";
export function createPanelSidebar({panelList, payload, width, depth, height, rows, count, detail, summary, state, panelSave, select, editor}){
  function renderRows() {
    if (!rows) return;
    rows.replaceChildren();
    for (const panel of panelList) {
      const row = document.createElement("tr");
      row.dataset.panel = panel.id;
      row.setAttribute("aria-selected", "false");
      row.title = panel.role || panel.panel_type;
      const nameCell = document.createElement("td");
      const dot = document.createElement("span");
      dot.className = `dot ${panel.material === "white" ? "white" : "wood"}`;
      nameCell.append(dot, document.createTextNode(panel.name));
      const role = document.createElement("div");
      role.className = "role";
      role.textContent = panel.role || panel.panel_type;
      nameCell.append(role);
      const sizeCell = document.createElement("td");
      sizeCell.className = "num";
      sizeCell.textContent = triple(panel.size_mm);
      const posCell = document.createElement("td");
      posCell.className = "num";
      posCell.textContent = `(${panel.pos_mm.map(formatMm).join(", ")})`;
      row.append(nameCell, sizeCell, posCell);
      row.addEventListener("click", () => select(panel.id === state.selected ? null : panel.id));
      rows.append(row);
    }
    if (count) count.textContent = String(panelList.length);
  }

  function renderDetail(panel) {
    if (!detail) return;
    if (!panel) {
      detail.hidden = true;
      detail.replaceChildren();
      return;
    }
    detail.hidden = false;
    detail.replaceChildren();
    const title = document.createElement("strong");
    title.textContent = panel.name;
    const list = document.createElement("dl");
    list.className = "kv";
    const facts = [
      ["角色", panel.role || "—"],
      ["类型", panel.panel_type || "—"],
      ["尺寸", `${triple(panel.size_mm)} mm`],
      ["位置", `(${panel.pos_mm.map(formatMm).join(", ")}) mm`],
      ["材料", materialLabel(panel.material)],
      ["材质角色", panel.material_role || "—"],
      ["内面 / 外面", `${panel.inner_face || "—"} / ${panel.outer_face || "—"}`],
      ["接触", `${panel.contact_count}`],
    ];
    for (const [key, value] of facts) {
      const dt = document.createElement("dt");
      dt.textContent = key;
      const dd = document.createElement("dd");
      dd.textContent = value;
      list.append(dt, dd);
    }
    // 顺纹方向：这是**板件的属性**，点一下就在竖纹 / 横纹之间切换（不是查看器上的显示开关）。
    // 只读分享的那一页不给改：`panelSave.editor` 缺了就当普通一行文字。
    const grainDt = document.createElement("dt");
    grainDt.textContent = "顺纹方向";
    const grainDd = document.createElement("dd");
    const direction = editor.grainDirectionOf(panel);
    const label = direction
      ? `${editor.GRAIN_DIRECTION_LABEL[direction]}${editor.grainIsPending(panel.id) ? "（待保存）" : ""}`
      : grainLabel(panel.grain.axis);
    if (panelSave.editor && direction) {
      // **点这一行才改纹理**（文字和画面同时变）。点板件只是选中——改数据不能和点选同一个动作。
      const button = document.createElement("span");
      button.className = "grainrow";
      button.setAttribute("role", "button");
      button.tabIndex = 0;
      button.title = "点一下把这块板的纹理翻成另一种（竖纹 ⇄ 横纹）";
      button.textContent = label;
      button.addEventListener("click", () => editor.toggleGrainDirection(panel.id));
      grainDd.append(button);
    } else {
      grainDd.textContent = label;
    }
    list.append(grainDt, grainDd);
    if (panel.panel_type === "door") {
      // 铰链侧：**左开＝铰链在左边，右开＝铰链在右边**，不解释拉手。
      // 对开腔的两扇由几何定死（左扇挂左、右扇挂右），这里只显示结果、不给改；
      // 单开腔没定的时候就给两个按钮让人选——这就是"提示客户选"的那一步。
      const hingeDt = document.createElement("dt");
      hingeDt.textContent = "铰链侧";
      const hingeDd = document.createElement("dd");
      const current = editor.hingeSideOf(panel);
      const label = current === "left" ? "左开" : current === "right" ? "右开" : "还没定";
      if (panel.hinge_locked || !panelSave.editor) {
        hingeDd.textContent = label;
        if (panel.hinge_locked) {
          hingeDd.title = "对开腔由几何决定：左扇挂左、右扇挂右，不能单独改";
        }
      } else {
        const group = document.createElement("span");
        group.className = "hingerow";
        for (const [side, text] of [["left", "左开"], ["right", "右开"]]) {
          const button = document.createElement("button");
          button.type = "button";
          button.textContent = text;
          button.className = "chip";
          button.setAttribute("aria-pressed", String(current === side));
          button.addEventListener("click", () => editor.setHingeSide(panel.id, side));
          group.append(button);
        }
        hingeDd.append(group);
        const hint = document.createElement("span");
        hint.className = "hint-inline";
        hint.textContent = current
          ? editor.hingeIsPending(panel.id) ? "（待保存）" : ""
          : "还没定——选一个，再点「保存并冻结」";
        if (hint.textContent) hingeDd.append(hint);
      }
      list.append(hingeDt, hingeDd);
    }
    detail.append(title, list);
    editor.renderPendingEdits();
  }

  function renderSummary() {    if (!summary) return;
    const materialText = (payload.materials || [])
      .map((item) => `${item.label} ${item.count}`)
      .join(" · ");
    const facts = [
      ["外形 W×D×H", `${triple([width, depth, height])} mm`],
      [
        "内部净空",
        payload.cavity_mm && payload.cavity_mm.width != null
          ? `${triple([payload.cavity_mm.width, payload.cavity_mm.depth, payload.cavity_mm.height])} mm`
          : "—",
      ],
      [
        "料厚 柜体/背/门",
        `${formatMm(payload.thickness_mm?.board)} / ${formatMm(payload.thickness_mm?.back)} / ${formatMm(payload.thickness_mm?.door)} mm`,
      ],
      ["背板安装", `${payload.back_mount?.effective || "—"}（请求 ${payload.back_mount?.requested || "—"}）`],
      ["门 / 抽屉 / 层板", `${payload.n_doors} / ${payload.drawer_count} / ${payload.shelf_count}`],
      ["踢脚高", `${formatMm(payload.toe_kick_height_mm)} mm`],
      ["材料", materialText || "—"],
      ["板件块数", `${panelList.length}`],
    ];
    summary.replaceChildren();
    for (const [key, value] of facts) {
      const dt = document.createElement("dt");
      dt.textContent = key;
      const dd = document.createElement("dd");
      dd.textContent = value;
      summary.append(dt, dd);
    }
  }


  return {renderRows, renderDetail, renderSummary};
}
