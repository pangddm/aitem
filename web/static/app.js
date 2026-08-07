/* ========================================================================
   Kubedoctor 前端应用 - ChatGPT 风格 (白色主题)
   ======================================================================== */

const EXEC_STAGE_TEXT = {
  rewriter:"正在理解用户需求", orchestrator:"正在分析用户需求",
  risk_validator:"正在进行风险评估", risk_assessor:"正在进行风险评估",
  executor:"正在执行命令", observer:"正在检查执行结果", reporter:"正在整理结果",
  resolved:"问题已解决，正在整理结果", query_complete:"查询完成，正在整理结果", planning_next:"正在分析下一步",
};
const EXEC_STAGE_LABEL = {
  rewriter:"理解问题", orchestrator:"意图分析", risk_validator:"风险评估", risk_assessor:"风险评估",
  executor:"执行命令", observer:"结果观察", reporter:"生成报告",
  resolved:"问题解决", query_complete:"查询完成", planning_next:"下一步分析",
};

const FLOW_LABELS = ["意图识别", "风险校验", "执行命令", "观察结果", "生成报告"];

const App = {
  webSearch: false,
  state: {
    userId: localStorage.getItem("kd_user_id") || "",
    username: localStorage.getItem("kd_username") || "",
    convId: null,
    conversations: [],
    messages: [],
    streaming: false,
    abortCtrl: null,
    attachedFile: null,
    hostId: null,
    hosts: [],
    // 设置
    theme: localStorage.getItem("kd_theme") || "light",
    language: localStorage.getItem("kd_language") || "zh",
    avatarEmoji: localStorage.getItem("kd_avatar") || "",
    testMode: localStorage.getItem("kd_test_mode") === "true",
  },

  // 多语言文本
  i18n: {
    zh: {
      newChat: "新对话",
      history: "历史对话",
      noHistory: "暂无对话",
      welcomeTitle: "你好，我是 Kubedoctor",
      welcomeDesc: "你的智能运维助手，可以帮你诊断问题、执行命令、分析文档。",
      inputPlaceholder: "输入你的问题...",
      footer: "Kubedoctor 可能会产生错误信息，请核实重要信息。",
      you: "你",
      assistant: "Kubedoctor",
      stop: "已停止",
      error: "发生错误",
      analyzing: "正在分析文档...",
      noResponse: "(无响应)",
      loading: "加载中...",
      loadFailed: "加载失败",
      noKnowledge: "暂无知识库",
      noHosts: "暂无主机，请在上方添加",
      defaultHost: "默认主机（环境变量）",
      addHost: "添加主机",
      testSuccess: "✓ 成功",
      testFail: "✗ 失败",
      testError: "✗ 错误",
      testing: "测试中...",
      test: "测试",
      delete: "删除",
      rename: "重命名",
      settings: "设置",
      themeLabel: "主题颜色",
      themeLight: "浅色",
      themeDark: "深色",
      languageLabel: "界面语言",
      langZh: "中文",
      langEn: "English",
      avatarLabel: "头像",
      avatarPlaceholder: "输入 emoji 表情作为头像",
      saveSettings: "保存设置",
      settingsSaved: "设置已保存",
      testModeLabel: "测试模式",
      testModeDesc: "开启后 AI 拥有所有权限，无命令黑名单限制",
      loginTitle: "🩺 Kubedoctor",
      loginDesc: "智能运维助手，登录后开始对话",
      loginTab: "登录",
      registerTab: "注册",
      usernameLabel: "用户名",
      passwordLabel: "密码",
      usernamePlaceholder: "输入用户名",
      passwordPlaceholder: "输入密码",
      loginBtn: "登录",
      registerBtn: "注册",
      fillRequired: "请填写用户名和密码",
      loginFailed: "登录失败",
      registerFailed: "注册失败",
      registerSuccessLoginFailed: "注册成功，但登录失败",
      networkError: "网络错误",
      confirmDelete: "确定删除此对话？",
      confirmDeleteHost: "确定删除此主机？",
      renamePrompt: "输入新名称:",
      hostName: "名称",
      hostAddr: "IP地址",
      hostPort: "端口",
      hostUser: "用户名",
      hostPass: "密码",
      hostMgr: "主机管理",
      knowledgeMgr: "知识库管理",
      checkSystem: "帮我检查系统状态",
      analyzeLogs: "分析最近的故障日志",
      diagnoseNetwork: "帮我诊断网络连接问题",
      checkContainers: "显示当前运行的容器",
      thinking: "思考链",
      intentAnalysis: "意图分析",
      riskAssessment: "风险评估",
      commandGen: "命令生成",
      resultObserve: "结果观察",
      reportGen: "报告生成",
      taskPlan: "任务计划",
      riskAssess: "风险评估",
      cmdValidate: "命令校验",
      execCmd: "执行命令",
      execResult: "执行结果",
      resultObs: "结果观察",
      downloadReport: "下载报告",
    },
    en: {
      newChat: "New Chat",
      history: "History",
      noHistory: "No conversations",
      welcomeTitle: "Hello, I'm Kubedoctor",
      welcomeDesc: "Your intelligent ops assistant for diagnostics, commands, and document analysis.",
      inputPlaceholder: "Ask me anything...",
      footer: "Kubedoctor may produce inaccurate information. Please verify important info.",
      you: "You",
      assistant: "Kubedoctor",
      stop: "Stopped",
      error: "Error occurred",
      analyzing: "Analyzing document...",
      noResponse: "(No response)",
      loading: "Loading...",
      loadFailed: "Failed to load",
      noKnowledge: "No knowledge bases",
      noHosts: "No hosts, add one above",
      defaultHost: "Default host (env)",
      addHost: "Add Host",
      testSuccess: "✓ Success",
      testFail: "✗ Failed",
      testError: "✗ Error",
      testing: "Testing...",
      test: "Test",
      delete: "Delete",
      rename: "Rename",
      settings: "Settings",
      themeLabel: "Theme",
      themeLight: "Light",
      themeDark: "Dark",
      languageLabel: "Language",
      langZh: "中文",
      langEn: "English",
      avatarLabel: "Avatar",
      avatarPlaceholder: "Enter an emoji as avatar",
      saveSettings: "Save Settings",
      settingsSaved: "Settings saved",
      testModeLabel: "Test Mode",
      testModeDesc: "When enabled, AI has full permissions with no command blacklist",
      loginTitle: "🩺 Kubedoctor",
      loginDesc: "Intelligent ops assistant. Log in to start.",
      loginTab: "Login",
      registerTab: "Register",
      usernameLabel: "Username",
      passwordLabel: "Password",
      usernamePlaceholder: "Enter username",
      passwordPlaceholder: "Enter password",
      loginBtn: "Login",
      registerBtn: "Register",
      fillRequired: "Please fill in username and password",
      loginFailed: "Login failed",
      registerFailed: "Registration failed",
      registerSuccessLoginFailed: "Registration succeeded but login failed",
      networkError: "Network error",
      confirmDelete: "Delete this conversation?",
      confirmDeleteHost: "Delete this host?",
      renamePrompt: "Enter new name:",
      hostName: "Name",
      hostAddr: "IP Address",
      hostPort: "Port",
      hostUser: "Username",
      hostPass: "Password",
      hostMgr: "Host Manager",
      knowledgeMgr: "Knowledge Base",
      checkSystem: "Check system status",
      analyzeLogs: "Analyze recent error logs",
      diagnoseNetwork: "Diagnose network issues",
      checkContainers: "Show running containers",
      thinking: "Thinking",
      intentAnalysis: "Intent Analysis",
      riskAssessment: "Risk Assessment",
      commandGen: "Command Generation",
      resultObserve: "Result Observation",
      reportGen: "Report Generation",
      taskPlan: "Task Plan",
      riskAssess: "Risk Assessment",
      cmdValidate: "Command Validation",
      execCmd: "Execute Command",
      execResult: "Execution Result",
      resultObs: "Result Observation",
      downloadReport: "Download Report",
    },
  },

  t(key) {
    const lang = this.state.language;
    return (this.i18n[lang] && this.i18n[lang][key]) || this.i18n["zh"][key] || key;
  },

  el: {},

  init() {
    this.applyTheme();
    this.cacheEls();
    this.bindEvents();
    if (this.state.userId) {
      this.showApp();
      this.loadConversations();
    } else {
      this.showLogin();
    }
  },

  applyTheme() {
    if (this.state.theme === "dark") {
      document.body.classList.add("dark");
    } else {
      document.body.classList.remove("dark");
    }
  },

  cacheEls() {
    const ids = [
      "sidebar", "newChatBtn", "conversationList", "userAvatar", "userName",
      "logoutBtn", "sidebarToggle", "currentChatTitle", "chatContainer",
      "chatMessages", "welcomeScreen", "messageInput", "sendBtn", "stopBtn",
      "attachBtn", "voiceBtn", "netBtn", "fileInput", "fileTag", "fileTagText",
      "fileTagRemove", "knowledgeBtn", "knowledgeModal", "knowledgeModalClose",
      "knowledgeModalBody", "loginOverlay",
      "hostSelect", "hostMgrBtn", "hostModal", "hostModalClose",
      "hostModalBody", "hostName", "hostAddr", "hostPort", "hostUser",
      "hostPass", "hostAddBtn", "hostListContainer",
      "settingsBtn", "settingsModal", "settingsModalClose",
      "settingsTheme", "settingsLanguage", "settingsAvatarInput",
      "settingsAvatarPreview", "settingsSaveBtn", "settingsTestMode",
      "graphPanel", "graphPanelClose", "graphRefreshBtn",
      "graphCanvas", "graphEmpty", "graphLegend", "graphPanelSub",
      "graphRefreshHint", "graphIntervalInput", "graphIntervalSave",
      "graphCollapseTab", "graphFloatBall", "graphReopenTab",
      "graphZoomIn", "graphZoomOut", "graphZoomReset", "graphZoomLabel",
    ];
    ids.forEach((id) => { this.el[id] = document.getElementById(id); });
    this.welcomeTpl = this.el.welcomeScreen ? this.el.welcomeScreen.outerHTML : "";
  },

  /* ───── 登录/注册 ───── */
  showLogin() {
    if (!this.el.loginOverlay) {
      this.buildLoginOverlay();
    }
    this.el.loginOverlay.style.display = "flex";
    document.querySelector(".sidebar").style.display = "none";
    document.querySelector(".main-area").style.display = "none";
  },

  buildLoginOverlay() {
    const ov = document.createElement("div");
    ov.className = "login-overlay";
    ov.id = "loginOverlay";
    const t = (k) => this.t(k);
    ov.innerHTML = `
      <div class="login-card">
        <h1>${t("loginTitle")}</h1>
        <p>${t("loginDesc")}</p>
        <div class="login-tabs">
          <button class="login-tab active" data-mode="login">${t("loginTab")}</button>
          <button class="login-tab" data-mode="register">${t("registerTab")}</button>
        </div>
        <div class="login-field">
          <label>${t("usernameLabel")}</label>
          <input type="text" id="loginUser" placeholder="${t("usernamePlaceholder")}" autocomplete="off">
        </div>
        <div class="login-field">
          <label>${t("passwordLabel")}</label>
          <input type="password" id="loginPass" placeholder="${t("passwordPlaceholder")}">
        </div>
        <button class="login-submit" id="loginSubmit">${t("loginBtn")}</button>
        <div class="login-error" id="loginError"></div>
      </div>
    `;
    document.body.appendChild(ov);
    this.el.loginOverlay = ov;

    let mode = "login";
    ov.querySelectorAll(".login-tab").forEach((tab) => {
      tab.addEventListener("click", () => {
        ov.querySelectorAll(".login-tab").forEach((x) => x.classList.remove("active"));
        tab.classList.add("active");
        mode = tab.dataset.mode;
        document.getElementById("loginSubmit").textContent = mode === "login" ? t("loginBtn") : t("registerBtn");
        document.getElementById("loginError").textContent = "";
      });
    });

    document.getElementById("loginSubmit").addEventListener("click", async () => {
      const username = document.getElementById("loginUser").value.trim();
      const password = document.getElementById("loginPass").value;
      const errEl = document.getElementById("loginError");
      errEl.textContent = "";
      if (!username || !password) { errEl.textContent = t("fillRequired"); return; }
      try {
        const res = await fetch(`/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username, password }),
        });
        const data = await res.json();
        if (mode === "login") {
          if (data.success) {
            this.state.userId = data.user_id;
            this.state.username = username;
            localStorage.setItem("kd_user_id", data.user_id);
            localStorage.setItem("kd_username", username);
            this.showApp();
            this.loadConversations();
          } else {
            errEl.textContent = data.message || t("loginFailed");
          }
        } else {
          if (data.success) {
            const loginRes = await fetch(`/login`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ username, password }),
            });
            const loginData = await loginRes.json();
            if (loginData.success) {
              this.state.userId = loginData.user_id;
              this.state.username = username;
              localStorage.setItem("kd_user_id", loginData.user_id);
              localStorage.setItem("kd_username", username);
              this.showApp();
              this.loadConversations();
            } else {
              errEl.textContent = t("registerSuccessLoginFailed");
            }
          } else {
            errEl.textContent = data.message || t("registerFailed");
          }
        }
      } catch (e) {
        errEl.textContent = t("networkError") + ": " + e.message;
      }
    });

    document.getElementById("loginPass").addEventListener("keydown", (e) => {
      if (e.key === "Enter") document.getElementById("loginSubmit").click();
    });
  },

  showApp() {
    if (this.el.loginOverlay) this.el.loginOverlay.style.display = "none";
    document.querySelector(".sidebar").style.display = "";
    document.querySelector(".main-area").style.display = "";
    this.el.userName.textContent = this.state.username;
    this.updateAvatar();
    this.loadHosts();
    this.updateUILanguage();
    // 登录后自动展示集群拓扑图
    this.openGraphPanel();
  },

  updateAvatar() {
    const emoji = this.state.avatarEmoji || this.state.username.charAt(0).toUpperCase();
    this.el.userAvatar.textContent = emoji;
  },

  updateUILanguage() {
    const t = (k) => this.t(k);
    // 更新静态文本
    this.el.newChatBtn.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <line x1="12" y1="5" x2="12" y2="19"></line>
        <line x1="5" y1="12" x2="19" y2="12"></line>
      </svg>
      ${t("newChat")}
    `;
    this.el.messageInput.placeholder = t("inputPlaceholder");
    const footer = document.querySelector(".composer-footer");
    if (footer) footer.textContent = t("footer");
    // 更新欢迎页
    const ws = this.el.chatMessages.querySelector(".welcome-screen");
    if (ws) {
      ws.querySelector("h2").textContent = t("welcomeTitle");
      ws.querySelector("p").textContent = t("welcomeDesc");
      const cards = ws.querySelectorAll(".suggestion-card");
      if (cards.length >= 4) {
        cards[0].querySelector(".card-text").textContent = t("checkSystem");
        cards[1].querySelector(".card-text").textContent = t("analyzeLogs");
        cards[2].querySelector(".card-text").textContent = t("diagnoseNetwork");
        cards[3].querySelector(".card-text").textContent = t("checkContainers");
      }
    }
    // 更新主机选择默认项
    const sel = this.el.hostSelect;
    if (sel && sel.options[0]) {
      sel.options[0].textContent = t("defaultHost");
    }
    // 更新设置面板
    this.updateSettingsPanelText();
    // 重新渲染对话列表
    this.renderConversationList();
  },

  updateSettingsPanelText() {
    const t = (k) => this.t(k);
    const modal = this.el.settingsModal;
    if (!modal || modal.style.display === "none") return;
    const header = modal.querySelector(".modal-header h3");
    if (header) header.textContent = "⚙️ " + t("settings");
    const themeLabel = modal.querySelector("[data-i18n='themeLabel']");
    if (themeLabel) themeLabel.textContent = t("themeLabel");
    const langLabel = modal.querySelector("[data-i18n='languageLabel']");
    if (langLabel) langLabel.textContent = t("languageLabel");
    const avatarLabel = modal.querySelector("[data-i18n='avatarLabel']");
    if (avatarLabel) avatarLabel.textContent = t("avatarLabel");
    const saveBtn = modal.querySelector(".settings-save-btn");
    if (saveBtn) saveBtn.textContent = t("saveSettings");
    // 更新 select options
    const themeSel = this.el.settingsTheme;
    if (themeSel) {
      themeSel.options[0].textContent = t("themeLight");
      themeSel.options[1].textContent = t("themeDark");
    }
    const langSel = this.el.settingsLanguage;
    if (langSel) {
      langSel.options[0].textContent = t("langZh");
      langSel.options[1].textContent = t("langEn");
    }
    const avatarInput = this.el.settingsAvatarInput;
    if (avatarInput) avatarInput.placeholder = t("avatarPlaceholder");
    const testModeLabel = modal.querySelector("[data-i18n='testModeLabel']");
    if (testModeLabel) testModeLabel.textContent = t("testModeLabel");
    const testModeDesc = modal.querySelector("[data-i18n='testModeDesc']");
    if (testModeDesc) testModeDesc.textContent = t("testModeDesc");
  },

  logout() {
    localStorage.removeItem("kd_user_id");
    localStorage.removeItem("kd_username");
    this.state.userId = "";
    this.state.convId = null;
    this.state.messages = [];
    this.state.conversations = [];
    location.reload();
  },

  /* ───── 事件绑定 ───── */
  bindEvents() {
    this.el.newChatBtn.addEventListener("click", () => this.newConversation());
    this.el.logoutBtn.addEventListener("click", () => this.logout());
    this.el.sidebarToggle.addEventListener("click", () => {
      this.el.sidebar.classList.toggle("collapsed");
    });

    // 输入框
    const input = this.el.messageInput;
    input.addEventListener("input", () => this.autoResize(input));
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        this.sendMessage();
      }
    });
    this.el.sendBtn.addEventListener("click", () => this.sendMessage());
    this.el.stopBtn.addEventListener("click", () => this.stopStream());

    // 附件
    this.el.attachBtn.addEventListener("click", () => this.el.fileInput.click());
    this.el.netBtn.addEventListener("click", () => this.toggleWebSearch());
    this.el.fileInput.addEventListener("change", (e) => this.handleFile(e));
    this.el.fileTagRemove.addEventListener("click", () => this.clearFile());

    // 建议
    document.querySelectorAll(".suggestion-card").forEach((c) => {
      c.addEventListener("click", () => {
        input.value = c.dataset.prompt;
        this.autoResize(input);
        this.sendMessage();
      });
    });

    // 知识库 modal
    this.el.knowledgeBtn.addEventListener("click", () => this.openKnowledgeModal());
    this.el.knowledgeModalClose.addEventListener("click", () => this.closeKnowledgeModal());
    this.el.knowledgeModal.addEventListener("click", (e) => {
      if (e.target === this.el.knowledgeModal) this.closeKnowledgeModal();
    });

    // 主机管理
    this.el.hostSelect.addEventListener("change", () => {
      this.state.hostId = this.el.hostSelect.value || null;
      // 连接某台主机时自动打开并加载拓扑图
      this.openGraphPanel();
    });
    this.el.hostMgrBtn.addEventListener("click", () => this.openHostModal());
    this.el.hostModalClose.addEventListener("click", () => this.closeHostModal());
    this.el.hostModal.addEventListener("click", (e) => {
      if (e.target === this.el.hostModal) this.closeHostModal();
    });
    this.el.hostAddBtn.addEventListener("click", () => this.addHost());

    // 设置
    this.el.settingsBtn.addEventListener("click", () => this.openSettingsModal());
    this.el.settingsModalClose.addEventListener("click", () => this.closeSettingsModal());
    this.el.settingsModal.addEventListener("click", (e) => {
      if (e.target === this.el.settingsModal) this.closeSettingsModal();
    });
    this.el.settingsSaveBtn.addEventListener("click", () => this.saveSettings());

    // 拓扑图（悬浮球作为常驻入口）
    this.el.graphPanelClose.addEventListener("click", () => this.closeGraphPanel());
    this.el.graphRefreshBtn.addEventListener("click", () => this.rebuildTopology());
    this.el.graphIntervalSave.addEventListener("click", () => this.saveTopologyInterval());
    // 面板边缘折叠箭头 -> 收起为悬浮球（展开靠悬浮球）
    if (this.el.graphCollapseTab) {
      this.el.graphCollapseTab.addEventListener("click", () => this.closeGraphPanel());
    }
    if (this.el.graphReopenTab) {
      this.el.graphReopenTab.addEventListener("click", () => this.openGraphPanel());
    }
    // 悬浮球：可拖动 + 点击展开/收起
    this.initFloatBall();
    // 缩放
    if (this.el.graphZoomIn) this.el.graphZoomIn.addEventListener("click", () => this.stepGraphZoom(0.2));
    if (this.el.graphZoomOut) this.el.graphZoomOut.addEventListener("click", () => this.stepGraphZoom(-0.2));
    if (this.el.graphZoomReset) this.el.graphZoomReset.addEventListener("click", () => this.setGraphZoom(1));
    if (this.el.graphCanvas) {
      this.el.graphCanvas.addEventListener("wheel", (e) => {
        if (e.ctrlKey || e.metaKey) {
          e.preventDefault();
          this.stepGraphZoom(e.deltaY < 0 ? 0.1 : -0.1);
        }
      }, { passive: false });
    }
    this.el.settingsTheme.addEventListener("change", () => {
      // 实时预览主题
      const val = this.el.settingsTheme.value;
      if (val === "dark") {
        document.body.classList.add("dark");
      } else {
        document.body.classList.remove("dark");
      }
    });
  },

  autoResize(el) {
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
    this.el.sendBtn.disabled = !el.value.trim() && !this.state.attachedFile;
  },

  /* ───── 设置面板 ───── */
  openSettingsModal() {
    this.el.settingsModal.style.display = "flex";
    this.el.settingsTheme.value = this.state.theme;
    this.el.settingsLanguage.value = this.state.language;
    this.el.settingsAvatarInput.value = this.state.avatarEmoji;
    this.el.settingsAvatarPreview.textContent = this.state.avatarEmoji || this.state.username.charAt(0).toUpperCase();
    this.el.settingsTestMode.checked = this.state.testMode;
    this.updateSettingsPanelText();
  },

  closeSettingsModal() {
    this.el.settingsModal.style.display = "none";
    // 恢复主题
    this.applyTheme();
  },

  saveSettings() {
    const newTheme = this.el.settingsTheme.value;
    const newLang = this.el.settingsLanguage.value;
    const newAvatar = this.el.settingsAvatarInput.value.trim();
    const newTestMode = this.el.settingsTestMode.checked;

    this.state.theme = newTheme;
    this.state.language = newLang;
    this.state.avatarEmoji = newAvatar;
    this.state.testMode = newTestMode;

    localStorage.setItem("kd_theme", newTheme);
    localStorage.setItem("kd_language", newLang);
    localStorage.setItem("kd_avatar", newAvatar);
    localStorage.setItem("kd_test_mode", newTestMode ? "true" : "false");

    // 同步测试模式到后端
    this.syncTestMode(newTestMode);

    this.applyTheme();
    this.updateAvatar();
    this.updateUILanguage();
    this.closeSettingsModal();

    // 短暂提示
    this.showToast(this.t("settingsSaved"));
  },

  async syncTestMode(enabled) {
    try {
      await fetch(`/chat/settings?user_id=${encodeURIComponent(this.state.userId)}&test_mode=${enabled}`, {
        method: "POST",
      });
    } catch (e) {
      console.error("syncTestMode error:", e);
    }
  },

  showToast(msg) {
    let toast = document.getElementById("kdToast");
    if (!toast) {
      toast = document.createElement("div");
      toast.id = "kdToast";
      toast.style.cssText = `
        position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
        background: var(--accent); color: var(--main-bg); padding: 10px 20px;
        border-radius: 20px; font-size: 14px; z-index: 9999;
        transition: opacity 0.3s; opacity: 0; pointer-events: none;
      `;
      document.body.appendChild(toast);
    }
    toast.textContent = msg;
    toast.style.opacity = "1";
    clearTimeout(toast._timeout);
    toast._timeout = setTimeout(() => { toast.style.opacity = "0"; }, 2000);
  },

  /* ───── 会话管理 ───── */
  async loadConversations() {
    try {
      const res = await fetch(`/conversations?user_id=${encodeURIComponent(this.state.userId)}`);
      const data = await res.json();
      if (data.success) {
        this.state.conversations = data.data || [];
        this.renderConversationList();
      }
    } catch (e) {
      console.error("loadConversations error:", e);
    }
  },

  renderConversationList() {
    const list = this.el.conversationList;
    list.innerHTML = "";
    if (!this.state.conversations.length) {
      list.innerHTML = `<div class="conv-group-label">${this.t("noHistory")}</div>`;
      return;
    }
    const group = document.createElement("div");
    group.className = "conv-group-label";
    group.textContent = this.t("history");
    list.appendChild(group);

    this.state.conversations.forEach((conv) => {
      const item = document.createElement("div");
      item.className = "conv-item" + (conv.id === this.state.convId ? " active" : "");
      item.dataset.id = conv.id;
      item.innerHTML = `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="flex-shrink:0">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
        </svg>
        <span class="conv-title">${this.escapeHtml(conv.title || this.t("newChat"))}</span>
        <div class="conv-actions">
          <button class="conv-action-btn" title="${this.t("rename")}" data-action="rename">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
            </svg>
          </button>
          <button class="conv-action-btn" title="${this.t("delete")}" data-action="delete">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            </svg>
          </button>
        </div>
      `;
      item.addEventListener("click", (e) => {
        const btn = e.target.closest("[data-action]");
        if (btn) {
          e.stopPropagation();
          this.handleConvAction(btn.dataset.action, conv);
        } else {
          this.selectConversation(conv.id);
        }
      });
      list.appendChild(item);
    });
  },

  async handleConvAction(action, conv) {
    if (action === "rename") {
      const title = prompt(this.t("renamePrompt"), conv.title);
      if (title && title.trim()) {
        await fetch(`/conversations/${conv.id}?title=${encodeURIComponent(title.trim())}&user_id=${encodeURIComponent(this.state.userId)}`, {
          method: "PUT",
        });
        this.loadConversations();
      }
    } else if (action === "delete") {
      if (confirm(this.t("confirmDelete"))) {
        await fetch(`/conversations/${conv.id}?user_id=${encodeURIComponent(this.state.userId)}`, {
          method: "DELETE",
        });
        if (this.state.convId === conv.id) {
          this.state.convId = null;
          this.state.messages = [];
          this.showWelcome();
        }
        this.loadConversations();
      }
    }
  },

  async selectConversation(convId) {
    this.state.convId = convId;
    this.renderConversationList();
    try {
      const res = await fetch(`/conversations/${convId}`);
      const data = await res.json();
      if (data.success) {
        this.state.messages = data.data || [];
        this.renderMessages();
        const conv = this.state.conversations.find((c) => c.id === convId);
        if (conv) this.el.currentChatTitle.textContent = conv.title || this.t("newChat");
      }
    } catch (e) {
      console.error("selectConversation error:", e);
    }
  },

  newConversation() {
    this.state.convId = null;
    this.state.messages = [];
    this.renderConversationList();
    this.showWelcome();
    this.el.currentChatTitle.textContent = "Kubedoctor";
    this.el.messageInput.focus();
  },

  /* ───── 消息渲染 ───── */
  showWelcome() {
    this.el.chatMessages.innerHTML = this.welcomeTpl;
    // 重新绑定建议卡片事件
    this.el.chatMessages.querySelectorAll(".suggestion-card").forEach((c) => {
      c.addEventListener("click", () => {
        this.el.messageInput.value = c.dataset.prompt;
        this.autoResize(this.el.messageInput);
        this.sendMessage();
      });
    });
    this.updateUILanguage();
  },

  // 后端思考链格式 → 前端渲染格式 的映射
  mapThinkingChainItem(tc) {
    // 如果已经是前端格式（有 cls 和 title），直接返回
    if (tc.cls && tc.title) return tc;

    // 从后端格式转换
    const type = tc.type || "thought";
    let content = tc.content || "";
    if (typeof content !== "string") {
      content = JSON.stringify(content, null, 2);
    }
    // 合并 command/result 信息
    if (tc.command) {
      content = tc.command + (tc.result ? "\n\n" + (typeof tc.result === "string" ? tc.result : JSON.stringify(tc.result, null, 2)) : "");
    } else if (tc.result) {
      content += (content ? "\n\n" : "") + (typeof tc.result === "string" ? tc.result : JSON.stringify(tc.result, null, 2));
    }

    const typeMap = {
      reasoning: { cls: "thought", title: `💭 ${this.t("thinking") || "思考"}` },
      task_plan: { cls: "plan", title: `📋 ${this.t("taskPlan") || "任务计划"}` },
      risk_assessment: { cls: "risk", title: `⚠️ ${this.t("riskAssess") || "风险评估"}` },
      validation: { cls: "validation", title: `✅ ${this.t("cmdValidate") || "命令校验"}` },
      tool_call: { cls: "tool", title: `🔧 ${this.t("execCmd") || "执行命令"}` },
      tool_result: { cls: "tool", title: `📋 ${this.t("execResult") || "执行结果"}` },
      observation: { cls: "observation", title: `👁️ ${this.t("resultObs") || "结果观察"}` },
      retry_loop: { cls: "retry", title: `🔄 ${this.t("retry") || "重试"}` },
    };

    const mapping = typeMap[type] || { cls: "thought", title: `💭 ${type}` };
    return { cls: mapping.cls, title: mapping.title, content };
  },

  renderMessages() {
    const container = this.el.chatMessages;
    container.innerHTML = "";
    if (!this.state.messages.length) {
      this.showWelcome();
      return;
    }
    this.state.messages.forEach((msg) => {
      const el = this.createMessageEl(msg.role, msg.content);
      container.appendChild(el);
      // 如果有思考链数据，渲染思考链
      if (msg.thinking_chain && msg.thinking_chain.length > 0) {
        const contentEl = el.querySelector(".message-content");
        const answerArea = contentEl.querySelector(".answer-area");
        
        // 先收集所有思考链块
        const blocks = [];
        msg.thinking_chain.forEach((tc) => {
          const item = this.mapThinkingChainItem(tc);
          const block = document.createElement("div");
          block.className = `event-block ${item.cls} completed`;
          const titleEl = document.createElement("div");
          titleEl.className = "event-title";
          titleEl.innerHTML = `<span>${item.title}</span><span class="event-status">✓</span>`;
          block.appendChild(titleEl);
          const contentDiv = document.createElement("div");
          contentDiv.className = "event-content collapsed";
          const textDiv = document.createElement("div");
          textDiv.className = "event-text";
          textDiv.dataset.raw = item.content || "";
          textDiv.innerHTML = this.formatThinkingContent(item.content || "");
          contentDiv.appendChild(textDiv);
          block.appendChild(contentDiv);
          titleEl.addEventListener("click", () => {
            contentDiv.classList.toggle("collapsed");
          });
          blocks.push(block);
        });
        
        // 创建大折叠容器
        const wrapper = document.createElement("div");
        wrapper.className = "event-block thinking-chain completed";
        const wrapperTitle = document.createElement("div");
        wrapperTitle.className = "event-title";
        wrapperTitle.innerHTML = `<span>▸ 展开处理过程</span><span class="event-status">✓</span>`;
        wrapper.appendChild(wrapperTitle);
        const wrapperContent = document.createElement("div");
        wrapperContent.className = "event-content collapsed";
        const innerContainer = document.createElement("div");
        innerContainer.className = "thinking-chain-inner";
        blocks.forEach((block) => {
          innerContainer.appendChild(block);
        });
        wrapperContent.appendChild(innerContainer);
        wrapper.appendChild(wrapperContent);
        wrapperTitle.addEventListener("click", () => {
          wrapperContent.classList.toggle("collapsed");
        });
        
        // 将大折叠容器插入到 answer-area 之前
        if (answerArea) {
          contentEl.insertBefore(wrapper, answerArea);
        } else {
          contentEl.prepend(wrapper);
        }
      }
    });
    // 使用 requestAnimationFrame 确保 DOM 渲染完成后再滚动到底部
    requestAnimationFrame(() => {
      this.scrollToBottom();
    });
  },

  createMessageEl(role, content) {
    const div = document.createElement("div");
    div.className = `message ${role}`;
    const avatar = role === "user"
      ? (this.state.avatarEmoji || this.state.username.charAt(0).toUpperCase())
      : "K";
    const roleLabel = role === "user" ? this.t("you") : this.t("assistant");
    div.innerHTML = `
      <div class="message-avatar">${this.escapeHtml(avatar)}</div>
      <div class="message-body">
        <div class="message-role">${roleLabel}</div>
        <div class="message-content"></div>
      </div>
    `;
    const contentEl = div.querySelector(".message-content");
    if (role === "assistant") {
      // assistant 消息：先添加 answer-area，思考链块会在 renderMessages 中插入到 answer-area 前面
      const answerArea = document.createElement("div");
      answerArea.className = "answer-area";
      answerArea.innerHTML = this.renderMarkdown(content);
      contentEl.appendChild(answerArea);
    } else {
      contentEl.innerHTML = this.renderMarkdown(content);
    }
    return div;
  },

  scrollToBottom() {
    this.el.chatContainer.scrollTop = this.el.chatContainer.scrollHeight;
  },

  /* ───── 发送消息 / 流式 ───── */
  async sendMessage() {
    const text = this.el.messageInput.value.trim();
    if ((!text && !this.state.attachedFile) || this.state.streaming) return;

    // 隐藏欢迎页
    const ws = this.el.chatMessages.querySelector(".welcome-screen");
    if (ws) ws.remove();

    // 如果有附件，走文档聊天接口
    if (this.state.attachedFile) {
      await this.sendWithDocument(text);
      return;
    }

    // 渲染用户消息
    const userMsg = { role: "user", content: text };
    this.state.messages.push(userMsg);
    this.el.chatMessages.appendChild(this.createMessageEl("user", text));
    this.el.messageInput.value = "";
    this.autoResize(this.el.messageInput);
    this.scrollToBottom();

    // 创建助手消息占位
    const assistantEl = this.createMessageEl("assistant", "");
    const contentEl = assistantEl.querySelector(".message-content");
    // 立即创建「意图识别」执行模块，让用户知道 AI 正在分析
    const answerArea = contentEl.querySelector(".answer-area");
    this.ensureExecBox(contentEl);
    // 将 typing-cursor 加到 answer-area 上
    if (answerArea) {
      answerArea.classList.add("typing-cursor");
    } else {
      contentEl.classList.add("typing-cursor");
    }
    this.el.chatMessages.appendChild(assistantEl);
    this.scrollToBottom();

    this.state.streaming = true;
    this.toggleStreamingUI(true);
    this.state.abortCtrl = new AbortController();

    let fullAnswer = "";
    try {
      const params = new URLSearchParams({
        user_id: this.state.userId,
        message: text,
      });
      if (this.state.convId) params.set("conv_id", this.state.convId);
      if (this.state.hostId) params.set("host_id", this.state.hostId);
      if (this.webSearch) params.set("web_search", "1");

      const res = await fetch(`/chat/stream?${params}`, {
        signal: this.state.abortCtrl.signal,
      });
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const payload = line.slice(6).trim();
          if (!payload) continue;
          try {
            const evt = JSON.parse(payload);
            this.handleStreamEvent(evt, contentEl, assistantEl);
            if (evt.type === "answer_chunk") {
              fullAnswer += evt.content || "";
            }
          } catch (e) {
            // 忽略解析错误
          }
        }
      }

      // 流结束后，折叠所有思考链
      this.collapseAllThinkingBlocks(contentEl);
    } catch (e) {
      if (e.name !== "AbortError") {
        contentEl.textContent = "⚠️ " + this.t("error") + ": " + e.message;
      } else {
        const answerArea = contentEl.querySelector(".answer-area");
        if (answerArea) {
          answerArea.innerHTML += `<br><em>(${this.t("stop")})</em>`;
        } else {
          contentEl.textContent += `\n\n_(${this.t("stop")})_`;
        }
      }
    } finally {
      // 移除 typing-cursor（可能在 answer-area 或 message-content 上）
      const answerArea = contentEl.querySelector(".answer-area");
      if (answerArea) {
        answerArea.classList.remove("typing-cursor");
      }
      contentEl.classList.remove("typing-cursor");
      this.state.streaming = false;
      this.toggleStreamingUI(false);
      if (fullAnswer) {
        this.state.messages.push({ role: "assistant", content: fullAnswer, thinking_chain: thinkingChain });
      }
      this.collapseExecBox(contentEl);
      this.loadConversations();
      this.scrollToBottom();
    }
  },

  /* ───── 任务状态 / 执行记录展示 ───── */
  ensureExecBox(contentEl) {
    let box = contentEl.querySelector(".execution-log.exec-box");
    if (box) return box;
    box = document.createElement("div");
    box.className = "execution-log animating exec-box";
    box._flowIdx = 0;
    box.innerHTML = `
      <div class="exec-box-body">
        <div class="flow-steps">
          <div class="flow-step" data-idx="0"><span class="flow-dot">1</span><span class="flow-label">意图识别</span></div>
          <div class="flow-connector"></div>
          <div class="flow-step" data-idx="1"><span class="flow-dot">2</span><span class="flow-label">风险校验</span></div>
          <div class="flow-connector"></div>
          <div class="flow-step" data-idx="2"><span class="flow-dot">3</span><span class="flow-label">执行命令</span></div>
          <div class="flow-connector"></div>
          <div class="flow-step" data-idx="3"><span class="flow-dot">4</span><span class="flow-label">观察结果</span></div>
          <div class="flow-connector"></div>
          <div class="flow-step" data-idx="4"><span class="flow-dot">5</span><span class="flow-label">生成报告</span></div>
        </div>
        <div class="exec-steps"></div>
      </div>
      <div class="exec-status-bar">
        <span class="exec-status-icon">&#9203;</span>
        <span class="exec-status-text">正在分析用户需求</span>
        <button class="exec-box-toggle" type="button" title="展开/折叠处理过程">▾ 收起</button>
      </div>
    `;
    const answer = contentEl.querySelector(".answer-area");
    if (answer) contentEl.insertBefore(box, answer);
    else contentEl.appendChild(box);
    const toggleBtn = box.querySelector(".exec-box-toggle");
    if (toggleBtn) {
      toggleBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        box.classList.toggle("collapsed");
        toggleBtn.textContent = box.classList.contains("collapsed") ? "▸ 展开" : "▾ 收起";
      });
    }
    return box;
  },

  setFlowStage(contentEl, idx) {
    const box = contentEl.querySelector(".execution-log.exec-box");
    if (!box) return;
    box._flowIdx = idx;
    const steps = box.querySelectorAll(".flow-step");
    steps.forEach((el, i) => {
      el.classList.remove("active", "done");
      const dot = el.querySelector(".flow-dot");
      if (i < idx) {
        el.classList.add("done");
        if (dot) dot.textContent = "✓";
      } else {
        if (dot) dot.textContent = String(i + 1);
        if (i === idx) el.classList.add("active");
      }
    });
    box.querySelectorAll(".flow-connector").forEach((cn, i) => {
      cn.classList.toggle("done", i < idx);
    });
    box.querySelectorAll(".exec-step").forEach((it) => {
      const ii = parseInt(it.getAttribute("data-idx"), 10);
      it.classList.remove("done", "active");
      if (ii < idx) it.classList.add("done");
      else if (ii === idx) it.classList.add("active");
    });
  },

  ensureStepItem(contentEl, idx) {
    const box = contentEl.querySelector(".execution-log.exec-box");
    if (!box) return null;
    let item = box.querySelector(`.exec-step[data-idx="${idx}"]`);
    if (item) return item;
    item = document.createElement("div");
    item.className = "exec-step";
    item.setAttribute("data-idx", idx);
    item.innerHTML = `
      <div class="exec-step-header">
        <span class="exec-step-dot"></span>
        <span class="exec-step-label">${FLOW_LABELS[idx]}</span>
        <span class="exec-step-state"></span>
      </div>
      <div class="exec-step-content"></div>
    `;
    const cur = (box._flowIdx != null) ? box._flowIdx : idx;
    if (idx < cur) item.classList.add("done");
    else if (idx === cur) item.classList.add("active");
    const container = box.querySelector(".exec-steps");
    if (!container) { contentEl.appendChild(item); return item; }
    let inserted = false;
    container.querySelectorAll(".exec-step").forEach((el) => {
      const ii = parseInt(el.getAttribute("data-idx"), 10);
      if (!inserted && ii > idx) {
        container.insertBefore(item, el);
        inserted = true;
      }
    });
    if (!inserted) container.appendChild(item);
    return item;
  },

  appendStep(contentEl, idx, text) {
    const t = typeof text === "string" ? text.trim() : JSON.stringify(text);
    if (!t) return;
    const item = this.ensureStepItem(contentEl, idx);
    if (!item) return;
    const body = item.querySelector(".exec-step-content");
    if (!body) return;
    if (body.dataset.lastLine === t) return;
    const div = document.createElement("div");
    div.className = "exec-step-line";
    div.textContent = t;
    body.appendChild(div);
    body.dataset.lastLine = t;
    // 思考链滚动刷新：滚动到当前阶段内容底部
    const stepsBox = item.closest(".exec-steps");
    if (stepsBox) stepsBox.scrollTop = stepsBox.scrollHeight;
    this.scrollToBottom();
  },

  flowIndexForStage(stage) {
    const map = {
      rewriter: 0, orchestrator: 0,
      risk_validator: 1, risk_assessor: 1,
      executor: 2,
      observer: 3,
      reporter: 4, resolved: 4, query_complete: 4, planning_next: 4,
    };
    return map[stage] != null ? map[stage] : null;
  },

  setExecStatus(contentEl, statusText) {
    const box = this.ensureExecBox(contentEl);
    const t = box.querySelector(".exec-status-text");
    if (t) t.textContent = statusText || "正在处理...";
    this.scrollToBottom();
  },



  markExecComplete(contentEl) {
    const box = contentEl.querySelector(".execution-log.exec-box");
    if (!box) return;
    const steps = box.querySelectorAll(".flow-step");
    steps.forEach((el) => {
      el.classList.remove("active");
      el.classList.add("done");
      const dot = el.querySelector(".flow-dot");
      if (dot) dot.textContent = "✓";
    });
    box.querySelectorAll(".flow-connector").forEach((cn) => cn.classList.add("done"));
    box.querySelectorAll(".exec-step").forEach((el) => {
      el.classList.remove("active");
      el.classList.add("done");
      const st = el.querySelector(".exec-step-state");
      if (st) st.textContent = "✓";
    });
    const icon = box.querySelector(".exec-status-icon");
    if (icon) icon.textContent = "✓";
    const t = box.querySelector(".exec-status-text");
    if (t) t.textContent = "报告生成完成";
    const hs = box.querySelector(".exec-box-status");
    if (hs) hs.textContent = "✓ 已完成";
    box.classList.remove("animating");
    box.classList.add("completed");
    this.collapseExecBox(contentEl);
  },



  collapseExecBox(contentEl) {
    const box = contentEl.querySelector(".execution-log.exec-box");
    if (!box) return;
    box.classList.add("collapsed");
    const toggleBtn = box.querySelector(".exec-box-toggle");
    if (toggleBtn) toggleBtn.textContent = "▸ 展开";
  },

  attachDownloadButton(contentEl) {
    if (!this.state.convId) return;
    const box = contentEl.querySelector(".execution-log.exec-box");
    let holder = box ? box.querySelector(".exec-status-bar") : null;
    if (!holder) holder = contentEl.querySelector(".answer-area") || contentEl;
    if (holder.querySelector(".report-download-btn")) return;
    const downloadBtn = document.createElement("a");
    downloadBtn.href = `/chat/report/${encodeURIComponent(this.state.convId)}?user_id=${encodeURIComponent(this.state.userId)}`;
    downloadBtn.download = `Kubedoctor_${this.state.convId.slice(0, 8)}_report.md`;
    downloadBtn.className = "report-download-btn";
    downloadBtn.innerHTML = `📥 ${this.t("downloadReport") || "下载报告"}`;
    holder.appendChild(downloadBtn);
  },

  handleStreamEvent(evt, contentEl, assistantEl) {
    const type = evt.type;
    const content = evt.content || "";

    if (type === "web_search") {
      if (this.webSearchNote) this.webSearchNote.remove();
      this.webSearchNote = document.createElement("div");
      this.webSearchNote.style.cssText = "font-size:12px;color:var(--text-tertiary);padding:4px 0 8px;border-bottom:1px solid var(--border);margin-bottom:8px";
      this.webSearchNote.textContent = "🌐 联网 (" + (evt.query || "") + ")" + (evt.content ? "：已接入检索结果" : "（无结果）");
      contentEl.prepend(this.webSearchNote);
      return;
    }

    if (type === "conv_created") {
      this.state.convId = evt.conv_id;
      return;
    }

    // 模型信息
    if (type === "model_info") {
      this.updateModelBadge(evt.model, evt.models);
      return;
    }

    // 模型切换通知
    if (type === "model_switched") {
      this.showModelSwitchToast(evt.display);
      return;
    }

    // 工作流状态（状态条 + 流程推进）
    if (type === "workflow_status") {
      const idx = this.flowIndexForStage(evt.stage);
      const st = EXEC_STAGE_TEXT[evt.stage] || evt.message || "正在处理...";
      if (idx != null) {
        this.setFlowStage(contentEl, idx);
        if (evt.message && evt.message !== st && evt.message !== (EXEC_STAGE_TEXT[evt.stage] || "")) {
          this.appendStep(contentEl, idx, evt.message);
        }
      }
      this.setExecStatus(contentEl, st);
      return;
    }

    // 反馈循环重试
    if (type === "retry_loop") {
      this.setFlowStage(contentEl, 3);
      const rtext = evt.reason ? "第" + evt.loop + "次重试: " + evt.reason : "第" + evt.loop + "次重试";
      this.appendStep(contentEl, 3, rtext);
      this.setExecStatus(contentEl, this.t("resultObserve") || "正在检查执行结果");
      return;
    }

    // 最终答案流式输出
    if (type === "answer_chunk") {
      // 思考完成，开始回复 -> 折叠思考过程
      this.collapseExecBox(contentEl);
      let answerArea = contentEl.querySelector(".answer-area");
      if (!answerArea) {
        answerArea = document.createElement("div");
        answerArea.className = "answer-area";
        contentEl.appendChild(answerArea);
      }
      const current = answerArea.dataset.raw || "";
      const updated = current + content;
      answerArea.dataset.raw = updated;
      answerArea.innerHTML = this.renderMarkdown(updated);
      this.scrollToBottom();
      return;
    }

    // 各阶段推理（根据 agent 推进流程）
    if (type === "reasoning" || type === "answer_reasoning") {
      const agentMap = { orchestrator:0, risk_assessor:1, validator:1, validator_retry:1, observer:3, reporter:4 };
      const idx = agentMap[evt.agent];
      if (idx != null) {
        this.setFlowStage(contentEl, idx);
        this.appendStep(contentEl, idx, content);
      }
      return;
    }

    // 任务计划 → 意图识别
    if (type === "task_plan") {
      this.setFlowStage(contentEl, 0);
      const text = typeof content === "string" ? content : JSON.stringify(content, null, 2);
      this.appendStep(contentEl, 0, text);
      return;
    }

    // 风险评估 / 命令校验 → 风险校验
    if (type === "risk_assessment" || type === "validation") {
      this.setFlowStage(contentEl, 1);
      const text = typeof content === "string" ? content : JSON.stringify(content, null, 2);
      this.appendStep(contentEl, 1, text);
      return;
    }

    // 工具调用 → 执行命令
    if (type === "tool_call") {
      this.setFlowStage(contentEl, 2);
      const cmd = evt.command || content;
      this.appendStep(contentEl, 2, cmd);
      return;
    }

    // 工具结果
    if (type === "tool_result") {
      // 执行了创建/删除等写操作后，若拓扑图打开则自动刷新
      if (evt && evt.success && evt.command) {
        this.refreshGraphAfterChange(evt.command);
      }
      const rtext = typeof content === "string" ? content : JSON.stringify(content);
      if (rtext) this.appendStep(contentEl, 2, rtext);
      return;
    }

    // 观察 → 观察结果
    if (type === "observation") {
      this.setFlowStage(contentEl, 3);
      const text = typeof content === "string" ? content : JSON.stringify(content, null, 2);
      this.appendStep(contentEl, 3, text);
      return;
    }

    // 自动修复通知
    if (type === "auto_fix") {
      const reason = typeof content === "string" ? content : JSON.stringify(content);
      this.appendStep(contentEl, 1, (this.t("autoFix") || "自动修复") + (reason ? ": " + reason : ""));
      this.setExecStatus(contentEl, this.t("autoFix") || "自动修复中...");
      return;
    }

    // 用户选择已应用
    if (type === "user_choice_applied") {
      return;
    }

    // 修复选项（多方案选择）
    if (type === "fix_options") {
      this.showFixOptions(contentEl, evt);
      return;
    }

    // 需要用户选择
    if (type === "choice_required") {
      // 存储 choice_id 供修复选项对话框使用
      contentEl.dataset.choiceId = evt.choice_id;
      return;
    }

    if (type === "confirm_required") {
      this.showConfirmDialog(contentEl, evt);
      return;
    }

    if (type === "confirm_id") {
      // 存储 confirm_id 供确认对话框使用
      contentEl.dataset.confirmId = evt.confirm_id;
      return;
    }

    if (type === "clarification_needed") {
      const question = evt.question || content;
      const answerArea = contentEl.querySelector(".answer-area");
      const target = answerArea || contentEl;
      target.innerHTML += `<div style="padding:12px;background:var(--bg-secondary);border-radius:8px;margin:8px 0;border-left:3px solid var(--accent)">
        <div style="font-weight:600;margin-bottom:4px">🤔 需要确认</div>
        <div style="font-size:14px">${this.escapeHtml(question)}</div>
      </div>`;
      this.scrollToBottom();
      return;
    }

    if (type === "error") {
      contentEl.innerHTML += `<div style="color:#ef4444">⚠️ ${this.escapeHtml(content)}</div>`;
      return;
    }

    if (type === "done" || type === "end") {
      this.markExecComplete(contentEl);
      this.attachDownloadButton(contentEl);
      this.collapseAllThinkingBlocks(contentEl);
      return;
    }
  },

  /**
   * 更新模型状态徽章
   */
  updateModelBadge(currentModel, models) {
    // 移除旧徽章
    const old = document.querySelector(".model-badge");
    if (old) old.remove();

    const badge = document.createElement("div");
    badge.className = "model-badge";
    badge.innerHTML = `
      <span class="model-badge-dot"></span>
      <span class="model-badge-text">${this.escapeHtml(currentModel)}</span>
    `;
    badge.title = models ? models.map(m => `${m.name} ${m.active ? "✓" : m.failed ? "✗" : ""}`).join("\n") : "";
    document.querySelector(".topbar-actions").prepend(badge);
  },

  /**
   * 模型切换 Toast
   */
  showModelSwitchToast(displayName) {
    let toast = document.getElementById("kdModelToast");
    if (!toast) {
      toast = document.createElement("div");
      toast.id = "kdModelToast";
      toast.style.cssText = `
        position: fixed; top: 80px; left: 50%; transform: translateX(-50%);
        background: #f59e0b; color: #fff; padding: 8px 16px;
        border-radius: 20px; font-size: 13px; z-index: 9999;
        transition: opacity 0.3s; opacity: 0; pointer-events: none;
        font-weight: 600;
      `;
      document.body.appendChild(toast);
    }
    toast.textContent = `🔄 已切换到 ${displayName}`;
    toast.style.opacity = "1";
    clearTimeout(toast._timeout);
    toast._timeout = setTimeout(() => { toast.style.opacity = "0"; }, 3000);
  },

  /**
   * 更新工作流进度条
   */
  updateWorkflowProgress(contentEl, stage, message) {
    let progressBar = contentEl.querySelector(".workflow-progress");
    if (!progressBar) {
      progressBar = document.createElement("div");
      progressBar.className = "workflow-progress";
      contentEl.appendChild(progressBar);
    }

    const stages = ["orchestrator", "risk_validator", "executor", "observer", "reporter"];
    const stageLabels = {
      orchestrator: "意图分析",
      risk_validator: "风险评估",
      executor: "执行命令",
      observer: "结果观察",
      reporter: "生成报告",
    };
    const currentIdx = stages.indexOf(stage);

    progressBar.innerHTML = stages.map((s, i) => {
      let cls = "pending";
      if (i < currentIdx) cls = "done";
      else if (i === currentIdx) cls = "active";
      return `<span class="wf-step ${cls}" title="${stageLabels[s]}">${stageLabels[s]}</span>`;
    }).join(" → ");

    // 更新当前步骤消息
    let msgEl = progressBar.querySelector(".wf-message");
    if (!msgEl) {
      msgEl = document.createElement("div");
      msgEl.className = "wf-message";
      progressBar.appendChild(msgEl);
    }
    msgEl.textContent = message || "";
  },

  /**
   * 思考链块：每个部分先展开滚动展示，然后自动折叠，再进入下一个
   * 支持流式追加：同一类型的思考块会复用并追加内容
   */
  appendThinkingBlock(contentEl, cls, title, content) {
    // 查找是否已有同类型的思考块（用于流式追加）
    let block = contentEl.querySelector(`.event-block.${cls}.animating`);

    if (block) {
      // 已有同类型块，追加内容
      const contentDiv = block.querySelector(".event-content");
      const textDiv = contentDiv.querySelector(".event-text");
      if (textDiv) {
        const current = textDiv.dataset.raw || "";
        const updated = current + content;
        textDiv.dataset.raw = updated;
        // 尝试解析 JSON 并美化显示
        textDiv.innerHTML = this.formatThinkingContent(updated);
      }
      // 重置自动折叠定时器
      this.resetCollapseTimer(block, contentDiv);
      this.scrollToBottom();
      return;
    }

    // 先折叠之前所有思考块，标记为完成
    const allBlocks = contentEl.querySelectorAll(".event-block");
    allBlocks.forEach((b) => {
      const cd = b.querySelector(".event-content");
      if (cd && !cd.classList.contains("collapsed")) {
        cd.classList.add("collapsed");
      }
      b.classList.remove("animating");
      b.classList.add("completed");
      const statusEl = b.querySelector(".event-status");
      if (statusEl) statusEl.textContent = "✓";
    });

    // 创建新的思考块
    block = document.createElement("div");
    block.className = `event-block ${cls} animating`;

    const titleEl = document.createElement("div");
    titleEl.className = "event-title";
    titleEl.innerHTML = `<span>${title}</span><span class="event-status">⏳</span>`;
    block.appendChild(titleEl);

    const contentDiv = document.createElement("div");
    contentDiv.className = "event-content";
    const textDiv = document.createElement("div");
    textDiv.className = "event-text";
    textDiv.dataset.raw = content || "";
    textDiv.innerHTML = this.formatThinkingContent(content || "");
    contentDiv.appendChild(textDiv);
    block.appendChild(contentDiv);

    // 如果存在 thinking-chain wrapper，将新块插入到其内部的 thinking-chain-inner 中
    const thinkingChain = contentEl.querySelector(".thinking-chain .thinking-chain-inner");
    if (thinkingChain) {
      thinkingChain.appendChild(block);
    } else {
      // 否则插入到 answer-area 之前（如果有的话）
      const answerArea = contentEl.querySelector(".answer-area");
      if (answerArea) {
        contentEl.insertBefore(block, answerArea);
      } else {
        contentEl.appendChild(block);
      }
    }

    this.scrollToBottom();

    // 点击标题切换折叠
    titleEl.addEventListener("click", () => {
      contentDiv.classList.toggle("collapsed");
    });

    // 自动折叠定时器
    this.resetCollapseTimer(block, contentDiv);
  },

  /**
   * 格式化思考链内容：尝试解析 JSON 美化，否则直接显示文本
   */
  formatThinkingContent(text) {
    if (!text) return "";
    // 尝试解析为 JSON 并美化
    try {
      const obj = JSON.parse(text);
      // 如果是对象，提取有意义的字段展示
      if (typeof obj === "object" && obj !== null) {
        // 优先展示 thought/reasoning/content/text 等字段
        const meaningful = obj.thought || obj.reasoning || obj.content || obj.text || obj.analysis || obj.summary || "";
        if (meaningful && typeof meaningful === "string") {
          return this.escapeHtml(meaningful).replace(/\n/g, "<br>");
        }
        // 否则美化 JSON
        return "<pre>" + this.escapeHtml(JSON.stringify(obj, null, 2)) + "</pre>";
      }
      return this.escapeHtml(String(obj));
    } catch (e) {
      // 不是 JSON，直接显示文本
      return this.escapeHtml(text).replace(/\n/g, "<br>");
    }
  },

  /**
   * 重置自动折叠定时器
   */
  resetCollapseTimer(block, contentDiv) {
    if (block._collapseTimer) {
      clearTimeout(block._collapseTimer);
    }
    const autoCollapseDelay = 8000;
    block._collapseTimer = setTimeout(() => {
      contentDiv.classList.add("collapsed");
      block.classList.remove("animating");
      block.classList.add("completed");
      const statusEl = block.querySelector(".event-status");
      if (statusEl) statusEl.textContent = "✓";
    }, autoCollapseDelay);
  },

  /**
   * 渲染思考链块（用于从历史记录恢复，始终折叠状态）
   */
  renderThinkingBlock(contentEl, cls, title, content) {
    const block = document.createElement("div");
    block.className = `event-block ${cls} completed`;

    const titleEl = document.createElement("div");
    titleEl.className = "event-title";
    titleEl.innerHTML = `<span>${title}</span><span class="event-status">✓</span>`;
    block.appendChild(titleEl);

    const contentDiv = document.createElement("div");
    contentDiv.className = "event-content collapsed";
    const textDiv = document.createElement("div");
    textDiv.className = "event-text";
    textDiv.dataset.raw = content || "";
    textDiv.innerHTML = this.formatThinkingContent(content || "");
    contentDiv.appendChild(textDiv);
    block.appendChild(contentDiv);

    // 插入到 contentEl 的最前面（answer-area 之前）
    const answerArea = contentEl.querySelector(".answer-area");
    if (answerArea) {
      contentEl.insertBefore(block, answerArea);
    } else {
      contentEl.prepend(block);
    }

    // 点击标题切换折叠
    titleEl.addEventListener("click", () => {
      contentDiv.classList.toggle("collapsed");
    });
  },

  /**
   * 流结束后折叠所有思考链块，合并成一个大的可折叠组
   * 大块展开后，里面是每个独立的小思考块（保持可折叠功能）
   */
  collapseAllThinkingBlocks(contentEl) {
    // 防重复：如果已经合并过了，不再处理
    if (contentEl.querySelector(".thinking-chain")) return;

    const allBlocks = contentEl.querySelectorAll(".event-block");
    if (allBlocks.length === 0) return;

    // 先折叠所有块，取消定时器
    allBlocks.forEach((block) => {
      const contentDiv = block.querySelector(".event-content");
      if (contentDiv) contentDiv.classList.add("collapsed");
      block.classList.remove("animating");
      block.classList.add("completed");
      const statusEl = block.querySelector(".event-status");
      if (statusEl) statusEl.textContent = "✓";
      if (block._collapseTimer) {
        clearTimeout(block._collapseTimer);
        block._collapseTimer = null;
      }
    });

    // 创建一个大的包裹容器
    const wrapper = document.createElement("div");
    wrapper.className = "event-block thinking-chain completed";

    const titleEl = document.createElement("div");
    titleEl.className = "event-title";
    titleEl.innerHTML = `<span>💭 思考链</span><span class="event-status">✓</span>`;
    wrapper.appendChild(titleEl);

    const contentDiv = document.createElement("div");
    contentDiv.className = "event-content collapsed";

    // 将所有小思考块移入大块内部
    const container = document.createElement("div");
    container.className = "thinking-chain-inner";
    allBlocks.forEach((block) => {
      container.appendChild(block);
    });
    contentDiv.appendChild(container);
    wrapper.appendChild(contentDiv);

    // 插入到 answer-area 之前
    const answerArea = contentEl.querySelector(".answer-area");
    if (answerArea) {
      contentEl.insertBefore(wrapper, answerArea);
    } else {
      contentEl.appendChild(wrapper);
    }

    // 点击标题切换折叠
    titleEl.addEventListener("click", () => {
      contentDiv.classList.toggle("collapsed");
    });

    // 折叠/隐藏工作流进度条
    const progressBar = contentEl.querySelector(".workflow-progress");
    if (progressBar) {
      progressBar.style.display = "none";
    }
  },

  /**
   * 显示修复选项对话框（多方案选择）
   */
  showFixOptions(contentEl, evt) {
    const options = evt.options || [];
    const message = evt.message || "🔍 发现以下可能的解决方案，请选择一个：";
    const observationSummary = evt.observation_summary || "";

    const dialog = document.createElement("div");
    dialog.className = "fix-options-dialog";
    dialog.style.cssText = `
      border: 2px solid var(--accent);
      border-radius: 8px;
      padding: 16px;
      margin: 8px 0;
      background: var(--bg-secondary);
    `;

    let html = `
      <div style="font-weight:700;color:var(--accent);margin-bottom:8px;font-size:15px">
        🔍 ${this.t("fixOptions") || "修复方案选择"}
      </div>
      <div style="margin-bottom:8px;font-size:13px;color:var(--text-secondary)">
        ${this.escapeHtml(message)}
      </div>
    `;

    if (observationSummary) {
      html += `<div style="margin-bottom:12px;padding:8px;background:var(--main-bg);border-radius:6px;font-size:12px;color:var(--text-tertiary)">
        <strong>📋 当前状态:</strong> ${this.escapeHtml(observationSummary)}
      </div>`;
    }

    html += `<div style="display:flex;flex-direction:column;gap:8px">`;
    options.forEach((opt, i) => {
      const confidencePercent = Math.round((opt.confidence || 0) * 100);
      const confidenceColor = confidencePercent >= 80 ? "#10b981" : confidencePercent >= 50 ? "#f59e0b" : "#ef4444";
      const isRecommended = i === 0;
      html += `
        <button class="fix-option-btn" data-choice="option_${i}" style="
          padding:12px;
          border:2px solid ${isRecommended ? 'var(--accent)' : 'var(--border)'};
          border-radius:8px;
          background:var(--main-bg);
          cursor:pointer;
          font-size:13px;
          text-align:left;
          transition: all 0.2s;
        ">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
            <span style="font-weight:600;color:var(--text-primary)">
              ${isRecommended ? '✅ ' : '💡 '}${this.escapeHtml(opt.label || opt.description || `方案 ${i+1}`)}
            </span>
            <span style="font-size:11px;color:${confidenceColor};font-weight:600">
              信心度: ${confidencePercent}%
            </span>
          </div>
          ${opt.command ? `<div style="font-size:12px;color:var(--text-tertiary);margin-top:4px"><code style="background:var(--bg-secondary);padding:2px 6px;border-radius:4px;font-size:11px">${this.escapeHtml(opt.command)}</code></div>` : ""}
        </button>
      `;
    });
    html += `</div>`;

    // 添加跳过和取消按钮
    html += `
      <div style="margin-top:12px;display:flex;gap:8px;justify-content:center">
        <button class="fix-option-btn" data-choice="skip" style="
          padding:8px 16px;
          border:1px solid var(--border);
          border-radius:6px;
          background:transparent;
          color:var(--text-tertiary);
          cursor:pointer;
          font-size:12px;
        ">⏭️ 跳过</button>
        <button class="fix-option-btn" data-choice="cancel" style="
          padding:8px 16px;
          border:1px solid #ef4444;
          border-radius:6px;
          background:transparent;
          color:#ef4444;
          cursor:pointer;
          font-size:12px;
        ">❌ 取消</button>
      </div>
    `;

    dialog.innerHTML = html;
    contentEl.appendChild(dialog);
    this.scrollToBottom();

    // 绑定按钮事件
    dialog.querySelectorAll(".fix-option-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const choice = btn.dataset.choice;
        const choiceId = contentEl.dataset.choiceId;
        if (!choiceId) {
          this.showToast("选择 ID 缺失");
          return;
        }
        // 禁用所有按钮
        dialog.querySelectorAll(".fix-option-btn").forEach((b) => { b.disabled = true; b.style.opacity = "0.5"; });
        try {
          await fetch(`/chat/confirm?confirm_id=${choiceId}&choice=${choice}`, { method: "POST" });
        } catch (e) {
          console.error("fix option error:", e);
        }
        // 更新对话框状态
        if (choice === "skip") {
          dialog.innerHTML = `<div style="text-align:center;padding:8px;color:var(--text-tertiary);font-size:13px">⏭️ 已跳过，正在生成报告...</div>`;
        } else if (choice === "cancel") {
          dialog.innerHTML = `<div style="text-align:center;padding:8px;color:#ef4444;font-size:13px">❌ 已取消，正在生成报告...</div>`;
        } else {
          dialog.innerHTML = `<div style="text-align:center;padding:8px;color:var(--text-tertiary);font-size:13px">✓ 已选择方案，正在执行...</div>`;
        }
      });
    });
  },

  /**
   * 显示危险命令确认对话框
   */
  showConfirmDialog(contentEl, evt) {
    const options = evt.options || [];
    const riskLevel = evt.risk_level || "dangerous";
    const command = evt.command || "";
    const reason = evt.reason || "";
    const suggestions = evt.suggestions || "";

    const riskColor = riskLevel === "critical" ? "#ef4444" : "#f59e0b";
    const riskIcon = riskLevel === "critical" ? "🚫" : "⚠️";

    const dialog = document.createElement("div");
    dialog.className = "confirm-dialog";
    dialog.style.cssText = `
      border: 2px solid ${riskColor};
      border-radius: 8px;
      padding: 16px;
      margin: 8px 0;
      background: var(--bg-secondary);
    `;

    let html = `
      <div style="font-weight:700;color:${riskColor};margin-bottom:8px;font-size:15px">
        ${riskIcon} ${riskLevel === "critical" ? "极高风险操作" : "高风险操作"} — 需要确认
      </div>
      <div style="margin-bottom:8px;font-size:13px;color:var(--text-secondary)">
        <strong>命令:</strong> <code style="background:var(--main-bg);padding:2px 6px;border-radius:4px">${this.escapeHtml(command)}</code>
      </div>
    `;

    if (reason) {
      html += `<div style="margin-bottom:8px;font-size:13px;color:var(--text-secondary)"><strong>风险:</strong> ${this.escapeHtml(reason)}</div>`;
    }
    if (suggestions) {
      html += `<div style="margin-bottom:12px;font-size:13px;color:var(--text-secondary)"><strong>建议:</strong> ${this.escapeHtml(suggestions)}</div>`;
    }

    html += `<div style="display:flex;flex-direction:column;gap:8px">`;
    options.forEach((opt) => {
      const bgColor = opt.value === "execute" ? riskColor : opt.value === "cancel" ? "var(--main-bg)" : "var(--accent)";
      const textColor = opt.value === "cancel" ? riskColor : "#fff";
      const borderColor = opt.value === "cancel" ? riskColor : "transparent";
      html += `<button class="confirm-option-btn" data-choice="${opt.value}" style="padding:10px;border:1px solid ${borderColor};border-radius:6px;background:${bgColor};color:${textColor};cursor:pointer;font-size:13px;text-align:left;font-weight:600">${opt.label}</button>`;
    });
    html += `</div>`;

    dialog.innerHTML = html;
    contentEl.appendChild(dialog);
    this.scrollToBottom();

    // 绑定按钮事件
    dialog.querySelectorAll(".confirm-option-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const choice = btn.dataset.choice;
        const confirmId = contentEl.dataset.confirmId;
        if (!confirmId) {
          this.showToast("确认 ID 缺失");
          return;
        }
        // 禁用所有按钮
        dialog.querySelectorAll(".confirm-option-btn").forEach((b) => { b.disabled = true; b.style.opacity = "0.5"; });
        try {
          await fetch(`/chat/confirm?confirm_id=${confirmId}&choice=${choice}`, { method: "POST" });
        } catch (e) {
          console.error("confirm error:", e);
        }
        // 对话框会被后续流式内容替换
        dialog.innerHTML = `<div style="text-align:center;padding:8px;color:var(--text-tertiary);font-size:13px">✓ 已选择，等待执行...</div>`;
      });
    });
  },

  toggleWebSearch() {
    this.webSearch = !this.webSearch;
    this.el.netBtn.classList.toggle("active", this.webSearch);
    this.el.netBtn.title = this.webSearch ? "联网搜索（已开启）" : "联网搜索";
    this.showToast(this.webSearch ? "🌐 已开启联网搜索" : "已关闭联网搜索");
  },

  stopStream() {
    if (this.state.abortCtrl) {
      this.state.abortCtrl.abort();
    }
  },

  toggleStreamingUI(on) {
    this.el.sendBtn.style.display = on ? "none" : "";
    this.el.stopBtn.style.display = on ? "" : "none";
  },

  /* ───── 拓扑图 ───── */
  async rebuildTopology() {
    const btn = this.el.graphRefreshBtn;
    const hint = this.el.graphRefreshHint;
    if (!btn || btn.classList.contains("loading")) return;
    try {
      btn.classList.add("loading");
      if (hint) hint.textContent = "正在从集群重建拓扑…";
      const res = await fetch(`/graph/rebuild?user_id=${encodeURIComponent(this.state.userId)}`, { method: "POST" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (hint) hint.textContent = "重建完成：" + ((data && data.nodes) || data.created_edges || "OK");
      await this.loadTopology();
    } catch (e) {
      if (hint) hint.textContent = "重建失败: " + e.message;
      console.error(e);
    } finally {
      btn.classList.remove("loading");
    }
  },


  openGraphPanel() {
    const panel = this.el.graphPanel;
    if (!panel || panel.classList.contains("open")) return;

    // 面板固定停靠在最右侧，从右侧滑出
    panel.classList.add("from-right");
    panel.classList.remove("from-left");
    panel.style.left = "auto";
    panel.style.right = "0px";
    panel.style.transform = "translateX(105%)";
    if (this.el.graphReopenTab) this.el.graphReopenTab.style.display = "none";
    void panel.offsetWidth; // 触发过渡
    panel.style.transform = "translateX(0)";
    panel.classList.add("open");
    if (this.el.graphCollapseTab) this.el.graphCollapseTab.textContent = "\u203a";
    this.loadTopology();
    this.loadTopologyInterval();
  },

  closeGraphPanel() {
    const panel = this.el.graphPanel;
    if (!panel || !panel.classList.contains("open")) return;
    // 收起：向右侧滑出
    panel.style.transform = "translateX(105%)";
    panel.classList.remove("open");
    // 折叠后显示可再展开的把手(右侧)
    const rt = this.el.graphReopenTab;
    if (rt) {
      // 右侧停靠：贴着屏幕右缘(平边朝边缘)，圆角朝内，箭头指向展开方向(向左)
      rt.classList.remove("right");
      rt.style.right = "0px";
      rt.style.left = "auto";
      rt.textContent = "\u2039";
      rt.style.display = "flex";
    }
    this.popFloatBall();
  },

    popFloatBall() {
    const ball = this.el.graphFloatBall;
    if (!ball) return;
    ball.classList.remove("pop");
    void ball.offsetWidth; // 重新触发动画
    ball.classList.add("pop");
    setTimeout(() => ball.classList.remove("pop"), 500);
  },

  async loadTopologyInterval() {
    try {
      const res = await fetch(`/graph/settings?user_id=${encodeURIComponent(this.state.userId)}`);
      if (!res.ok) return;
      const data = await res.json();
      const sec = data.interval_seconds || 300;
      if (this.el.graphIntervalInput) this.el.graphIntervalInput.value = Math.max(1, Math.round(sec / 60));
    } catch (e) { /* 忽略 */ }
  },

  async saveTopologyInterval() {
    const input = this.el.graphIntervalInput;
    if (!input) return;
    let mins = parseInt(input.value, 10);
    if (isNaN(mins) || mins < 1) mins = 5;
    if (mins > 60) mins = 60;
    const hint = this.el.graphRefreshHint;
    try {
      const res = await fetch(`/graph/settings?user_id=${encodeURIComponent(this.state.userId)}&interval_seconds=${mins * 60}`, { method: "POST" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      input.value = Math.round((data.interval_seconds || mins * 60) / 60);
      if (hint) hint.textContent = `已设为每 ${Math.round((data.interval_seconds || mins * 60) / 60)} 分钟自动重建`;
    } catch (e) {
      if (hint) hint.textContent = "保存间隔失败: " + e.message;
    }
  },

  initFloatBall() {
    const ball = this.el.graphFloatBall;
    if (!ball) return;
    ball.addEventListener("click", () => {
      if (this._ballDragged) { this._ballDragged = false; return; }
      if (this.el.graphPanel.classList.contains("open")) {
        this.closeGraphPanel();
      } else {
        this.openGraphPanel();
      }
    });
    // 拖动（Pointer Events）
    let dragging = false, moved = false, sx = 0, sy = 0, ox = 0, oy = 0;
    ball.addEventListener("pointerdown", (e) => {
      dragging = true; moved = false;
      sx = e.clientX; sy = e.clientY;
      const r = ball.getBoundingClientRect();
      ox = r.left; oy = r.top;
      ball.setPointerCapture && ball.setPointerCapture(e.pointerId);
    });
    ball.addEventListener("pointermove", (e) => {
      if (!dragging) return;
      const dx = e.clientX - sx, dy = e.clientY - sy;
      if (Math.abs(dx) + Math.abs(dy) > 3) moved = true;
      const maxX = window.innerWidth - (ball.offsetWidth || 56) - 8;
      const maxY = window.innerHeight - (ball.offsetHeight || 56) - 8;
      ball.style.left = Math.max(8, Math.min(maxX, ox + dx)) + "px";
      ball.style.top = Math.max(8, Math.min(maxY, oy + dy)) + "px";
      ball.style.right = "auto";
    });
    const endDrag = () => {
      if (dragging && moved) this._ballDragged = true;
      dragging = false;
    };
    ball.addEventListener("pointerup", endDrag);
    ball.addEventListener("pointercancel", () => { dragging = false; });
  },

  toggleGraphCollapse(id) {
    const set = this._graphCollapsed = this._graphCollapsed || new Set();
    if (set.has(id)) set.delete(id); else set.add(id);
    if (this._graphData) this.renderGraph(this._graphData);
  },

  setGraphZoom(z) {
    this._graphZoom = Math.max(0.3, Math.min(3, z));
    this.applyGraphZoom();
  },

  stepGraphZoom(delta) {
    const cur = this._graphZoom != null ? this._graphZoom : 1;
    this.setGraphZoom(Math.round((cur + delta) * 100) / 100);
  },

  applyGraphZoom() {
    const z = this._graphZoom != null ? this._graphZoom : 1;
    if (this.el.graphZoomLabel) this.el.graphZoomLabel.textContent = Math.round(z * 100) + "%";
    const svg = this._graphSvg;
    const g = this._graphG;
    if (!svg || !g) return;
    const bw = this._graphBaseW || 1, bh = this._graphBaseH || 1;
    svg.setAttribute("width", Math.round(bw * z));
    svg.setAttribute("height", Math.round(bh * z));
    g.setAttribute("transform", `scale(${z})`);
    g.setAttribute("transform-origin", "0 0");
  },

  async loadTopology() {
    const btn = this.el.graphRefreshBtn;
    try {
      btn.classList.add("loading");
      const res = await fetch(`/graph/topology?user_id=${encodeURIComponent(this.state.userId)}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      this._graphData = data;
      this.renderGraph(data);
    } catch (e) {
      this.el.graphEmpty.style.display = "block";
      this.el.graphEmpty.textContent = "加载拓扑失败: " + e.message;
      this.el.graphCanvas.innerHTML = "";
    } finally {
      btn.classList.remove("loading");
    }
  },

  renderGraphLegend() {
    const el = this.el.graphLegend;
    if (!el) return;
    const groups = [
      ["命名空间", "#3b82f6"],
      ["节点 Node", "#6366f1"],
      ["工作负载 Deploy/STS/DS/Job/CronJob", "#22c55e"],
      ["Pod", "#06b6d4"],
      ["ReplicaSet", "#14b8a6"],
      ["Service/Endpoints/Ingress", "#f59e0b"],
      ["配置 ConfigMap/Secret", "#64748b"],
      ["存储 PVC/PV/StorageClass", "#b45309"],
      ["权限 RBAC", "#ec4899"],
    ];
    el.innerHTML = groups.map((g) =>
      `<span class="legend-item"><i style="background:${g[1]}"></i>${g[0]}</span>`
    ).join("");
  },

  renderGraph(data) {
    const canvas = this.el.graphCanvas;
    const empty = this.el.graphEmpty;
    let nodes = (data && data.nodes) ? data.nodes : [];
    let links = (data && data.links) ? data.links : [];
    if (this.el.graphPanelSub) {
      this.el.graphPanelSub.textContent = `${nodes.length} 节点 · ${links.length} 关系`;
    }
    if (!nodes.length) {
      canvas.innerHTML = "";
      empty.style.display = "block";
      empty.textContent = "暂无拓扑数据，先连接主机或让 AI 执行一些查询";
      return;
    }
    empty.style.display = "none";
    this.renderGraphLegend();

    // ── 折叠逻辑：隐藏被折叠资源（含命名空间）的下级 ──
    this._graphCollapsed = this._graphCollapsed || new Set();
    const childMap = {};
    links.forEach((l) => {
      if (l.rel === "BELONGS_TO" || l.rel === "BACKS") {
        (childMap[l.target] = childMap[l.target] || []).push(l.source);
      }
    });
    const hasKids = (id) => (childMap[id] || []).length > 0;
    const hiddenIds = new Set();
    const hst = [];
    this._graphCollapsed.forEach((id) => hst.push(id));
    while (hst.length) {
      const hid = hst.pop();
      (childMap[hid] || []).forEach((c) => {
        if (!hiddenIds.has(c)) { hiddenIds.add(c); hst.push(c); }
      });
    }
    if (hiddenIds.size) {
      links = links.filter((l) => !hiddenIds.has(l.source) && !hiddenIds.has(l.target));
      nodes = nodes.filter((n) => !hiddenIds.has(n.id));
    }

    const COLOR = {
      Namespace:"#3b82f6",
      Node:"#6366f1",
      Deployment:"#22c55e", StatefulSet:"#22c55e", DaemonSet:"#22c55e", Job:"#22c55e", CronJob:"#22c55e",
      ReplicaSet:"#14b8a6", Pod:"#06b6d4", Service:"#f59e0b", Endpoints:"#f59e0b", Ingress:"#f59e0b",
      ConfigMap:"#94a3b8", Secret:"#64748b", Role:"#f43f5e", ClusterRole:"#f43f5e",
      RoleBinding:"#ec4899", ClusterRoleBinding:"#ec4899", ServiceAccount:"#a855f7", Group:"#d946ef", ClusterUser:"#e879f9",
      PersistentVolumeClaim:"#b45309", PersistentVolume:"#92500e", StorageClass:"#a16207",
    };
    const REL_COLOR = {
      BELONGS_TO:"#8b93a7", GRANTS:"#f43f5e", ASSIGNED_TO:"#ec4899", SELECTS:"#f59e0b",
      EXPOSES:"#f59e0b", USES:"#94a3b8", DEPENDS_ON:"#94a3b8", RUNS_IN:"#3b82f6", RUNS_ON:"#3b82f6",
    };
    const color = (t) => COLOR[t] || "#6b7280";
    const relColor = (r) => REL_COLOR[r] || "#8b93a7";

    const depth = {};
    nodes.forEach(n => { depth[n.id] = 0; });
    for (let pass = 0; pass < 12; pass++) {
      let changed = false;
      for (const l of links) {
        if ((l.rel === "BELONGS_TO" || l.rel === "BACKS") && depth[l.source] != null && depth[l.target] != null) {
          if (depth[l.source] < depth[l.target] + 1) {
            depth[l.source] = depth[l.target] + 1;
            changed = true;
          }
        }
      }
      if (!changed) break;
    }

    const cols = {};
    nodes.forEach(n => { const d = depth[n.id] || 0; (cols[d] = cols[d] || []).push(n); });
    const depths = Object.keys(cols).map(Number).sort((a, b) => a - b);

    const COLW = 220, ROWH = 102, NODEW = 186, NODEH = 58, PAD = 24;
    const W = depths.length * COLW;
    let maxRows = 1;
    depths.forEach(d => { maxRows = Math.max(maxRows, cols[d].length); });
    const H = Math.max(200, maxRows * ROWH);

    const pos = {};
    depths.forEach((d, ci) => {
      const items = cols[d].slice().sort((a, b) => a.name.localeCompare(b.name));
      const cx = PAD + ci * COLW;
      items.forEach((n, ri) => {
        let py = null, cnt = 0;
        for (const l of links) {
          if ((l.rel === "BELONGS_TO" || l.rel === "BACKS")) {
            if (l.source === n.id && pos[l.target]) { py = (py||0) + pos[l.target].y; cnt++; }
          }
        }
        let y;
        if (py != null && cnt) {
          y = Math.round(py / cnt);
        } else {
          y = PAD + ri * ROWH + (ROWH - NODEH) / 2;
        }
        y = Math.max(PAD, Math.min(H - NODEH - PAD, y));
        pos[n.id] = { x: cx, y, cx: cx + NODEW / 2, cy: y + NODEH / 2 };
      });
      const sorted = items.slice().sort((a, b) => pos[a.id].y - pos[b.id].y);
      let lastY = -1e9;
      for (const n of sorted) {
        if (pos[n.id].y < lastY + ROWH) pos[n.id].y = lastY + ROWH;
        lastY = pos[n.id].y;
        pos[n.id].cy = pos[n.id].y + NODEH / 2;
      }
    });

    // 上级资源映射（BELONGS_TO/BACKS: source 属于 target）
    const byId = {};
    nodes.forEach((nd) => { byId[nd.id] = nd; });
    const parents = {};
    links.forEach((l) => {
      if (l.rel === "BELONGS_TO" || l.rel === "BACKS") {
        if (byId[l.source] && byId[l.target]) {
          (parents[l.source] = parents[l.source] || []).push(byId[l.target]);
        }
      }
    });
    Object.keys(parents).forEach((k) => parents[k].sort((a, b) => a.type.localeCompare(b.type)));

    const svgNS = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(svgNS, "svg");
    this._graphBaseW = W + PAD * 2;
    this._graphBaseH = H + PAD * 2;
    const zoomG = document.createElementNS(svgNS, "g");
    svg.appendChild(zoomG);
    this._graphSvg = svg;
    this._graphG = zoomG;

    // 按层级绘制分栏背景，增强层次感
    depths.forEach((d, ci) => {
      const col = document.createElementNS(svgNS, "rect");
      col.setAttribute("x", PAD + ci * COLW - 10);
      col.setAttribute("y", PAD - 10);
      col.setAttribute("width", COLW + 20);
      col.setAttribute("height", Math.max(H - PAD, 120) + 20);
      col.setAttribute("rx", 12);
      col.setAttribute("class", "g-column");
      zoomG.appendChild(col);
    });

    for (const l of links) {
      const a = pos[l.source], b = pos[l.target];
      if (!a || !b) continue;
      const line = document.createElementNS(svgNS, "line");
      line.setAttribute("x1", a.cx); line.setAttribute("y1", a.cy);
      line.setAttribute("x2", b.cx); line.setAttribute("y2", b.cy);
      line.setAttribute("class", "g-edge");
      line.setAttribute("stroke", relColor(l.rel));
      if (l.rel === "BELONGS_TO") line.setAttribute("stroke-dasharray", "4 3");
      zoomG.appendChild(line);
      if (l.rel !== "BELONGS_TO" && l.rel !== "BACKS") {
        const lbl = document.createElementNS(svgNS, "text");
        lbl.setAttribute("x", (a.cx + b.cx) / 2);
        lbl.setAttribute("y", (a.cy + b.cy) / 2 - 4);
        lbl.setAttribute("text-anchor", "middle");
        lbl.setAttribute("class", "g-edge-label");
        lbl.setAttribute("fill", relColor(l.rel));
        lbl.setAttribute("style", "paint-order:stroke;stroke:#14141d;stroke-width:2px;stroke-linejoin:round");
        lbl.textContent = l.rel;
        zoomG.appendChild(lbl);
      }
    }

    for (const n of nodes) {
      const p = pos[n.id];
      if (!p) continue;
      const g = document.createElementNS(svgNS, "g");
      g.setAttribute("class", "g-node");
      g.setAttribute("transform", `translate(${p.x},${p.y})`);
      const rect = document.createElementNS(svgNS, "rect");
      rect.setAttribute("width", NODEW); rect.setAttribute("height", NODEH);
      rect.setAttribute("rx", 9); rect.setAttribute("fill", color(n.type));
      const title = document.createElementNS(svgNS, "title");
      const parList = (parents[n.id] || []).map((pp) => `${pp.type} / ${pp.name}`).join(", ");
      title.textContent = `${n.type} / ${n.name}` + (parList ? `\n上级资源: ${parList}` : "");
      rect.appendChild(title);
      // 类型徽标（资源种类写清楚）
      const tlabel = document.createElementNS(svgNS, "text");
      tlabel.setAttribute("x", NODEW / 2); tlabel.setAttribute("y", 19);
      tlabel.setAttribute("text-anchor", "middle");
      tlabel.setAttribute("class", "g-type");
      tlabel.textContent = n.type;
      // 资源名称
      const nameText = document.createElementNS(svgNS, "text");
      nameText.setAttribute("x", NODEW / 2); nameText.setAttribute("y", 42);
      nameText.setAttribute("text-anchor", "middle");
      nameText.setAttribute("class", "g-name");
      nameText.textContent = n.name.length > 24 ? n.name.slice(0, 22) + "…" : n.name;
      g.appendChild(rect); g.appendChild(tlabel); g.appendChild(nameText);

      // 折叠按钮：当该资源（如命名空间）有下级时显示 +/-
      if (hasKids(n.id)) {
        const isCollapsed = this._graphCollapsed.has(n.id);
        const tgl = document.createElementNS(svgNS, "g");
        tgl.setAttribute("class", "g-collapse");
        const tc = document.createElementNS(svgNS, "circle");
        tc.setAttribute("cx", NODEW - 12); tc.setAttribute("cy", 15);
        tc.setAttribute("r", 8);
        tc.setAttribute("fill", "rgba(59,130,246,.88)");
        tc.setAttribute("stroke", "rgba(255,255,255,.9)"); tc.setAttribute("stroke-width", 1.4);
        const tt = document.createElementNS(svgNS, "text");
        tt.setAttribute("x", NODEW - 12); tt.setAttribute("y", 19);
        tt.setAttribute("text-anchor", "middle"); tt.setAttribute("font-size", 12);
        tt.setAttribute("fill", "#fff"); tt.setAttribute("class", "g-collapse-text");
        tt.textContent = isCollapsed ? "+" : "\u2212";
        const tTip = document.createElementNS(svgNS, "title");
        tTip.textContent = isCollapsed ? "展开下级资源" : "折叠下级资源";
        tgl.appendChild(tc); tgl.appendChild(tt); tgl.appendChild(tTip);
        tgl.addEventListener("click", (ev) => { ev.stopPropagation(); this.toggleGraphCollapse(n.id); });
        g.appendChild(tgl);
      }

      zoomG.appendChild(g);
    }

    this._graphZoom = (this._graphZoom != null) ? this._graphZoom : 1;
    this.applyGraphZoom();
    canvas.innerHTML = "";
    canvas.appendChild(svg);
  },

  refreshGraphAfterChange(commandStr) {
    if (!this.el.graphPanel.classList.contains("open")) return;
    const cmd = (commandStr || "").toLowerCase();
    if (/create|apply|delete|scale|run|patch|edit|rollout|label|annotate|expose/.test(cmd)) {
      clearTimeout(this._graphRefreshTimer);
      this._graphRefreshTimer = setTimeout(() => this.rebuildTopology(), 400);
    }
  },

  /* ───── 文件 / 文档聊天 ───── */

  handleFile(e) {
    const file = e.target.files[0];
    if (!file) return;
    this.state.attachedFile = file;
    this.el.fileTagText.textContent = file.name;
    this.el.fileTag.style.display = "inline-flex";
    this.el.sendBtn.disabled = false;
  },

  clearFile() {
    this.state.attachedFile = null;
    this.el.fileInput.value = "";
    this.el.fileTag.style.display = "none";
    this.autoResize(this.el.messageInput);
  },

  async sendWithDocument(text) {
    const file = this.state.attachedFile;
    this.el.chatMessages.appendChild(this.createMessageEl("user", `${text}\n\n📎 ${this.t("attach") || "附件"}: ${file.name}`));
    this.clearFile();
    this.el.messageInput.value = "";
    this.autoResize(this.el.messageInput);
    this.scrollToBottom();

    // 创建助手消息占位（含执行/思考链模块 + 流式答案区）
    const assistantEl = this.createMessageEl("assistant", "");
    const contentEl = assistantEl.querySelector(".message-content");
    const answerArea = contentEl.querySelector(".answer-area");
    this.ensureExecBox(contentEl);
    if (answerArea) answerArea.classList.add("typing-cursor");
    this.el.chatMessages.appendChild(assistantEl);
    this.scrollToBottom();

    this.state.streaming = true;
    this.toggleStreamingUI(true);
    this.state.abortCtrl = new AbortController();

    const formData = new FormData();
    formData.append("user_id", this.state.userId);
    formData.append("message", text);
    formData.append("file", file);

    let fullAnswer = "";
    try {
      const res = await fetch("/chat_with_document", {
        method: "POST",
        body: formData,
        signal: this.state.abortCtrl.signal,
      });
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const payload = line.slice(6).trim();
          if (!payload) continue;
          try {
            const evt = JSON.parse(payload);
            this.handleStreamEvent(evt, contentEl, assistantEl);
            if (evt.type === "answer_chunk") fullAnswer += evt.content || "";
            if (evt.type === "conv_created") this.state.convId = evt.conv_id;
          } catch (e) {
            // 忽略单条解析错误
          }
        }
      }
    } catch (e) {
      if (e.name !== "AbortError") {
        const aa = contentEl.querySelector(".answer-area");
        if (aa) aa.innerHTML += `<br><em>⚠️ ${this.escapeHtml(this.t("error"))}: ${this.escapeHtml(e.message)}</em>`;
        else contentEl.textContent = "⚠️ " + this.t("error") + ": " + e.message;
      }
    } finally {
      if (answerArea) answerArea.classList.remove("typing-cursor");
      contentEl.classList.remove("typing-cursor");
      this.state.streaming = false;
      this.toggleStreamingUI(false);
      if (fullAnswer) this.state.messages.push({ role: "assistant", content: fullAnswer });
      this.collapseExecBox(contentEl);
      this.loadConversations();
      this.scrollToBottom();
    }
  },

  /* ───── 知识库 Modal ───── */
  async openKnowledgeModal() {
    this.el.knowledgeModal.style.display = "flex";
    this.el.knowledgeModalBody.innerHTML = `<p class="loading-text">${this.t("loading")}</p>`;
    try {
      const res = await fetch(`/knowledge/kb/list?owner=${encodeURIComponent(this.state.userId)}`);
      const data = await res.json();
      this.renderKnowledgeList(data.success ? data.data : []);
    } catch (e) {
      this.el.knowledgeModalBody.innerHTML = `<p class="loading-text">${this.t("loadFailed")}: ${this.escapeHtml(e.message)}</p>`;
    }
  },

  renderKnowledgeList(bases) {
    const body = this.el.knowledgeModalBody;

    // 新建知识库按钮
    const createBtn = document.createElement("button");
    createBtn.className = "kb-create-btn";
    createBtn.textContent = "+ " + (this.t("newKnowledgeBase") || "新建知识库");
    createBtn.style.cssText = "width:100%;padding:10px;margin-bottom:12px;background:var(--accent);color:#fff;border:none;border-radius:8px;cursor:pointer;font-size:14px;font-weight:600";
    createBtn.addEventListener("click", () => this.showCreateKBForm());

    if (!bases || !bases.length) {
      body.innerHTML = `<p class="loading-text">${this.t("noKnowledge")}</p>`;
      body.appendChild(createBtn);
      return;
    }

    const listHtml = bases.map((kb) => `
      <div class="kb-item" data-kb-id="${this.escapeHtml(kb.id)}" style="padding:12px;border:1px solid var(--border);border-radius:8px;margin-bottom:8px;display:flex;justify-content:space-between;align-items:center">
        <div style="flex:1">
          <div style="font-weight:600">${this.escapeHtml(kb.name)}</div>
          <div style="font-size:13px;color:var(--text-tertiary)">${this.escapeHtml(kb.description || "")}</div>
        </div>
        <div class="kb-actions" style="display:flex;gap:6px;flex-shrink:0;margin-left:12px">
          <button class="kb-upload-btn" data-kb-id="${this.escapeHtml(kb.id)}" data-kb-name="${this.escapeHtml(kb.name)}" style="padding:4px 8px;border:1px solid var(--accent);border-radius:4px;background:var(--accent);color:#fff;cursor:pointer;font-size:12px">📁 上传文件</button>
          <button class="kb-edit-btn" data-kb-id="${this.escapeHtml(kb.id)}" data-kb-name="${this.escapeHtml(kb.name)}" data-kb-desc="${this.escapeHtml(kb.description || "")}" style="padding:4px 8px;border:1px solid var(--border);border-radius:4px;background:var(--main-bg);cursor:pointer;font-size:12px">${this.t("rename") || "重命名"}</button>
          <button class="kb-delete-btn" data-kb-id="${this.escapeHtml(kb.id)}" style="padding:4px 8px;border:1px solid #ef4444;border-radius:4px;background:var(--main-bg);color:#ef4444;cursor:pointer;font-size:12px">${this.t("delete") || "删除"}</button>
        </div>
      </div>
    `).join("");

    body.innerHTML = listHtml;
    body.appendChild(createBtn);

    // 绑定上传按钮
    body.querySelectorAll(".kb-upload-btn").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        this.showUploadForm(btn.dataset.kbId, btn.dataset.kbName);
      });
    });

    // 绑定编辑按钮
    body.querySelectorAll(".kb-edit-btn").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        this.showEditKBForm(btn.dataset.kbId, btn.dataset.kbName, btn.dataset.kbDesc);
      });
    });

    // 绑定删除按钮
    body.querySelectorAll(".kb-delete-btn").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        this.deleteKnowledgeBase(btn.dataset.kbId);
      });
    });
  },

  showUploadForm(kbId, kbName) {
    const body = this.el.knowledgeModalBody;
    body.innerHTML = `
      <div class="kb-upload-form">
        <h4 style="margin:0 0 12px 0">📁 上传文件到: ${this.escapeHtml(kbName)}</h4>
        <div style="margin-bottom:12px;padding:16px;border:2px dashed var(--border);border-radius:8px;text-align:center;cursor:pointer" id="kbDropZone">
          <p style="margin:0;color:var(--text-tertiary)">点击选择文件或拖拽文件到此处</p>
          <p style="margin:4px 0 0 0;font-size:12px;color:var(--text-tertiary)">支持 PDF, Word, Markdown, TXT, 日志等</p>
          <input type="file" id="kbFileInput" multiple style="display:none">
        </div>
        <div id="kbFileList" style="margin-bottom:12px"></div>
        <div style="display:flex;gap:8px">
          <button id="kbUploadSubmit" style="flex:1;padding:8px;background:var(--accent);color:#fff;border:none;border-radius:6px;cursor:pointer;font-weight:600" disabled>开始上传</button>
          <button id="kbUploadCancel" style="flex:1;padding:8px;background:var(--main-bg);border:1px solid var(--border);border-radius:6px;cursor:pointer">返回</button>
        </div>
        <div id="kbUploadProgress" style="margin-top:12px"></div>
      </div>
    `;

    const fileInput = document.getElementById("kbFileInput");
    const dropZone = document.getElementById("kbDropZone");
    const submitBtn = document.getElementById("kbUploadSubmit");
    const fileListEl = document.getElementById("kbFileList");
    let selectedFiles = [];

    // 点击选择文件
    dropZone.addEventListener("click", () => fileInput.click());

    // 拖拽支持
    dropZone.addEventListener("dragover", (e) => {
      e.preventDefault();
      dropZone.style.borderColor = "var(--accent)";
    });
    dropZone.addEventListener("dragleave", () => {
      dropZone.style.borderColor = "var(--border)";
    });
    dropZone.addEventListener("drop", (e) => {
      e.preventDefault();
      dropZone.style.borderColor = "var(--border)";
      if (e.dataTransfer.files.length > 0) {
        selectedFiles = Array.from(e.dataTransfer.files);
        this.renderKBFileList(fileListEl, selectedFiles);
        submitBtn.disabled = false;
      }
    });

    fileInput.addEventListener("change", (e) => {
      if (e.target.files.length > 0) {
        // 追加到已有列表，而不是替换
        const newFiles = Array.from(e.target.files);
        selectedFiles = selectedFiles.concat(newFiles);
        this.renderKBFileList(fileListEl, selectedFiles);
        submitBtn.disabled = false;
        // 清空 input value 以便可以重复选择同一文件
        fileInput.value = "";
      }
    });

    submitBtn.addEventListener("click", () => this.uploadFilesToKB(kbId, selectedFiles));
    document.getElementById("kbUploadCancel").addEventListener("click", () => this.openKnowledgeModal());
  },

  renderKBFileList(container, files) {
    container.innerHTML = files.map((f, i) => `
      <div class="kb-file-item" data-idx="${i}" style="display:flex;justify-content:space-between;align-items:center;padding:6px 8px;border:1px solid var(--border);border-radius:4px;margin-bottom:4px">
        <span style="font-size:13px;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">📄 ${this.escapeHtml(f.name)}</span>
        <span style="font-size:12px;color:var(--text-tertiary);margin:0 8px;flex-shrink:0">${(f.size / 1024).toFixed(1)} KB</span>
        <button class="kb-file-remove" data-idx="${i}" style="padding:2px 6px;border:none;background:transparent;color:#ef4444;cursor:pointer;font-size:14px;flex-shrink:0">✕</button>
      </div>
    `).join("");

    // 绑定删除按钮
    container.querySelectorAll(".kb-file-remove").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const idx = parseInt(btn.dataset.idx);
        files.splice(idx, 1);
        this.renderKBFileList(container, files);
        // 如果文件列表为空，禁用上传按钮
        const submitBtn = document.getElementById("kbUploadSubmit");
        if (submitBtn) submitBtn.disabled = files.length === 0;
      });
    });
  },

  async uploadFilesToKB(kbId, files) {
    if (!files || files.length === 0) return;

    const submitBtn = document.getElementById("kbUploadSubmit");
    const cancelBtn = document.getElementById("kbUploadCancel");
    const progressEl = document.getElementById("kbUploadProgress");
    submitBtn.disabled = true;
    submitBtn.textContent = "上传中...";
    cancelBtn.disabled = true;

    const formData = new FormData();
    formData.append("owner", this.state.userId);
    files.forEach((f) => formData.append("files", f));

    progressEl.innerHTML = `<div style="padding:8px;background:var(--bg-secondary);border-radius:6px;font-size:13px">⏳ 正在上传 ${files.length} 个文件...</div>`;

    try {
      const res = await fetch(`/knowledge/kb/${kbId}/batch-upload`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json();

      if (data.success) {
        progressEl.innerHTML = `
          <div style="padding:12px;background:#d1fae5;border-radius:6px;font-size:13px;color:#065f46">
            ✅ 上传完成！共 ${data.total_files} 个文件，生成 ${data.total_incidents} 条知识
          </div>
        `;
        // 显示每个文件的结果
        if (data.results && data.results.length > 0) {
          const resultsHtml = data.results.map((r) => {
            const icon = r.status === "success" ? "✅" : "❌";
            const detail = r.status === "success" ? `${r.incidents} 条知识` : r.error;
            return `<div style="padding:4px 0;font-size:12px">${icon} ${this.escapeHtml(r.file)} - ${detail}</div>`;
          }).join("");
          progressEl.innerHTML += `<div style="margin-top:8px;padding:8px;border:1px solid var(--border);border-radius:4px">${resultsHtml}</div>`;
        }
        // 3秒后返回列表
        setTimeout(() => this.openKnowledgeModal(), 3000);
      } else {
        progressEl.innerHTML = `<div style="padding:8px;background:#fee2e2;border-radius:6px;font-size:13px;color:#991b1b">❌ 上传失败: ${this.escapeHtml(data.message || "未知错误")}</div>`;
        submitBtn.disabled = false;
        submitBtn.textContent = "开始上传";
        cancelBtn.disabled = false;
      }
    } catch (e) {
      progressEl.innerHTML = `<div style="padding:8px;background:#fee2e2;border-radius:6px;font-size:13px;color:#991b1b">❌ 网络错误: ${this.escapeHtml(e.message)}</div>`;
      submitBtn.disabled = false;
      submitBtn.textContent = "开始上传";
      cancelBtn.disabled = false;
    }
  },

  showCreateKBForm() {
    const body = this.el.knowledgeModalBody;
    body.innerHTML = `
      <div class="kb-form">
        <h4 style="margin:0 0 12px 0">${this.t("newKnowledgeBase") || "新建知识库"}</h4>
        <input id="kbFormName" placeholder="${this.t("hostName") || "名称"}" style="width:100%;padding:8px;margin-bottom:8px;border:1px solid var(--border);border-radius:6px">
        <input id="kbFormDesc" placeholder="${this.t("description") || "描述"}" style="width:100%;padding:8px;margin-bottom:12px;border:1px solid var(--border);border-radius:6px">
        <div style="display:flex;gap:8px">
          <button id="kbFormSubmit" style="flex:1;padding:8px;background:var(--accent);color:#fff;border:none;border-radius:6px;cursor:pointer;font-weight:600">${this.t("saveSettings") || "保存"}</button>
          <button id="kbFormCancel" style="flex:1;padding:8px;background:var(--main-bg);border:1px solid var(--border);border-radius:6px;cursor:pointer">${this.t("cancel") || "取消"}</button>
        </div>
      </div>
    `;
    document.getElementById("kbFormSubmit").addEventListener("click", () => this.createKnowledgeBase());
    document.getElementById("kbFormCancel").addEventListener("click", () => this.openKnowledgeModal());
  },

  showEditKBForm(kbId, kbName, kbDesc) {
    const body = this.el.knowledgeModalBody;
    body.innerHTML = `
      <div class="kb-form">
        <h4 style="margin:0 0 12px 0">${this.t("rename") || "重命名知识库"}</h4>
        <input id="kbFormName" value="${this.escapeHtml(kbName)}" style="width:100%;padding:8px;margin-bottom:8px;border:1px solid var(--border);border-radius:6px">
        <input id="kbFormDesc" value="${this.escapeHtml(kbDesc)}" placeholder="${this.t("description") || "描述"}" style="width:100%;padding:8px;margin-bottom:12px;border:1px solid var(--border);border-radius:6px">
        <div style="display:flex;gap:8px">
          <button id="kbFormSubmit" style="flex:1;padding:8px;background:var(--accent);color:#fff;border:none;border-radius:6px;cursor:pointer;font-weight:600">${this.t("saveSettings") || "保存"}</button>
          <button id="kbFormCancel" style="flex:1;padding:8px;background:var(--main-bg);border:1px solid var(--border);border-radius:6px;cursor:pointer">${this.t("cancel") || "取消"}</button>
        </div>
      </div>
    `;
    document.getElementById("kbFormSubmit").addEventListener("click", () => this.updateKnowledgeBase(kbId));
    document.getElementById("kbFormCancel").addEventListener("click", () => this.openKnowledgeModal());
  },

  async createKnowledgeBase() {
    const name = document.getElementById("kbFormName").value.trim();
    const desc = document.getElementById("kbFormDesc").value.trim();
    if (!name) { alert(this.t("fillRequired")); return; }
    try {
      const formData = new FormData();
      formData.append("owner", this.state.userId);
      formData.append("name", name);
      if (desc) formData.append("description", desc);
      const res = await fetch("/knowledge/kb", { method: "POST", body: formData });
      const data = await res.json();
      if (data.success) {
        this.openKnowledgeModal();
      } else {
        alert(data.message || this.t("testFail"));
      }
    } catch (e) {
      alert(this.t("networkError") + ": " + e.message);
    }
  },

  async updateKnowledgeBase(kbId) {
    const name = document.getElementById("kbFormName").value.trim();
    const desc = document.getElementById("kbFormDesc").value.trim();
    if (!name) { alert(this.t("fillRequired")); return; }
    try {
      const formData = new FormData();
      formData.append("name", name);
      if (desc) formData.append("description", desc);
      const res = await fetch(`/knowledge/kb/${kbId}`, { method: "PUT", body: formData });
      const data = await res.json();
      if (data.success) {
        this.openKnowledgeModal();
      } else {
        alert(data.message || this.t("testFail"));
      }
    } catch (e) {
      alert(this.t("networkError") + ": " + e.message);
    }
  },

  async deleteKnowledgeBase(kbId) {
    if (!confirm(this.t("confirmDelete") || "确定删除？")) return;
    try {
      const res = await fetch(`/knowledge/kb/${kbId}`, { method: "DELETE" });
      const data = await res.json();
      if (data.success) {
        this.openKnowledgeModal();
      } else {
        alert(data.message || this.t("testFail"));
      }
    } catch (e) {
      alert(this.t("networkError") + ": " + e.message);
    }
  },

  closeKnowledgeModal() {
    this.el.knowledgeModal.style.display = "none";
  },

  /* ───── 主机管理 ───── */
  async loadHosts() {
    try {
      const res = await fetch(`/hosts?user_id=${encodeURIComponent(this.state.userId)}`);
      const data = await res.json();
      if (data.success) {
        this.state.hosts = data.data || [];
        this.renderHostSelect();
      }
    } catch (e) {
      console.error("loadHosts error:", e);
    }
  },

  renderHostSelect() {
    const sel = this.el.hostSelect;
    sel.innerHTML = `<option value="">${this.t("defaultHost")}</option>`;
    this.state.hosts.forEach((h) => {
      const opt = document.createElement("option");
      opt.value = h.id;
      opt.textContent = `${h.name} (${h.host})`;
      sel.appendChild(opt);
    });
    sel.value = this.state.hostId || "";
  },

  openHostModal() {
    this.el.hostModal.style.display = "flex";
    this.renderHostList();
  },

  closeHostModal() {
    this.el.hostModal.style.display = "none";
  },

  renderHostList() {
    const container = this.el.hostListContainer;
    if (!this.state.hosts.length) {
      container.innerHTML = `<p class="loading-text">${this.t("noHosts")}</p>`;
      return;
    }
    container.innerHTML = this.state.hosts.map((h) => `
      <div class="host-card">
        <div class="host-info-text">
          <div class="host-name">${this.escapeHtml(h.name)}</div>
          <div class="host-addr">${this.escapeHtml(h.username)}@${this.escapeHtml(h.host)}:${h.port}</div>
        </div>
        <div class="host-card-actions">
          <button class="host-action-btn test" data-action="test" data-id="${h.id}">${this.t("test")}</button>
          <button class="host-action-btn del" data-action="delete" data-id="${h.id}">${this.t("delete")}</button>
        </div>
      </div>
    `).join("");
    container.querySelectorAll("[data-action]").forEach((btn) => {
      btn.addEventListener("click", () => this.handleHostAction(btn.dataset.action, btn.dataset.id));
    });
  },

  async handleHostAction(action, hostId) {
    if (action === "test") {
      const btn = this.el.hostListContainer.querySelector(`[data-id="${hostId}"][data-action="test"]`);
      btn.textContent = this.t("testing");
      btn.disabled = true;
      try {
        const res = await fetch(`/hosts/${hostId}/test?user_id=${encodeURIComponent(this.state.userId)}`);
        const data = await res.json();
        btn.textContent = data.success ? this.t("testSuccess") : this.t("testFail");
        btn.style.color = data.success ? "var(--green)" : "#ef4444";
        if (!data.success) alert(data.message);
      } catch (e) {
        btn.textContent = this.t("testError");
        btn.style.color = "#ef4444";
      }
      setTimeout(() => { btn.textContent = this.t("test"); btn.disabled = false; btn.style.color = ""; }, 3000);
    } else if (action === "delete") {
      if (!confirm(this.t("confirmDeleteHost"))) return;
      await fetch(`/hosts/${hostId}?user_id=${encodeURIComponent(this.state.userId)}`, { method: "DELETE" });
      if (this.state.hostId === hostId) {
        this.state.hostId = null;
      }
      this.loadHosts();
    }
  },

  async addHost() {
    const name = this.el.hostName.value.trim();
    const host = this.el.hostAddr.value.trim();
    const port = parseInt(this.el.hostPort.value) || 22;
    const username = this.el.hostUser.value.trim();
    const password = this.el.hostPass.value;
    if (!name || !host || !username) {
      alert(this.t("fillRequired"));
      return;
    }
    try {
      const res = await fetch(`/hosts?user_id=${encodeURIComponent(this.state.userId)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, host, port, username, password }),
      });
      const data = await res.json();
      if (data.success) {
        this.el.hostName.value = "";
        this.el.hostAddr.value = "";
        this.el.hostPort.value = "22";
        this.el.hostUser.value = "";
        this.el.hostPass.value = "";
        this.loadHosts();
      } else {
        alert(this.t("addHost") + " " + this.t("testFail"));
      }
    } catch (e) {
      alert(this.t("networkError") + ": " + e.message);
    }
  },

  /* ───── 工具函数 ───── */
  escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str == null ? "" : String(str);
    return div.innerHTML;
  },

  renderMarkdown(text) {
    if (!text) return "";
    let html = this.escapeHtml(text);
    // 代码块
    html = html.replace(/```(\w*)\n?([\s\S]*?)```/g, (m, lang, code) => {
      return `<pre><code>${code.trim()}</code></pre>`;
    });
    // 行内代码
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    // 加粗
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    // 标题
    html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
    html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
    html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');
    // 列表
    html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
    html = html.replace(/(<li>[\s\S]*?<\/li>)/g, '<ul>$1</ul>');
    // 换行
    html = html.replace(/\n/g, '<br>');
    return html;
  },
};

document.addEventListener("DOMContentLoaded", () => App.init());