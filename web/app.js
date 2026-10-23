/* qpquiz-web 前端：原生 JS，无框架。 */

const app = document.getElementById("app");
const toastEl = document.getElementById("toast");
const tabs = document.getElementById("tabs");

const DIFF = { 1: "★☆☆", 2: "★★☆", 3: "★★★" };
const STORAGE_KEY = "qpquiz.session";

const ui = { view: "home", meta: null, session: null, feedback: null, summary: null, busy: false, qStart: 0 };
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

async function api(path, options = {}) {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `请求失败（${res.status}）`);
  return data;
}

let toastTimer = null;
function toast(message) {
  toastEl.textContent = message;
  toastEl.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toastEl.classList.remove("show"), 2200);
}

function fmtDuration(ms) {
  const total = Math.max(0, Math.round(ms / 1000));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function pct(value) {
  return `${(value * 100).toFixed(1)}%`;
}

/* -------------------------------------------------------------- 导航 */
function setTab(name) {
  for (const btn of tabs.querySelectorAll("button")) {
    btn.classList.toggle("active", btn.dataset.nav === name);
  }
}

function go(view) {
  if (ui.view === "quiz" && view !== "quiz" && ui.session && ui.session.status === "active") {
    if (!confirm("本轮还没答完，确定离开？")) return;
    ui.session = null;
    ui.feedback = null;
    localStorage.removeItem(STORAGE_KEY);
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
  if (ui.view === "home") renderHome();
  else if (ui.view === "quiz") renderQuiz();
  else if (ui.view === "result") renderResult();
  else if (ui.view === "stats") renderStats();
  else if (ui.view === "history") renderHistory();
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

  const resumeId = Number(localStorage.getItem(STORAGE_KEY));
  if (resumeId && !ui.session) {
    try {
      const session = await api(`/sessions/${resumeId}`);
      if (session.status === "active") {
        app.append(
          h("div", { class: "card", style: "margin-bottom:14px" },
            h("div", { class: "spread" },
              h("div", {}, h("h2", {}, "上次还有一轮没答完"), h("p", { style: "margin:0" }, `已答 ${session.answered}/${session.total} 题`)),
              h("button", { class: "btn primary", onclick: () => { ui.session = session; ui.feedback = null; ui.qStart = Date.now(); go("quiz"); } }, "继续")),
          ),
        );
      } else {
        localStorage.removeItem(STORAGE_KEY);
      }
    } catch {
      localStorage.removeItem(STORAGE_KEY);
    }
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
    }, name),
  );

  app.append(
    h("div", { class: "card" },
      h("h1", {}, "Python 自测"),
      h("p", {}, `${meta.question_count} 道内置题 · 答完自动记录成绩与错题`),

      h("div", { class: "field" },
        h("label", {}, "模式"),
        h("div", { class: "chips" },
          ["exam", "practice"].map((mode) =>
            h("button", {
              class: `chip${prefs.mode === mode ? " on" : ""}`,
              onclick: (event) => {
                prefs.mode = mode;
                event.target.parentElement.querySelectorAll(".chip").forEach((el) => el.classList.remove("on"));
                event.target.classList.add("on");
              },
            }, mode === "exam" ? "考试（最后统一看解析）" : "练习（立刻看解析）")),
        )),

      h("div", { class: "field" },
        h("label", {}, "题量"),
        h("div", { class: "chips" },
          [5, 10, 15].map((count) =>
            h("button", {
              class: `chip${prefs.count === count ? " on" : ""}`,
              onclick: (event) => {
                prefs.count = count;
                event.target.parentElement.querySelectorAll(".chip").forEach((el) => el.classList.remove("on"));
                event.target.classList.add("on");
              },
            }, `${count} 题`)),
        )),

      h("div", { class: "field" },
        h("label", {}, "分类（不选=全部）"),
        h("div", { class: "chips" }, catChips)),

      h("button", { class: "btn primary", style: "width:100%", onclick: startQuiz }, "开始答题"),
    ),
    h("p", { class: "center muted", style: "margin-top:16px;font-size:12px" },
      "提示：手机浏览器菜单里选「添加到主屏幕」，可以当 App 用。"),
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
    ui.qStart = Date.now();
    localStorage.setItem(STORAGE_KEY, String(session.id));
    go("quiz");
  } catch (err) {
    toast(err.message);
  }
}

/* -------------------------------------------------------------- 答题 */
function renderQuiz() {
  const session = ui.session;
  if (!session) return go("home");
  const question = session.question;
  if (!question) return showResult(session.id);

  const done = session.answered;
  const progress = h("div", { class: "progress" }, h("i", { style: `width:${(done / session.total) * 100}%` }));

  const options = question.options.map((text, index) => {
    const classes = ["option"];
    let disabled = Boolean(ui.feedback);
    if (ui.feedback) {
      if (index === ui.feedback.answer_index) classes.push("right");
      else if (ui.feedback.choice === index) classes.push("wrong");
    }
    return h("button", {
      class: classes.join(" "),
      disabled: disabled ? "" : null,
      onclick: () => submitAnswer(index),
    },
      h("span", { class: "key" }, String.fromCharCode(65 + index)),
      h("span", {}, text),
    );
  });

  app.append(
    h("div", { class: "card" },
      progress,
      h("div", { class: "meta-row" },
        h("span", {}, `第 ${question.position} / ${session.total} 题`),
        h("span", {}, session.mode === "practice" ? "练习模式" : "考试模式")),
      h("div", { class: "spread", style: "margin-bottom:10px" },
        h("span", { class: "badge" }, question.category),
        h("span", { class: "badge dim" }, `${DIFF[question.difficulty]} · ${question.points} 分`)),
      h("div", { class: "prompt" }, question.prompt),
      h("div", { class: "options" }, options),
      ui.feedback ? feedbackPanel() : null,
      ui.feedback ? null : h("div", { class: "row end", style: "margin-top:16px" },
        h("button", { class: "btn ghost", onclick: () => submitAnswer(null) }, "跳过"),
        h("button", { class: "btn ghost", onclick: () => go("home") }, "退出")),
    ),
  );
}

function feedbackPanel() {
  const fb = ui.feedback;
  const right = fb.correct;
  return h("div", { class: `feedback ${right ? "ok" : "bad"}` },
    h("strong", { style: `color:${right ? "var(--accent-2)" : "var(--danger)"}` },
      right ? `回答正确 +${fb.points} 分` : "回答错误"),
    h("p", { style: "margin:0 0 6px" }, `正确答案：${String.fromCharCode(65 + fb.answer_index)}`),
    h("p", { style: "margin:0 0 12px" }, fb.explanation),
    h("div", { class: "row end" },
      h("button", { class: "btn primary", onclick: continueAfterFeedback }, "继续")),
  );
}

async function submitAnswer(choice) {
  if (ui.busy || !ui.session || ui.feedback) return;
  ui.busy = true;
  try {
    const question = ui.session.question;
    const elapsed = Date.now() - ui.qStart;
    const res = await api(`/sessions/${ui.session.id}/answers`, {
      method: "POST",
      body: JSON.stringify({ question_id: question.id, choice, elapsed_ms: elapsed }),
    });
    ui.session = res.session;
    ui.feedback = res.feedback;
    if (ui.feedback) ui.feedback.choice = choice;
    if (!ui.feedback && ui.session.status === "finished") {
      await showResult(ui.session.id);
      return;
    }
    render();
  } catch (err) {
    toast(err.message);
  } finally {
    ui.busy = false;
  }
}

async function continueAfterFeedback() {
  ui.feedback = null;
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
    localStorage.removeItem(STORAGE_KEY);
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
        h("span", { class: "muted" }, `你的选择：${item.choice === null ? "跳过" : String.fromCharCode(65 + item.choice)}　正确：${String.fromCharCode(65 + item.answer_index)}`)),
      h("div", { class: "prompt" }, item.question.prompt),
      h("p", { style: "margin:0" }, item.explanation)),
  );

  app.append(
    h("div", { class: "card" },
      h("div", { class: "score-hero" },
        h("div", { class: "value" }, `${summary.score}`, h("small", {}, ` / ${summary.max_score}`)),
        h("p", { style: "margin:4px 0 0" }, `${summary.correct}/${summary.total} 正确 · 正确率 ${pct(summary.accuracy)}`)),
      h("div", { class: "grid" },
        h("div", { class: "stat" }, h("span", {}, "用时"), h("b", {}, fmtDuration(summary.duration_ms))),
        h("div", { class: "stat" }, h("span", {}, "模式"), h("b", { style: "font-size:17px" }, summary.mode === "practice" ? "练习" : "考试")),
        h("div", { class: "stat" }, h("span", {}, "题目数"), h("b", {}, String(summary.total)))),
      summary.categories.length ? h("h2", { style: "margin-top:18px" }, "分类正确率") : null,
      summary.categories.map((item) =>
        h("div", { style: "margin-bottom:12px" },
          h("div", { class: "spread" }, h("span", {}, item.category), h("span", { class: "muted" }, `${item.correct}/${item.total}`)),
          h("div", { class: "bar" }, h("i", { style: `width:${(item.correct / item.total) * 100}%` })))),
      wrong.length ? h("h2", { style: "margin-top:18px" }, `错题回顾（${wrong.length}）`) : null,
      wrong,
      h("div", { class: "row", style: "margin-top:18px" },
        h("button", { class: "btn primary", onclick: startQuiz }, "再来一轮"),
        h("button", { class: "btn ghost", onclick: () => go("stats") }, "看统计")),
    ),
  );
}

/* -------------------------------------------------------------- 统计 */
async function renderStats() {
  try {
    const data = await api("/stats");
    const stats = data.stats;
    const cards = [
      ["答题轮数", String(stats.sessions)],
      ["累计题数", String(stats.answers)],
      ["总正确率", pct(stats.accuracy)],
      ["最佳单轮", `${stats.best_score} 分`],
    ];
    const rows = data.categories.map((item) =>
      h("div", { style: "margin-bottom:12px" },
        h("div", { class: "spread" }, h("span", {}, item.category), h("span", { class: "muted" }, `${item.correct}/${item.total} · ${pct(item.accuracy)}`)),
        h("div", { class: "bar" }, h("i", { style: `width:${item.accuracy * 100}%` }))));

    app.append(
      h("div", { class: "card" },
        h("h1", {}, "统计"),
        h("div", { class: "grid" }, cards.map(([label, value]) => h("div", { class: "stat" }, h("span", {}, label), h("b", {}, value)))),
        h("p", { style: "margin-top:14px" }, `平均分 ${stats.average_score.toFixed(1)} · 最近一次 ${stats.last_played ? stats.last_played.replace("T", " ").slice(0, 16) : "暂无"}`),
        rows.length ? h("h2", { style: "margin-top:18px" }, "分类正确率") : null,
        rows,
        rows.length ? null : h("p", { class: "center muted" }, "还没有记录，先去答一轮吧。")),
    );
  } catch (err) {
    toast(err.message);
  }
}

/* -------------------------------------------------------------- 历史 */
async function renderHistory() {
  try {
    const data = await api("/history?limit=30");
    const items = data.sessions.map((session) =>
      h("div", {
        class: "list-item",
        style: "cursor:pointer",
        onclick: () => showResult(session.id),
      },
        h("div", {},
          h("div", {}, `${session.mode === "practice" ? "练习" : "考试"} · ${session.correct}/${session.total}`),
          h("div", { class: "muted", style: "font-size:12px" },
            `${session.started_at.replace("T", " ").slice(0, 16)}${session.status === "finished" ? "" : " · 未完成"}`)),
        h("b", {}, `${session.score} 分`)));

    app.append(
      h("div", { class: "card" },
        h("h1", {}, "历史记录"),
        items.length ? h("div", { class: "list" }, items) : h("p", { class: "center muted" }, "还没有历史记录。")),
    );
  } catch (err) {
    toast(err.message);
  }
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
  const key = event.key.toLowerCase();
  const index = "1234".indexOf(key) >= 0 ? "1234".indexOf(key) : "abcd".indexOf(key);
  if (index >= 0 && index < ui.session.question.options.length) submitAnswer(index);
  if (key === "s") submitAnswer(null);
});

/* -------------------------------------------------------------- 启动 */
render();
