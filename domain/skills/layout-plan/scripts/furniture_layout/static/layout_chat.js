/**
 * 布局工作台右侧 AI 对话栏与本机大模型设置组件。
 *
 * 支持本机已登录 OAuth CLI（ChatGPT Codex / Gemini AGY，无需 API Key）以及通用 OpenAI 样式本地/兼容模型入口。
 * 按不同厂商与模型家族自动适配对应的思考深度（Thinking / Reasoning Effort）选项与参数叫法。
 * 仅做前端 UI 交互与结构化 HTTP 调用（`/api/llm/config`、`/api/project/{id}/chat`），
 * 不在前端解析自然语言或改写业务规则。
 */

const STAGE_LABELS = {
  layout_plan: "房间布局",
  panel_plan: "板件规划",
  manufacture_plan: "制造与五金",
  feature_tree_planned: "特征树",
  cad_generated: "CAD 模型",
  delivery_validated: "交付校验",
};

const PROVIDER_PRESETS = {
  codex_cli: {
    provider: "codex_cli",
    base_url: "",
    model: "gpt-6.1-sol",
    effort: "high",
  },
  agy_cli: {
    provider: "agy_cli",
    base_url: "",
    model: "gemini-3.8-flash-high",
    effort: "high",
  },
  local_openai: {
    provider: "openai_compatible",
    base_url: "http://127.0.0.1:11434/v1",
    model: "gpt-oss-120b",
    effort: "none",
  },
};

const AGY_TIERED_PREFIXES = [
  "gemini-4-argon-",
  "gemini-3.8-flash-",
];

/**
 * 根据厂商通道 (provider) 与具体模型名称 (model)，返回该模型专属的思考模式档位定义。
 */
export function getEffortProfile(provider, model) {
  const p = String(provider || "codex_cli").trim();
  const m = String(model || "").trim().toLowerCase();

  // 1. OpenAI Codex CLI (gpt-6.1-sol / gpt-6-astra / gpt-5.6-sol 等)
  if (p === "codex_cli") {
    return {
      paramLabel: "OpenAI Codex · model_reasoning_effort",
      hint: "通过 Codex CLI `-c model_reasoning_effort=\"...\"` 传递；gpt-6.1-sol 支持 minimal / low / medium / high / xhigh。",
      defaultEffort: "high",
      options: [
        { value: "minimal", shortLabel: "Effort: minimal", fullLabel: "minimal（极简推理）" },
        { value: "low", shortLabel: "Effort: low", fullLabel: "low（快速推理）" },
        { value: "medium", shortLabel: "Effort: medium", fullLabel: "medium（标准推理）" },
        { value: "high", shortLabel: "Effort: high", fullLabel: "high（深度推理 · 推荐）" },
        { value: "xhigh", shortLabel: "Effort: xhigh", fullLabel: "xhigh（超深推理 · Pro 专属）" },
      ],
    };
  }

  // 2. Google Antigravity / Gemini CLI (agy_cli)
  if (p === "agy_cli") {
    return {
      paramLabel: "Gemini · Thinking Level (--effort & 模型后缀联动)",
      hint: "切换档位时会自动同步 Gemini 模型后缀（-low / -medium / -high）与 `--effort` 参数。",
      defaultEffort: "high",
      options: [
        { value: "low", shortLabel: "Thinking: Low", fullLabel: "Low（对应 -low 模型后缀 · 极速）" },
        { value: "medium", shortLabel: "Thinking: Medium", fullLabel: "Medium（对应 -medium 模型后缀 · 均衡）" },
        { value: "high", shortLabel: "Thinking: High", fullLabel: "High（对应 -high 模型后缀 · 深度）" },
        { value: "xhigh", shortLabel: "Effort: xhigh", fullLabel: "xhigh（AGY --effort xhigh 扩展推理）" },
        { value: "max", shortLabel: "Effort: max", fullLabel: "max（AGY --effort max 最大推理预算）" },
      ],
    };
  }

  // 3. 通用 OpenAI 兼容本地/远端接口
  if (m.includes("gemini")) {
    return {
      paramLabel: "Gemini (OpenAI 兼容) · reasoning_effort",
      hint: "Gemini 系列在 OpenAI 兼容接口下支持 low / medium / high 思考预算映射。",
      defaultEffort: "high",
      options: [
        { value: "none", shortLabel: "Thinking: Off", fullLabel: "none（不传 reasoning_effort）" },
        { value: "low", shortLabel: "Thinking: low", fullLabel: "low（轻量思考预算）" },
        { value: "medium", shortLabel: "Thinking: medium", fullLabel: "medium（中等思考预算）" },
        { value: "high", shortLabel: "Thinking: high", fullLabel: "high（深度思考预算）" },
      ],
    };
  }

  return {
    paramLabel: "通用 OpenAI 接口 · reasoning_effort",
    hint: "支持 reasoning_effort 的模型可选 low / medium / high；普通或本地自托管模型请选择 none（不传该参数）。",
    defaultEffort: /^(o1|o3|o4|gpt-5|gpt-6)/.test(m) ? "high" : "none",
    options: [
      { value: "none", shortLabel: "思考: 默认/不传", fullLabel: "none（不传 reasoning_effort · 适用于通用本地模型）" },
      { value: "minimal", shortLabel: "Effort: minimal", fullLabel: "minimal（极简推理）" },
      { value: "low", shortLabel: "Effort: low", fullLabel: "low（快速推理）" },
      { value: "medium", shortLabel: "Effort: medium", fullLabel: "medium（均衡推理）" },
      { value: "high", shortLabel: "Effort: high", fullLabel: "high（深度推理）" },
      { value: "xhigh", shortLabel: "Effort: xhigh", fullLabel: "xhigh（极限推理）" },
    ],
  };
}

/**
 * 若当前是 AGY CLI 且 Gemini 模型名以 -low / -medium / -high 结尾，切换档位时同步更新模型名后缀。
 */
function syncAgyModelWithEffort(provider, model, effort) {
  const m = String(model || "").trim();
  const e = String(effort || "").trim().toLowerCase();
  if (provider !== "agy_cli") return { model: m, effort: e };

  for (const prefix of AGY_TIERED_PREFIXES) {
    if (m.startsWith(prefix)) {
      const suffix = ["low", "medium", "high"].includes(e) ? e : "high";
      return { model: `${prefix}${suffix}`, effort: e };
    }
  }
  return { model: m, effort: e };
}

/**
 * 若用户在 AGY CLI 下直接手改了 Gemini 模型后缀（如改成 gemini-4-argon-low），反推对应的 effort。
 */
function inferEffortFromModelName(provider, model, currentEffort) {
  const m = String(model || "").trim().toLowerCase();
  if (provider === "agy_cli") {
    if (m.endsWith("-low")) return "low";
    if (m.endsWith("-medium")) return "medium";
    if (m.endsWith("-high") && ["low", "medium"].includes(currentEffort)) return "high";
  }
  return currentEffort;
}

function populateSelectOptions(selectEl, options, selectedValue, useFullLabel) {
  if (!selectEl) return "";
  const validValues = options.map((o) => o.value);
  const finalValue = validValues.includes(selectedValue)
    ? selectedValue
    : (options[0] ? options[0].value : "high");

  selectEl.innerHTML = "";
  for (const opt of options) {
    const el = document.createElement("option");
    el.value = opt.value;
    el.textContent = useFullLabel ? opt.fullLabel : opt.shortLabel;
    if (opt.value === finalValue) el.selected = true;
    selectEl.appendChild(el);
  }
  selectEl.value = finalValue;
  selectEl.disabled = options.length <= 1;
  return finalValue;
}

function formatStageBadge(project) {
  if (!project || typeof project !== "object") return "未加载状态";
  const cur = project.current_stage || "layout_plan";
  const approved = Array.isArray(project.approved_stages) ? project.approved_stages : [];
  const isApproved = approved.includes(cur);
  const label = STAGE_LABELS[cur] || cur;
  if (cur === "layout_plan" && !isApproved) {
    const pendingRooms = Array.isArray(project.pending_rooms) ? project.pending_rooms : [];
    return pendingRooms.length > 0
      ? `${label} · 待确认 (${pendingRooms.join(", ")})`
      : `${label} · 待确认`;
  }
  if (isApproved && project.next_stage) {
    const nextLabel = STAGE_LABELS[project.next_stage] || project.next_stage;
    return `${label}已确认 · 可进入${nextLabel}`;
  }
  return isApproved ? `${label} · 已确认` : `${label} · 待确认`;
}

export function mountProjectChat({
  chatUrl,
  llmConfigUrl,
  onProjectUpdated,
  onStatusToast,
}) {
  const panel = document.getElementById("chat-panel");
  const toggleBtn = document.getElementById("toggle-chat");
  if (!panel || !chatUrl || !llmConfigUrl) return null;

  document.body.classList.add("has-chat");
  panel.hidden = false;
  if (toggleBtn) {
    toggleBtn.hidden = false;
    toggleBtn.setAttribute("aria-pressed", "true");
  }

  const stagePill = document.getElementById("chat-stage-pill");
  const messagesEl = document.getElementById("chat-messages");
  const formEl = document.getElementById("chat-form");
  const inputEl = document.getElementById("chat-input");
  const sendBtn = document.getElementById("chat-send-btn");
  const clearBtn = document.getElementById("chat-clear-btn");
  const effortSelect = document.getElementById("chat-effort-select");
  const settingsBtn = document.getElementById("chat-settings-btn");
  const settingsDot = document.getElementById("chat-settings-dot");
  const quickBar = document.getElementById("chat-quick-bar");

  const modal = document.getElementById("llm-modal");
  const modalForm = document.getElementById("llm-config-form");
  const providerSelect = document.getElementById("llm-provider");
  const baseUrlField = document.getElementById("llm-base-url-field");
  const baseUrlInput = document.getElementById("llm-base-url");
  const modelInput = document.getElementById("llm-model");
  const modalEffortLabel = document.getElementById("llm-effort-label");
  const modalEffortSelect = document.getElementById("llm-effort");
  const modalEffortHint = document.getElementById("llm-effort-hint");
  const modelHint = document.getElementById("llm-model-hint");
  const apiKeyField = document.getElementById("llm-api-key-field");
  const apiKeyInput = document.getElementById("llm-api-key");
  const apiKeyHint = document.getElementById("llm-key-hint");
  const modalCloseBtn = document.getElementById("llm-modal-close");
  const modalStatus = document.getElementById("llm-modal-status");

  let state = {
    sending: false,
    llm: null,
    project: null,
    messages: [],
  };

  function syncModalProviderFields(preferredEffort) {
    if (!providerSelect) return;
    const provider = providerSelect.value;
    const model = modelInput ? modelInput.value.trim() : "";
    const isCli = provider === "codex_cli" || provider === "agy_cli";
    if (baseUrlField) baseUrlField.hidden = isCli;
    if (baseUrlInput) baseUrlInput.required = !isCli;
    if (apiKeyField) apiKeyField.hidden = isCli;
    if (modelHint) {
      if (provider === "codex_cli") {
        modelHint.textContent =
          "直接使用本机 Codex OAuth 登录态（免 API Key）。可选 ChatGPT 模型：gpt-6.1-sol、gpt-6-astra、gpt-6-sol、gpt-5.6-sol";
      } else if (provider === "agy_cli") {
        modelHint.textContent =
          "直接使用本机 AGY / Gemini OAuth 登录态（免 API Key）。可选 Gemini 模型：gemini-4-argon-high、gemini-3.8-flash-high";
      } else {
        modelHint.textContent =
          "填写本地或兼容 OpenAI 接口的模型 ID（本机 127.0.0.1 / localhost 地址免填 API Key）";
      }
    }

    const profile = getEffortProfile(provider, model);
    if (modalEffortLabel) {
      modalEffortLabel.textContent = `思考模式 (${profile.paramLabel})`;
    }
    if (modalEffortHint) {
      modalEffortHint.textContent = profile.hint;
    }
    const currentVal =
      preferredEffort ||
      (modalEffortSelect ? modalEffortSelect.value : "") ||
      profile.defaultEffort;
    const inferred = inferEffortFromModelName(provider, model, currentVal);
    const chosenEffort = populateSelectOptions(
      modalEffortSelect,
      profile.options,
      inferred || profile.defaultEffort,
      true,
    );
    if (provider === "agy_cli" && modelInput) {
      const synced = syncAgyModelWithEffort(provider, model, chosenEffort);
      if (synced.model && synced.model !== modelInput.value) {
        modelInput.value = synced.model;
      }
    }
  }

  function updateLlmIndicator(llm) {
    state.llm = llm || null;
    const provider = (llm && llm.provider) || "codex_cli";
    const model = (llm && llm.model) || "gpt-6.1-sol";
    const profile = getEffortProfile(provider, model);
    const rawEffort = (llm && llm.reasoning_effort) || profile.defaultEffort;
    const activeEffort = populateSelectOptions(
      effortSelect,
      profile.options,
      rawEffort,
      false,
    );
    if (effortSelect) {
      effortSelect.title = `${profile.paramLabel} — ${profile.hint}`;
    }

    if (!settingsDot || !settingsBtn) return;
    const configured = Boolean(llm && llm.configured);
    settingsDot.classList.toggle("ok", configured);
    settingsDot.classList.toggle("warn", !configured);
    if (configured) {
      const modeName =
        llm.provider === "codex_cli"
          ? "本机 ChatGPT 订阅"
          : llm.provider === "agy_cli"
            ? "本机 Gemini 订阅"
            : llm.base_url;
      settingsBtn.title = `当前模型：${llm.model} · ${profile.paramLabel}: ${activeEffort} (${modeName})`;
    } else {
      settingsBtn.title = "点击选择本机 ChatGPT/Gemini 订阅或配置本地 OpenAI 模型入口";
    }
  }

  function updateProjectSummary(project) {
    if (!project) return;
    state.project = project;
    if (stagePill) {
      stagePill.textContent = formatStageBadge(project);
    }
  }

  function createToolTraceNode(traceList) {
    const wrap = document.createElement("div");
    wrap.className = "chat-tool-trace";
    for (const item of traceList) {
      const chip = document.createElement("span");
      chip.className = "chat-tool-chip " + (item.ok ? "ok" : "err");
      const mark = item.ok ? "✓" : "⚠";
      const suffix = item.progressed ? " · 已更新项目" : "";
      const errText =
        !item.ok && item.error && item.error.message
          ? ` (${item.error.message})`
          : "";
      chip.textContent = `${mark} ${item.tool}${suffix}${errText}`;
      wrap.appendChild(chip);
    }
    return wrap;
  }

  function renderMessages() {
    if (!messagesEl) return;
    messagesEl.innerHTML = "";
    if (!state.messages || state.messages.length === 0) {
      const empty = document.createElement("div");
      empty.className = "chat-empty";
      const configured = Boolean(state.llm && state.llm.configured);
      let modelTag = "";
      if (configured && state.llm) {
        const profile = getEffortProfile(state.llm.provider, state.llm.model);
        const matchOpt =
          profile.options.find((o) => o.value === state.llm.reasoning_effort) ||
          profile.options[0];
        const effortLabel = matchOpt ? matchOpt.shortLabel : state.llm.reasoning_effort;
        modelTag = `<br><span style="color:#4f46e5;font-weight:600">当前已连接：${state.llm.model} (${effortLabel})</span>`;
      }
      empty.innerHTML = configured
        ? `<strong>直接在这里和 AI 对话</strong>${modelTag}<br>你可以让 AI 修改房间家具尺寸、确认当前布局，或生成各台柜子的板件草稿，左侧 3D 视图会自动同步更新。`
        : "<strong>欢迎使用网页端 AI 助手</strong><br>点击右上角「⚙️ 模型设置」，可直接选用本机已登录的 ChatGPT / Gemini 订阅账号（免 API Key）。";
      messagesEl.appendChild(empty);
      return;
    }

    for (const msg of state.messages) {
      const item = document.createElement("div");
      const role = msg.role === "user" ? "user" : "assistant";
      item.className = `chat-msg ${role}`;

      if (role === "assistant" && Array.isArray(msg.tool_trace) && msg.tool_trace.length > 0) {
        item.appendChild(createToolTraceNode(msg.tool_trace));
      }

      const bubble = document.createElement("div");
      bubble.className = "chat-bubble";
      bubble.textContent = msg.content || "";
      item.appendChild(bubble);
      messagesEl.appendChild(item);
    }

    if (state.sending) {
      const thinking = document.createElement("div");
      thinking.className = "chat-msg assistant thinking";
      const bubble = document.createElement("div");
      bubble.className = "chat-bubble";
      bubble.textContent = "AI 正在思考并执行工具…";
      thinking.appendChild(bubble);
      messagesEl.appendChild(thinking);
    }

    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  async function loadInitialChat() {
    try {
      const resp = await fetch(chatUrl, { cache: "no-store" });
      if (!resp.ok) return;
      const data = await resp.json();
      state.messages = Array.isArray(data.messages) ? data.messages : [];
      updateLlmIndicator(data.llm);
      updateProjectSummary(data.project);
      renderMessages();
    } catch (err) {
      // 忽略初始加载网络异常
    }
  }

  async function sendMessage(text) {
    const trimmed = String(text || "").trim();
    if (!trimmed || state.sending) return;
    if (!state.llm || !state.llm.configured) {
      openSettingsModal("请先选择本机 ChatGPT/Gemini 订阅模式或配置本地模型入口");
      return;
    }

    state.sending = true;
    const optimisticUser = {
      id: "temp_user",
      role: "user",
      content: trimmed,
    };
    state.messages = [...state.messages, optimisticUser];
    if (inputEl) inputEl.value = "";
    if (sendBtn) sendBtn.disabled = true;
    renderMessages();

    try {
      const resp = await fetch(chatUrl, {
        method: "POST",
        cache: "no-store",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: trimmed }),
      });
      const payload = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        const detail = payload && payload.detail;
        const errMsg =
          typeof detail === "object" && detail !== null
            ? detail.message || JSON.stringify(detail)
            : String(detail || `请求失败 (${resp.status})`);
        state.messages = [
          ...state.messages,
          {
            id: "temp_err",
            role: "assistant",
            content: `⚠️ ${errMsg}`,
          },
        ];
        if (detail && detail.code && detail.code.startsWith("LLM_NOT_CONFIGURED")) {
          openSettingsModal(errMsg);
        }
        return;
      }

      if (Array.isArray(payload.messages)) {
        state.messages = payload.messages;
      }
      if (payload.project) {
        updateProjectSummary(payload.project);
      }
      if (payload.progressed || (Array.isArray(payload.tool_trace) && payload.tool_trace.length > 0)) {
        if (typeof onProjectUpdated === "function") {
          onProjectUpdated();
        }
        if (typeof onStatusToast === "function" && payload.progressed) {
          onStatusToast("AI 已更新项目状态，3D 视图已同步");
        }
      }
    } catch (err) {
      state.messages = [
        ...state.messages,
        {
          id: "temp_err",
          role: "assistant",
          content: `⚠️ 请求异常：${err}`,
        },
      ];
    } finally {
      state.sending = false;
      if (sendBtn) sendBtn.disabled = false;
      renderMessages();
    }
  }

  function openSettingsModal(noticeText = "") {
    if (!modal) return;
    const llm = state.llm || {};
    if (providerSelect) providerSelect.value = llm.provider || "codex_cli";
    if (baseUrlInput) {
      const url = llm.base_url && !llm.base_url.startsWith("local://") ? llm.base_url : "http://127.0.0.1:11434/v1";
      baseUrlInput.value = url;
    }
    if (modelInput) modelInput.value = llm.model || "gpt-6.1-sol";
    if (apiKeyInput) {
      apiKeyInput.value = "";
      apiKeyInput.placeholder = llm.has_api_key
        ? `已保存 (${llm.api_key_masked})，留空保持不变`
        : "本机地址可留空；远端接口填 API Key";
    }
    if (apiKeyHint) {
      apiKeyHint.textContent = llm.has_api_key
        ? `当前已保存密钥：${llm.api_key_masked}（仅存本机 store/_llm_config.json）`
        : "密钥仅保存在本机 store/_llm_config.json，绝不上传 Git。";
    }
    syncModalProviderFields(llm.reasoning_effort || "high");
    if (modalStatus) {
      modalStatus.textContent = noticeText || "";
    }
    modal.hidden = false;
  }

  function closeSettingsModal() {
    if (modal) modal.hidden = true;
  }

  if (toggleBtn) {
    toggleBtn.addEventListener("click", () => {
      const hidden = !panel.hidden;
      panel.hidden = hidden;
      document.body.classList.toggle("has-chat", !hidden);
      toggleBtn.setAttribute("aria-pressed", hidden ? "false" : "true");
      window.dispatchEvent(new Event("resize"));
    });
  }

  if (effortSelect) {
    effortSelect.addEventListener("change", async () => {
      const newEffort = effortSelect.value || "high";
      const llm = state.llm || {};
      const provider = llm.provider || "codex_cli";
      const isCli = provider === "codex_cli" || provider === "agy_cli";
      const synced = syncAgyModelWithEffort(
        provider,
        llm.model || "gpt-6.1-sol",
        newEffort,
      );
      try {
        const resp = await fetch(llmConfigUrl, {
          method: "POST",
          cache: "no-store",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            provider,
            base_url: isCli ? "" : (llm.base_url || ""),
            model: synced.model,
            reasoning_effort: synced.effort,
            api_key: null,
          }),
        });
        if (resp.ok) {
          const data = await resp.json();
          updateLlmIndicator(data);
          renderMessages();
          if (typeof onStatusToast === "function") {
            onStatusToast(`已切换思考模式：${data.model} (${data.reasoning_effort})`);
          }
        }
      } catch (err) {}
    });
  }

  if (providerSelect) {
    providerSelect.addEventListener("change", () => {
      const p = providerSelect.value;
      if (p === "codex_cli" && modelInput) modelInput.value = "gpt-6.1-sol";
      else if (p === "agy_cli" && modelInput) modelInput.value = "gemini-3.8-flash-high";
      else if (p === "openai_compatible") {
        if (baseUrlInput && (!baseUrlInput.value || baseUrlInput.value.startsWith("local://"))) {
          baseUrlInput.value = "http://127.0.0.1:11434/v1";
        }
      }
      syncModalProviderFields();
    });
  }

  if (modelInput) {
    modelInput.addEventListener("input", () => {
      syncModalProviderFields();
    });
  }

  if (modalEffortSelect) {
    modalEffortSelect.addEventListener("change", () => {
      const p = providerSelect ? providerSelect.value : "codex_cli";
      const m = modelInput ? modelInput.value.trim() : "";
      const e = modalEffortSelect.value;
      if (p === "agy_cli" && modelInput) {
        const synced = syncAgyModelWithEffort(p, m, e);
        if (synced.model) modelInput.value = synced.model;
      }
    });
  }

  if (settingsBtn) {
    settingsBtn.addEventListener("click", () => openSettingsModal());
  }
  if (modalCloseBtn) {
    modalCloseBtn.addEventListener("click", closeSettingsModal);
  }
  if (modal) {
    modal.addEventListener("click", (e) => {
      if (e.target === modal) closeSettingsModal();
    });
    modal.querySelectorAll("button[data-llm-preset]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const key = btn.getAttribute("data-llm-preset");
        const preset = PROVIDER_PRESETS[key];
        if (!preset) return;
        if (providerSelect) providerSelect.value = preset.provider;
        if (baseUrlInput && preset.base_url) baseUrlInput.value = preset.base_url;
        if (modelInput) modelInput.value = preset.model;
        syncModalProviderFields(preset.effort);
      });
    });
  }

  if (modalForm) {
    modalForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (modalStatus) modalStatus.textContent = "正在保存…";
      try {
        const provider = providerSelect ? providerSelect.value : "codex_cli";
        const isCli = provider === "codex_cli" || provider === "agy_cli";
        const rawModel = modelInput ? modelInput.value.trim() : "";
        const rawEffort = modalEffortSelect ? modalEffortSelect.value : "high";
        const synced = syncAgyModelWithEffort(provider, rawModel, rawEffort);
        const body = {
          provider,
          base_url: isCli ? "" : (baseUrlInput ? baseUrlInput.value.trim() : ""),
          model: synced.model,
          reasoning_effort: synced.effort,
          api_key: !isCli && apiKeyInput && apiKeyInput.value.trim() ? apiKeyInput.value.trim() : null,
        };
        const resp = await fetch(llmConfigUrl, {
          method: "POST",
          cache: "no-store",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok) {
          if (modalStatus) {
            modalStatus.textContent = `保存失败：${data.detail || resp.status}`;
          }
          return;
        }
        updateLlmIndicator(data);
        renderMessages();
        closeSettingsModal();
        if (typeof onStatusToast === "function") {
          onStatusToast(`已切换模型：${data.model} (思考模式: ${data.reasoning_effort})`);
        }
      } catch (err) {
        if (modalStatus) modalStatus.textContent = `保存出错：${err}`;
      }
    });
  }

  if (clearBtn) {
    clearBtn.addEventListener("click", async () => {
      if (state.sending) return;
      try {
        await fetch(chatUrl, { method: "DELETE", cache: "no-store" });
        state.messages = [];
        renderMessages();
      } catch (err) {}
    });
  }

  if (quickBar) {
    quickBar.addEventListener("click", (e) => {
      const btn = e.target && e.target.closest ? e.target.closest("button[data-prompt]") : null;
      if (!btn || state.sending) return;
      const prompt = btn.getAttribute("data-prompt");
      if (prompt) sendMessage(prompt);
    });
  }

  if (formEl) {
    formEl.addEventListener("submit", (e) => {
      e.preventDefault();
      if (inputEl) sendMessage(inputEl.value);
    });
  }

  if (inputEl) {
    inputEl.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage(inputEl.value);
      }
    });
  }

  loadInitialChat();
  return {
    reload: loadInitialChat,
    sendMessage,
  };
}
