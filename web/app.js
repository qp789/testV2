/* qpquiz-web（高级版）前端：账号、答题、SRS 复习、离线同步。 */

const app = document.getElementById("app");
const toastEl = document.getElementById("toast");
const tabs = document.getElementById("tabs");

const DIFF = { 1: "★☆☆", 2: "★★☆", 3: "★★★" };
const SESSION_KEY = "qpquiz.session";
const TOKEN_KEY = "qpquiz.token";
const QUEUE_KEY = "qpquiz.queue";

const ui = {
  view: "home", meta: null, session: null, feedback: null, summary: null,
  busy: false, qStart: 0, user: null, authMode: "login",
  selected: [], study: null,
};
const prefs = { mode: "exam", count: 10, categories: [] };

/* ------------------------------------------------------------ 基础工具 */
function h(tag, props = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(props || {})) {
    if (value === null || value === undefined) continue;
    if (key === "class") el.className = value;
    else if (key === "text") el.textContent = value;
    else if (key.startsWith("on") && typeof value === "function") {
      el.addEventListener(key.slice(2).toLowerCase(), value);
    } else el.setAttribute(key, value);
  }
  for (const kid of kids.flat()) {
    if (kid === null || kid === undefined || kid === false) continue;
    el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return el;
}

function token() { return localStorage.getItem(TOKEN_KEY) || ""; }

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json" };
  if (token()) headers.Authorization = `Bearer ${token()}`;
  const res = await fetch(`/api${path}`, { headers, ...options });
  if (res.status === 401) {
    localStorage.removeItem(TOKEN_KEY);
    ui.user = null;
    ui.view = "auth";
    render();
    throw new Error("登录已过期，请重新登录");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `请求失败（${res.status}）`);
  return data;
}

let toastTimer = null;
function toast(message) {
  toastEl.textContent = message;
  toastEl.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toastEl.classList.remove("show"), 2400);
}

function fmtDuration(ms) {
  const total = Math.max(0, Math.round(ms / 1000));
  return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}
const pct = (value) => `${(value * 100).toFixed(1)}%`;
const letters = (indexes) => indexes.map((i) => String.fromCharCode(65 + i)).join("");

/* -------------------------------------------------------------- 离线队列 */
function queueEvent(event) {
  const queue = JSON.parse(localStorage.getItem(QUEUE_KEY) || "[]");
  queue.push(event);
  localStorage.setItem(QUEUE_KEY, JSON.stringify(queue));
}

async function flushQueue() {
  if (!token()) return;
  const queue = JSON.parse(localStorage.getItem(QUEUE_KEY) || "[]");
  if (!queue.length) return;
  try {
    const data = await api("/sync", { method: "POST", body: JSON.stringify({ events: queue }) });
    localStorage.setItem(QUEUE_KEY, "[]");
    toast(`已同步 ${data.results.length} 条离线记录`);
  } catch {
    /* 仍然离线，等下一次 */
  }
}

window.addEventListener("online", flushQueue);
setInterval(flushQueue, 30_000);

/* -------------------------------------------------------------- 导航 */
function setTab(name) {
  for (const btn of tabs.querySelectorAll("button")) {
    btn.classList.toggle("active", btn.dataset.nav === name);
  }
}

function go(view) {
  if (!token() && view !== "auth") view = "auth";
  if (ui.view === "quiz" && view !== "quiz" && ui.session && ui.session.status === "active") {
    if (!confirm("本轮还没答完，确定离开？")) return;
    ui.session = null;
    ui.feedback = null;
    localStorage.removeItem(SESSION_KEY);
  }
  ui.view = view;
  setTab(view === "result" ? "home" : view);
  render();
}

tabs.addEventListener("click", (event) => {
  const btn = event.target.closest("button[data-nav]");
  if (btn) go(btn.dataset.nav);
});

/* ------------------------------------------------------------ 渲染入口 */
function render() {
  app.replaceChildren();
  if (!token()) return renderAuth();
  if (ui.view === "auth") return renderAuth();
  if (ui.view === "home") renderHome();
  else if (ui.view === "quiz") renderQuiz();
  else if (ui.view === "result") renderResult();
  else if (ui.view === "stats") renderStats();
  else if (ui.view === "history") renderHistory();
  else if (ui.view === "study") renderStudy();
}

/* -------------------------------------------------------------- 登录 */
function renderAuth() {
  const register = ui.authMode === "register";
  const email = h("input", { type: "email", placeholder: "you@example.com", autocomplete: "email" });
  const password = h("input", { type: "password", placeholder: "至少 8 位", autocomplete: "current-password" });
  const error = h("p", { class: "center", style: "color:var(--danger);min-height:18px" });

  async function submit(event) {
    event.preventDefault();
    error.textContent = "";
    try {
      const data = await api(`/auth/${register ? "register" : "login"}`, {
        method: "POST",
        body: JSON.stringify({ email: email.value.trim(), password: password.value }),
      });
      localStorage.setItem(TOKEN_KEY, data.token);
      ui.user = data.user;
      ui.view = "home";
      setTab("home");
      render();
    } catch (err) {
      error.textContent = err.message;
    }
  }

  app.append(
    h("div", { class: "card", style: "margin-top:8vh" },
      h("h1", {}, register ? "注册账号" : "登录 qpquiz"),
      h("p", {}, "成绩、错题与复习计划都按账号保存。"),
      h("form", { onsubmit: submit },
        h("div", { class: "field" }, h("label", {}, "邮箱"), email),
        h("div", { class: "field" }, h("label", {}, "密码"), password),
        error,
        h("button", { class: "btn primary", type: "submit", style: "width:100%" },
          register ? "注册并登录" : "登录")),
      h("p", { class: "center", style: "margin-top:14px" },
        register ? "已经有账号？" : "还没有账号？",
        h("a", {
          href: "#", style: "color:var(--accent);margin-left:6px",
          onclick: (event) => {
            event.preventDefault();
            ui.authMode = register ? "login" : "register";
            renderAuth();
          },
        }, register ? "去登录" : "去注册")),
    ),
  );
}

/* ------------------------------------------------------------ 首页 */
async function ensureMeta() {
  if (!ui.meta) ui.meta = await api("/meta");
  return ui.meta;
}

async function renderHome() {
  let meta;
  try {
    meta = await ensureMeta();
  } catch (err) {
    app.append(h("div", { class: "card" }, h("h2", {}, "无法连接服务"), h("p", {}, err.message)));
    return;
  }

  const resumeId = Number(localStorage.getItem(SESSION_KEY));
  if (resumeId && !ui.session) {
    try {
      const session = await api(`/sessions/${resumeId}`);
      if (session.status === "active") {
        app.append(
          h("div", { class: "card", style: "margin-bottom:14px" },
            h("div", { class: "spread" },
              h("div", {}, h("h2", {}, "继续上次"),
                h("p", { style: "margin:0" }, `已答 ${session.answered}/${session.total} 题`)),
              h("button", {
                class: "btn primary",
                onclick: () => {
                  ui.session = session;
                  ui.feedback = null;
                  ui.selected = [];
                  ui.qStart = Date.now();
                  go("quiz");
                },
              }, "继续"))),
        );
      } else localStorage.removeItem(SESSION_KEY);
    } catch { localStorage.removeItem(SESSION_KEY); }
  }

  const catChips = meta.categories.map((name) =>
    h("button", {
      class: `chip${prefs.categories.includes(name) ? " on" : ""}`,
      onclick: (event) => {
        const index = prefs.categories.indexOf(name);
        if (index >= 0) prefs.categories.splice(index, 1);
        else prefs.categories.push(name);
        event.target.classList.toggle("on");
      },
    }, name));

  app.append(
    h("div", { class: "card" },
      h("div", { class: "spread" },
        h("h1", {}, "Python 自测"),
        h("button", {
          class: "btn ghost", style: "min-height:34px;padding:0 12px;font-size:13px",
          onclick: () => {
            localStorage.removeItem(TOKEN_KEY);
            ui.user = null;
            ui.view = "auth";
            render();
          },
        }, "退出")),
      h("p", {}, `${meta.question_count} 道题 · ${ui.user ? ui.user.email : ""}`),

      h("div", { class: "field" }, h("label", {}, "模式"),
        h("div", { class: "chips" }, ["exam", "practice"].map((mode) =>
          h("button", {
            class: `chip${prefs.mode === mode ? " on" : ""}`,
            onclick: (event) => {
              prefs.mode = mode;
              event.target.parentElement.querySelectorAll(".chip").forEach((el) => el.classList.remove("on"));
              event.target.classList.add("on");
            },
          }, mode === "exam" ? "考试" : "练习（即时解析）")))),

      h("div", { class: "field" }, h("label", {}, "题量"),
        h("div", { class: "chips" }, [5, 10, 15].map((count) =>
          h("button", {
            class: `chip${prefs.count === count ? " on" : ""}`,
            onclick: (event) => {
              prefs.count = count;
              event.target.parentElement.querySelectorAll(".chip").forEach((el) => el.classList.remove("on"));
              event.target.classList.add("on");
            },
          }, `${count} 题`)))),

      h("div", { class: "field" }, h("label", {}, "分类（不选=全部）"),
        h("div", { class: "chips" }, catChips)),

      h("button", { class: "btn primary", style: "width:100%", onclick: startQuiz }, "开始答题")),

    h("p", { class: "center muted", style: "margin-top:16px;font-size:12px" },
      "离线时作答会先存本地，联网后自动同步。"),
  );
}

async function startQuiz() {
  try {
    const session = await api("/sessions", {
      method: "POST",
      body: JSON.stringify({ mode: prefs.mode, count: prefs.count, categories: prefs.categories }),
    });
    ui.session = session;
    ui.feedback = null;
    ui.selected = [];
    ui.qStart = Date.now();
    localStorage.setItem(SESSION_KEY, String(session.id));
    go("quiz");
  } catch (err) { toast(err.message); }
}

/* -------------------------------------------------------------- 答题 */
function optionButton(question, index, disabled) {
  const classes = ["option"];
  if (ui.feedback) {
    if (ui.feedback.answers.includes(index)) classes.push("right");
    else if (ui.selected.includes(index)) classes.push("wrong");
  } else if (ui.selected.includes(index)) classes.push("on");

  return h("button", {
    class: classes.join(" "),
    disabled: disabled ? "" : null,
    onclick: () => pickOption(question, index),
  },
    h("span", { class: "key" }, String.fromCharCode(65 + index)),
    h("span", {}, question.options[index]));
}

function pickOption(question, index) {
  if (ui.feedback || ui.busy) return;
  if (question.kind === "multi") {
    const at = ui.selected.indexOf(index);
    if (at >= 0) ui.selected.splice(at, 1);
    else ui.selected.push(index);
    render();
  } else {
    ui.selected = [index];
    submitAnswer(index);
  }
}

function renderQuiz() {
  const session = ui.session;
  if (!session) return go("home");
  const question = session.question;
  if (!question) return showResult(session.id);

  ui.selected = ui.selected.filter((index) => index < question.options.length);
  const multi = question.kind === "multi";

  app.append(
    h("div", { class: "card" },
      h("div", { class: "progress" },
        h("i", { style: `width:${(session.answered / session.total) * 100}%` })),
      h("div", { class: "meta-row" },
        h("span", {}, `第 ${question.position} / ${session.total} 题`),
        h("span", {}, session.mode === "practice" ? "练习模式" : "考试模式")),
      h("div", { class: "spread", style: "margin-bottom:10px" },
        h("span", { class: "badge" },
          `${question.category} · ${question.kind === "multi" ? "多选" : question.kind === "judge" ? "判断" : "单选"}`),
        h("span", { class: "badge dim" }, `${DIFF[question.difficulty]} · ${question.points} 分`)),
      h("div", { class: "prompt" }, question.prompt),
      h("div", { class: "options" },
        question.options.map((_, index) => optionButton(question, index, Boolean(ui.feedback)))),
      ui.feedback ? feedbackPanel() : null,
      (!ui.feedback && multi)
        ? h("div", { class: "row end", style: "margin-top:16px" },
            h("button", {
              class: "btn ghost",
              onclick: () => { ui.selected = []; render(); },
            }, "清空"),
            h("button", {
              class: "btn primary",
              disabled: ui.selected.length ? null : "",
              onclick: () => submitAnswer([...ui.selected]),
            }, "提交答案"))
        : null,
      (!ui.feedback && !multi)
        ? h("div", { class: "row end", style: "margin-top:16px" },
            h("button", { class: "btn ghost", onclick: () => submitAnswer(null) }, "跳过"),
            h("button", { class: "btn ghost", onclick: () => go("home") }, "退出"))
        : null,
    ),
  );
}

function feedbackPanel() {
  const fb = ui.feedback;
  return h("div", { class: `feedback ${fb.correct ? "ok" : "bad"}` },
    h("strong", { style: `color:${fb.correct ? "var(--accent-2)" : "var(--danger)"}` },
      fb.correct ? `回答正确 +${fb.points} 分` : "回答错误"),
    h("p", { style: "margin:0 0 6px" }, `正确答案：${letters(fb.answers)}`),
    h("p", { style: "margin:0 0 12px" }, fb.explanation),
    h("div", { class: "row end" },
      h("button", { class: "btn primary", onclick: continueAfterFeedback }, "继续")));
}

async function submitAnswer(choice) {
  if (ui.busy || !ui.session || ui.feedback) return;
  ui.busy = true;
  const question = ui.session.question;
  try {
    const res = await api(`/sessions/${ui.session.id}/answers`, {
      method: "POST",
      body: JSON.stringify({
        question_id: question.id, choice, elapsed_ms: Date.now() - ui.qStart,
      }),
    });
    ui.session = res.session;
    ui.feedback = res.feedback;
    if (!ui.feedback && ui.session.status === "finished") return await showResult(ui.session.id);
    render();
  } catch (err) {
    if (err.message.includes("登录")) return;
    const offline = !navigator.onLine || err instanceof TypeError;
    if (offline) {
      queueEvent({
        client_id: (crypto.randomUUID ? crypto.randomUUID() : String(Date.now())),
        session_id: ui.session.id,
        question_id: question.id,
        choice,
        elapsed_ms: Date.now() - ui.qStart,
      });
      toast("网络异常，已离线保存，恢复后自动同步");
    } else {
      toast(err.message);
    }
  } finally {
    ui.busy = false;
  }
}

async function continueAfterFeedback() {
  ui.feedback = null;
  ui.selected = [];
  ui.qStart = Date.now();
  if (ui.session.status === "finished") await showResult(ui.session.id);
  else render();
}

/* -------------------------------------------------------------- 结果 */
async function showResult(sessionId) {
  try {
    const summary = await api(`/sessions/${sessionId}/summary`);
    ui.summary = summary;
    ui.session = null;
    ui.feedback = null;
    localStorage.removeItem(SESSION_KEY);
    ui.view = "result";
    setTab("home");
    render();
  } catch (err) {
    toast(err.message);
    go("home");
  }
}

function renderResult() {
  const summary = ui.summary;
  if (!summary) return go("home");
  const wrong = summary.wrong.map((item) =>
    h("div", { class: "wrong-item" },
      h("div", { class: "spread" },
        h("span", { class: "badge dim" }, item.question.category),
        h("span", { class: "muted" },
          `你选：${item.choice === null || item.choice === undefined
            ? "跳过"
            : letters(Array.isArray(item.choice) ? item.choice : [item.choice])}　正确：${letters(item.answers)}`)),
      h("div", { class: "prompt" }, item.question.prompt),
      h("p", { style: "margin:0" }, item.explanation)));

  app.append(
    h("div", { class: "card" },
      h("div", { class: "score-hero" },
        h("div", { class: "value" }, `${summary.score}`, h("small", {}, ` / ${summary.max_score}`)),
        h("p", { style: "margin:4px 0 0" },
          `${summary.correct}/${summary.total} 正确 · 正确率 ${pct(summary.accuracy)}`)),
      h("div", { class: "grid" },
        h("div", { class: "stat" }, h("span", {}, "用时"), h("b", {}, fmtDuration(summary.duration_ms))),
        h("div", { class: "stat" }, h("span", {}, "模式"),
          h("b", { style: "font-size:17px" }, summary.mode === "practice" ? "练习" : "考试")),
        h("div", { class: "stat" }, h("span", {}, "题目数"), h("b", {}, String(summary.total)))),
      summary.categories.length ? h("h2", { style: "margin-top:18px" }, "分类正确率") : null,
      summary.categories.map((item) =>
        h("div", { style: "margin-bottom:12px" },
          h("div", { class: "spread" },
            h("span", {}, item.category),
            h("span", { class: "muted" }, `${item.correct}/${item.total}`)),
          h("div", { class: "bar" },
            h("i", { style: `width:${(item.correct / item.total) * 100}%` })))),
      wrong.length ? h("h2", { style: "margin-top:18px" }, `错题回顾（${wrong.length}）`) : null,
      wrong,
      h("div", { class: "row", style: "margin-top:18px" },
        h("button", { class: "btn primary", onclick: startQuiz }, "再来一轮"),
        h("button", { class: "btn ghost", onclick: () => go("study") }, "去复习"))),
  );
}

/* -------------------------------------------------------------- 复习 */
async function renderStudy() {
  try {
    const data = await api("/study/due?limit=10");
    if (!data.questions.length) {
      app.append(h("div", { class: "card" },
        h("h1", {}, "今日复习"),
        h("p", {}, "没有到期题目，去答一轮新的吧。"),
        h("button", { class: "btn primary", onclick: () => go("home") }, "去答题")));
      return;
    }
    const index = ui.study ? ui.study.index : 0;
    const question = data.questions[index % data.questions.length];
    const feedback = ui.study ? ui.study.feedback : null;

    app.append(
      h("div", { class: "card" },
        h("div", { class: "spread" },
          h("h1", {}, "今日复习"),
          h("span", { class: "muted" }, `到期 ${data.due} · 新题 ${data.new}`)),
        h("div", { class: "meta-row" },
          h("span", {}, `第 ${(index % data.questions.length) + 1} / ${data.questions.length} 张`),
          h("span", {}, question.category)),
        h("div", { class: "prompt" }, question.prompt),
        h("div", { class: "options" }, question.options.map((_, optionIndex) =>
          h("button", {
            class: "option",
            disabled: feedback ? "" : null,
            onclick: () => reviewAnswer(question, optionIndex),
          },
            h("span", { class: "key" }, String.fromCharCode(65 + optionIndex)),
            h("span", {}, question.options[optionIndex])))),
        feedback
          ? h("div", { class: `feedback ${feedback.correct ? "ok" : "bad"}` },
              h("strong", {}, feedback.correct ? "正确" : "错误"),
              h("p", { style: "margin:6px 0" },
                `答案 ${letters(feedback.answers)} · 下次复习 ${feedback.interval_days} 天后`),
              h("p", { style: "margin:0 0 12px" }, feedback.explanation),
              h("div", { class: "row end" },
                h("button", {
                  class: "btn primary",
                  onclick: () => {
                    ui.study = { index: index + 1, feedback: null };
                    renderStudy();
                  },
                }, "下一张")))
          : null),
    );
  } catch (err) { toast(err.message); }
}

async function reviewAnswer(question, optionIndex) {
  try {
    const res = await api("/study/review", {
      method: "POST",
      body: JSON.stringify({ question_id: question.id, choice: [optionIndex] }),
    });
    ui.study = { index: ui.study ? ui.study.index : 0, feedback: res };
    renderStudy();
  } catch (err) { toast(err.message); }
}

/* -------------------------------------------------------------- 统计 / 历史 */
async function renderStats() {
  try {
    const data = await api("/stats");
    const stats = data.stats;
    const rows = data.categories.map((item) =>
      h("div", { style: "margin-bottom:12px" },
        h("div", { class: "spread" },
          h("span", {}, item.category),
          h("span", { class: "muted" }, `${item.correct}/${item.total} · ${pct(item.accuracy)}`)),
        h("div", { class: "bar" }, h("i", { style: `width:${item.accuracy * 100}%` }))));

    app.append(h("div", { class: "card" },
      h("h1", {}, "统计"),
      h("div", { class: "grid" },
        [["答题轮数", String(stats.sessions)], ["累计题数", String(stats.answers)],
         ["总正确率", pct(stats.accuracy)], ["最佳单轮", `${stats.best_score} 分`]]
          .map(([label, value]) => h("div", { class: "stat" }, h("span", {}, label), h("b", {}, value)))),
      h("p", { style: "margin-top:14px" },
        `平均分 ${stats.average_score.toFixed(1)} · 最近 ${stats.last_played ? stats.last_played.replace("T", " ").slice(0, 16) : "暂无"}`),
      rows.length ? h("h2", { style: "margin-top:18px" }, "分类正确率") : null,
      rows));
  } catch (err) { toast(err.message); }
}

async function renderHistory() {
  try {
    const data = await api("/history?limit=30");
    app.append(h("div", { class: "card" },
      h("h1", {}, "历史记录"),
      data.sessions.length
        ? h("div", { class: "list" }, data.sessions.map((session) =>
            h("div", {
              class: "list-item", style: "cursor:pointer",
              onclick: () => showResult(session.id),
            },
              h("div", {},
                h("div", {}, `${session.mode === "practice" ? "练习" : "考试"} · ${session.correct}/${session.total}`),
                h("div", { class: "muted", style: "font-size:12px" },
                  session.started_at.replace("T", " ").slice(0, 16))),
              h("b", {}, `${session.score} 分`))))
        : h("p", { class: "center muted" }, "还没有历史记录。")));
  } catch (err) { toast(err.message); }
}

/* -------------------------------------------------------------- 键盘 */
document.addEventListener("keydown", (event) => {
  if (ui.view !== "quiz") return;
  if (ui.feedback) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      continueAfterFeedback();
    }
    return;
  }
  const question = ui.session && ui.session.question;
  if (!question) return;
  const key = event.key.toLowerCase();
  const digit = "1234".indexOf(key);
  const letter = "abcd".indexOf(key);
  const index = digit >= 0 ? digit : letter;
  if (index >= 0 && index < question.options.length) pickOption(question, index);
});

/* -------------------------------------------------------------- 启动 */
(async function boot() {
  if (token()) {
    try {
      const data = await api("/auth/me");
      ui.user = data.user;
    } catch { /* 401 已处理 */ }
  }
  if (!token()) ui.view = "auth";
  render();
  flushQueue();
})();
