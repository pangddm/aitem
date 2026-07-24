/* ========================================================================
   Kubedoctor 前端应用 - ChatGPT 风格 (白色主题)
   ======================================================================== */

const App = {
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
      "attachBtn", "voiceBtn", "fileInput", "fileTag", "fileTagText",
      "fileTagRemove", "knowledgeBtn", "knowledgeModal", "knowledgeModalClose",
      "knowledgeModalBody", "loginOverlay",
      "hostSelect", "hostMgrBtn", "hostModal", "hostModalClose",
      "hostModalBody", "hostName", "hostAddr", "hostPort", "hostUser",
      "hostPass", "hostAddBtn", "hostListContainer",
      "settingsBtn", "settingsModal", "settingsModalClose",
      "settingsTheme", "settingsLanguage", "settingsAvatarInput",
      "settingsAvatarPreview", "settingsSaveBtn", "settingsTestMode",
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
        msg.thinking_chain.forEach((tc) => {
          const item = this.mapThinkingChainItem(tc);
          this.renderThinkingBlock(contentEl, item.cls, item.title, item.content);
        });
      }
    });
    this.scrollToBottom();
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
        <div class="message-content">${this.renderMarkdown(content)}</div>
      </div>
    `;
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
    contentEl.classList.add("typing-cursor");
    this.el.chatMessages.appendChild(assistantEl);
    this.scrollToBottom();

    this.state.streaming = true;
    this.toggleStreamingUI(true);
    this.state.abortCtrl = new AbortController();

    // 思考链管理
    let currentThinkingBlock = null;
    let thinkingQueue = [];
    let thinkingTimer = null;
    let thinkingChain = [];  // 收集思考链数据用于持久化

    let fullAnswer = "";
    try {
      const params = new URLSearchParams({
        user_id: this.state.userId,
        message: text,
      });
      if (this.state.convId) params.set("conv_id", this.state.convId);
      if (this.state.hostId) params.set("host_id", this.state.hostId);

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
      contentEl.classList.remove("typing-cursor");
      this.state.streaming = false;
      this.toggleStreamingUI(false);
      if (fullAnswer) {
        this.state.messages.push({ role: "assistant", content: fullAnswer, thinking_chain: thinkingChain });
      }
      this.loadConversations();
      this.scrollToBottom();
    }
  },

  handleStreamEvent(evt, contentEl, assistantEl) {
    const type = evt.type;
    const content = evt.content || "";

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

    // 工作流状态（进度条）
    if (type === "workflow_status") {
      this.updateWorkflowProgress(contentEl, evt.stage, evt.message);
      return;
    }

    // 反馈循环重试
    if (type === "retry_loop") {
      const title = `🔄 第${evt.loop}次重试`;
      this.appendThinkingBlock(contentEl, "retry", title, evt.reason || "Observer 建议重试");
      thinkingChain.push({ cls: "retry", title, content: evt.reason || "Observer 建议重试" });
      return;
    }

    // 最终答案流式输出
    if (type === "answer_chunk") {
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

    // 思考链：各 Agent 的推理过程
    if (type === "reasoning" || type === "answer_reasoning") {
      const agentName = evt.agent || "reporter";
      const agentLabelMap = {
        orchestrator: this.t("intentAnalysis"),
        risk_assessor: this.t("riskAssessment"),
        validator: this.t("commandGen"),
        validator_retry: "命令修正",
        observer: this.t("resultObserve"),
        reporter: this.t("reportGen"),
      };
      const agentLabel = agentLabelMap[agentName] || agentName;
      const title = `💭 ${this.t("thinking")} · ${agentLabel}`;
      this.appendThinkingBlock(contentEl, "thought", title, content);
      thinkingChain.push({ cls: "thought", title, content });
      return;
    }

    // 任务计划
    if (type === "task_plan") {
      const text = typeof content === "string" ? content : JSON.stringify(content, null, 2);
      const title = `📋 ${this.t("taskPlan")}`;
      this.appendThinkingBlock(contentEl, "plan", title, text);
      thinkingChain.push({ cls: "plan", title, content: text });
      return;
    }

    // 风险评估
    if (type === "risk_assessment") {
      const text = typeof content === "string" ? content : JSON.stringify(content, null, 2);
      const title = `⚠️ ${this.t("riskAssess")}`;
      this.appendThinkingBlock(contentEl, "risk", title, text);
      thinkingChain.push({ cls: "risk", title, content: text });
      return;
    }

    // 命令校验
    if (type === "validation") {
      const text = typeof content === "string" ? content : JSON.stringify(content, null, 2);
      const title = `✅ ${this.t("cmdValidate")}`;
      this.appendThinkingBlock(contentEl, "validation", title, text);
      thinkingChain.push({ cls: "validation", title, content: text });
      return;
    }

    // 工具调用
    if (type === "tool_call") {
      const cmd = evt.command || content;
      const title = `🔧 ${this.t("execCmd")} (${evt.tool || "execute_command"})`;
      this.appendThinkingBlock(contentEl, "tool", title, cmd);
      thinkingChain.push({ cls: "tool", title, content: cmd });
      return;
    }

    // 工具结果
    if (type === "tool_result") {
      const title = `📋 ${this.t("execResult")}`;
      this.appendThinkingBlock(contentEl, "tool", title, content);
      thinkingChain.push({ cls: "tool", title, content });
      return;
    }

    // 观察
    if (type === "observation") {
      const text = typeof content === "string" ? content : JSON.stringify(content, null, 2);
      const title = `👁️ ${this.t("resultObs")}`;
      this.appendThinkingBlock(contentEl, "observation", title, text);
      thinkingChain.push({ cls: "observation", title, content: text });
      return;
    }

    // 自动修复通知
    if (type === "auto_fix") {
      const title = `🤖 ${this.t("autoFix") || "自动修复"}`;
      this.appendThinkingBlock(contentEl, "auto-fix", title, content);
      thinkingChain.push({ cls: "auto-fix", title, content });
      return;
    }

    // 用户选择已应用
    if (type === "user_choice_applied") {
      const title = `✅ ${this.t("choiceApplied") || "已选择方案"}`;
      this.appendThinkingBlock(contentEl, "choice-applied", title, content);
      thinkingChain.push({ cls: "choice-applied", title, content });
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
      // 流结束，立即折叠所有思考链
      this.collapseAllThinkingBlocks(contentEl);
      // 添加报告下载按钮
      if (this.state.convId) {
        const answerArea = contentEl.querySelector(".answer-area");
        const target = answerArea || contentEl;
        const downloadBtn = document.createElement("a");
        downloadBtn.href = `/chat/report/${encodeURIComponent(this.state.convId)}?user_id=${encodeURIComponent(this.state.userId)}`;
        downloadBtn.download = `Kubedoctor_${this.state.convId.slice(0, 8)}_report.md`;
        downloadBtn.className = "report-download-btn";
        downloadBtn.style.cssText = `
          display: inline-flex; align-items: center; gap: 6px;
          margin-top: 12px; padding: 8px 16px;
          background: var(--accent); color: #fff;
          border-radius: 8px; text-decoration: none;
          font-size: 13px; font-weight: 600;
          transition: opacity 0.2s;
        `;
        downloadBtn.innerHTML = `📥 ${this.t("downloadReport") || "下载报告"}`;
        downloadBtn.addEventListener("mouseenter", () => { downloadBtn.style.opacity = "0.85"; });
        downloadBtn.addEventListener("mouseleave", () => { downloadBtn.style.opacity = "1"; });
        target.appendChild(downloadBtn);
      }
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

    // 插入到 answer-area 之前（如果有的话）
    const answerArea = contentEl.querySelector(".answer-area");
    if (answerArea) {
      contentEl.insertBefore(block, answerArea);
    } else {
      contentEl.appendChild(block);
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

    // 插入到 answer-area 之前（如果有的话）
    const answerArea = contentEl.querySelector(".answer-area");
    if (answerArea) {
      contentEl.insertBefore(block, answerArea);
    } else {
      contentEl.appendChild(block);
    }

    // 点击标题切换折叠
    titleEl.addEventListener("click", () => {
      contentDiv.classList.toggle("collapsed");
    });
  },

  /**
   * 流结束后折叠所有思考链块
   */
  collapseAllThinkingBlocks(contentEl) {
    const allBlocks = contentEl.querySelectorAll(".event-block");
    allBlocks.forEach((block) => {
      const contentDiv = block.querySelector(".event-content");
      if (contentDiv && !contentDiv.classList.contains("collapsed")) {
        contentDiv.classList.add("collapsed");
      }
      block.classList.remove("animating");
      block.classList.add("completed");
      const statusEl = block.querySelector(".event-status");
      if (statusEl) statusEl.textContent = "✓";
      if (block._collapseTimer) {
        clearTimeout(block._collapseTimer);
        block._collapseTimer = null;
      }
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

    // 添加跳过按钮
    html += `
      <div style="margin-top:12px;text-align:center">
        <button class="fix-option-btn" data-choice="skip" style="
          padding:8px 16px;
          border:1px solid var(--border);
          border-radius:6px;
          background:transparent;
          color:var(--text-tertiary);
          cursor:pointer;
          font-size:12px;
        ">⏭️ ${this.t("skip") || "跳过，直接生成报告"}</button>
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

  stopStream() {
    if (this.state.abortCtrl) {
      this.state.abortCtrl.abort();
    }
  },

  toggleStreamingUI(on) {
    this.el.sendBtn.style.display = on ? "none" : "";
    this.el.stopBtn.style.display = on ? "" : "none";
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

    const assistantEl = this.createMessageEl("assistant", this.t("analyzing"));
    this.el.chatMessages.appendChild(assistantEl);
    this.scrollToBottom();

    const formData = new FormData();
    formData.append("user_id", this.state.userId);
    formData.append("message", text);
    formData.append("file", file);

    try {
      const res = await fetch("/chat_with_document", {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      const contentEl = assistantEl.querySelector(".message-content");
      contentEl.innerHTML = this.renderMarkdown(data.response || this.t("noResponse"));
      this.state.messages.push({ role: "assistant", content: data.response || "" });
    } catch (e) {
      assistantEl.querySelector(".message-content").textContent = "⚠️ " + this.t("error") + ": " + e.message;
    }
    this.scrollToBottom();
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