// PSPtool UI. Plain JS, talks to /api/*.
"use strict";

const $ = (s, el = document) => el.querySelector(s);
const h = (tag, attrs = {}, ...kids) => {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (v !== false && v != null) el.setAttribute(k, v === true ? "" : v);
  }
  for (const k of kids.flat()) if (k != null) el.append(k.nodeType ? k : String(k));
  return el;
};

// replaceChildren that skips null/false (optional parts of a view)
const fill = (el, ...kids) => el.replaceChildren(...kids.flat().filter(k => k != null && k !== false));

const ICONS = {
  search: '<path d="M7 12A5 5 0 1 0 7 2a5 5 0 0 0 0 10Zm4-1 3.5 3.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>',
  copy: '<rect x="5" y="5" width="9" height="9" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M11 3H3.5A1.5 1.5 0 0 0 2 4.5V11" fill="none" stroke="currentColor" stroke-width="1.5"/>',
  all: '<path d="M2 4h9M2 8h9M2 12h6m3.5-1.5L13 12l2.5-3" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>',
  spark: '<path d="M8 1.5 9.4 6.6 14.5 8 9.4 9.4 8 14.5 6.6 9.4 1.5 8l5.1-1.4Z" fill="currentColor"/>',
  check: '<path d="m3.5 8.5 3 3 6-7" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
  play: '<path d="M4.5 2.5v11l9-5.5Z" fill="currentColor"/>',
  eye: '<path d="M1.5 8S4 3.5 8 3.5 14.5 8 14.5 8 12 12.5 8 12.5 1.5 8 1.5 8Z" fill="none" stroke="currentColor" stroke-width="1.5"/><circle cx="8" cy="8" r="2" fill="currentColor"/>',
  undo: '<path d="M5.5 3 2.5 6l3 3" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/><path d="M3 6h6.5a4 4 0 0 1 0 8H7" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>',
  icon: '<rect x="2.5" y="2.5" width="11" height="11" rx="3" fill="none" stroke="currentColor" stroke-width="1.5"/><circle cx="8" cy="8" r="2.2" fill="currentColor"/>',
  close: '<path d="m4 4 8 8m0-8-8 8" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>',
  download: '<path d="M8 2v8m-3.5-3.5L8 10l3.5-3.5M2.5 13.5h11" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>',
};
const icon = name => {
  const s = h("span", { class: "i" });
  s.innerHTML = `<svg viewBox="0 0 16 16">${ICONS[name]}</svg>`;
  return s;
};
const iconBtn = (name, title, onclick, label) => h("button", { class: "icon-btn", title, onclick }, icon(name), label || null);
const drawIcons = (root = document) => root.querySelectorAll("[data-icon]").forEach(el => {
  el.innerHTML = `<svg viewBox="0 0 16 16">${ICONS[el.dataset.icon]}</svg>`;
});
const seg = (el, onchange) => {
  el.addEventListener("click", e => {
    const b = e.target.closest("button"); if (!b) return;
    el.querySelectorAll("button").forEach(x => x.classList.toggle("on", x === b));
    onchange(b.dataset.v);
  });
  return () => el.querySelector("button.on").dataset.v;
};
// settings form: [label, control...] rows
const form = rows => h("div", { class: "form" }, ...rows.filter(Boolean).flatMap(([l, ...c]) => [h("label", {}, l), h("div", { class: "f" }, ...c)]));
// the screen's title row: an h1 and one grey line about the data
const titlebar = (title, sub, ...right) => h("div", { class: "titlebar" }, h("h1", {}, title),
  sub ? h("span", { class: "sub" }, sub) : null, right.length ? h("span", { class: "sp" }) : null, ...right);
const section = (title, ...kids) => h("div", { class: "section" }, title ? h("h2", {}, title) : null, ...kids);

// pages of PAGE items: ‹ 1 2 … 9 › ; onpage(n) re-renders
const PAGE = 300;
// a path input with "Обзор": the server opens the system file dialog
// (a web page never gets full paths of chosen files)
function pathField(input, kind = "open", prompt = "", name = "") {
  const b = h("button", { type: "button", class: "btn", title: "Выбрать в Finder", onclick: async () => {
    b.disabled = true;
    try {
      const r = await api("pick", { body: { kind, prompt, start: input.value || input.placeholder || "", name } });
      if (r.path) {
        input.value = kind === "folder" ? r.path.replace(/\/$/, "") : r.path;
        input.dispatchEvent(new Event("input"));
        input.dispatchEvent(new Event("change"));
      }
    } catch (e) { alert(e.message); }
    b.disabled = false;
  } }, "Обзор…");
  return h("div", { class: "pathrow" }, input, state.project?.client_remote ? null : b);
}

// several values out of a list: a button with the count, a popover of
// checkboxes. options: [[value, text, count]]; onchange(values) on close
function multiPick(label, options, selected, onchange, allText = "все") {
  let chosen = new Set(selected);
  const btn = h("button", { type: "button", class: "btn mpick-btn" });
  const paint = () => { btn.textContent = `${label}: ${chosen.size ? (chosen.size === 1 ? [...chosen][0] : chosen.size) : allText}`; };
  const pop = h("div", { class: "mpick-pop", hidden: true });
  const boxes = options.map(([v, text, n]) => {
    const c = h("input", { type: "checkbox", checked: chosen.has(v) });
    c.onchange = () => { c.checked ? chosen.add(v) : chosen.delete(v); paint(); };
    return [v, c, h("label", { class: "mpick-row" }, c, h("span", {}, text), n != null ? h("span", { class: "muted small num" }, n) : null)];
  });
  const setAll = on => { boxes.forEach(([v, c]) => { c.checked = on; on ? chosen.add(v) : chosen.delete(v); }); paint(); };
  fill(pop, h("div", { class: "mpick-tools" },
      h("button", { type: "button", class: "icon-btn", onclick: () => setAll(true) }, "Выбрать все"),
      h("button", { type: "button", class: "icon-btn", onclick: () => setAll(false) }, "Сбросить")),
    h("div", { class: "mpick-list" }, ...boxes.map(b => b[2])));
  const wrap = h("div", { class: "mpick" }, btn, pop);
  let before = null;
  const close = () => {
    if (pop.hidden) return;
    pop.hidden = true;
    document.removeEventListener("pointerdown", outside, true);
    const now = [...chosen].sort().join(",");
    if (now !== before) onchange([...chosen]);
  };
  const outside = e => { if (!wrap.contains(e.target)) close(); };
  btn.onclick = () => {
    if (!pop.hidden) return close();
    before = [...chosen].sort().join(",");
    pop.hidden = false;
    document.addEventListener("pointerdown", outside, true);
  };
  wrap.addEventListener("keydown", e => { if (e.key === "Escape") { e.stopPropagation(); close(); } });
  paint();
  return wrap;
}

function pager(total, page, onpage, size = PAGE) {
  const pages = Math.ceil(total / size);
  if (pages <= 1) return null;
  const btn = (n, label = String(n + 1)) => h("button", { class: n === page ? "on" : "", disabled: n < 0 || n >= pages,
    onclick: () => onpage(n) }, label);
  const nums = [...new Set([0, page - 2, page - 1, page, page + 1, page + 2, pages - 1])].filter(n => n >= 0 && n < pages).sort((a, b) => a - b);
  const kids = [btn(page - 1, "‹")];
  nums.forEach((n, i) => { if (i && n - nums[i - 1] > 1) kids.push(h("span", { class: "gap" }, "…")); kids.push(btn(n)); });
  kids.push(btn(page + 1, "›"));
  return h("div", { class: "pager" }, ...kids,
    h("span", { class: "muted small" }, `${page * size + 1}–${Math.min(total, (page + 1) * size)} из ${total}`));
}

async function api(path, opts = {}) {
  const r = await fetch("/api/" + path, {
    method: opts.method || (opts.body ? "POST" : "GET"),
    headers: opts.body ? { "Content-Type": "application/json" } : {},
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (r.status === 401) { location.href = "/login.html"; throw new Error("login"); }
  const data = await r.json();
  if (!r.ok) throw new Error(data.error || r.statusText);
  return data;
}

const state = { project: null, tab: "project", entry: null, summary: [], icons: [] };
const TABS = [
  { id: "project", title: "Проект" },
  { id: "texts", title: "Текст", feature: "texts" },
  { id: "font", title: "Шрифт", feature: "font" },
  { id: "llm", title: "LLM", feature: "texts" },
  { id: "textures", title: "Текстуры", feature: "textures" },
  { id: "hd", title: "HD-текстуры", feature: "textures" },
  { id: "charmap", title: "Таблица символов", feature: "charmap" },
];

// ---- tabs ---------------------------------------------------------------

function renderTabs() {
  const feats = state.project?.plugin?.features || [];
  $("#play").hidden = !state.project?.open;
  // the scope next to the mark: which game this project translates
  $("#scope").textContent = state.project?.open ? (state.project.plugin?.name || state.project.meta?.title || "") : "";
  fill($("#tabs"), ...TABS.filter(t => !t.feature || (state.project?.open && feats.includes(t.feature)))
    .map(t => h("button", { class: t.id === state.tab ? "on" : "", onclick: () => show(t.id) }, t.title)));
}

function show(tab) {
  state.tab = tab;
  try { localStorage.setItem("psptool.tab", tab); } catch (e) {}
  for (const v of document.querySelectorAll(".view")) v.hidden = v.id !== "view-" + tab;
  renderTabs();
  ({ project: renderProject, texts: loadTexts, charmap: loadCharmap, font: renderFont, llm: renderLLM, textures: loadTextures, hd: () => renderHd($("#view-hd")).then(() => renderMovies($("#view-hd"))) })[tab]?.();
}

// ---- jobs ---------------------------------------------------------------

// jobLog: the log element of the page that started the job; jobOwner: that
// job's name, so a log never shows the output of a job started elsewhere
let jobLog = null, jobNext = 0, jobOwner = null;
async function runJob(what, body = {}) {
  await api("run/" + what, { body });
  jobNext = 0;
  jobOwner = what;
  if (jobLog) jobLog.textContent = "";
  pollJob();
}
async function pollJob() {
  const j = await api("job?since=" + jobNext);
  jobNext = j.next;
  if (jobLog && j.name === jobOwner) { jobLog.textContent += j.log.map(l => l + "\n").join(""); jobLog.scrollTop = 1e9; }
  const bar = $("#jobbar");
  bar.hidden = !j.name;
  const pr = j.progress && j.progress[1] ? Math.min(100, Math.round(100 * j.progress[0] / j.progress[1])) : null;
  bar.textContent = j.running ? j.name + (pr != null ? ` ${pr}%` : "…") : j.error ? j.name + ": ошибка" : j.name + ": готово";
  document.querySelectorAll(".jobpanel").forEach(p => paintJob(p, j, pr));
  bar.title = (j.error ? j.error + "\n" : "") + "Открыть журнал";
  bar.className = "pill" + (j.error ? " err" : j.running ? " run" : "");
  document.querySelectorAll("[data-job]").forEach(b => b.disabled = j.running);
  if (j.running) setTimeout(pollJob, 500);
  // a failed job whose page shows no log (Play in the header): open the log
  if (!j.running && j.error && jobOwner === j.name && !(jobLog && jobLog.offsetParent)) { jobOwner = null; showJobLog(); }
  if (!j.running && j.name) { state.project = await api("project"); renderTabs(); if (state.tab === "project") renderProject(false); if (state.tab === "hd") renderHd($("#view-hd")).then(() => renderMovies($("#view-hd"))); }
}
function paintJob(p, j, pr) {
  p.querySelector(".jbar i").style.width = (pr ?? (j.running ? 0 : 100)) + "%";
  p.querySelector(".jbar").classList.toggle("err", !!j.error);
  p.querySelector(".jnum").textContent = j.progress ? `${Math.min(j.progress[0], j.progress[1])} из ${j.progress[1]}` + (pr != null ? ` · ${pr}%` : "")
    : j.running ? "…" : "";
  if (!j.running) p.querySelector(".jtitle").textContent = j.error ? "Ошибка: " + j.error : j.stopping ? "Остановлено" : "Готово";
  const stop = p.querySelector(".jstop");
  if (stop) {
    stop.hidden = !(j.running && j.stoppable);
    stop.disabled = !!j.stopping;
    stop.textContent = j.stopping ? "Останавливаю…" : "Стоп";
    stop.onclick = () => api("job/stop", { body: {} }).then(() => pollJob());
  }
}
function openJobPanel(p, title) {
  p.hidden = false;
  p.querySelector(".jtitle").textContent = title;
  p.querySelector(".log").textContent = "";
  p.querySelector(".jclose").onclick = () => { p.hidden = true; };
  const log = p.querySelector(".log"), tg = p.querySelector(".jtoggle");
  tg.onclick = () => { log.hidden = !log.hidden; tg.textContent = log.hidden ? "▾" : "▴"; };
  jobLog = log;
}

// the whole log of the last job, error last; the pill in the header opens it
async function showJobLog() {
  const j = await api("job?since=0");
  let m = $("#job-log");
  if (!m) { m = h("div", { id: "job-log", class: "modal" }); document.body.append(m); m.onclick = () => { m.hidden = true; }; }
  m.hidden = false;
  const text = j.log.join("\n") + (j.error ? "\n\nОшибка: " + j.error : "");
  const copy = h("button", { class: "btn", onclick: () => navigator.clipboard.writeText(text).then(() => { copy.textContent = "Скопировано"; }) }, "Копировать");
  const pre = h("pre", { class: "log" });
  for (const l of j.log) pre.append(h("div", { class: /Traceback|Error\b|ошибк/.test(l) ? "err" : "" }, l));
  if (j.error) pre.append(h("div", { class: "err" }, "Ошибка: " + j.error));
  fill(m, h("div", { class: "box wide", onclick: e => e.stopPropagation() },
    h("h2", {}, "Журнал: " + j.name, h("span", { class: j.error ? "status err" : "muted" }, j.running ? "идёт…" : j.error ? "ошибка" : "готово"),
      h("span", { class: "sp" }), copy,
      h("button", { class: "icon-btn", title: "Закрыть", onclick: () => { m.hidden = true; } }, icon("close"))),
    h("div", { class: "joblog" }, pre, j.log_file ? h("div", { class: "muted small" }, "Сохранён в " + j.log_file) : null)));
  pre.scrollTop = 1e9;
}
document.addEventListener("keydown", e => { if (e.key === "Escape" && $("#job-log")) $("#job-log").hidden = true; });

async function waitJob(then) {
  const j = await api("job");
  if (j.running) return setTimeout(() => waitJob(then), 1000);
  then();
}

// ---- project ------------------------------------------------------------

function renderProject(resetLog = true) {
  const p = state.project, v = $("#view-project");
  const kids = [];
  if (!p.open) {
    const iso = h("input", { type: "text", placeholder: "/путь/к/игре.iso" });
    const dir = h("input", { type: "text", placeholder: "/путь/к/папке" });
    const msg = h("span", { class: "status err" });
    kids.push(section("Новый проект", form([["Образ игры", pathField(iso, "open", "Образ игры (.iso)")],
      ["Папка проекта", pathField(dir, "folder", "Папка проекта")]]),
      h("div", { class: "actions" }, msg, h("button", { class: "btn primary", onclick: async () => {
        msg.textContent = "";
        try { state.project = await api("init", { body: { iso: iso.value, workdir: dir.value } }); show("project"); }
        catch (e) { msg.textContent = e.message; }
      } }, "Создать"))));
  } else {
    const go = h("button", { class: "btn", hidden: true }, "Продолжить перевод");
    // the answer, then the next job at the card's foot, beside the finding that calls for it
    const progress = h("div", { class: "section progress" }, h("div", { class: "figures" }),
      h("div", { class: "actions" }, h("p", { class: "finding" }), go));
    const map = h("div", { class: "section" });
    kids.push(titlebar(p.plugin.name, `${(p.meta.title || "").normalize("NFKC")} · ${p.meta.disc_id}`),
      p.texts ? h("div", { class: "overview" }, progress, map) : null);
    if (p.texts) renderOverview(progress, map, go);
    const ref = h("input", { type: "text", placeholder: "Путь к образу другой версии", value: p.meta.ref_iso || "" });
    const out = h("input", { type: "text", value: p.root.replace(/\/$/, "") + "/out.iso" });
    const step = (title, extra, btn, fn, done) => h("div", { class: "step" + (extra?.classList?.contains("pathrow") ? " field" : "") },
      h("span", { class: "dot" + (done ? " done" : "") }, done ? icon("check") : null),
      h("div", {}, h("div", { class: "t" }, title), extra),
      h("button", { class: "btn" + (btn.primary ? " primary" : ""), "data-job": true, onclick: fn }, btn.label));
    const steps = [step("Распаковать образ", h("div", { class: "muted small path" }, p.meta.iso), { label: "Распаковать", primary: !p.unpacked }, () => runJob("unpack"), p.unpacked)];
    if (p.plugin.features.includes("texts")) {
      steps.push(step("Текст игры", null, { label: p.texts ? "Обновить" : "Достать", primary: p.unpacked && !p.texts }, () => runJob("texts"), p.texts));
      steps.push(step("Подсказка из другой версии", pathField(ref, "open", "Образ другой версии (.iso)"),
        { label: p.meta.ref_iso ? "Обновить" : "Загрузить" }, () => runJob("ref", { iso: ref.value }), !!p.ref));
    }
    if (p.plugin.features.includes("movies")) {
      steps.push(step("Субтитры роликов", h("div", { class: "muted small" }, "из роликов подсказки"),
        { label: p.movies ? "Обновить" : "Достать" }, () => runJob("subs"), p.movies));
    }
    if (p.plugin.features.includes("eboot")) {
      const eb = h("input", { type: "text", placeholder: "~/.config/ppsspp/PSP/SYSTEM/DUMP/" + p.meta.disc_id + "_EBOOT.BIN" });
      steps.push(step("Патч EBOOT", pathField(eb, "open", "Расшифрованный EBOOT.BIN (дамп PPSSPP)"), { label: p.eboot ? "Заменить" : "Загрузить" }, () => runJob("eboot", { path: eb.value || eb.placeholder }), p.eboot));
    }
    steps.push(step("Собрать образ", pathField(out, "save", "Куда сохранить образ", "out.iso"), { label: "Собрать", primary: p.texts }, () => runJob("pack", { out: out.value }), false));
    if (resetLog || !jobLog) jobLog = h("pre", { class: "log" });
    kids.push(section("Шаги", h("div", { class: "steps" }, ...steps), jobLog));
  }
  if (p.recent?.length > (p.open ? 1 : 0)) {
    kids.push(section("Недавние", h("div", { class: "steps" }, ...p.recent.filter(r => r !== p.root).map(r =>
      h("div", { class: "step" }, h("span"), h("div", {}, r), h("button", { class: "btn", onclick: async () => {
        state.project = await api("open", { body: { workdir: r } }); show("project");
      } }, "Открыть"))))));
  }
  const ocrSlot = h("div"), remoteSlot = h("div");
  fill(v, ...kids, ocrSlot, remoteSlot);
  if (p.open) renderPlaytest(v, ocrSlot);
  if (!p.client_remote) { renderOcr(ocrSlot); renderRemote(remoteSlot); }
}

// text recognition engine (movie subtitles, text in textures)
async function renderOcr(slot) {
  const o = await api("ocr");
  const sel = h("select", { onchange: () => api("ocr", { method: "PUT", body: { engine: sel.value } }).then(() => renderOcr(slot)) },
    ...Object.entries(o.engines).filter(([k]) => k !== "vision" || o.vision).map(([k, t]) => h("option", { value: k, selected: k === o.engine }, t)));
  const exe = h("input", { type: "text", value: o.tesseract, placeholder: "tesseract" });
  exe.addEventListener("change", () => api("ocr", { method: "PUT", body: { tesseract: exe.value } }).then(() => renderOcr(slot)));
  const names = { vision: "macOS Vision", tesseract: "Tesseract" };
  const langs = o.tesseract ? (o.tesseract_langs.length ? "языки: " + o.tesseract_langs.join(", ") : "нет языков jpn/eng: установите tesseract-lang") : "не найден";
  fill(slot, section("Распознавание текста", form([
    ["Движок", h("div", {}, sel, h("div", { class: "muted small" }, o.active ? "сейчас работает: " + names[o.active] : "ни одного движка: установите Tesseract"))],
    ["Tesseract", h("div", { style: "width:100%" }, pathField(exe, "open", "Программа tesseract"), h("div", { class: "muted small" }, langs))],
  ])));
}

// access from the phone / other computers: only set up on this computer
async function renderRemote(slot) {
  const r = await api("remote");
  const pw = h("input", { type: "password", placeholder: r.has_password ? "задан, введите новый чтобы сменить" : "не короче 6 символов", autocomplete: "new-password" });
  const msg = h("span", { class: "status" });
  const put = async body => {
    msg.textContent = ""; msg.className = "status";
    try { await api("remote", { method: "PUT", body }); }
    catch (e) { msg.textContent = e.message; msg.className = "status err"; return; }
    setTimeout(() => renderRemote(slot), body.on !== undefined ? 900 : 0);  // the server moves to the new address first
  };
  const on = h("input", { type: "checkbox", checked: r.on, onchange: () => put({ on: on.checked }) });
  const ts = r.tailscale;
  const tsLine = !ts.installed ? h("span", {}, "не установлен · ", h("a", { href: "https://tailscale.com/download", target: "_blank" }, "скачать"))
    : !ts.running ? "установлен, но не подключён: откройте Tailscale и войдите"
    : "подключён" + (ts.name ? " · " + ts.name : "");
  const links = r.addresses.length ? h("div", { class: "addrs" }, ...r.addresses.map(a =>
    h("div", {}, h("span", { class: "muted small" }, a.kind === "tailscale" ? "Tailscale" : "Wi-Fi"), h("code", {}, a.url))))
    : h("span", { class: "muted" }, r.on ? "…" : "выключено");
  const sec = section("Доступ с других устройств", form([
    ["Пароль", h("div", { class: "pathrow" }, pw, h("button", { type: "button", class: "btn", onclick: () => pw.value && put({ password: pw.value }) }, "Сохранить"))],
    ["Доступ", h("label", { class: "check" }, on, h("span", {}, "Открыть для телефона и других компьютеров"))],
    ["Tailscale", h("span", {}, tsLine)],
    ["Адреса", links],
  ]), h("div", { class: "actions" }, msg));
  fill(slot, sec);
}

// all upscaled textures, before / after. Filters (original size, model,
// marked), marks: a set to redo with another model
const MODEL_SHORT = { waifu2x: "waifu2x", cugan: "CUGAN", "anime-video": "ESRGAN", anime: "ESRGAN+", resize: "без ИИ", "?": "?" };
async function hdGallery(f = {}) {
  f = { page: 0, q: "", size: "", model: "", marked: false, ...f };
  let m = $("#hd-gallery");
  if (!m) { m = h("div", { id: "hd-gallery", class: "modal" }); document.body.append(m); m.onclick = () => { m.hidden = true; }; }
  const st = await api("hd");
  const qs = new URLSearchParams({ offset: f.page * 60, limit: 60, q: f.q, size: f.size, model: f.model, marked: f.marked ? "1" : "" });
  const res = await api("hd/gallery?" + qs);
  const marks = await api("hd/marks");
  const again = patch => hdGallery({ ...f, page: 0, ...patch });
  const find = h("input", { type: "search", placeholder: "Имя файла", value: f.q });
  find.onchange = () => again({ q: find.value.trim() });
  const split = v => v ? v.split(",") : [];
  const size = multiPick("Размеры", res.sizes.map(([k, n]) => [k, k, n]), split(f.size), v => again({ size: v.join(",") }));
  const model = multiPick("Модели", res.models.map(([k, n]) => [k, MODEL_SHORT[k] || k, n]), split(f.model), v => again({ model: v.join(",") }));
  const onlyMarked = h("input", { type: "checkbox", checked: f.marked });
  onlyMarked.onchange = () => again({ marked: onlyMarked.checked });
  const markFilter = async value => { await api("hd/marks", { body: { filter: f, value } }); hdGallery(f); };
  const ver = Date.now();
  const thumb = (n, which) => h("img", { src: `/api/hd/thumb?name=${encodeURIComponent(n)}&which=${which}&v=${ver}`, loading: "lazy" });
  const card = it => {
    const box = h("input", { type: "checkbox", checked: it.marked, title: "Отметить", onclick: e => e.stopPropagation() });
    box.onchange = async () => {
      const r = await api("hd/marks", { method: "PUT", body: { names: [it.name], value: box.checked } });
      cnt.textContent = r.count; redo.disabled = !r.count;
      el.classList.toggle("marked", box.checked);
    };
    const el = h("div", { class: "hdpair" + (it.marked ? " marked" : ""), title: it.name, onclick: () => hdCompare(it, st, () => hdGallery(f)) },
      thumb(it.name, "orig"), thumb(it.name, "hd"),
      h("div", { class: "cap muted small" }, box, h("span", {}, `${it.w}×${it.h}`),
        h("span", { class: "badge" }, (MODEL_SHORT[(it.by || "?").split(" ")[0]] || it.by) + (it.by ? " " + it.by.split(" ")[1] : ""))));
    return el;
  };
  const cnt = h("b", {}, marks.count);
  const rmodel = h("select", {}, ...st.models.map(x => h("option", { value: x.id, disabled: !x.ok, selected: x.id === st.hd.model }, x.name)));
  const rscale = h("select", {}, ...[2, 3, 4].map(n => h("option", { value: n, selected: n === (st.hd.scale || 3) }, "×" + n)));
  const redo = h("button", { class: "btn primary", "data-job": true, disabled: !marks.count, onclick: async () => {
    // the HD tab picks up the running job and shows its progress
    await runJob("hd", { marked: true, model: rmodel.value, scale: +rscale.value });
    m.hidden = true;
    show("hd");
  } }, "Пересчитать отмеченные");
  const go = n => hdGallery({ ...f, page: n });
  fill(m, h("div", { class: "box wide", onclick: e => e.stopPropagation() },
    h("h2", {}, "Галерея HD", h("span", { class: "muted small" }, `${res.total}`), h("span", { class: "sp" }),
      h("button", { class: "icon-btn", title: "Закрыть", onclick: () => { m.hidden = true; } }, icon("close"))),
    h("div", { class: "hdgal" },
      h("div", { class: "toolbar" }, size, model, h("label", { class: "switch" }, onlyMarked, "Отмеченные"),
        h("div", { class: "search grow" }, icon("search"), find),
        h("button", { class: "btn", onclick: () => markFilter(true), title: "Отметить все текстуры, что подходят под фильтр" }, `Отметить все ${res.total}`),
        h("button", { class: "btn", onclick: () => markFilter(false), title: "Снять отметку с текстур под фильтром" }, "Снять")),
      pager(res.total, f.page, go, 60),
      res.items.length ? h("div", { class: "hdgrid" }, ...res.items.map(card)) : h("p", { class: "muted" }, "Ничего нет"),
      pager(res.total, f.page, go, 60)),
    h("div", { class: "hdbar" }, h("span", {}, "Отмечено: ", cnt), h("span", { class: "sp" }), rmodel, rscale, redo)));
  m.hidden = false;
}

// one texture big: a slider between the original and the HD version
function hdCompare(it, st, back) {
  const m = $("#hd-gallery");
  const ver = Date.now();
  const room = Math.max(240, Math.min(640, window.innerHeight - 220, window.innerWidth - 80));
  const zoom = Math.min(4, room / Math.max(it.w, it.h));
  const W = it.w * zoom, H = it.h * zoom;
  const hd = h("img", { src: `/api/hd/img?name=${encodeURIComponent(it.name)}&which=hd&v=${ver}`, style: `width:${W}px;height:${H}px` });
  const orig = h("img", { class: "px", src: `/api/hd/img?name=${encodeURIComponent(it.name)}&which=orig`, style: `width:${W}px;height:${H}px` });
  const clip = h("div", { class: "clip", style: `width:${W / 2}px` }, orig);
  const bar = h("i", { class: "bar", style: `left:${W / 2}px` });
  const view = h("div", { class: "slider", style: `width:${W}px;height:${H}px` }, hd, clip, bar);
  const move = e => { const r = view.getBoundingClientRect(); const x = Math.max(0, Math.min(W, e.clientX - r.left)); clip.style.width = x + "px"; bar.style.left = x + "px"; };
  view.addEventListener("pointermove", e => { if (e.buttons || e.pointerType === "mouse") move(e); });
  const model = h("select", {}, ...st.models.map(x => h("option", { value: x.id, disabled: !x.ok, selected: x.id === st.hd.model }, x.name)));
  const scale = h("select", {}, ...[2, 3, 4].map(n => h("option", { value: n, selected: n === Math.round(it.hw / it.w) }, "×" + n)));
  const msg = h("span", { class: "msg" });
  fill(m, h("div", { class: "box wide", onclick: e => e.stopPropagation() },
    h("h2", {}, it.name, h("span", { class: "muted small" }, `${it.w}×${it.h} → ${it.hw}×${it.hh}`), h("span", { class: "sp" }),
      h("button", { class: "btn", onclick: back }, "Назад"),
      h("button", { class: "icon-btn", title: "Закрыть", onclick: () => { m.hidden = true; } }, icon("close"))),
    h("div", { class: "hdcmp" }, h("div", { class: "muted small labels" }, h("span", {}, "до"), h("span", {}, "после")), view,
      h("div", { class: "actions" }, msg, model, scale,
        h("button", { class: "btn primary", "data-job": true, onclick: async () => {
          msg.textContent = "Считаю…";
          await api("run/hd", { body: { names: [it.name], model: model.value, scale: +scale.value } });
          waitJob(() => { msg.textContent = ""; it.hw = it.w * +scale.value; it.hh = it.h * +scale.value; hdCompare(it, st, back); });
        } }, "Пересчитать")))));
  m.hidden = false;
}

// the project's answer: how far the translation is, and where it is not
async function renderOverview(progress, map, go) {
  const sum = state.summary = await api("texts");
  const tot = k => sum.reduce((a, e) => a + (e[k] || 0), 0);
  const total = tot("total"), done = tot("done"), checked = tot("checked");
  const pct = (a, b) => b ? Math.floor(100 * a / b) : 0;
  const filesDone = sum.filter(e => e.total && e.done === e.total).length;
  const fig = (label, value, unit, lead) => h("div", { class: "figure" + (lead ? " lead" : "") },
    h("div", { class: "label" }, label), h("div", { class: "value" }, value), unit ? h("div", { class: "unit" }, unit) : null);
  fill(progress.querySelector(".figures"),
    fig("Переведено", `${pct(done, total)}%`, `${done.toLocaleString("ru")} из ${total.toLocaleString("ru")} строк`, true),
    fig("Проверено", `${pct(checked, total)}%`, `${checked.toLocaleString("ru")} строк`),
    fig("Файлов готово", filesDone, `из ${sum.length}`));
  const open = sum.filter(e => e.done < e.total).sort((a, b) => (b.total - b.done) - (a.total - a.done));
  const left = total - done;
  progress.querySelector(".finding").textContent = left
    ? `Осталось ${left.toLocaleString("ru")} строк в ${open.length} файлах; больше всего в ${open[0].name || String(open[0].entry).padStart(4, "0")}: ${open[0].total - open[0].done}.`
    : (checked < total ? `Всё переведено; не проверено ещё ${(total - checked).toLocaleString("ru")} строк.` : "Всё переведено и проверено.");
  const next = sum.find(e => e.done < e.total) || sum.find(e => (e.checked || 0) < e.total);
  if (next) {
    go.hidden = false;
    go.textContent = next.done < next.total ? `Продолжить: ${next.name || String(next.entry).padStart(4, "0")}` : "Проверять дальше";
    go.onclick = () => { show("texts"); openEntry(next.entry); };
  }
  // one cell per file: the deeper the orange, the more is translated; green when checked
  const level = e => !e.total || !e.done ? "" : (e.checked || 0) === e.total ? "c4" : e.done === e.total ? "c3" : e.done / e.total >= .5 ? "c2" : "c1";
  const key = (cls, label) => h("span", {}, h("i", { class: "cells-key " + cls, style: `background:${{ "": "var(--raised)", c1: "color-mix(in srgb, var(--accent) 35%, var(--raised))", c3: "var(--accent)", c4: "var(--positive)" }[cls]}` }), label);
  fill(map, h("div", { class: "cover" },
    h("div", { class: "cover-head" }, h("h2", {}, "Файлы игры"),
      h("div", { class: "cover-key" }, key("", "не тронут"), key("c1", "начат"), key("c3", "переведён"), key("c4", "проверен"))),
    h("div", { class: "cells" }, ...sum.map(e => h("button", {
      class: level(e), title: `${e.name || String(e.entry).padStart(4, "0")} · ${e.done} из ${e.total} · проверено ${e.checked || 0}\n${e.preview}`,
      "aria-label": `${e.name || e.entry}: ${e.done} из ${e.total}`,
      onclick: () => { show("texts"); openEntry(e.entry); } })))));
}

// before an upscale run: which model, how big, which original sizes (and on
// a redo, which of the current results); the count updates as you choose
async function hdRunDialog(redo, st, run) {
  let m = $("#hd-run");
  if (!m) { m = h("div", { id: "hd-run", class: "modal" }); document.body.append(m); m.onclick = () => { m.hidden = true; }; }
  const model = h("select", {}, ...st.models.map(x => h("option", { value: x.id, disabled: !x.ok, selected: x.id === st.hd.model }, x.name)));
  const scale = h("select", {}, ...[2, 3, 4].map(n => h("option", { value: n, selected: n === (st.hd.scale || 3) }, "×" + n)));
  let sizes = [], made = [];
  const count = h("span", { class: "muted" });
  const go = h("button", { class: "btn primary" }, redo ? "Пересчитать" : "Увеличить");
  const sizeBox = h("div", { class: "chips" }), madeBox = h("div", { class: "chips" });
  const chips = (box, items, chosen, label, set) => fill(box, ...items.map(([k, n]) => {
    const c = h("input", { type: "checkbox", checked: chosen.includes(k) });
    c.onchange = () => { set(c.checked ? [...chosen, k] : chosen.filter(x => x !== k)); };
    return h("label", { class: "chip" + (chosen.includes(k) ? " on" : "") }, c, h("span", {}, label(k)), h("span", { class: "muted small num" }, n));
  }));
  const refresh = async () => {
    const r = await api(`hd/pick?redo=${redo ? 1 : ""}&sizes=${sizes.join(",")}&models=${made.join(",")}`);
    chips(sizeBox, r.sizes, sizes, k => k, v => { sizes = v; refresh(); });
    if (redo) chips(madeBox, r.models, made, k => k === "-" ? "ещё не увеличены" : (MODEL_SHORT[k] || k), v => { made = v; refresh(); });
    count.textContent = `Будет обработано: ${r.count.toLocaleString("ru")}` + (sizes.length ? "" : " (все размеры)");
    go.disabled = !r.count;
  };
  go.onclick = () => {
    m.hidden = true;
    run("hd", { model: model.value, scale: +scale.value, redo, sizes, models: made }, redo ? "Пересчёт текстур" : "Увеличение текстур");
  };
  fill(m, h("div", { class: "box", onclick: e => e.stopPropagation() },
    h("h2", {}, redo ? "Пересчитать текстуры" : "Увеличить новые текстуры", h("span", { class: "sp" }),
      h("button", { class: "icon-btn", title: "Закрыть", onclick: () => { m.hidden = true; } }, icon("close"))),
    form([
      ["Модель", model, scale],
      ["Исходные размеры", h("div", { style: "width:100%" }, h("div", { class: "muted small", style: "margin-bottom:6px" }, "ничего не выбрано — все размеры"), sizeBox)],
      ...(redo ? [["Сейчас сделаны", h("div", { style: "width:100%" }, h("div", { class: "muted small", style: "margin-bottom:6px" }, "ничего не выбрано — любые"), madeBox)]] : []),
    ]),
    h("div", { class: "actions" }, count, h("button", { class: "btn", onclick: () => { m.hidden = true; } }, "Отмена"), go)));
  m.hidden = false;
  await refresh();
}

// a job's progress bar, Stop, its log (filled by openJobPanel / pollJob)
const jobPanel = () => h("div", { class: "jobpanel", hidden: true },
  h("div", { class: "jhead" }, h("span", { class: "jtitle" }), h("div", { class: "jbar" }, h("i")), h("span", { class: "jnum muted small" }),
    h("button", { class: "btn jstop", hidden: true }, "Стоп"),
    h("button", { class: "icon-btn jtoggle", title: "Журнал" }, "▾"), h("button", { class: "icon-btn jclose", title: "Закрыть" }, icon("close"))),
  h("pre", { class: "log", hidden: true }));

// the movies, cleaned by Real-CUGAN at their own 480x272: settings, the
// preparation job, and a frame of any movie before / after in any mode
async function renderMovies(v) {
  const st = await api("movies");
  const total = st.movies.length;
  const on = h("input", { type: "checkbox", checked: st.settings.on });
  const mode = h("select", {}, ...st.modes.map(m => h("option", { value: m.id, selected: m.id === st.settings.mode }, m.name)));
  const save = async patch => { await api("movies", { method: "PUT", body: patch }); renderMovies(v); };
  on.onchange = () => save({ on: on.checked });
  mode.onchange = () => save({ mode: mode.value });
  const panel = jobPanel();
  api("job").then(j => { if (j.running && j.name === "movies") { openJobPanel(panel, "Подготовка роликов"); jobOwner = j.name; jobNext = 0; pollJob(); } });
  const left = total - st.ready;
  // preview: one frame, original against the chosen mode
  const pick = h("select", {}, ...st.movies.map(m => h("option", { value: m.n }, `movie${String(m.n).padStart(2, "0")} · ${m.frames} кадров`)));
  pick.value = state.moviePick ?? 7;
  const pos = h("input", { type: "range", min: 0, style: "flex:1" });
  pos.max = (st.movies.find(m => m.n === +pick.value) || st.movies[0]).frames - 1;  // the max before the value, or it clamps
  pos.value = state.movieFrame ?? 180;
  const at = h("span", { class: "muted small num", style: "min-width:120px;text-align:right" });
  const W = 720, H = 408;
  const after = h("img", { style: `width:${W}px;height:${H}px` });
  const before = h("img", { style: `width:${W}px;height:${H}px` });
  const clip = h("div", { class: "clip", style: `width:${W / 2}px` }, before);
  const bar = h("i", { class: "bar", style: `left:${W / 2}px` });
  const view = h("div", { class: "slider", style: `width:${W}px;height:${H}px;max-width:100%` }, after, clip, bar);
  view.addEventListener("pointermove", e => {
    if (!(e.buttons || e.pointerType === "mouse")) return;
    const r = view.getBoundingClientRect(), x = Math.max(0, Math.min(r.width, e.clientX - r.left));
    clip.style.width = x + "px"; bar.style.left = x + "px";
  });
  const wait = h("span", { class: "muted small" });
  let t = null;
  const show_ = () => {
    const m = st.movies.find(x => x.n === +pick.value);
    pos.max = m.frames - 1;
    if (+pos.value > m.frames - 1) pos.value = 0;
    const sec = +pos.value * 1001 / 30000;
    at.textContent = `кадр ${pos.value} · ${Math.floor(sec / 60)}:${(sec % 60).toFixed(1).padStart(4, "0")}`;
    clearTimeout(t);
    t = setTimeout(() => {
      state.moviePick = +pick.value; state.movieFrame = +pos.value;
      const q = `n=${pick.value}&frame=${pos.value}&mode=${mode.value}`;
      wait.textContent = "считаю кадр…";
      before.src = `/api/movies/frame.png?${q}&which=orig`;
      after.onload = () => { wait.textContent = ""; };
      after.src = `/api/movies/frame.png?${q}&which=enh`;
    }, 250);
  };
  pick.onchange = show_;
  pos.oninput = show_;
  const old = v.querySelector(".movies");
  const sec = section("Ролики", form([
    ["Сборка", h("label", { class: "switch" }, on, "Собирать образ из улучшенных роликов"),
      h("span", { class: "muted small" }, "субтитры рисуются поверх")],
    ["Режим Real-CUGAN", mode, h("span", { class: "muted small" }, "ролики остаются 480×272: ИИ чистит линии и блоки сжатия")],
    ["Подготовлено", h("div", { class: "cov", style: "width:100%" },
      h("div", { class: "cov-top" }, h("span", {}, mode.selectedOptions[0].textContent), h("span", { class: "muted small" }, `${st.ready} из ${total}`)),
      h("div", { class: "jbar" + (st.ready === total ? " full" : "") }, h("i", { style: `width:${100 * st.ready / total}%` })),
      h("div", { class: "muted small" }, left ? `осталось ${left}, около ${Math.max(1, Math.round(st.movies.filter(m => !m.ready).reduce((a, m) => a + m.frames, 0) / 1100))} мин` : "все ролики готовы"))],
  ]),
  h("div", { class: "actions" },
    h("button", { class: "btn", "data-job": true, disabled: !left, onclick: () => { openJobPanel(panel, "Подготовка роликов"); runJob("movies", { mode: mode.value }); } },
      left ? `Подготовить ${left}` : "Готово")),
  panel,
  h("div", { class: "moviecmp" },
    h("div", { class: "row" }, pick, pos, at),
    h("div", { class: "labels muted small" }, h("span", {}, "оригинал"), wait, h("span", {}, mode.selectedOptions[0].textContent)),
    view));
  sec.classList.add("movies");
  old ? old.replaceWith(sec) : v.append(sec);
  show_();
}

// HD textures for PPSSPP: dump while playing, upscale, done
async function renderHd(v) {
  const st = await api("hd");
  const scale = h("select", {}, ...[2, 3, 4].map(n => h("option", { value: n, selected: n === (st.hd.scale || 3) }, "×" + n)));
  const model = h("select", {}, ...st.models.map(m => h("option", { value: m.id, disabled: !m.ok, selected: m.id === st.hd.model }, m.name)));
  const saving = h("input", { type: "checkbox", checked: st.saving });
  saving.addEventListener("change", async () => { await api("hd", { method: "PUT", body: { saving: saving.checked } }); renderHd(v); });
  const panel = jobPanel();
  const run = (what, body, title) => { openJobPanel(panel, title); runJob(what, body); };
  // a job still running (page reloaded): show its panel again
  api("job").then(j => { if (j.running && (j.name === "hd" || j.name === "hdarchive")) { openJobPanel(panel, "Увеличение текстур"); jobOwner = j.name; jobNext = 0; pollJob(); } });
  const left = st.total - st.done;
  // coverage: what is collected and how much of it is HD already
  const meter = (label, done, total, hint) => h("div", { class: "cov" },
    h("div", { class: "cov-top" }, h("span", {}, label), h("span", { class: "muted small" }, total ? `${done} из ${total} · ${Math.floor(100 * done / total)}%` : "—")),
    h("div", { class: "jbar" + (total && done === total ? " full" : "") }, h("i", { style: `width:${total ? 100 * done / total : 0}%` })),
    hint ? h("div", { class: "muted small" }, hint) : null);
  const today = st.days?.[0];
  const ready = st.total > 0 && left === 0;
  const coverage = h("div", { class: "covs" },
    meter("Из архива игры", st.archive_done, st.archive, st.archive ? null : "ещё не собрано: «Собрать из архива»"),
    meter("Из игры (сохранено PPSSPP)", st.dumped_done, st.dumped,
      today ? `последняя игра ${today[0]}: +${today[1]} новых` + (st.days.length > 1 ? ` · до этого ${st.days[1][0]}: +${st.days[1][1]}` : "") : "поиграй с включённым сохранением"),
    meter("Всего в HD", st.done, st.total, ready ? "Всё собранное увеличено, пак можно паковать" : st.total ? `осталось увеличить: ${left}` : null));
  const pairs = st.samples?.length ? h("div", { class: "hdpairs" }, ...st.samples.map(n => h("div", { class: "hdpair" },
    h("img", { src: `/api/hd/img?name=${encodeURIComponent(n)}&which=orig`, loading: "lazy" }),
    h("img", { src: `/api/hd/img?name=${encodeURIComponent(n)}&which=hd`, loading: "lazy" })))) : null;
  const old = v.querySelector(".hdtex");
  if (!v.querySelector(".titlebar")) v.prepend(titlebar("HD-текстуры", "пак для PPSSPP: текстуры игры в высоком разрешении, игра не меняется"));
  const sec = section("Пак текстур", form([
    ["PPSSPP", h("label", { class: "switch", title: "Эмулятор сохраняет каждую новую текстуру, пока ты играешь. Переключай при закрытом эмуляторе." },
      saving, "Сохранять новые текстуры")],
    ["Покрытие", coverage,
      st.frames ? h("span", { class: "muted small", title: "Кадры роликов: у каждого свой хеш, увеличивать их бесполезно" }, `кадры видео пропущены: ${st.frames}`) : null],
    st.tools.some(t => !t.ok) ? ["Нейросети", h("div", { class: "tools" }, ...st.tools.map(t => t.ok
      ? h("span", { class: "muted small" }, t.name + " ✓")
      : h("button", { class: "btn", "data-job": true, onclick: () => run("hdtool", { tool: t.id }, "Загрузка " + t.name) }, icon("download"), "Скачать " + t.name)))] : null]),
  h("div", { class: "actions" },
    h("button", { class: "btn", disabled: !st.done, onclick: () => hdGallery() }, "Галерея"),
    h("button", { class: "btn" + (ready ? " primary" : ""), "data-job": true, disabled: !st.done, onclick: () => run("hdzip", {}, "Пак HD-текстур") }, "Запаковать пак"),
    h("button", { class: "btn", "data-job": true, disabled: !st.upscaler, title: "Посчитать текстуры прямо из файлов игры и увеличить",
      onclick: () => run("hdarchive", { scale: +scale.value, model: model.value }, "Текстуры из архива") }, st.archive ? "Обновить из архива" : "Собрать из архива"),
    h("button", { class: "btn", "data-job": true, disabled: !st.total || !st.upscaler, onclick: () => hdRunDialog(true, st, run) }, "Пересчитать…"),
    h("button", { class: "btn" + (ready ? "" : " primary"), "data-job": true, disabled: !left || !st.upscaler, onclick: () => hdRunDialog(false, st, run) },
      left ? `Увеличить новые (${left})` : "Увеличить новые")),
  panel, pairs);
  sec.classList.add("hdtex");
  old ? old.replaceWith(sec) : v.append(sec);
}

async function renderPlaytest(v, before = null) {
  const pt = await api("playtest");
  const emu = h("input", { type: "text", value: pt.emulator, placeholder: "/Applications/PPSSPPSDL.app/Contents/MacOS/PPSSPPSDL" });
  const emuField = pathField(emu, "open", "Эмулятор PPSSPP (.app)");
  emu.addEventListener("change", () => api("playtest", { method: "PUT", body: { emulator: emu.value } }));
  const slots = h("input", { type: "text", value: pt.probe_slots.join(", ") });
  slots.addEventListener("change", () => api("playtest", { method: "PUT", body: { probe_slots: slots.value.split(",").map(x => x.trim()).filter(Boolean) } }));
  const pick = path => api("playtest", { method: "PUT", body: { state: path } }).then(() => renderPlaytest(v));
  const card = (st, label, img) => h("div", { class: "scard" + (pt.state === st ? " on" : ""), onclick: () => pick(st), title: st || "" },
    img ? h("img", { src: img }) : h("div", { class: "noimg" }, "▶"), h("div", { class: "small" }, label));
  const old = v.querySelector(".playtest");
  const sec = section("Проверка в игре", form([
    ["Эмулятор", emuField],
    ["Запуск", h("div", { class: "states" }, card("", "с начала"),
      ...pt.states.map(s => card(s.path, new Date(s.mtime * 1000).toLocaleString("ru", { dateStyle: "short", timeStyle: "short" }),
        `/api/state.jpg?path=${encodeURIComponent(s.path)}`)))],
    ["Тестовое место", slots],
  ]), h("div", { class: "actions" }, h("button", { class: "btn primary", "data-job": true, onclick: () => runJob("playtest") }, icon("play"), "Проверить в игре")));
  sec.classList.add("playtest");
  old ? old.replaceWith(sec) : before ? before.before(sec) : v.append(sec);
}

// ---- texts --------------------------------------------------------------

function richText(s, q) {
  const frag = document.createDocumentFragment();
  const re = /(\[[#0-9a-fA-F]+\])/g;
  for (const part of s.split(re)) {
    if (!part) continue;
    if (/^\[[#0-9a-fA-F]+\]$/.test(part)) {
      const code = part.startsWith("[#") ? parseInt(part.slice(2, -1), 16) : 0;
      frag.append(code >= 0x1000
        ? h("img", { src: `/api/glyph/${code.toString(16)}.png?new=1`, class: "inl", title: part, style: "width:16px;height:16px;vertical-align:-3px;background:var(--game);border-radius:3px" })
        : h("span", { class: "tag" }, part));
      continue;
    }
    if (q) {
      const lo = part.toLowerCase(), ql = q.toLowerCase();
      let i = 0, j;
      while ((j = lo.indexOf(ql, i)) >= 0) {
        frag.append(part.slice(i, j), h("span", { class: "hl" }, part.slice(j, j + q.length)));
        i = j + q.length;
      }
      frag.append(part.slice(i));
    } else frag.append(part);
  }
  return frag;
}

async function loadTexts() {
  state.summary = await api("texts");
  if (!state.icons.length) state.icons = (await api("charmap")).filter(isIcon).map(g => g.code);
  renderEntries();
  if (state.entry == null && state.summary.length) state.entry = state.summary[0].entry;
  if ($("#search").value || getMode() !== "all") doSearch(); else if (state.entry != null) openEntry(state.entry);
}

function renderEntries() {
  const f = $("#entry-filter").value.toLowerCase();
  const sum = k => state.summary.reduce((a, e) => a + (e[k] || 0), 0);
  fill($("#texts-status"), h("span", { class: "c-done", title: "Переведено" }, sum("done")), " / ",
    h("span", { class: "c-chk", title: "Проверено" }, sum("checked")), " / ", h("span", { title: "Всего" }, sum("total")));
  const em = getEntryMode();
  fill($("#entry-list"), ...state.summary
    .filter(e => !f || String(e.entry).includes(f) || (e.name || "").includes(f) || e.preview.toLowerCase().includes(f))
    // "done"/"checked": only the finished files; "undone"/"unchecked": hide them
    .filter(e => em === "all" || (em === "done" && e.done === e.total) || (em === "checked" && (e.checked || 0) === e.total)
      || (em === "undone" && e.done < e.total) || (em === "unchecked" && (e.checked || 0) < e.total))
    .map(e => h("li", { class: e.entry === state.entry ? "on" : "", onclick: () => { $("#search").value = ""; openEntry(e.entry); } },
      h("div", { class: "top" }, h("span", { class: "num" }, e.name || String(e.entry).padStart(4, "0")),
        h("span", { class: "muted" }, h("span", { class: "c-done" }, e.done), " / ", h("span", { class: "c-chk" }, e.checked || 0), " / ", e.total)),
      h("div", { class: "pv" }, e.preview),
      h("div", { class: "bar", title: "Переведено" }, h("i", { style: `width:${100 * e.done / e.total}%` })),
      h("div", { class: "bar chk", title: "Проверено" }, h("i", { style: `width:${100 * (e.checked || 0) / e.total}%` })))));
}

async function refreshSummary(i) {
  const s = state.summary.find(e => e.entry === i);
  if (!s) return;
  const rows = await api("texts/" + i);
  s.done = rows.filter(r => r.dst).length;
  s.checked = rows.filter(r => r.dst && r.checked).length;
  renderEntries();
}

async function openEntry(i) {
  state.entry = i;
  renderEntries();
  const b = $("#llm-entry");
  b.hidden = false;
  b.onclick = async () => {
    openJobPanel($("#texts-job"), `Перевод файла ${String(i).padStart(4, "0")}`);
    await runJob("llm", { entry: i });
    waitJob(() => { refreshSummary(i); openEntry(i); });
  };
  const token = state.loading = {};
  let rows = await api("texts/" + i);
  if (state.loading !== token) return;  // another file was opened meanwhile
  const mode = getMode();
  if (mode === "todo") rows = rows.filter(r => !r.dst);
  if (mode === "mt") rows = rows.filter(r => r.mt);
  if (mode === "unchecked") rows = rows.filter(r => r.dst && !r.checked);
  // whole-file check: on if anything translated is unchecked, else "uncheck"
  const all = await api("texts/" + i);
  const translated = all.filter(r => r.dst), allChecked = translated.length && translated.every(r => r.checked);
  const name = state.summary?.find(e => e.entry === i)?.name || String(i).padStart(4, "0");
  $("#texts-title").textContent = name;
  $("#texts-sub").textContent = `${translated.length} из ${all.length} переведено · ${all.filter(r => r.dst && r.checked).length} проверено`;
  const cb = $("#check-entry");
  cb.hidden = !translated.length;
  cb.lastChild.textContent = allChecked ? "Снять проверку" : "Проверить файл";
  cb.onclick = async () => {
    await flush();
    await api(`texts/${i}/checked`, { method: "PUT", body: { ids: null, value: !allChecked } });
    await refreshSummary(i); openEntry(i);
  };
  renderRows(rows.map(r => ({ ...r, entry: i })));
}

let searchTimer = null;
function doSearch() {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(async () => {
    const q = $("#search").value, mode = getMode();
    if (!q) return state.entry != null && openEntry(state.entry);
    const token = state.loading = {};
    const rows = await api(`search?q=${encodeURIComponent(q)}&in=${$("#search-in").value}&mode=${mode}`);
    if (state.loading !== token) return;
    $("#texts-title").textContent = "Поиск";
    $("#texts-sub").textContent = `«${q}»: ${rows.length} строк`;
    renderRows(rows, q);
  }, 250);
}

let rowViews = [];
function renderRows(rows, q = "", page = 0) {
  rowViews = [];
  const go = n => { renderRows(rows, q, n); $("#rows").scrollTop = 0; };
  fill($("#rows"), pager(rows.length, page, go),
    ...rows.slice(page * PAGE, (page + 1) * PAGE).map(r => textRow(r, q)),
    pager(rows.length, page, go),
    rows.length ? null : h("p", { class: "muted" }, "Ничего нет"));
}

const pending = new Map();
let saveTimer = null;
function queueSave(entry, id, value, row) {
  if (!pending.has(entry)) pending.set(entry, {});
  pending.get(entry)[id] = { value, row };
  clearTimeout(saveTimer);
  saveTimer = setTimeout(flush, 600);
}
async function flush() {
  const batch = [...pending.entries()];
  pending.clear();
  for (const [entry, items] of batch) {
    const body = Object.fromEntries(Object.entries(items).map(([k, v]) => [k, v.value]));
    await api("texts/" + entry, { method: "PUT", body });
    await refreshSummary(Number(entry));
  }
}

const UTF8_MAX = 120;  // server: UTF8_MAX_BYTES

// preview in the game font + width against the window limit
function preview(r, ta) {
  const box = h("div", { class: "preview", hidden: true });
  const meter = h("div", { class: "meter" });
  const msg = h("div", { class: "msg" });
  let t = null;
  if (r.sub) {  // movie line: the frame with the subtitle burned in
    const tc = f => { const t = f * 1001 / 30000; return `${Math.floor(t / 60)}:${(t % 60).toFixed(2).padStart(5, "0")}`; };
    meter.textContent = `${tc(r.start)} – ${tc(r.end)}`;
    const img = h("img", { class: "subframe" });
    const update = () => {
      clearTimeout(t);
      t = setTimeout(() => {
        img.src = `/api/subframe.png?entry=${r.entry}&id=${encodeURIComponent(r.id)}&text=${encodeURIComponent(ta.value)}`;
        fill(box, img); box.hidden = false;
      }, 300);
    };
    update();
    return { box, meter, msg, update };
  }
  if (r.utf8) {  // save dialog: system font, no game preview; limit in bytes
    const update = () => {
      const n = new TextEncoder().encode(ta.value).length;
      meter.textContent = ta.value ? `${n} / ${UTF8_MAX} байт · системный шрифт` : "";
      meter.classList.toggle("over", n > UTF8_MAX);
    };
    return { box, meter, msg, update };
  }
  const update = () => {
    clearTimeout(t);
    t = setTimeout(async () => {
      const text = ta.value;
      msg.textContent = "";
      ta.classList.remove("bad");
      if (!text) { box.hidden = true; meter.textContent = ""; return; }
      const res = await fetch("/api/render.png?text=" + encodeURIComponent(text));
      if (!res.ok) {
        const e = await res.json();
        box.hidden = true; meter.textContent = "";
        ta.classList.add("bad");
        msg.textContent = "Нет в шрифте: " + e.error.replace(/^.*no glyph for /, "");
        return;
      }
      const url = URL.createObjectURL(await res.blob());
      const img = h("img", { src: url });
      img.onload = () => {
        // image is 2x scale; text starts at x=2
        const lines = text.split("\n").length;
        fill(box, img);
        if (r.limit_px) box.append(h("div", { class: "limit", style: `left:${4 + (2 + r.limit_px) * 2}px` }));
        box.hidden = false;
        const w = img.naturalWidth / 2 - 16;  // server pads 16px
        meter.textContent = r.limit_px ? `${w} / ${r.limit_px} px` : `${w} px`;
        meter.classList.toggle("over", !!r.limit_px && w > r.limit_px);
      };
    }, 300);
  };
  return { box, meter, msg, update };
}

function textRow(r, q) {
  const ta = h("textarea", { spellcheck: "true", placeholder: "Перевод" });
  ta.value = r.dst || "";
  const pv = preview(r, ta);
  const mt = r.mt ? h("span", { class: "badge mt", title: "Машинный перевод" }, "LLM") : null;
  const chk = iconBtn("check", "Отметить как проверенное", async () => {
    if (!ta.value) return;
    await flush();
    r.checked = !r.checked;
    await api(`texts/${r.entry}/checked`, { method: "PUT", body: { ids: [r.id], value: r.checked } });
    paintChecked(); refreshSummary(r.entry);
  });
  const row = h("div", { class: "trow" });
  const samples = h("div", { class: "muted small samples", hidden: true });
  rowViews.push({ r, set: v => {
    ta.value = v; r.dst = v; pv.update();
    row.querySelector(".badge.mt")?.remove();
    if (r.checked) { r.checked = false; paintChecked(); }
  } });
  const paintChecked = () => { chk.classList.toggle("on", !!r.checked); row.classList.toggle("checked", !!r.checked);
    chk.title = r.checked ? "Проверено. Нажми, чтобы снять" : "Отметить как проверенное"; };
  ta.addEventListener("input", () => {
    mt?.remove(); queueSave(r.entry, r.id, ta.value, r); pv.update();
    if (r.checked) { r.checked = false; paintChecked(); }   // the server drops it too
  });
  const insert = s => {
    const a = ta.selectionStart ?? ta.value.length, b = ta.selectionEnd ?? a;
    ta.value = ta.value.slice(0, a) + s + ta.value.slice(b);
    ta.selectionStart = ta.selectionEnd = a + s.length;
    ta.focus(); ta.dispatchEvent(new Event("input"));
  };
  // icons of this line are at hand; "+" shows the rest
  const used = [...new Set([...(r.src.matchAll(/\[#(1[0-9a-f]{3})\]/g))].map(m => parseInt(m[1], 16)))];
  const iconBtnFor = c => h("button", { type: "button", title: `[#${c.toString(16)}]`, onmousedown: e => e.preventDefault(),
    onclick: () => insert(`[#${c.toString(16)}]`) }, h("img", { src: `/api/glyph/${c.toString(16)}.png?new=1`, loading: "lazy" }));
  const palette = h("div", { class: "palette", hidden: !used.length }, ...used.map(iconBtnFor));
  const more = h("button", { type: "button", class: "more", title: "Все значки", onclick: () => {
    more.remove(); palette.append(...state.icons.filter(c => !used.includes(c)).map(iconBtnFor));
  } }, "+");
  if (state.icons.length > used.length) palette.append(more);
  const dups = r.dups > 1 ? iconBtn("all", `Записать этот перевод во все повторы строки, заменив их перевод (${r.dups})`, async ev => {
    await flush();
    const b = ev.currentTarget;
    const res = await api("propagate", { body: { src: r.src, dst: ta.value } });
    b.title = `Записано: ${res.count}`;
    for (const v of rowViews) if (v.r !== r && v.r.src === r.src) v.set(ta.value);
    refreshSummary(r.entry);
  }, `×${r.dups}`) : null;
  const toggleIcons = state.icons.length ? iconBtn("icon", "Значки кнопок", () => { palette.hidden = !palette.hidden; }) : null;
  if (r.dst) pv.update();
  const head = h("div", { class: "head" }, h("span", {}, `${state.summary.find(e => e.entry === r.entry)?.name || String(r.entry).padStart(4, "0")} · ${r.id}`), mt, h("span", { class: "sp" }),
      iconBtn("spark", "Перевести эту строку через LLM", async ev => {
        const b = ev.currentTarget; b.disabled = true; b.classList.add("busy");
        await flush();
        const res = await api("llm/row", { body: { entry: r.entry, id: r.id } }).catch(e => ({ error: e.message }));
        b.disabled = false; b.classList.remove("busy");
        if (res.error) { pv.msg.textContent = res.error; return; }
        ta.value = res.dst; pv.update();
        const ex = res.examples || [];
        fill(samples, ex.length ? `По образцу проверенных: ${ex.length}` : "Похожих проверенных строк нет");
        samples.title = ex.map(([a, b]) => `${a} → ${b}`).join("\n");
        samples.hidden = false;
        if (!head.querySelector(".mt")) head.insertBefore(h("span", { class: "badge mt", title: "Машинный перевод" }, "LLM"), head.children[1]);
      }),
      r.utf8 || r.sub ? null : iconBtn("eye", "Показать в игре: подставить этот перевод на тестовое место и запустить", async () => {
        if (!ta.value) { pv.msg.textContent = "Нечего показывать: перевод пустой"; return; }
        await flush();
        openJobPanel($("#texts-job"), "Проверка в игре");
        runJob("playtest", { probe: ta.value });
      }),
      r.ref ? iconBtn("copy", "Вставить подсказку в перевод", () => { ta.value = r.ref; ta.dispatchEvent(new Event("input")); }) : null,
      toggleIcons, dups, chk);
  paintChecked();
  row.append(head,
    h("div", { class: "body" },
      h("div", { class: "cell" }, richText(r.src, q)),
      h("div", { class: "cell muted" }, richText(r.ref || "", q)),
      h("div", {}, ta, palette, pv.msg, samples, pv.box, pv.meter)));
  return row;
}

// ---- font -----------------------------------------------------------------

function renderFont() {
  const p = state.project, v = $("#view-font");
  const st = p.font?.settings || {};
  const ttf = h("input", { type: "text", value: st.ttf || "", placeholder: "/путь/к/шрифту.ttf" });
  const idx = h("input", { type: "number", value: st.index ?? 0, min: 0, style: "width:80px" });
  const px = h("input", { type: "number", value: st.px ?? 14, min: 8, max: 24, style: "width:80px" });
  const chars = h("textarea", { rows: 3 }); chars.value = st.chars || "";
  const ascii = h("input", { type: "checkbox" }); ascii.checked = st.redraw_ascii !== false;
  const track = h("input", { type: "number", value: st.tracking ?? 1, min: 0, max: 4, style: "width:80px" });
  jobLog = h("pre", { class: "log" });
  const cells = Object.entries(p.font?.cells || {}).filter(([c]) => parseInt(c, 16) >= 0x5e);
  fill(v, titlebar("Шрифт", "кириллица в шрифте игры: какой шрифт, какого размера и в какие ячейки"),
    section("Шрифт", form([
      ["Файл шрифта", pathField(ttf, "open", "Шрифт (.ttf, .otf, .ttc)")],
      ["Начертание", idx, h("span", { class: "muted small" }, "номер в .ttc")],
      ["Размер", px, h("span", { class: "muted small" }, "px")],
      ["Интервал", track, h("span", { class: "muted small" }, "px между буквами")],
      ["Буквы", chars],
      ["Латиница", h("label", { class: "switch" }, ascii, "перерисовать тем же шрифтом")],
    ]), h("div", { class: "actions" }, h("button", { class: "btn primary", "data-job": true, onclick: async () => {
      await runJob("font", { ttf: ttf.value, index: +idx.value, px: +px.value, chars: chars.value, redraw_ascii: ascii.checked, tracking: +track.value });
      waitJob(async () => { state.project = await api("project"); renderFont(); });
    } }, "Собрать")), jobLog),
    cells.length ? section(`Новые знаки · ${cells.length}`, h("div", { class: "glyphs", style: "padding:12px" },
      ...cells.map(([c, ch]) => h("div", { class: "glyph", title: c },
        h("img", { src: `/api/glyph/${c}.png?new=1&t=${Date.now()}`, alt: ch }), h("div", {}, ch))))) : null);
}

// ---- LLM ------------------------------------------------------------------

async function renderLLM() {
  const v = $("#view-llm");
  const s = await api("llm/settings");
  const gl = await api("glossary");
  const prov = h("select", {}, h("option", { value: "anthropic" }, "Anthropic"), h("option", { value: "openai" }, "OpenAI-совместимый"));
  prov.value = s.provider;
  const a = s.anthropic, o = s.openai;
  const aKey = h("input", { type: "password", value: a.api_key, placeholder: a.has_key ? "из окружения" : "sk-ant-…", autocomplete: "off" });
  const aModel = h("input", { type: "text", value: a.model });
  const aEffort = h("select", {}, ...[["low", "низкое"], ["medium", "среднее"], ["high", "высокое"], ["xhigh", "очень высокое"], ["max", "максимум"]].map(([v, t]) => h("option", { value: v }, t)));
  aEffort.value = a.effort || "medium";
  const oUrl = h("input", { type: "text", value: o.base_url, list: "llm-urls" });
  const urls = h("datalist", { id: "llm-urls" }, ...["https://api.openai.com/v1", "https://openrouter.ai/api/v1", "http://localhost:11434/v1", "http://localhost:1234/v1"].map(u => h("option", { value: u })));
  const oKey = h("input", { type: "password", value: o.api_key, placeholder: "не нужен для локальных", autocomplete: "off" });
  const oModel = h("input", { type: "text", value: o.model });
  const batch = h("input", { type: "number", value: s.batch, min: 1, max: 100, style: "width:80px" });
  const lang = h("input", { type: "text", value: s.target_lang });
  const gloss = h("textarea", { rows: 10, placeholder: "黒崎一護 / Ichigo Kurosaki → Ичиго Куросаки" });
  gloss.value = gl.text;
  const status = h("span", { class: "status" });
  const aForm = form([["Ключ API", aKey], ["Модель", aModel], ["Усилие", aEffort]]);
  const oForm = form([["Адрес", oUrl, urls], ["Ключ API", oKey], ["Модель", oModel]]);
  const sync = () => { aForm.hidden = prov.value !== "anthropic"; oForm.hidden = prov.value !== "openai"; };
  prov.onchange = sync; sync();
  const save = () => Promise.all([
    api("llm/settings", { method: "PUT", body: {
      provider: prov.value, batch: +batch.value, target_lang: lang.value,
      anthropic: { api_key: aKey.value, model: aModel.value, effort: aEffort.value },
      openai: { api_key: oKey.value, base_url: oUrl.value, model: oModel.value } } }),
    api("glossary", { method: "PUT", body: { text: gloss.value } })]);
  const limit = h("input", { type: "number", value: 50, min: 1, style: "width:100px" });
  jobLog = h("pre", { class: "log" });
  // autosave: every field, a moment after the last change
  let t = null;
  const autosave = () => {
    clearTimeout(t);
    status.textContent = ""; status.className = "status";
    t = setTimeout(async () => { await save(); status.textContent = "Сохранено"; }, 500);
  };
  for (const el of [prov, aKey, aModel, aEffort, oUrl, oKey, oModel, batch, lang, gloss]) {
    el.addEventListener("input", autosave); el.addEventListener("change", autosave);
  }
  fill(v, titlebar("LLM", "перевод строк языковой моделью: подключение, язык и глоссарий"),
    section("Подключение", form([["Провайдер", prov]]), aForm, oForm,
      h("div", { class: "actions" }, status,
        h("button", { class: "btn", onclick: async () => { await save(); status.textContent = "Проверка…"; const r = await api("llm/test", { body: {} }); status.textContent = r.ok ? "Подключено" : r.reply; status.className = "status" + (r.ok ? "" : " err"); } }, "Проверить"))),
    section("Перевод", form([["Язык", lang], ["Строк за запрос", batch], ["Глоссарий", gloss]]),
      h("div", { class: "actions" }, limit, h("span", { class: "muted small" }, "строк"),
        h("button", { class: "btn primary", "data-job": true, onclick: async () => { await save(); runJob("llm", { limit: +limit.value }); } }, icon("spark"), "Перевести")),
      jobLog));
}

// ---- textures -------------------------------------------------------------

async function loadTextures(page = 0) {
  if (typeof page !== "number") page = 0;
  state.txPage = page;
  const mode = getTxMode(), q = $("#tx-find").value.trim();
  const res = await api(`textures?filter=${mode}&q=${encodeURIComponent(q)}&offset=${page * PAGE}&limit=${PAGE}`);
  if (!res.indexed) {
    $("#tx-status").textContent = "";
    fill($("#tx-grid"), h("div", { class: "muted" }, "Каталог ещё не собран: нажми «Обновить каталог»."));
    return;
  }
  $("#tx-status").textContent = `${res.total}`;
  const go = n => { loadTextures(n); window.scrollTo(0, 0); };
  fill($("#tx-pager"), ...[pager(res.total, page, go)].filter(Boolean));
  fill($("#tx-grid"), ...res.items.map(texCard));
}

async function uploadTexture(t, file) {
  const r = await fetch(`/api/texture/${t.id}`, { method: "PUT", body: await file.arrayBuffer() });
  const d = await r.json();
  if (!r.ok) { alert(d.error); return false; }
  t.edited = true;
  return true;
}

function texCard(t) {
  const ver = Date.now();
  const card = h("div", { class: "tcard", title: t.id, onclick: () => texDetail(t) },
    h("div", { class: "th" }, h("img", { src: `/api/texture/${t.id}.png${t.edited ? "?which=edit&v=" + ver : ""}`, loading: "lazy" })),
    h("div", { class: "meta" }, h("span", {}, `${String(t.entry).padStart(4, "0")} · ${t.w}×${t.h}`),
      t.edited ? h("span", { class: "badge ok" }, "RU") : t.ref ? h("span", { class: "badge" }, "текст") : null));
  card.addEventListener("dragover", e => { e.preventDefault(); card.classList.add("drop"); });
  card.addEventListener("dragleave", () => card.classList.remove("drop"));
  card.addEventListener("drop", async e => {
    e.preventDefault(); card.classList.remove("drop");
    const f = e.dataTransfer.files[0];
    if (f) texEditor(t, f);
  });
  return card;
}

function texDetail(t) {
  const m = $("#tx-detail");
  // the picture, with a download button for the file at its own size
  const fig = (title, src, file, name) => h("figure", {}, h("figcaption", {}, title),
    src ? h("div", { class: "pic" }, h("img", { src }),
      h("a", { class: "dl", href: file, download: name, title: "Скачать PNG", onclick: e => e.stopPropagation() }, icon("download")))
      : h("div", { class: "pic empty" }, "нет"));
  const scale = t.w <= 128 && t.h <= 128 ? 3 : 2;
  const file = h("input", { type: "file", accept: "image/png", hidden: true, onchange: async () => {
    if (file.files[0]) texEditor(t, file.files[0]);
  } });
  const close = () => { m.hidden = true; };
  fill(m, h("div", { class: "box", onclick: e => e.stopPropagation() },
    h("h2", {}, `${t.id}`, h("span", { class: "muted small" }, `${t.w}×${t.h}`), h("span", { class: "sp" }),
      h("button", { class: "btn", onclick: () => texAuto(t) }, icon("spark"), "Автоперевод"),
      h("button", { class: "btn primary", onclick: () => file.click() }, "Загрузить PNG"), file,
      t.edited ? h("button", { class: "btn", onclick: () => texEditor(t, `/api/texture/${t.id}.png?which=edit&v=${Date.now()}`) }, "Редактировать") : null,
      t.edited ? h("button", { class: "btn", onclick: async () => { await api(`texture/${t.id}`, { method: "DELETE" }); t.edited = false; texDetail(t); loadTextures(state.txPage); } }, "Сбросить") : null,
      h("button", { class: "icon-btn", title: "Закрыть", onclick: close }, icon("close"))),
    h("div", { class: "cmp" },
      fig("Оригинал", `/api/texture/${t.id}.png?scale=${scale}`, `/api/texture/${t.id}.png`, t.id + ".png"),
      fig("Подсказка", state.project.meta.ref_iso ? `/api/texture/${t.id}.png?which=ref&scale=${scale}` : null,
        `/api/texture/${t.id}.png?which=ref`, t.id + "_ref.png"),
      fig("Перевод", t.edited ? `/api/texture/${t.id}.png?which=edit&v=${Date.now()}` : null,
        `/api/texture/${t.id}.png?which=edit&v=${Date.now()}`, t.id + "_ru.png"))));
  m.onclick = close;
  m.hidden = false;
}

// automatic translation of the text on a texture: OCR finds the lines, the
// server wipes them and draws the translation; boxes can be moved/resized
async function texAuto(t) {
  const m = $("#tx-detail");
  const got = await api(`texture/${t.id}/auto`);
  let layout = got.layout || { font: "pt-sans-bold", note: "", boxes: [] };
  const zoom = Math.min(4, 480 / Math.max(t.w, t.h));
  const pic = h("img", { class: "autopic", style: `width:${t.w * zoom}px;height:${t.h * zoom}px` });
  const stage = h("div", { class: "autostage", style: `width:${t.w * zoom}px;height:${t.h * zoom}px` }, pic);
  const msg = h("span", { class: "msg" });
  const note = h("input", { type: "text", value: layout.note || "", placeholder: "Уточнение: например, коротко, заглавными" });
  const font = h("select", {}, ...got.fonts.map(f => h("option", { value: f.id, selected: f.id === layout.font }, f.name)));
  const list = h("div", { class: "autolist" });
  let timer = null, url = null;
  const redraw = () => {
    clearTimeout(timer);
    timer = setTimeout(async () => {
      layout.note = note.value; layout.font = font.value;
      const r = await fetch(`/api/texture/${t.id}/render.png`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ layout }) });
      if (url) URL.revokeObjectURL(url);
      url = URL.createObjectURL(await r.blob());
      pic.src = url;
    }, 250);
  };
  const overlays = () => {
    stage.querySelectorAll(".abox").forEach(x => x.remove());
    layout.boxes.forEach((b, k) => {
      if (!b.on) return;
      const el = h("div", { class: "abox", title: b.src, style: `left:${b.x * zoom}px;top:${b.y * zoom}px;width:${b.w * zoom}px;height:${b.h * zoom}px` },
        h("span", { class: "num" }, k + 1), h("i", { class: "grip" }));
      // drag: move; the corner grip: resize
      el.addEventListener("pointerdown", e => {
        e.preventDefault(); el.setPointerCapture(e.pointerId);
        const grip = e.target.classList.contains("grip");
        const sx = e.clientX, sy = e.clientY, o = { ...b };
        el.onpointermove = ev => {
          const dx = Math.round((ev.clientX - sx) / zoom), dy = Math.round((ev.clientY - sy) / zoom);
          if (grip) { b.w = Math.max(4, o.w + dx); b.h = Math.max(4, o.h + dy); }
          else { b.x = Math.max(0, Math.min(t.w - b.w, o.x + dx)); b.y = Math.max(0, Math.min(t.h - b.h, o.y + dy)); }
          Object.assign(el.style, { left: b.x * zoom + "px", top: b.y * zoom + "px", width: b.w * zoom + "px", height: b.h * zoom + "px" });
        };
        el.onpointerup = () => { el.onpointermove = null; redraw(); };
      });
      stage.append(el);
    });
  };
  const rows = () => fill(list, ...layout.boxes.map((b, k) => {
    const on = h("input", { type: "checkbox", checked: !!b.on });
    on.onchange = () => { b.on = on.checked; rows(); overlays(); redraw(); };
    const dst = h("input", { type: "text", value: b.dst || "", placeholder: "Перевод" });
    dst.oninput = () => { b.dst = dst.value; redraw(); };
    const fillc = h("input", { type: "color", value: b.fill || "#ffffff", title: "Буквы" });
    fillc.oninput = () => { b.fill = fillc.value; redraw(); };
    const out = h("input", { type: "color", value: b.outline || "#000000", title: "Обводка" });
    out.oninput = () => { b.outline = out.value; redraw(); };
    const ow = h("input", { type: "number", value: b.outline ? b.ow : 0, min: 0, max: 4, step: 0.5, title: "Обводка, px", style: "width:56px" });
    ow.oninput = () => { const v = +ow.value; if (v) { b.ow = v; b.outline = out.value; } else b.outline = null; redraw(); };
    const size = h("input", { type: "number", value: b.size || "", min: 4, max: 64, step: 0.5, placeholder: "авто", title: "Размер, px", style: "width:64px" });
    size.oninput = () => { b.size = +size.value || null; redraw(); };
    const swap = h("button", { class: "icon-btn", title: "Поменять цвета местами", onclick: () => {
      const f = fillc.value; fillc.value = out.value; out.value = f; b.fill = fillc.value; if (b.outline) b.outline = out.value; redraw();
    } }, "⇄");
    const again = iconBtn("spark", "Перевести заново", async ev => {
      const btn = ev.currentTarget; btn.disabled = true;
      layout.note = note.value;
      const r = await api(`texture/${t.id}/auto`, { body: { retranslate: true, layout, only: [k] } });
      btn.disabled = false;
      msg.textContent = r.error || "";
      layout.boxes[k].dst = r.boxes[k].dst; dst.value = layout.boxes[k].dst; redraw();
    });
    return h("div", { class: "arow" + (b.on ? "" : " off") },
      h("div", { class: "ahead" }, on, h("span", { class: "num" }, k + 1), h("span", { class: "src" }, b.src),
        b.ref ? h("span", { class: "muted small" }, b.ref) : null),
      b.on ? h("div", { class: "aedit" }, dst, again, fillc, swap, out, ow, size) : null);
  }));
  const find = async () => {
    msg.textContent = "Ищу текст и перевожу…";
    const r = await api(`texture/${t.id}/auto`, { body: { note: note.value, font: font.value } }).catch(e => ({ error: e.message }));
    if (r.boxes) layout = r;
    msg.textContent = r.error || (layout.boxes.length ? "" : "Текст не найден");
    rows(); overlays(); redraw();
  };
  font.onchange = redraw;
  note.onchange = () => { layout.note = note.value; };
  fill(m, h("div", { class: "box wide", onclick: e => e.stopPropagation() },
    h("h2", {}, "Автоперевод", h("span", { class: "muted small" }, t.id), h("span", { class: "sp" }),
      h("button", { class: "btn", onclick: () => texDetail(t) }, "Назад"),
      h("button", { class: "icon-btn", title: "Закрыть", onclick: () => { m.hidden = true; } }, icon("close"))),
    h("div", { class: "auto" },
      h("div", {}, stage),
      h("div", { class: "aside" },
        h("div", { class: "row" }, note, font, h("button", { class: "btn", onclick: find }, icon("spark"), layout.boxes.length ? "Заново" : "Найти и перевести")),
        list,
        h("div", { class: "actions" }, msg,
          h("button", { class: "btn primary", onclick: async () => {
            layout.note = note.value; layout.font = font.value;
            await fetch(`/api/texture/${t.id}/render.png`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ layout, save: true }) });
            t.edited = true; loadTextures(state.txPage); texDetail(t);
          } }, "Сохранить"))))));
  m.onclick = () => { m.hidden = true; };
  m.hidden = false;
  rows(); overlays(); redraw();
  if (!layout.boxes.length) find();
}

// image editor for a texture: move / scale / crop to the frame, erase.
// `input` is a File/Blob (new upload) or a URL (edit the saved one).
function texEditor(t, input) {
  const m = $("#tx-detail");
  const hasRef = !!state.project.meta.ref_iso;
  const src = new Image(), unders = { jp: new Image(), ref: new Image() };
  src.src = typeof input === "string" ? input : URL.createObjectURL(input);
  unders.jp.src = `/api/texture/${t.id}.png`;
  if (hasRef) unders.ref.src = `/api/texture/${t.id}.png?which=ref`;
  const zoom = Math.max(1, Math.min(4, Math.floor(560 / Math.max(t.w, t.h))));
  const cv = h("canvas", { width: t.w * zoom, height: t.h * zoom, class: "editcv", tabindex: 0 });
  const ctx = cv.getContext("2d");
  const layer = document.createElement("canvas");   // the picture, its own pixels (erasable)
  // underlays as canvases too, so the eraser works on them (one per source)
  const underCv = { jp: document.createElement("canvas"), ref: document.createElement("canvas") };
  const st = { x: 0, y: 0, s: 1, under: 0.4, which: "jp", keep: false, smooth: true, tool: "move", brush: 4, target: "pic" };
  const undo = [];

  const scale = h("input", { type: "range", min: 5, max: 400, value: 100 });
  const scaleNum = h("span", { class: "muted small" }, "100%");
  const under = h("input", { type: "range", min: 0, max: 100, value: 40 });
  const keep = h("input", { type: "checkbox" });
  const smooth = h("input", { type: "checkbox", checked: true });
  const brush = h("input", { type: "range", min: 1, max: 32, value: 4 });
  const brushNum = h("span", { class: "muted small" }, "4 px");
  const pos = h("span", { class: "muted small" });
  const undoBtn = iconBtn("undo", "Отменить (Ctrl+Z)", () => doUndo());
  undoBtn.disabled = true;
  const targetSeg = h("div", { class: "seg" }, h("button", { "data-v": "pic", class: "on" }, "Картинка"), h("button", { "data-v": "under" }, "Подложка"));
  const toolSeg = h("div", { class: "seg" }, h("button", { "data-v": "move", class: "on" }, "Двигать"), h("button", { "data-v": "erase" }, "Ластик"));
  const underSeg = h("div", { class: "seg" }, h("button", { "data-v": "jp", class: "on" }, "Оригинал"),
    hasRef ? h("button", { "data-v": "ref" }, "Подсказка") : null);

  const draw = (c, z, guide) => {
    const u = underCv[st.which];
    c.imageSmoothingEnabled = false;
    c.clearRect(0, 0, t.w * z, t.h * z);
    if (st.keep) c.drawImage(u, 0, 0, t.w * z, t.h * z);
    else if (guide && st.under > 0) { c.globalAlpha = st.under; c.drawImage(u, 0, 0, t.w * z, t.h * z); c.globalAlpha = 1; }
    c.imageSmoothingEnabled = st.smooth;
    c.drawImage(layer, st.x * z, st.y * z, layer.width * st.s * z, layer.height * st.s * z);
  };
  let cursor = null;
  const redraw = () => {
    draw(ctx, zoom, true);
    if (st.tool === "erase" && cursor) {
      const r = st.brush * zoom / 2;
      ctx.strokeStyle = "#e0574a"; ctx.lineWidth = 1;
      ctx.strokeRect(cursor.x * zoom - r, cursor.y * zoom - r, r * 2, r * 2);
    }
    scale.value = Math.round(st.s * 100); scaleNum.textContent = Math.round(st.s * 100) + "%";
    pos.textContent = `x ${Math.round(st.x)}, y ${Math.round(st.y)}`;
    undoBtn.disabled = !undo.length;
  };
  const fit = cover => {
    const k = cover ? Math.max(t.w / layer.width, t.h / layer.height) : Math.min(t.w / layer.width, t.h / layer.height);
    st.s = k; st.x = (t.w - layer.width * k) / 2; st.y = (t.h - layer.height * k) / 2; redraw();
  };
  const setScale = (k, cx = t.w / 2, cy = t.h / 2) => {
    const px = (cx - st.x) / st.s, py = (cy - st.y) / st.s;   // keep the point under the cursor
    st.s = Math.max(0.05, Math.min(4, k)); st.x = cx - px * st.s; st.y = cy - py * st.s; redraw();
  };
  const target = () => st.target === "under" ? underCv[st.which] : layer;
  const snapshot = () => {
    const c = target();
    undo.push({ c, d: c.getContext("2d").getImageData(0, 0, c.width, c.height) });
    if (undo.length > 30) undo.shift();
  };
  const doUndo = () => { const u = undo.pop(); if (u) { u.c.getContext("2d").putImageData(u.d, 0, 0); redraw(); } };
  // erase a square brush (in texture pixels) at texture point (x, y)
  const erase = (x, y) => {
    const half = st.brush / 2;
    if (st.target === "under") {   // underlay is in texture pixels already
      underCv[st.which].getContext("2d").clearRect(Math.floor(x - half), Math.floor(y - half), Math.ceil(st.brush), Math.ceil(st.brush));
      return;
    }
    const lx = (x - half - st.x) / st.s, ly = (y - half - st.y) / st.s, sz = st.brush / st.s;
    layer.getContext("2d").clearRect(Math.floor(lx), Math.floor(ly), Math.ceil(sz), Math.ceil(sz));
  };
  const at = e => { const r = cv.getBoundingClientRect(); return { x: (e.clientX - r.left) / zoom, y: (e.clientY - r.top) / zoom }; };

  let drag = null;
  cv.addEventListener("pointerdown", e => {
    cv.setPointerCapture(e.pointerId); cv.focus();
    if (st.tool === "erase") { snapshot(); const p = at(e); erase(p.x, p.y); drag = { erase: true, last: p }; redraw(); return; }
    drag = { x: e.clientX, y: e.clientY, sx: st.x, sy: st.y };
  });
  cv.addEventListener("pointermove", e => {
    cursor = at(e);
    if (drag?.erase) {
      // fill the gap between pointer events
      const p = cursor, l = drag.last, n = Math.max(1, Math.ceil(Math.hypot(p.x - l.x, p.y - l.y) / Math.max(1, st.brush / 3)));
      for (let i = 1; i <= n; i++) erase(l.x + (p.x - l.x) * i / n, l.y + (p.y - l.y) * i / n);
      drag.last = p;
    } else if (drag) { st.x = drag.sx + (e.clientX - drag.x) / zoom; st.y = drag.sy + (e.clientY - drag.y) / zoom; }
    redraw();
  });
  cv.addEventListener("pointerup", () => { if (drag && !drag.erase) { st.x = Math.round(st.x); st.y = Math.round(st.y); } drag = null; redraw(); });
  cv.addEventListener("pointerleave", () => { cursor = null; redraw(); });
  cv.addEventListener("wheel", e => { e.preventDefault(); const p = at(e); setScale(st.s * (e.deltaY < 0 ? 1.1 : 1 / 1.1), p.x, p.y); }, { passive: false });
  cv.addEventListener("keydown", e => {
    if ((e.ctrlKey || e.metaKey) && e.key === "z") { e.preventDefault(); doUndo(); return; }
    if (e.key === "e") setTool("erase");
    if (e.key === "v") setTool("move");
    const d = e.shiftKey ? 10 : 1, k = { ArrowLeft: [-d, 0], ArrowRight: [d, 0], ArrowUp: [0, -d], ArrowDown: [0, d] }[e.key];
    if (k) { e.preventDefault(); st.x += k[0]; st.y += k[1]; redraw(); }
  });
  const setTool = v => { st.tool = v; cv.classList.toggle("erasing", v === "erase");
    toolSeg.querySelectorAll("button").forEach(b => b.classList.toggle("on", b.dataset.v === v)); redraw(); };
  seg(toolSeg, setTool);
  seg(underSeg, v => { st.which = v; redraw(); });
  seg(targetSeg, v => {
    st.target = v;
    // erasing the underlay only matters if it goes into the result
    if (v === "under" && !st.keep) { st.keep = keep.checked = true; }
    redraw();
  });
  scale.oninput = () => setScale(scale.value / 100);
  under.oninput = () => { st.under = under.value / 100; redraw(); };
  keep.onchange = () => { st.keep = keep.checked; redraw(); };
  smooth.onchange = () => { st.smooth = smooth.checked; redraw(); };
  brush.oninput = () => { st.brush = +brush.value; brushNum.textContent = brush.value + " px"; redraw(); };

  const apply = async () => {
    const out = h("canvas", { width: t.w, height: t.h });
    draw(out.getContext("2d"), 1, false);
    const blob = await new Promise(r => out.toBlob(r, "image/png"));
    if (await uploadTexture(t, blob)) { texDetail(t); loadTextures(state.txPage); }
  };
  const close = () => { m.hidden = true; };
  fill(m, h("div", { class: "box", onclick: e => e.stopPropagation() },
    h("h2", {}, `${t.id}`, h("span", { class: "muted small" }, `${t.w}×${t.h}`), h("span", { class: "sp" }),
      undoBtn,
      h("button", { class: "btn", onclick: () => texDetail(t) }, "Отмена"),
      h("button", { class: "btn primary", onclick: apply }, "Применить"),
      h("button", { class: "icon-btn", title: "Закрыть", onclick: close }, icon("close"))),
    h("div", { class: "editor" },
      h("div", { class: "stage" }, cv),
      h("div", { class: "form" },
        h("label", {}, "Инструмент"), h("div", { class: "f" }, toolSeg),
        h("label", {}, "Ластик"), h("div", { class: "f" }, brush, brushNum),
        h("label", {}, "Стирать"), h("div", { class: "f" }, targetSeg),
        h("label", {}, "Масштаб"), h("div", { class: "f" }, scale, scaleNum),
        h("label", {}, ""), h("div", { class: "f" },
          h("button", { class: "btn", onclick: () => fit(false) }, "Вписать"),
          h("button", { class: "btn", onclick: () => fit(true) }, "Заполнить"),
          h("button", { class: "btn", onclick: () => { st.s = 1; redraw(); } }, "1:1")),
        h("label", {}, "Позиция"), h("div", { class: "f" }, pos),
        h("label", {}, "Подложка"), h("div", { class: "f" }, underSeg),
        h("label", {}, "Прозрачность"), h("div", { class: "f" }, under),
        h("label", {}, ""), h("div", { class: "f" }, h("label", { class: "switch" }, keep, "оставить под картинкой")),
        h("label", {}, "Сглаживание"), h("div", { class: "f" }, h("label", { class: "switch" }, smooth, "при масштабе"))))));
  m.onclick = close;
  m.hidden = false;
  const imgs = [src, unders.jp].concat(hasRef ? [unders.ref] : []);
  let loaded = 0;
  const ready = () => {
    if (++loaded < imgs.length) return;
    layer.width = src.naturalWidth; layer.height = src.naturalHeight;
    layer.getContext("2d").drawImage(src, 0, 0);
    for (const k of Object.keys(underCv)) {
      underCv[k].width = t.w; underCv[k].height = t.h;
      if (unders[k].naturalWidth) underCv[k].getContext("2d").drawImage(unders[k], 0, 0);
    }
    if (src.naturalWidth === t.w && src.naturalHeight === t.h) redraw(); else fit(false);
    cv.focus();
  };
  imgs.forEach(i => { if (i.complete && i.naturalWidth) ready(); else i.onload = ready; });
}

// ---- charmap --------------------------------------------------------------

let charmap = [];
const isIcon = g => g.code >= 0x1000 && !g.ch && !g.blank;
async function loadCharmap() {
  charmap = await api("charmap");
  renderCharmap();
}
async function setChar(g, ch) {
  await api("charmap", { method: "PUT", body: { [g.code]: ch } });
  g.ch = ch; g.unsure = false;
  const fresh = await api("charmap");
  for (const x of charmap) { const f = fresh.find(y => y.code === x.code); x.dup = f && f.dup; }
  state.icons = charmap.filter(isIcon).map(x => x.code);
}
function renderCharmap(page = 0) {
  const mode = getCmMode(), f = $("#cm-find").value.trim();
  const list = charmap.filter(g =>
    (mode === "all" || (mode === "unsure" && (g.unsure || g.dup)) || (mode === "icons" && isIcon(g))) &&
    (!f || g.ch === f || g.code.toString(16) === f.toLowerCase().replace(/^0x/, "")));
  $("#cm-status").textContent = `${list.length} из ${charmap.length}`;
  const go = n => { renderCharmap(n); window.scrollTo(0, 0); };
  fill($("#cm-pager"), ...[pager(list.length, page, go)].filter(Boolean));
  fill($("#glyphs"), ...list.slice(page * PAGE, (page + 1) * PAGE).map(g => {
    const card = h("div", { class: "glyph" + (g.unsure || g.dup ? " unsure" : ""),
      title: g.dup ? "Этот же символ у " + g.dup.map(c => c.toString(16).padStart(4, "0")).join(", ") : "" });
    const draw = () => {
      const isIcon = !g.ch && !g.editing;
      const inp = h("input", { value: g.ch, maxlength: 2 });
      inp.addEventListener("change", async () => { g.editing = false; await setChar(g, inp.value); card.classList.remove("unsure"); inp.classList.add("saved"); });
      const keep = iconBtn("icon", isIcon ? "Значок, остаётся как есть. Нажми, чтобы задать символ" : "Значок: оставить как есть", async () => {
        if (isIcon) { g.editing = true; draw(); card.querySelector("input").focus(); return; }
        g.editing = false; await setChar(g, ""); card.classList.remove("unsure"); draw();
      });
      if (isIcon) keep.classList.add("on");
      fill(card, 
        h("img", { src: `/api/glyph/${g.code.toString(16)}.png`, loading: "lazy", alt: g.ch }),
        h("div", { class: "code" }, g.code.toString(16).padStart(4, "0"), g.dup ? h("span", { class: "dupmark" }, " = " + g.dup.map(c => c.toString(16)).join(",")) : null),
        h("div", { class: "edit" }, isIcon ? h("span", { class: "isicon" }, "значок") : inp, keep));
    };
    draw();
    return card;
  }));
}

// ---- boot -----------------------------------------------------------------

const getMode = seg($("#mode"), () => doSearch());
const getEntryMode = () => $("#entry-mode").value;
$("#entry-mode").addEventListener("change", () => renderEntries());
const getCmMode = seg($("#cm-mode"), () => renderCharmap());
const getTxMode = seg($("#tx-mode"), () => loadTextures());
$("#tx-find").addEventListener("input", () => { clearTimeout(searchTimer); searchTimer = setTimeout(loadTextures, 300); });
$("#tx-index").addEventListener("click", async () => { await runJob("textures"); waitJob(loadTextures); });
document.addEventListener("keydown", e => { if (e.key === "Escape") $("#tx-detail").hidden = true; });
drawIcons();
$("#play").addEventListener("click", () => runJob("playtest"));
$("#jobbar").addEventListener("click", showJobLog);
$("#entry-filter").addEventListener("input", renderEntries);
$("#search").addEventListener("input", doSearch);
$("#search-in").addEventListener("change", doSearch);
$("#cm-find").addEventListener("input", renderCharmap);
window.addEventListener("beforeunload", () => { if (pending.size) flush(); });

(async () => {
  state.project = await api("project");
  let tab = "project";
  try { tab = localStorage.getItem("psptool.tab") || "project"; } catch (e) {}
  const feats = state.project.plugin?.features || [];
  const t = TABS.find(x => x.id === tab);
  if (!state.project.open || !t || (t.feature && !feats.includes(t.feature))) tab = "project";
  show(tab);
  pollJob();
})();
