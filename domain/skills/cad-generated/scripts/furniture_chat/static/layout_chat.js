/**
 * 布局工作台右侧 AI 对话栏与本机大模型设置组件（基于 Angular Standalone Component & Reactive Signals）。
 *
 * Codex 使用仓库外独立登录；同时支持 Gemini AGY 和通用 OpenAI 兼容接口。
 * 按不同厂商与模型家族自动适配对应的思考深度（Thinking / Reasoning Effort）选项与参数叫法。
 * 仅做前端 UI 交互与结构化 HTTP 调用（`/api/llm/config`、`/api/project/{id}/chat`），
 * 不在前端解析自然语言或改写业务规则。
 */

import { Component, Injectable, signal, computed, effect } from "/layout-view/layout_angular.js";

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

const MODEL_SUGGESTIONS = {
  codex_cli: ["gpt-6.1-sol", "gpt-6-astra", "gpt-6-sol", "gpt-5.6-sol"],
  agy_cli: [
    "gemini-3.8-flash-high",
    "gemini-3.8-flash-medium",
    "gemini-3.8-flash-low",
    "gemini-4-argon-high",
    "gemini-4-argon-medium",
    "gemini-4-argon-low",
  ],
  openai_compatible: ["gpt-oss-120b", "qwen3-coder", "deepseek-r1"],
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
      paramLabel: "思考深度",
      hint: "家具项目独立 Codex 登录 · 不使用 Codex App 的登录文件和配置",
      defaultEffort: "high",
      options: [
        { value: "minimal", shortLabel: "思考 · 极简", fullLabel: "minimal · 极简" },
        { value: "low", shortLabel: "思考 · 低", fullLabel: "low · 快速" },
        { value: "medium", shortLabel: "思考 · 中", fullLabel: "medium · 标准" },
        { value: "high", shortLabel: "思考 · 高", fullLabel: "high · 深度（推荐）" },
        { value: "xhigh", shortLabel: "思考 · 极高", fullLabel: "xhigh · 极限" },
      ],
    };
  }

  // 2. Google Antigravity / Gemini CLI (agy_cli)
  if (p === "agy_cli") {
    return {
      paramLabel: "Thinking Level",
      hint: "本机 AGY OAuth 免密直连 · 切换档位自动联动 Gemini 模型后缀 (-low / -medium / -high)",
      defaultEffort: "high",
      options: [
        { value: "low", shortLabel: "Thinking · Low", fullLabel: "Low · 极速 (-low)" },
        { value: "medium", shortLabel: "Thinking · Med", fullLabel: "Medium · 均衡 (-medium)" },
        { value: "high", shortLabel: "Thinking · High", fullLabel: "High · 深度 (-high)" },
        { value: "xhigh", shortLabel: "Thinking · xhigh", fullLabel: "xhigh · 扩展推理" },
        { value: "max", shortLabel: "Thinking · max", fullLabel: "max · 最大预算" },
      ],
    };
  }

  // 3. 通用 OpenAI 兼容本地/远端接口
  if (m.includes("gemini")) {
    return {
      paramLabel: "Thinking",
      hint: "通用 OpenAI 兼容接口 · Gemini 思考预算映射",
      defaultEffort: "high",
      options: [
        { value: "none", shortLabel: "思考 · 关", fullLabel: "none · 关闭" },
        { value: "low", shortLabel: "思考 · 低", fullLabel: "low · 轻量" },
        { value: "medium", shortLabel: "思考 · 中", fullLabel: "medium · 标准" },
        { value: "high", shortLabel: "思考 · 高", fullLabel: "high · 深度" },
      ],
    };
  }

  return {
    paramLabel: "思考深度",
    hint: "标准 /v1/chat/completions 接口 · 本机 127.0.0.1 免填 API Key",
    defaultEffort: /^(o1|o3|o4|gpt-5|gpt-6)/.test(m) ? "high" : "none",
    options: [
      { value: "none", shortLabel: "思考 · 默认", fullLabel: "none · 默认（不传）" },
      { value: "minimal", shortLabel: "思考 · 极简", fullLabel: "minimal · 极简" },
      { value: "low", shortLabel: "思考 · 低", fullLabel: "low · 快速" },
      { value: "medium", shortLabel: "思考 · 中", fullLabel: "medium · 标准" },
      { value: "high", shortLabel: "思考 · 高", fullLabel: "high · 深度" },
      { value: "xhigh", shortLabel: "思考 · 极高", fullLabel: "xhigh · 极限" },
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

function populateModelDatalist(datalistEl, provider) {
  if (!datalistEl) return;
  const list = MODEL_SUGGESTIONS[provider] || [];
  datalistEl.innerHTML = list.map((m) => `<option value="${m}"></option>`).join("");
}

function formatStageBadge(project) {
  if (!project || typeof project !== "object") return "未加载";
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
    return `${label}已确认 → ${nextLabel}`;
  }
  return isApproved ? `${label} · 已确认` : `${label} · 待确认`;
}

export const LayoutChatService = Injectable({ providedIn: "root" })(
  class LayoutChatService {
    constructor() {
      this.sending = signal(false);
      this.activeTurn = signal(null);
      this.elapsedSec = signal(0);
      this.llm = signal(null);
      this.project = signal(null);
      this.messages = signal([]);
      this.modalOpen = signal(false);
      this.modalNotice = signal("");
      this.stageBadgeText = computed(() => formatStageBadge(this.project()));
    }
  }
);

export const LayoutChatComponent = Component({
  selector: "#chat-panel",
  standalone: true,
})(
  class LayoutChatComponent {
    constructor({ chatUrl, llmConfigUrl, onProjectUpdated, onStatusToast }) {
      this.chatUrl = chatUrl;
      this.llmConfigUrl = llmConfigUrl;
      this.onProjectUpdated = onProjectUpdated;
      this.onStatusToast = onStatusToast;
      this.service = new LayoutChatService();
    }

    mount() {
      const panel = document.getElementById("chat-panel");
      const toggleBtn = document.getElementById("toggle-chat");
      if (!panel || !this.chatUrl || !this.llmConfigUrl) return null;

      document.body.classList.add("has-chat");
      panel.hidden = false;
      if (toggleBtn) {
        toggleBtn.hidden = false;
        toggleBtn.setAttribute("aria-pressed", "true");
      }
      window.dispatchEvent(new Event("resize"));

      const stagePill = document.getElementById("chat-stage-pill");
      const messagesEl = document.getElementById("chat-messages");
      const formEl = document.getElementById("chat-form");
      const inputEl = document.getElementById("chat-input");
      const sendBtn = document.getElementById("chat-send-btn");
      const clearBtn = document.getElementById("chat-clear-btn");
      const effortSelect = document.getElementById("chat-effort-select");
      const settingsBtn = document.getElementById("chat-settings-btn");
      const settingsDot = document.getElementById("chat-settings-dot");
      const modelLabelEl = document.getElementById("chat-model-label");
      const quickBar = document.getElementById("chat-quick-bar");

      const modal = document.getElementById("llm-modal");
      const modalForm = document.getElementById("llm-config-form");
      const providerSelect = document.getElementById("llm-provider");
      const baseUrlField = document.getElementById("llm-base-url-field");
      const baseUrlInput = document.getElementById("llm-base-url");
      const modelInput = document.getElementById("llm-model");
      const modelDatalist = document.getElementById("llm-model-datalist");
      const modalEffortLabel = document.getElementById("llm-effort-label");
      const modalEffortSelect = document.getElementById("llm-effort");
      const modelHint = document.getElementById("llm-model-hint");
      const apiKeyField = document.getElementById("llm-api-key-field");
      const apiKeyInput = document.getElementById("llm-api-key");
      const modalCloseBtn = document.getElementById("llm-modal-close");
      const modalStatus = document.getElementById("llm-modal-status");
      const codexAuthBox = document.getElementById("llm-codex-auth");
      const codexAuthStatus = document.getElementById("llm-codex-auth-status");
      const codexLoginBtn = document.getElementById("llm-codex-login");
      const codexLoginLink = document.getElementById("llm-codex-login-link");
      const codexAuthUrl = "/api/llm/codex/status";
      const codexLoginUrl = "/api/llm/codex/login";
      let authPollTimer = null;
      let authPollInFlight = false;
      let codexAuthenticated = false;

      const svc = this.service;
      const { chatUrl, llmConfigUrl, onProjectUpdated, onStatusToast } = this;

      function syncTabButtons(provider) {
        if (!modal) return;
        const activeKey =
          provider === "codex_cli"
            ? "codex_cli"
            : provider === "agy_cli"
              ? "agy_cli"
              : "local_openai";
        modal.querySelectorAll("button[data-llm-preset]").forEach((btn) => {
          btn.classList.toggle("active", btn.getAttribute("data-llm-preset") === activeKey);
        });
      }

      function syncModalProviderFields(preferredEffort) {
        if (!providerSelect) return;
        const provider = providerSelect.value;
        const model = modelInput ? modelInput.value.trim() : "";
        const isCli = provider === "codex_cli" || provider === "agy_cli";
        syncTabButtons(provider);
        populateModelDatalist(modelDatalist, provider);

        if (baseUrlField) baseUrlField.hidden = isCli;
        if (baseUrlInput) baseUrlInput.required = !isCli;
        if (apiKeyField) apiKeyField.hidden = isCli;
        if (codexAuthBox) codexAuthBox.hidden = provider !== "codex_cli";

        const profile = getEffortProfile(provider, model);
        if (modalEffortLabel) {
          modalEffortLabel.textContent = profile.paramLabel;
        }
        if (modelHint) {
          modelHint.textContent = profile.hint;
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

      function extractThinkingSteps(msg) {
        if (!msg || typeof msg !== "object") return [];
        if (Array.isArray(msg.thinking_steps) && msg.thinking_steps.length > 0) {
          return msg.thinking_steps
            .map((s) => String(s || "").trim())
            .filter(Boolean);
        }
        if (typeof msg.thinking === "string" && msg.thinking.trim()) {
          return [msg.thinking.trim()];
        }
        return [];
      }

      function createToolTraceNode(traceList) {
        const wrap = document.createElement("div");
        wrap.className = "chat-tool-trace";
        for (const item of traceList) {
          const chip = document.createElement("div");
          chip.className = "chat-tool-chip " + (item.ok ? "ok" : "err");
          const head = document.createElement("div");
          head.className = "chat-tool-chip-head";
          const mark = item.ok ? "✓" : "⚠";
          const suffix = item.progressed ? " · 已更新" : "";
          const errText =
            !item.ok && item.error && item.error.message
              ? ` (${item.error.message})`
              : "";
          head.textContent = `${mark} 工具调用: ${item.tool}${suffix}${errText}`;
          chip.appendChild(head);

          if (item.arguments && typeof item.arguments === "object" && Object.keys(item.arguments).length > 0) {
            const argsEl = document.createElement("div");
            argsEl.className = "chat-tool-chip-args";
            argsEl.textContent = JSON.stringify(item.arguments);
            chip.appendChild(argsEl);
          }
          wrap.appendChild(chip);
        }
        return wrap;
      }

      function createThinkingNode(msg, defaultOpen) {
        const steps = extractThinkingSteps(msg);
        const tools = Array.isArray(msg.tool_trace) ? msg.tool_trace : [];
        if (steps.length === 0 && tools.length === 0) return null;

        const details = document.createElement("details");
        details.className = "chat-thinking";
        if (defaultOpen) details.open = true;

        const summary = document.createElement("summary");
        summary.className = "chat-thinking-summary";

        const titleWrap = document.createElement("span");
        titleWrap.className = "chat-thinking-title";
        const chevron = document.createElement("span");
        chevron.className = "chat-thinking-chevron";
        chevron.textContent = "▸";
        const titleText = document.createElement("span");
        titleText.textContent = "💭 思考过程";
        titleWrap.appendChild(chevron);
        titleWrap.appendChild(titleText);

        const meta = document.createElement("span");
        meta.className = "chat-thinking-meta";
        const metaParts = [];
        if (steps.length > 0) metaParts.push(`${steps.length} 步推理`);
        if (tools.length > 0) metaParts.push(`${tools.length} 个工具`);
        meta.textContent = metaParts.join(" · ");

        summary.appendChild(titleWrap);
        summary.appendChild(meta);
        details.appendChild(summary);

        const body = document.createElement("div");
        body.className = "chat-thinking-body";

        steps.forEach((stepText, idx) => {
          const stepEl = document.createElement("div");
          stepEl.className = "chat-thinking-step";
          if (steps.length > 1) {
            const label = document.createElement("span");
            label.className = "chat-thinking-step-label";
            label.textContent = `Step ${idx + 1}`;
            stepEl.appendChild(label);
          }
          const contentNode = document.createElement("span");
          contentNode.textContent = stepText;
          stepEl.appendChild(contentNode);
          body.appendChild(stepEl);
        });

        if (tools.length > 0) {
          body.appendChild(createToolTraceNode(tools));
        }

        details.appendChild(body);
        return details;
      }

      function createLiveThinkingNode(activeTurn, elapsedSec) {
        const details = document.createElement("details");
        details.className = "chat-thinking live";
        details.open = true;

        const summary = document.createElement("summary");
        summary.className = "chat-thinking-summary";

        const titleWrap = document.createElement("span");
        titleWrap.className = "chat-thinking-title";
        const pulse = document.createElement("i");
        pulse.className = "chat-thinking-pulse";
        const titleText = document.createElement("span");
        titleText.textContent = "💭 思考过程（进行中）";
        titleWrap.appendChild(pulse);
        titleWrap.appendChild(titleText);

        const meta = document.createElement("span");
        meta.className = "chat-thinking-meta";
        meta.textContent = `${Number(elapsedSec || 0).toFixed(1)}s`;

        summary.appendChild(titleWrap);
        summary.appendChild(meta);
        details.appendChild(summary);

        const body = document.createElement("div");
        body.className = "chat-thinking-body";

        const steps = activeTurn && Array.isArray(activeTurn.thinking_steps)
          ? activeTurn.thinking_steps
          : [];
        steps.forEach((stepText, idx) => {
          const stepEl = document.createElement("div");
          stepEl.className = "chat-thinking-step";
          const label = document.createElement("span");
          label.className = "chat-thinking-step-label";
          label.textContent = `Step ${idx + 1}`;
          stepEl.appendChild(label);
          const contentNode = document.createElement("span");
          contentNode.textContent = stepText;
          stepEl.appendChild(contentNode);
          body.appendChild(stepEl);
        });

        const tools = activeTurn && Array.isArray(activeTurn.tool_trace)
          ? activeTurn.tool_trace
          : [];
        if (tools.length > 0) {
          body.appendChild(createToolTraceNode(tools));
        }

        const statusRow = document.createElement("div");
        statusRow.className = "chat-thinking-status";
        statusRow.textContent =
          (activeTurn && activeTurn.status) || "正在读取项目快照与思考方案…";
        body.appendChild(statusRow);

        details.appendChild(body);
        return details;
      }

      // Angular Reactive Effect: 阶段标签同步
      effect(() => {
        const text = svc.stageBadgeText();
        if (stagePill && svc.project()) {
          stagePill.textContent = text;
        }
      });

      // Angular Reactive Effect: 模型连接状态栏与思考深度选择器同步
      effect(() => {
        const llm = svc.llm();
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
          effortSelect.title = `${profile.paramLabel}: ${activeEffort}`;
        }

        const configured = Boolean(llm && llm.configured);
        if (modelLabelEl) {
          modelLabelEl.textContent = configured ? model : "点击配置模型…";
        }
        if (!settingsDot || !settingsBtn) return;
        settingsDot.classList.toggle("ok", configured);
        settingsDot.classList.toggle("warn", !configured);
        if (configured) {
          const modeName =
            llm.provider === "codex_cli"
              ? "ChatGPT 订阅"
              : llm.provider === "agy_cli"
                ? "Gemini 订阅"
                : llm.base_url;
          settingsBtn.title = `${modeName} · ${llm.model} (${activeEffort})`;
        } else {
          settingsBtn.title = "点击选择 ChatGPT / Gemini 订阅或通用 OpenAI 模型";
        }
      });

      // Angular Reactive Effect: 消息列表与实时思考轨迹同步
      effect(() => {
        const msgs = svc.messages();
        const isSending = svc.sending();
        const activeTurn = svc.activeTurn();
        const elapsedSec = svc.elapsedSec();
        const llm = svc.llm();
        if (sendBtn) sendBtn.disabled = isSending;
        if (!messagesEl) return;
        messagesEl.innerHTML = "";
        if (!msgs || msgs.length === 0) {
          const empty = document.createElement("div");
          empty.className = "chat-empty";
          const configured = Boolean(llm && llm.configured);
          const heading = document.createElement("strong");
          heading.textContent = configured ? `已就绪 · ${llm.model}` : "未连接模型";
          empty.appendChild(heading);
          empty.appendChild(document.createElement("br"));
          empty.appendChild(document.createTextNode(configured
            ? "输入需求以修改家具尺寸、确认布局或生成板件。"
            : "点击上方模型栏配置模型；首次使用 Codex 需单独登录。"));
          messagesEl.appendChild(empty);
          return;
        }

        let lastAssistantIdx = -1;
        msgs.forEach((m, idx) => {
          if (m.role !== "user") lastAssistantIdx = idx;
        });

        msgs.forEach((msg, idx) => {
          const item = document.createElement("div");
          const role = msg.role === "user" ? "user" : "assistant";
          item.className = `chat-msg ${role}`;

          if (role === "assistant") {
            const thinkingNode = createThinkingNode(
              msg,
              idx === lastAssistantIdx && !isSending,
            );
            if (thinkingNode) {
              item.appendChild(thinkingNode);
            }
          }

          const bubble = document.createElement("div");
          bubble.className = "chat-bubble";
          bubble.textContent = msg.content || "";
          item.appendChild(bubble);
          messagesEl.appendChild(item);
        });

        if (isSending) {
          const thinkingWrap = document.createElement("div");
          thinkingWrap.className = "chat-msg assistant thinking";
          thinkingWrap.appendChild(createLiveThinkingNode(activeTurn, elapsedSec));
          messagesEl.appendChild(thinkingWrap);
        }

        messagesEl.scrollTop = messagesEl.scrollHeight;
      });

      async function loadInitialChat() {
        try {
          const resp = await fetch(chatUrl, { cache: "no-store" });
          if (!resp.ok) return;
          const data = await resp.json();
          svc.llm.set(data.llm || null);
          if (data.project) svc.project.set(data.project);
          svc.messages.set(Array.isArray(data.messages) ? data.messages : []);
          if (data.active_turn) svc.activeTurn.set(data.active_turn);
        } catch (err) {}
      }

      async function sendMessage(text) {
        const trimmed = String(text || "").trim();
        if (!trimmed || svc.sending()) return;
        const llm = svc.llm();
        if (!llm || !llm.configured) {
          openSettingsModal("请先选择模型");
          return;
        }

        const startMs = Date.now();
        svc.elapsedSec.set(0);
        svc.activeTurn.set({
          status: "正在读取项目快照与思考方案…",
          thinking_steps: [],
          tool_trace: [],
        });
        svc.sending.set(true);

        const optimisticUser = {
          id: "temp_user",
          role: "user",
          content: trimmed,
        };
        svc.messages.update((prev) => [...prev, optimisticUser]);
        if (inputEl) inputEl.value = "";

        const tickTimer = window.setInterval(() => {
          svc.elapsedSec.set((Date.now() - startMs) / 1000);
        }, 200);

        const pollTimer = window.setInterval(async () => {
          if (!svc.sending()) return;
          try {
            const r = await fetch(chatUrl, { cache: "no-store" });
            if (!r.ok) return;
            const d = await r.json();
            if (d && d.active_turn && svc.sending()) {
              svc.activeTurn.set(d.active_turn);
            }
          } catch (e) {}
        }, 900);

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
            svc.messages.update((prev) => [
              ...prev,
              {
                id: "temp_err",
                role: "assistant",
                content: `⚠️ ${errMsg}`,
              },
            ]);
            if (detail && detail.code && detail.code.startsWith("LLM_NOT_CONFIGURED")) {
              openSettingsModal(errMsg);
            }
            return;
          }

          if (Array.isArray(payload.messages)) {
            svc.messages.set(payload.messages);
          }
          if (payload.project) {
            svc.project.set(payload.project);
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
          svc.messages.update((prev) => [
            ...prev,
            {
              id: "temp_err",
              role: "assistant",
              content: `⚠️ 请求异常：${err}`,
            },
          ]);
        } finally {
          window.clearInterval(tickTimer);
          window.clearInterval(pollTimer);
          svc.activeTurn.set(null);
          svc.sending.set(false);
        }
      }

      function openSettingsModal(noticeText = "") {
        if (!modal) return;
        const llm = svc.llm() || {};
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
            : "本机地址免填；远端接口填 API Key";
        }
        syncModalProviderFields(llm.reasoning_effort || "high");
        if (modalStatus) {
          modalStatus.textContent = noticeText || "";
        }
        svc.modalOpen.set(true);
        modal.hidden = false;
        if (providerSelect && providerSelect.value === "codex_cli") {
          refreshCodexAuth();
        }
      }

      function closeSettingsModal() {
        if (authPollTimer) window.clearInterval(authPollTimer);
        authPollTimer = null;
        if (codexLoginLink) {
          codexLoginLink.hidden = true;
          codexLoginLink.removeAttribute("href");
        }
        svc.modalOpen.set(false);
        if (modal) modal.hidden = true;
      }

      async function refreshCodexAuth() {
        if (authPollInFlight) return;
        authPollInFlight = true;
        try {
          const resp = await fetch(codexAuthUrl, { cache: "no-store" });
          if (!resp.ok) throw new Error("无法检查独立登录状态");
          const state = await resp.json();
          codexAuthenticated = Boolean(state.authenticated);
          const labels = {
            authenticated: "已登录 · 使用家具项目的独立凭据",
            awaiting_login: "等待你在登录页面完成授权…",
            needs_login: "尚未登录家具项目的 Codex",
            unavailable: "本机未找到 Codex 程序",
            error: "无法检查登录状态，请检查运行目录和网络",
          };
          if (codexAuthStatus) codexAuthStatus.textContent = labels[state.status] || "正在检查…";
          if (codexLoginBtn) {
            codexLoginBtn.disabled = state.authenticated || state.status === "unavailable";
            codexLoginBtn.textContent = state.authenticated ? "已登录" : state.status === "awaiting_login" ? "重新打开登录页面" : "单独登录 Codex";
          }
          if (state.authenticated) {
            if (authPollTimer) window.clearInterval(authPollTimer);
            authPollTimer = null;
            if (codexLoginLink) {
              codexLoginLink.hidden = true;
              codexLoginLink.removeAttribute("href");
            }
            const configResp = await fetch(llmConfigUrl, { cache: "no-store" });
            if (configResp.ok) svc.llm.set(await configResp.json());
          } else if (state.status === "awaiting_login" && modal && !modal.hidden && !authPollTimer) {
            authPollTimer = window.setInterval(refreshCodexAuth, 2000);
          }
        } catch (err) {
          if (codexAuthStatus) codexAuthStatus.textContent = "无法检查独立登录状态，请稍后重试";
        } finally {
          authPollInFlight = false;
        }
      }

      if (codexLoginBtn) {
        codexLoginBtn.addEventListener("click", async () => {
          codexLoginBtn.disabled = true;
          if (codexAuthStatus) codexAuthStatus.textContent = "正在启动独立登录…";
          try {
            const resp = await fetch(codexLoginUrl, { method: "POST", cache: "no-store" });
            const data = await resp.json();
            if (!resp.ok) throw new Error(data.detail && data.detail.message || "无法启动登录");
            if (data.auth_url) {
              const url = new URL(data.auth_url);
              if (url.protocol !== "https:" || !["auth.openai.com", "chatgpt.com"].includes(url.hostname) || url.username || url.password) {
                throw new Error("登录地址无效");
              }
              // OAuth URL stays only in the current DOM; no browser storage or logs.
              if (codexLoginLink) {
                codexLoginLink.href = url.href;
                codexLoginLink.hidden = false;
                codexLoginLink.click();
              }
            }
            await refreshCodexAuth();
            if (!data.authenticated && !authPollTimer) {
              authPollTimer = window.setInterval(refreshCodexAuth, 2000);
            }
          } catch (err) {
            if (codexAuthStatus) codexAuthStatus.textContent = err.message || "无法启动独立登录";
          } finally {
            codexLoginBtn.disabled = codexAuthenticated;
          }
        });
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
          const llm = svc.llm() || {};
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
              svc.llm.set(data);
              if (typeof onStatusToast === "function") {
                onStatusToast(`已切换：${data.model} (${data.reasoning_effort})`);
              }
            }
          } catch (err) {}
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
            if (preset.provider === "codex_cli") refreshCodexAuth();
          });
        });
      }

      if (modalForm) {
        modalForm.addEventListener("submit", async (e) => {
          e.preventDefault();
          if (modalStatus) modalStatus.textContent = "保存中…";
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
            svc.llm.set(data);
            closeSettingsModal();
            if (typeof onStatusToast === "function") {
              onStatusToast(`已切换模型：${data.model} (${data.reasoning_effort})`);
            }
          } catch (err) {
            if (modalStatus) modalStatus.textContent = `保存出错：${err}`;
          }
        });
      }

      if (clearBtn) {
        clearBtn.addEventListener("click", async () => {
          if (svc.sending()) return;
          try {
            await fetch(chatUrl, { method: "DELETE", cache: "no-store" });
            svc.messages.set([]);
          } catch (err) {}
        });
      }

      if (quickBar) {
        quickBar.addEventListener("click", (e) => {
          const btn = e.target && e.target.closest ? e.target.closest("button[data-prompt]") : null;
          if (!btn || svc.sending()) return;
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
        service: svc,
      };
    }
  }
);

export function mountProjectChat(options) {
  const comp = new LayoutChatComponent(options);
  return comp.mount();
}
