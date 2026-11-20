(() => {
  "use strict";

  const csrfToken = document.querySelector('meta[name="seed-csrf-token"]').content;
  const sessionStorageKey = "seed.desktop.session";
  const sessionId = sessionStorage.getItem(sessionStorageKey) || crypto.randomUUID();
  sessionStorage.setItem(sessionStorageKey, sessionId);
  let latestEventId = 0;
  let requestPending = false;
  let currentView = "assistant";

  // Voice Engine
  const voice = {
    speaking: false,
    listening: false,
    recognition: null,
    voices: [],
    currentLang: 'en-US',
    
    async init() {
      this.voices = await new Promise(resolve => {
        const v = speechSynthesis.getVoices();
        if (v.length) resolve(v);
        speechSynthesis.onvoiceschanged = () => resolve(speechSynthesis.getVoices());
      });
      
      window.seedEventBus = {
        callbacks: {},
        publish(event, data) {
          (this.callbacks[event] || []).forEach(cb => cb(data));
        },
        subscribe(event, callback) {
          this.callbacks[event] = this.callbacks[event] || [];
          this.callbacks[event].push(callback);
        }
      };
      
      window.seedEventBus.subscribe('voice:speaking', ({ state }) => {
        this.speaking = state;
        this.updateVoiceUI();
      });

      const langToggle = document.getElementById('lang-toggle-btn');
      if (langToggle) {
        langToggle.addEventListener('click', () => this.toggleLanguage());
      }
    },

    toggleLanguage() {
      this.currentLang = this.currentLang === 'en-US' ? 'ar-SA' : 'en-US';
      const badge = document.getElementById('lang-badge');
      if (badge) badge.textContent = this.currentLang === 'ar-SA' ? 'AR' : 'EN';
      if (this.recognition) {
        this.recognition.lang = this.currentLang;
      }
    },
    
    speak(text) {
      if (!text) return;
      speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1.0;
      utterance.pitch = 1.0;
      utterance.lang = this.currentLang;
      
      const v = this.voices.find(item => item.lang.startsWith(this.currentLang.slice(0,2))) 
             || this.voices[0];
      if (v) utterance.voice = v;
      
      utterance.onstart = () => { this.speaking = true; this.updateVoiceUI(); };
      utterance.onend = () => { this.speaking = false; this.updateVoiceUI(); };
      utterance.onerror = () => { this.speaking = false; this.updateVoiceUI(); };
      
      speechSynthesis.speak(utterance);
    },
    
    startListening() {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SpeechRecognition) {
        alert('Speech recognition not supported in this browser');
        return;
      }
      
      this.recognition = new SpeechRecognition();
      this.recognition.continuous = false;
      this.recognition.interimResults = true;
      this.recognition.lang = this.currentLang;
      
      this.recognition.onstart = () => { 
        this.listening = true; 
        this.updateVoiceUI();
      };
      
      this.recognition.onresult = (event) => {
        const result = event.results[event.results.length - 1];
        if (result.isFinal) {
          const transcript = result[0].transcript;
          elements.input.value = transcript;
          this.listening = false;
          this.updateVoiceUI();
          elements.form.requestSubmit();
        }
      };
      
      this.recognition.onerror = () => { 
        this.listening = false; 
        this.updateVoiceUI(); 
      };
      
      this.recognition.onend = () => { 
        this.listening = false; 
        this.updateVoiceUI(); 
      };
      
      this.recognition.start();
    },
    
    stopListening() {
      if (this.recognition) {
        this.recognition.stop();
        this.recognition = null;
      }
      this.listening = false;
      this.updateVoiceUI();
    },
    
    updateVoiceUI() {
      const micBtn = document.getElementById('voice-listen-btn');
      const voiceIndicator = document.querySelector('.privacy-dot');
      const voiceLabel = document.querySelector('.privacy-indicator span:last-child');
      
      if (micBtn) {
        micBtn.classList.toggle('listening', this.listening);
      }
      
      if (voiceIndicator && voiceLabel) {
        voiceIndicator.style.background = this.listening ? '#ef4444' : '#22c55e';
        voiceLabel.textContent = this.listening ? 'Listening (' + this.currentLang + ')...' : (this.speaking ? 'Speaking...' : 'Microphone ready');
      }
    },
    
    stop() {
      speechSynthesis.cancel();
      this.stopListening();
      this.speaking = false;
      this.updateVoiceUI();
    }
  };

  window.SeedVoice = voice;
  voice.init();

  const elements = {
    orb: document.getElementById("smart-orb"),
    state: document.getElementById("assistant-state"),
    stateLabel: document.getElementById("orb-state-label"),
    orbCaption: document.getElementById("orb-caption-state"),
    feed: document.getElementById("conversation-feed"),
    emptyFeed: document.getElementById("empty-conversation"),
    form: document.getElementById("request-form"),
    input: document.getElementById("request-input"),
    send: document.getElementById("send-button"),
    voiceBtn: document.getElementById("voice-mic-btn"),
    providerName: document.getElementById("provider-name"),
    providerStatus: document.getElementById("provider-status"),
    providerDetail: document.getElementById("provider-detail"),
    serviceList: document.getElementById("service-list"),
    serviceCount: document.getElementById("service-count"),
    approvalList: document.getElementById("approval-list"),
    approvalCount: document.getElementById("approval-count"),
    connectionDot: document.getElementById("connection-dot"),
    connectionLabel: document.getElementById("connection-label"),
    eventConnection: document.getElementById("event-connection"),
    sessionShortId: document.getElementById("session-short-id"),
    navTaskCount: document.getElementById("nav-task-count"),
    taskSummary: document.getElementById("task-summary"),
    taskTable: document.getElementById("task-table"),
    auditList: document.getElementById("audit-list"),
    settingsProvider: document.getElementById("settings-provider"),
    settingsProviders: document.getElementById("settings-providers"),
  };

  elements.sessionShortId.textContent = sessionId.slice(0, 8).toUpperCase();

  function setOrbState(state, label) {
    elements.orb.dataset.state = state;
    elements.orb.setAttribute("aria-label", "Smart Orb " + state.replaceAll("_", " "));
    elements.state.dataset.state = state;
    elements.stateLabel.textContent = state.replaceAll("_", " ").toUpperCase();
    elements.orbCaption.textContent = label;
  }

  const modeOrbBtn = document.getElementById("mode-orb-btn");
  const modeAvatarBtn = document.getElementById("mode-avatar-btn");
  const avatarContainer = document.getElementById("avatar-container");
  const smartOrb = document.getElementById("smart-orb");

  if (modeOrbBtn && modeAvatarBtn && avatarContainer && smartOrb) {
    modeOrbBtn.addEventListener("click", () => {
      modeOrbBtn.classList.add("active");
      modeAvatarBtn.classList.remove("active");
      smartOrb.hidden = false;
      avatarContainer.hidden = true;
    });
    modeAvatarBtn.addEventListener("click", () => {
      modeAvatarBtn.classList.add("active");
      modeOrbBtn.classList.remove("active");
      smartOrb.hidden = true;
      avatarContainer.hidden = false;
    });
  }

  function appendMessage(role, text) {
    if (elements.emptyFeed.isConnected) elements.emptyFeed.remove();
    const bubble = document.createElement("div");
    bubble.className = "message " + role;
    bubble.setAttribute("dir", "auto");
    const meta = document.createElement("span");
    meta.className = "message-meta";
    meta.textContent = role === "user" ? "YOU" : "SEED";
    const body = document.createElement("span");
    body.textContent = String(text || "");
    bubble.append(meta, body);
    elements.feed.appendChild(bubble);
    elements.feed.scrollTop = elements.feed.scrollHeight;
  }

  function appendToolSummary(results) {
    for (const item of results || []) {
      const summary = document.createElement("div");
      summary.className = "tool-summary";
      const nested = item && item.result;
      let text = "SEED tool · " + String(item && item.status || "unknown");
      if (nested && nested.status === "success" && Array.isArray(nested.entries)) {
        text += " · " + nested.entries.length + " workspace entries";
      }
      summary.textContent = text;
      elements.feed.appendChild(summary);
    }
    elements.feed.scrollTop = elements.feed.scrollHeight;
  }

  async function api(path, options = {}) {
    const headers = new Headers(options.headers || {});
    if (options.method === "POST") {
      headers.set("Content-Type", "application/json");
      headers.set("X-SEED-CSRF", csrfToken);
    }
    const response = await fetch(path, { ...options, headers, credentials: "same-origin" });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.error || ("Request failed: " + response.status));
    return result;
  }

  async function loadSession() {
    try {
      const result = await api("/api/sessions/" + encodeURIComponent(sessionId));
      for (const message of result.messages || []) appendMessage(message.role, message.content);
    } catch (_error) {
      setOrbState("error", "Session history unavailable");
    }
  }

  function statusTag(status) {
    const tag = document.createElement("span");
    tag.className = "status-tag " + String(status || "unknown");
    tag.textContent = String(status || "unknown").replaceAll("_", " ");
    return tag;
  }

  async function loadTasks() {
    const result = await api("/api/history?limit=100");
    const tasks = result.tasks || [];
    elements.navTaskCount.textContent = String(tasks.filter((task) => ["pending", "running", "approval_required"].includes(task.status)).length);
    const counts = { pending: 0, running: 0, completed: 0, failed: 0, approval_required: 0 };
    for (const task of tasks) if (Object.hasOwn(counts, task.status)) counts[task.status] += 1;
    elements.taskSummary.replaceChildren();
    for (const [label, value] of Object.entries(counts)) {
      const block = document.createElement("div");
      block.className = "summary-item";
      const title = document.createElement("span");
      title.textContent = label.replaceAll("_", " ");
      const count = document.createElement("strong");
      count.textContent = String(value);
      block.append(title, count);
      elements.taskSummary.appendChild(block);
    }
    elements.taskTable.replaceChildren();
    if (!tasks.length) {
      const row = document.createElement("tr");
      const cell = document.createElement("td");
      cell.colSpan = 4;
      cell.className = "list-placeholder";
      cell.textContent = "No tasks have been recorded.";
      row.appendChild(cell);
      elements.taskTable.appendChild(row);
      return;
    }
    for (const task of tasks) {
      const row = document.createElement("tr");
      const requestCell = document.createElement("td");
      requestCell.textContent = task.command;
      const statusCell = document.createElement("td");
      statusCell.appendChild(statusTag(task.status));
      const projectCell = document.createElement("td");
      projectCell.textContent = task.project_ids || "Local";
      const createdCell = document.createElement("td");
      createdCell.textContent = task.created_at;
      row.append(requestCell, statusCell, projectCell, createdCell);
      elements.taskTable.appendChild(row);
    }
  }

  async function loadApprovals() {
    const result = await api("/api/approvals");
    const approvals = result.approvals || [];
    elements.approvalCount.textContent = String(approvals.length);
    elements.approvalList.replaceChildren();
    if (!approvals.length) {
      const empty = document.createElement("p");
      empty.className = "list-placeholder";
      empty.textContent = "No approval requests.";
      elements.approvalList.appendChild(empty);
      return;
    }
    for (const approval of approvals) {
      const item = document.createElement("div");
      item.className = "approval-item";
      const title = document.createElement("strong");
      title.textContent = approval.tool + " · " + approval.action;
      const metadata = document.createElement("small");
      metadata.textContent = approval.scope + " scope · expires " + approval.expires_at;
      item.append(title, metadata);
      elements.approvalList.appendChild(item);
    }
  }

  async function loadAudit() {
    const result = await api("/api/audit?limit=100");
    const events = result.events || [];
    elements.auditList.replaceChildren();
    if (!events.length) {
      const empty = document.createElement("p");
      empty.className = "list-placeholder";
      empty.style.padding = "18px";
      empty.textContent = "No audit events have been recorded.";
      elements.auditList.appendChild(empty);
      return;
    }
    for (const event of events.slice().reverse()) {
      const row = document.createElement("div");
      row.className = "event-row";
      const name = document.createElement("span");
      name.className = "event-name";
      name.textContent = event.event_type.replaceAll("_", " ");
      const task = document.createElement("span");
      task.className = "event-task";
      task.textContent = event.task_id ? "Task #" + event.task_id : "System event";
      const time = document.createElement("span");
      time.className = "event-time";
      time.textContent = event.created_at;
      row.append(name, task, time);
      elements.auditList.appendChild(row);
      latestEventId = Math.max(latestEventId, Number(event.id) || 0);
    }
  }

  async function loadMemory() {
    const result = await api("/api/memory");
    const items = result.memory_items || [];
    const table = document.getElementById("memory-table");
    if (!table) return;
    table.replaceChildren();
    if (!items.length) {
      const row = document.createElement("tr");
      const cell = document.createElement("td");
      cell.colSpan = 5;
      cell.className = "list-placeholder";
      cell.textContent = "No memory items have been recorded.";
      row.appendChild(cell);
      table.appendChild(row);
      return;
    }
    for (const item of items) {
      const row = document.createElement("tr");
      const typeCell = document.createElement("td");
      typeCell.textContent = item.memory_type;
      const keyCell = document.createElement("td");
      keyCell.textContent = item.memory_key;
      const contentCell = document.createElement("td");
      contentCell.textContent = item.content;
      const projectCell = document.createElement("td");
      projectCell.textContent = item.project_id || "Local";
      const updatedCell = document.createElement("td");
      updatedCell.textContent = item.updated_at;
      row.append(typeCell, keyCell, contentCell, projectCell, updatedCell);
      table.appendChild(row);
    }
  }

  async function loadStatus() {
    try {
      const status = await api("/api/status");
      latestEventId = Math.max(latestEventId, Number(status.event_cursor) || 0);
      elements.connectionDot.classList.add("online");
      elements.connectionLabel.textContent = "SEED local service online";
      const registry = status.provider_registry || {};
      elements.providerName.textContent = registry.default || "No default provider";
      elements.providerDetail.textContent = (registry.registered || []).join(" · ") || "No providers registered";
      const health = status.providers || {};
      const defaultHealth = health[registry.default];
      elements.providerStatus.textContent = defaultHealth ? (defaultHealth.healthy ? "Healthy" : "Unavailable") : "Not checked";
      elements.providerStatus.style.color = defaultHealth ? (defaultHealth.healthy ? "var(--mint)" : "var(--amber)") : "";
      elements.serviceList.replaceChildren();
      const services = Object.entries(status.services || {});
      elements.serviceCount.textContent = String(services.length);
      for (const [name, service] of services) {
        const row = document.createElement("li");
        row.className = "service-row";
        const label = document.createElement("span");
        const dot = document.createElement("i");
        dot.className = "service-dot" + (service.status === "healthy" ? " healthy" : "");
        label.append(dot, document.createTextNode(name));
        const state = document.createElement("span");
        state.textContent = service.status;
        row.append(label, state);
        elements.serviceList.appendChild(row);
      }
      elements.settingsProvider.textContent = registry.default || "None";
      elements.settingsProviders.textContent = (registry.registered || []).join(", ") || "None";
      await Promise.all([loadTasks(), loadApprovals()]);
    } catch (_error) {
      elements.connectionDot.classList.remove("online");
      elements.connectionLabel.textContent = "SEED service unavailable";
      setOrbState("error", "Local service unavailable");
    }
  }

  async function approveAndResume(approval, originalRequest) {
    if (!window.confirm("Approve " + approval.tool + " for this exact request? SEED will re-evaluate and resume through its permission engine.")) return;
    const button = document.querySelector('[data-approval-id="' + CSS.escape(approval.approval_id) + '"]');
    if (button) button.disabled = true;
    setOrbState("processing", "Resuming approved request");
    try {
      const result = await api("/api/approvals/approve", {
        method: "POST",
        body: JSON.stringify({
          approval_id: approval.approval_id,
          request: originalRequest,
          session_id: sessionId,
        }),
      });
      appendToolSummary(result.tool_results);
      appendMessage("assistant", result.response || "SEED completed the request.");
      renderApprovalCards(result.pending_approvals, originalRequest);
      setOrbState(result.status === "completed" ? "responding" : result.status === "approval_required" ? "awaiting_approval" : "error", result.status.replaceAll("_", " "));
      await Promise.all([loadTasks(), loadApprovals(), loadAudit()]);
    } catch (error) {
      appendMessage("assistant", "Approval could not be completed: " + error.message);
      setOrbState("error", "Approval could not be completed");
    } finally {
      if (button) button.disabled = false;
    }
  }

  function renderApprovalCards(approvals, originalRequest) {
    for (const approval of approvals || []) {
      const card = document.createElement("div");
      card.className = "approval-card";
      const title = document.createElement("strong");
      title.textContent = "SEED requires approval · " + approval.tool;
      const summary = document.createElement("p");
      const safeArguments = Object.entries(approval.arguments || {}).map(([key, value]) => {
        const shown = /secret|token|password|api.?key/i.test(key) ? "[redacted]" : JSON.stringify(value);
        return key + ": " + String(shown).slice(0, 180);
      }).join(" · ");
      summary.textContent = approval.action + " in " + approval.scope + " scope. "
        + (safeArguments ? "Parameters: " + safeArguments + ". " : "")
        + "The grant is bound to this exact action and expires at " + approval.expires_at + ".";
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.approvalId = approval.approval_id;
      button.textContent = "Approve and resume through SEED";
      button.addEventListener("click", () => approveAndResume(approval, originalRequest));
      card.append(title, summary, button);
      elements.feed.appendChild(card);
    }
  }

  elements.form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (requestPending) return;
    const request = elements.input.value.trim();
    if (!request) return;
    requestPending = true;
    elements.send.disabled = true;
    appendMessage("user", request);
    elements.input.value = "";
    setOrbState("processing", "SEED is interpreting the request");
    try {
      const result = await api("/api/request", {
        method: "POST",
        body: JSON.stringify({ request, session_id: sessionId }),
      });
      appendToolSummary(result.tool_results);
      appendMessage("assistant", result.response || "SEED returned no response text.");
      if (result.pending_approvals && result.pending_approvals.length) {
        renderApprovalCards(result.pending_approvals, request);
        setOrbState("awaiting_approval", "Approval required");
      } else if (result.status === "completed") {
        setOrbState("responding", "SEED response received");
        window.setTimeout(() => setOrbState("idle", "Ready for a request"), 1200);
      } else if (result.status === "failed") {
        setOrbState("error", "SEED request failed");
      } else {
        setOrbState(result.status, result.status.replaceAll("_", " "));
      }
      await Promise.all([loadTasks(), loadApprovals()]);
    } catch (error) {
      appendMessage("assistant", "SEED could not process this request: " + error.message);
      setOrbState("error", "Request failed");
    } finally {
      requestPending = false;
      elements.send.disabled = false;
      elements.input.focus();
    }
  });

  document.querySelectorAll("[data-view]").forEach((button) => {
    button.addEventListener("click", () => {
      currentView = button.dataset.view;
      document.querySelectorAll("[data-view]").forEach((item) => item.classList.toggle("active", item === button));
      document.querySelectorAll(".view").forEach((view) => {
        const active = view.id === currentView + "-view";
        view.hidden = !active;
        view.classList.toggle("active", active);
      });
      const sectionLabels = {
        assistant: "Assistant",
        tasks: "Task center",
        activity: "Activity & audit",
        memory: "Memory & knowledge",
        settings: "System settings",
      };
      document.getElementById("topbar-section").textContent = sectionLabels[currentView];
      if (currentView === "tasks") loadTasks().catch(() => {});
      if (currentView === "activity") loadAudit().catch(() => {});
      if (currentView === "memory") loadMemory().catch(() => {});
    });
  });

  document.getElementById("refresh-button").addEventListener("click", () => {
    loadStatus().catch(() => {});
    if (currentView === "activity") loadAudit().catch(() => {});
    if (currentView === "memory") loadMemory().catch(() => {});
  });
  document.getElementById("tasks-refresh").addEventListener("click", () => loadTasks().catch(() => {}));
  document.getElementById("audit-refresh").addEventListener("click", () => loadAudit().catch(() => {}));
  const memRefresh = document.getElementById("memory-refresh");
  if (memRefresh) memRefresh.addEventListener("click", () => loadMemory().catch(() => {}));

  document.addEventListener("click", (e) => {
    if (e.target.classList.contains("suggestion-chip")) {
      const prompt = e.target.dataset.prompt;
      if (prompt && elements.input) {
        elements.input.value = prompt;
        elements.form.requestSubmit();
      }
    }
  });

  const planButton = document.getElementById("plan-button");
  const planPanel = document.getElementById("plan-panel");
  const closePlanBtn = document.getElementById("close-plan-btn");
  const planContent = document.getElementById("plan-content");

  if (planButton && planPanel && closePlanBtn && planContent) {
    closePlanBtn.addEventListener("click", () => { planPanel.hidden = true; });
    planButton.addEventListener("click", async () => {
      const objective = elements.input.value.trim();
      if (!objective) {
        alert("Please enter an objective for the plan.");
        return;
      }
      setOrbState("processing", "Generating live execution plan");
      planPanel.hidden = false;
      planContent.replaceChildren();
      const loading = document.createElement("p");
      loading.className = "list-placeholder";
      loading.textContent = "Generating plan…";
      planContent.appendChild(loading);

      try {
        const plan = await api("/api/plan", {
          method: "POST",
          body: JSON.stringify({ objective }),
        });
        planContent.replaceChildren();
        const title = document.createElement("strong");
        title.textContent = "Plan #" + (plan.plan_id || "generated") + " (" + (plan.status || "ready") + ")";
        planContent.appendChild(title);

        for (const step of plan.steps || []) {
          const stepRow = document.createElement("div");
          stepRow.className = "plan-step";
          const desc = document.createElement("span");
          desc.textContent = "Step " + step.step_id + ": " + step.description;
          const actions = document.createElement("div");
          actions.className = "plan-step-actions";
          const badge = document.createElement("span");
          badge.className = "status-tag " + (step.status || "pending");
          badge.textContent = step.status || "pending";
          actions.appendChild(badge);
          stepRow.append(desc, actions);
          planContent.appendChild(stepRow);
        }

        const executeBtn = document.createElement("button");
        executeBtn.type = "button";
        executeBtn.className = "send-button";
        executeBtn.style.marginTop = "10px";
        executeBtn.textContent = "Execute Plan";
        executeBtn.addEventListener("click", async () => {
          executeBtn.disabled = true;
          setOrbState("executing", "Executing live plan");
          try {
            const execResult = await api("/api/plan/execute", {
              method: "POST",
              body: JSON.stringify({ plan_id: plan.plan_id }),
            });
            appendMessage("assistant", "Plan execution finished with status: " + execResult.status);
            setOrbState("responding", "Plan executed");
            planPanel.hidden = true;
          } catch (err) {
            alert("Plan execution failed: " + err.message);
            setOrbState("error", "Plan execution failed");
          } finally {
            executeBtn.disabled = false;
          }
        });
        planContent.appendChild(executeBtn);
        setOrbState("idle", "Plan ready");
      } catch (err) {
        planContent.replaceChildren();
        const errP = document.createElement("p");
        errP.style.color = "var(--red)";
        errP.textContent = "Plan generation failed: " + err.message;
        planContent.appendChild(errP);
        setOrbState("error", "Plan generation failed");
      }
    });
  }

  function connectEvents() {
    const source = new EventSource("/api/events?after=" + latestEventId);
    source.onopen = () => { elements.eventConnection.textContent = "SEED event stream connected"; };
    source.onerror = () => { elements.eventConnection.textContent = "Reconnecting to SEED events"; };
    source.addEventListener("seed", (event) => {
      try {
        const payload = JSON.parse(event.data);
        latestEventId = Math.max(latestEventId, Number(payload.event_id) || 0);
        if (payload.state) setOrbState(payload.state, payload.event_type.replaceAll("_", " "));
        if (["tool_completed", "tool_failed", "tool_denied", "approval_required", "response_completed"].includes(payload.event_type)) {
          loadTasks().catch(() => {});
          loadApprovals().catch(() => {});
        }
      } catch (_error) {
        elements.eventConnection.textContent = "SEED event could not be parsed";
      }
    });
  }

  document.getElementById("motion-setting").textContent = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "Reduced motion" : "Standard motion";
  Promise.all([loadSession(), loadStatus(), loadAudit()])
    .then(connectEvents)
    .catch(() => connectEvents());
})();