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
  // sections (sidebar, tab bar)
  folder: '<path d="M1.75 4.5c0-.83.67-1.5 1.5-1.5h3l1.5 1.75h5c.83 0 1.5.67 1.5 1.5v5.5c0 .83-.67 1.5-1.5 1.5H3.25c-.83 0-1.5-.67-1.5-1.5Z" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/>',
  text: '<path d="M2.5 3.5h11M2.5 6.5h11M2.5 9.5h7M2.5 12.5h9" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>',
  font: '<path d="m1.5 13 3.6-10h.8l3.6 10M2.8 9.5h5.4M11.5 8.2a2 2 0 1 1 0 3.9 2 2 0 0 1 0-3.9Zm2 0V13" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>',
  photo: '<rect x="1.75" y="2.75" width="12.5" height="10.5" rx="2" fill="none" stroke="currentColor" stroke-width="1.4"/><circle cx="5.5" cy="6.3" r="1.2" fill="currentColor"/><path d="m2.5 12 3.8-3.6 2.4 2.1 2.2-2 2.6 2.4" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/>',
  hd: '<rect x="1.25" y="3" width="13.5" height="10" rx="2.2" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M4 5.8v4.4M4 8h2.6M6.6 5.8v4.4M9 5.8v4.4h1.2a2.2 2.2 0 0 0 0-4.4Z" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>',
  grid: '<rect x="2" y="2" width="5" height="5" rx="1.3" fill="none" stroke="currentColor" stroke-width="1.4"/><rect x="9" y="2" width="5" height="5" rx="1.3" fill="none" stroke="currentColor" stroke-width="1.4"/><rect x="2" y="9" width="5" height="5" rx="1.3" fill="none" stroke="currentColor" stroke-width="1.4"/><rect x="9" y="9" width="5" height="5" rx="1.3" fill="none" stroke="currentColor" stroke-width="1.4"/>',
  more: '<circle cx="3.5" cy="8" r="1.4" fill="currentColor"/><circle cx="8" cy="8" r="1.4" fill="currentColor"/><circle cx="12.5" cy="8" r="1.4" fill="currentColor"/>',
  back: '<path d="M10 2.5 4.5 8l5.5 5.5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
  sidebar: '<rect x="1.75" y="2.75" width="12.5" height="10.5" rx="2.2" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M6 3v10" stroke="currentColor" stroke-width="1.4"/><path d="M3.5 5.5h1M3.5 7.5h1" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>',
  // sort (arrow.up.arrow.down), filter (line.3.horizontal.decrease.circle, outlined / filled when on)
  gear: '<path d="M8 1.6l1.1 1.5 1.8-.4.5 1.8 1.7.8-.5 1.8 1.2 1.4-1.2 1.4.5 1.8-1.7.8-.5 1.8-1.8-.4L8 14.4l-1.1-1.5-1.8.4-.5-1.8-1.7-.8.5-1.8L2.2 8l1.2-1.4-.5-1.8 1.7-.8.5-1.8 1.8.4Z" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/><circle cx="8" cy="8" r="2.2" fill="none" stroke="currentColor" stroke-width="1.3"/>',
  sort: '<path d="M5 13V3m0 0L2.5 5.5M5 3l2.5 2.5M11 3v10m0 0-2.5-2.5M11 13l2.5-2.5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>',
  filter: '<circle cx="8" cy="8" r="6.6" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M4.8 6h6.4M5.9 8.2h4.2M7 10.4h2" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>',
  filterOn: '<circle cx="8" cy="8" r="7.3" fill="currentColor"/><path d="M4.8 6h6.4M5.9 8.2h4.2M7 10.4h2" stroke="#1d1004" stroke-width="1.5" stroke-linecap="round"/>',
  up: '<path d="M8 13V3m0 0L4 7m4-4 4 4" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>',
  down: '<path d="M8 3v10m0 0-4-4m4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>',
  chev: '<path d="m6 3.5 4.5 4.5L6 12.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>',
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
  const b = h("button", { type: "button", class: "btn", title: L("Выбрать в Finder"), onclick: async () => {
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
  } }, L("Обзор…"));
  return h("div", { class: "pathrow" }, input, state.project?.client_remote ? null : b);
}

// several values out of a list: a button with the count, a popover of
// checkboxes. options: [[value, text, count]]; onchange(values) on close
// ---- sort and filter, the way Apple's apps do it -------------------------
// Two toolbar icons next to the search field: Sort (⇅) opens a menu with a
// tick on the current order; choosing it again flips the direction (Finder,
// Files). Filter (the circled lines of Mail) opens independent groups of
// conditions; it fills with the accent while anything is filtered. The
// active filters show as tokens under the toolbar, each with its ✕.
// spec: { key, sorts: [[id, label, dir]], groups: [{ id, label, multi, options: [[value, label, count]] }] }
// single groups: "" means all; multi groups: [] means all. Kept per screen.
function viewState(spec) {
  const st = { sort: spec.sorts?.[0]?.[0] || "", dir: spec.sorts?.[0]?.[2] || "asc", f: {} };
  for (const g of spec.groups || []) st.f[g.id] = g.multi ? [] : (g.def ?? "");
  try {
    const saved = JSON.parse(localStorage.getItem("psptool.view." + spec.key) || "{}");
    if (spec.sorts?.some(x => x[0] === saved.sort)) { st.sort = saved.sort; st.dir = saved.dir === "desc" ? "desc" : "asc"; }
    for (const g of spec.groups || []) if (saved.f && g.id in saved.f && !g.volatile) st.f[g.id] = saved.f[g.id];
  } catch (e) {}
  return st;
}
const saveView = (spec, st) => { try { localStorage.setItem("psptool.view." + spec.key, JSON.stringify(st)); } catch (e) {} };
const filterOn = (spec, st, g) => g.multi ? st.f[g.id]?.length : (st.f[g.id] ?? "") !== (g.def ?? "");

// a glass menu under its button: sections of rows with a tick column
let openMenu = null;
function showMenu(anchor, build) {
  if (openMenu) { const was = openMenu.anchor; openMenu.close(); if (was === anchor) return; }
  const pop = h("div", { class: "mpick-pop menu", role: "menu" });
  document.body.append(pop);
  const place = () => {
    if (phone.matches) return;   // the phone shows it as a sheet at the bottom (CSS)
    const r = anchor.getBoundingClientRect(), w = pop.offsetWidth;
    pop.style.top = r.bottom + 6 + "px";
    pop.style.left = Math.max(8, Math.min(innerWidth - w - 8, r.right - w)) + "px";
    pop.style.transformOrigin = "top right";
  };
  const render = () => { fill(pop, ...build(render, close)); place(); };
  const outside = e => { if (!pop.contains(e.target) && !anchor.contains(e.target)) close(); };
  const key = e => { if (e.key === "Escape") close(); };
  function close() {
    pop.remove(); openMenu = null; anchor.classList.remove("open");
    document.removeEventListener("pointerdown", outside, true); document.removeEventListener("keydown", key);
  }
  openMenu = { anchor, close };
  anchor.classList.add("open");
  render();
  document.addEventListener("pointerdown", outside, true); document.addEventListener("keydown", key);
}
const menuRow = (label, on, onclick, extra) => h("button", { type: "button", class: "menu-row" + (on ? " on" : ""), role: "menuitemcheckbox",
  "aria-checked": on ? "true" : "false", onclick }, h("span", { class: "tick" }, on ? icon("check") : null), h("span", { class: "lbl" }, label), extra || null);

function viewControls(spec, onchange) {
  const st = viewState(spec);
  const changed = () => { saveView(spec, st); paint(); onchange(st); };
  const sortBtn = spec.sorts?.length ? h("button", { type: "button", class: "icon-btn tool", title: L("Сортировка"), "aria-label": L("Сортировка") }, icon("sort")) : null;
  const filterBtn = spec.groups?.length ? h("button", { type: "button", class: "icon-btn tool", title: L("Фильтр"), "aria-label": L("Фильтр") }) : null;
  const chips = h("div", { class: "tokens" });
  sortBtn && (sortBtn.onclick = () => showMenu(sortBtn, (render, close) => [
    h("div", { class: "menu-head" }, L("Сортировка")),
    ...spec.sorts.map(([id, label, dir]) => menuRow(label, st.sort === id, () => {
      if (st.sort === id) st.dir = st.dir === "asc" ? "desc" : "asc";   // again: the other way
      else { st.sort = id; st.dir = dir || "asc"; }
      changed(); close();
    }, st.sort === id ? h("span", { class: "dir", title: st.dir === "asc" ? L("по возрастанию") : L("по убыванию") }, icon(st.dir === "asc" ? "up" : "down")) : null))]));
  filterBtn && (filterBtn.onclick = () => showMenu(filterBtn, render => {
    const out = [];
    for (const g of spec.groups) {
      out.push(h("div", { class: "menu-head" }, g.label));
      for (const [v, label, n] of g.options) {
        const on = g.multi ? st.f[g.id].includes(v) : st.f[g.id] === v;
        out.push(menuRow(label, on, () => {
          if (g.multi) st.f[g.id] = on ? st.f[g.id].filter(x => x !== v) : [...st.f[g.id], v];
          else st.f[g.id] = v;
          changed(); render();   // stays open: several groups can be set in one go
        }, n != null ? h("span", { class: "count num" }, n) : null));
      }
    }
    if (spec.groups.some(g => filterOn(spec, st, g))) out.push(h("div", { class: "menu-sep" }),
      h("button", { type: "button", class: "menu-row reset", onclick: () => { for (const g of spec.groups) st.f[g.id] = g.multi ? [] : (g.def ?? ""); changed(); render(); } },
        h("span", { class: "tick" }), h("span", { class: "lbl" }, L("Сбросить фильтры"))));
    return out;
  }));
  function paint() {
    const any = spec.groups?.some(g => filterOn(spec, st, g));
    if (filterBtn) { fill(filterBtn, icon(any ? "filterOn" : "filter")); filterBtn.classList.toggle("active", !!any); }
    // the tokens: one per active condition, ✕ takes it away
    const toks = [];
    for (const g of spec.groups || []) {
      if (!filterOn(spec, st, g)) continue;
      const vals = g.multi ? st.f[g.id] : [st.f[g.id]];
      for (const v of vals) {
        const label = (g.options.find(o => o[0] === v) || [v, v])[1];
        toks.push(h("span", { class: "token" }, g.token ? g.token + ": " + label : label,
          h("button", { type: "button", class: "x", title: L("Убрать"), "aria-label": L("Убрать фильтр {0}", label), onclick: () => {
            st.f[g.id] = g.multi ? st.f[g.id].filter(x => x !== v) : (g.def ?? ""); changed();
          } }, icon("close"))));
      }
    }
    fill(chips, ...toks);
    chips.hidden = !toks.length;
  }
  paint();
  return { buttons: [sortBtn, filterBtn].filter(Boolean), chips, st, setOptions: groups => { spec.groups = groups; paint(); } };
}

// sorting helpers: a comparator from a key function, Russian collation for text
const coll = new Intl.Collator(I18N.lang, { numeric: true, sensitivity: "base" });
const byKey = (key, dir) => (a, b) => {
  const x = key(a), y = key(b);
  const c = typeof x === "string" || typeof y === "string" ? coll.compare(String(x), String(y)) : x - y;
  return dir === "desc" ? -c : c;
};

function multiPick(label, options, selected, onchange, allText = L("все")) {
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
      h("button", { type: "button", class: "icon-btn", onclick: () => setAll(true) }, L("Выбрать все")),
      h("button", { type: "button", class: "icon-btn", onclick: () => setAll(false) }, L("Сбросить"))),
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
    h("span", { class: "muted small" }, L("{0}–{1} из {2}", page * size + 1, Math.min(total, (page + 1) * size), total)));
}

async function api(path, opts = {}) {
  const r = await fetch("/api/" + path, {
    method: opts.method || (opts.body ? "POST" : "GET"),
    headers: opts.body ? { "Content-Type": "application/json" } : {},
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (r.status === 401) { location.href = "/login.html"; throw new Error("login"); }
  const data = await r.json();
  // the server's message, in the interface language when we know it ("ValueError: текст")
  if (!r.ok) { const e = data.error || r.statusText, m = /^(\w+): ([\s\S]*)$/.exec(e); throw new Error(m && I18N.dict[m[2]] ? L(m[2]) : e); }
  return data;
}

const state = { project: null, tab: "project", entry: null, summary: [], icons: [] };
const TABS = [
  { id: "project", title: L("Проект") },
  { id: "texts", title: L("Текст"), feature: "texts" },
  { id: "font", title: L("Шрифт"), feature: "font" },
  { id: "llm", title: "LLM", feature: "texts" },
  { id: "textures", title: L("Текстуры"), feature: "textures" },
  { id: "hd", title: L("HD-текстуры"), short: "HD", feature: "textures" },
  { id: "charmap", title: L("Таблица символов"), feature: "charmap" },
  { id: "settings", title: L("Настройки"), side: true },  // at the foot of the sidebar, in "Ещё" on the phone
];

// ---- tabs ---------------------------------------------------------------

const TAB_ICONS = { project: "folder", texts: "text", font: "font", llm: "spark", textures: "photo", hd: "hd", charmap: "grid", settings: "gear" };
// the phone's tab bar has room for four; the rest go under "Ещё"
const PHONE_TABS = ["project", "texts", "textures", "hd"];
const phone = matchMedia("(max-width: 760px)");

function renderTabs() {
  const feats = state.project?.plugin?.features || [];
  $("#play").hidden = !state.project?.open;
  // the scope under the name: which game this project translates
  $("#scope").textContent = state.project?.open ? (state.project.plugin?.name || state.project.meta?.title || "") : "";
  const tabs = TABS.filter(t => !t.side && (!t.feature || (state.project?.open && feats.includes(t.feature))));
  $("#side-settings").classList.toggle("on", state.tab === "settings");
  const btn = (t, short) => h("button", { class: t.id === state.tab ? "on" : "", title: t.title, "aria-current": t.id === state.tab ? "page" : null,
    onclick: () => show(t.id) }, icon(TAB_ICONS[t.id]), h("span", {}, short && t.short || t.title));
  fill($("#tabs"), ...tabs.map(t => btn(t)));
  const more = [...tabs.filter(t => !PHONE_TABS.includes(t.id)), TABS.find(t => t.id === "settings")];
  fill($("#tabbar"), ...tabs.filter(t => PHONE_TABS.includes(t.id)).map(t => btn(t, true)),
    more.length || state.project?.open ? h("button", { class: more.some(t => t.id === state.tab) ? "on" : "", onclick: () => moreSheet(more) },
      icon("more"), h("span", {}, L("Ещё"))) : null);
  if (!state.back) $("#top-title").textContent = TABS.find(t => t.id === state.tab)?.title || "PSPtool";
  requestAnimationFrame(() => placeLens(true));
}

// the sections that did not fit the tab bar, as a sheet
function moreSheet(tabs) {
  let m = $("#more-sheet");
  if (!m) { m = h("div", { id: "more-sheet", class: "modal" }); document.body.append(m); m.onclick = () => { m.hidden = true; }; }
  m.hidden = false;
  fill(m, h("div", { class: "box narrow", onclick: e => e.stopPropagation() },
    h("h2", {}, L("Ещё"), h("span", { class: "sp" }), h("button", { class: "icon-btn", title: L("Закрыть"), onclick: () => { m.hidden = true; } }, icon("close"))),
    // the phone keeps the test run here instead of a button over the content
    state.project?.open ? h("div", { class: "more-list" }, h("button", { class: "action", "data-job": true,
      disabled: $("#play").disabled, onclick: () => { m.hidden = true; runJob("playtest"); } }, icon("play"), L("Проверить в игре"))) : null,
    h("div", { class: "more-list" }, ...tabs.map(t => h("button", { class: t.id === state.tab ? "on" : "", onclick: () => { m.hidden = true; show(t.id); } },
      icon(TAB_ICONS[t.id]), t.title, h("span", { class: "chev" }, icon("chev")))))));
}

// the job status and Play live in the sidebar, on the phone in the top bar
function placeChrome() {
  (phone.matches ? $("#top-right") : $("#side-foot")).append($("#jobbar"), $("#play"));
}
phone.addEventListener("change", () => { placeChrome(); syncSegs(); });

function show(tab) {
  // another section starts at its top: the title pill goes at once, without
  // its fade, before it could show the new name
  const pill = $("#top-title");
  pill.style.transition = "none";
  document.body.classList.remove("scrolled", "moved");
  pill.offsetWidth;  // apply the hidden state now
  requestAnimationFrame(() => requestAnimationFrame(() => { pill.style.transition = ""; }));
  state.tab = tab;
  state.back = null; document.body.classList.remove("has-back");
  if (tab !== "texts") $("#view-texts").classList.remove("detail");
  try { localStorage.setItem("psptool.tab", tab); } catch (e) {}
  for (const v of document.querySelectorAll(".view")) v.hidden = v.id !== "view-" + tab;
  renderTabs();
  window.scrollTo(0, 0);
  onScroll();
  requestAnimationFrame(syncSegs);
  ({ project: renderProject, texts: loadTexts, charmap: loadCharmap, font: renderFont, llm: renderLLM, textures: loadTextures, hd: () => renderHd($("#view-hd")).then(() => renderMovies($("#view-hd"))),
     settings: () => renderSettings($("#view-settings")) })[tab]?.();
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
  bar.textContent = j.running ? j.name + (pr != null ? ` ${pr}%` : "…") : j.error ? j.name + L(": ошибка") : j.name + L(": готово");
  document.querySelectorAll(".jobpanel").forEach(p => paintJob(p, j, pr));
  bar.title = (j.error ? j.error + "\n" : "") + L("Открыть журнал");
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
  p.querySelector(".jnum").textContent = j.progress ? L("{0} из {1}", Math.min(j.progress[0], j.progress[1]), j.progress[1]) + (pr != null ? ` · ${pr}%` : "")
    : j.running ? "…" : "";
  if (!j.running) p.querySelector(".jtitle").textContent = j.error ? L("Ошибка: ") + j.error : j.stopping ? L("Остановлено") : L("Готово");
  const stop = p.querySelector(".jstop");
  if (stop) {
    stop.hidden = !(j.running && j.stoppable);
    stop.disabled = !!j.stopping;
    stop.textContent = j.stopping ? L("Останавливаю…") : L("Стоп");
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
  const text = j.log.join("\n") + (j.error ? L("\n\nОшибка: ") + j.error : "");
  const copy = h("button", { class: "btn", onclick: () => navigator.clipboard.writeText(text).then(() => { copy.textContent = L("Скопировано"); }) }, L("Копировать"));
  const pre = h("pre", { class: "log" });
  for (const l of j.log) pre.append(h("div", { class: /Traceback|Error\b|ошибк/.test(l) ? "err" : "" }, l));
  if (j.error) pre.append(h("div", { class: "err" }, L("Ошибка: ") + j.error));
  fill(m, h("div", { class: "box wide", onclick: e => e.stopPropagation() },
    h("h2", {}, L("Журнал: ") + j.name, h("span", { class: j.error ? "status err" : "muted" }, j.running ? L("идёт…") : j.error ? L("ошибка") : L("готово")),
      h("span", { class: "sp" }), copy,
      h("button", { class: "icon-btn", title: L("Закрыть"), onclick: () => { m.hidden = true; } }, icon("close"))),
    h("div", { class: "joblog" }, pre, j.log_file ? h("div", { class: "muted small" }, L("Сохранён в ") + j.log_file) : null)));
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
    const iso = h("input", { type: "text", placeholder: L("/путь/к/игре.iso") });
    const dir = h("input", { type: "text", placeholder: L("/путь/к/папке") });
    const msg = h("span", { class: "status err" });
    kids.push(section(L("Новый проект"), form([[L("Образ игры"), pathField(iso, "open", L("Образ игры (.iso)"))],
      [L("Папка проекта"), pathField(dir, "folder", L("Папка проекта"))]]),
      h("div", { class: "actions" }, msg, h("button", { class: "btn primary", onclick: async () => {
        msg.textContent = "";
        try { state.project = await api("init", { body: { iso: iso.value, workdir: dir.value } }); show("project"); }
        catch (e) { msg.textContent = e.message; }
      } }, L("Создать")))));
  } else {
    const go = h("button", { class: "btn", hidden: true }, L("Продолжить перевод"));
    // the answer, then the next job at the card's foot, beside the finding that calls for it
    const progress = h("div", { class: "section progress" }, h("div", { class: "figures" }),
      h("div", { class: "actions" }, h("p", { class: "finding" }), go));
    const map = h("div", { class: "section" });
    kids.push(titlebar(p.plugin.name, `${(p.meta.title || "").normalize("NFKC")} · ${p.meta.disc_id}`),
      p.texts ? h("div", { class: "overview" }, progress, map) : null);
    if (p.texts) renderOverview(progress, map, go);
    const ref = h("input", { type: "text", placeholder: L("Путь к образу другой версии"), value: p.meta.ref_iso || "" });
    const out = h("input", { type: "text", value: p.root.replace(/\/$/, "") + "/out.iso" });
    const step = (title, extra, btn, fn, done) => h("div", { class: "step" + (extra?.classList?.contains("pathrow") ? " field" : "") },
      h("span", { class: "dot" + (done ? " done" : "") }, done ? icon("check") : null),
      h("div", {}, h("div", { class: "t" }, title), extra),
      h("button", { class: "btn" + (btn.primary ? " primary" : ""), "data-job": true, onclick: fn }, btn.label));
    const steps = [step(L("Распаковать образ"), h("div", { class: "muted small path" }, p.meta.iso), { label: L("Распаковать"), primary: !p.unpacked }, () => runJob("unpack"), p.unpacked)];
    if (p.plugin.features.includes("texts")) {
      steps.push(step(L("Текст игры"), null, { label: p.texts ? L("Обновить") : L("Достать"), primary: p.unpacked && !p.texts }, () => runJob("texts"), p.texts));
      steps.push(step(L("Подсказка из другой версии"), pathField(ref, "open", L("Образ другой версии (.iso)")),
        { label: p.meta.ref_iso ? L("Обновить") : L("Загрузить") }, () => runJob("ref", { iso: ref.value }), !!p.ref));
    }
    if (p.plugin.features.includes("movies")) {
      steps.push(step(L("Субтитры роликов"), h("div", { class: "muted small" }, L("из роликов подсказки")),
        { label: p.movies ? L("Обновить") : L("Достать") }, () => runJob("subs"), p.movies));
    }
    if (p.plugin.features.includes("eboot")) {
      const eb = h("input", { type: "text", placeholder: "~/.config/ppsspp/PSP/SYSTEM/DUMP/" + p.meta.disc_id + "_EBOOT.BIN" });
      steps.push(step(L("Патч EBOOT"), pathField(eb, "open", L("Расшифрованный EBOOT.BIN (дамп PPSSPP)")), { label: p.eboot ? L("Заменить") : L("Загрузить") }, () => runJob("eboot", { path: eb.value || eb.placeholder }), p.eboot));
    }
    steps.push(step(L("Собрать образ"), pathField(out, "save", L("Куда сохранить образ"), "out.iso"), { label: L("Собрать"), primary: p.texts }, () => runJob("pack", { out: out.value }), false));
    if (resetLog || !jobLog) jobLog = h("pre", { class: "log" });
    kids.push(section(L("Шаги"), h("div", { class: "steps" }, ...steps), jobLog));
  }
  if (p.recent?.length > (p.open ? 1 : 0)) {
    kids.push(section(L("Недавние"), h("div", { class: "steps" }, ...p.recent.filter(r => r !== p.root).map(r =>
      h("div", { class: "step" }, h("span"), h("div", {}, r), h("button", { class: "btn", onclick: async () => {
        state.project = await api("open", { body: { workdir: r } }); show("project");
      } }, L("Открыть")))))));
  }
  fill(v, ...kids);
  if (p.open) renderPlaytest(v);
}

// text recognition engine (movie subtitles, text in textures)
async function renderOcr(slot) {
  const o = await api("ocr");
  const sel = h("select", { onchange: () => api("ocr", { method: "PUT", body: { engine: sel.value } }).then(() => renderOcr(slot)) },
    ...Object.entries(o.engines).filter(([k]) => k !== "vision" || o.vision).map(([k, t]) => h("option", { value: k, selected: k === o.engine }, t)));
  const exe = h("input", { type: "text", value: o.tesseract, placeholder: "tesseract" });
  exe.addEventListener("change", () => api("ocr", { method: "PUT", body: { tesseract: exe.value } }).then(() => renderOcr(slot)));
  const names = { vision: "macOS Vision", tesseract: "Tesseract" };
  const langs = o.tesseract ? (o.tesseract_langs.length ? L("языки: ") + o.tesseract_langs.join(", ") : L("нет языков jpn/eng: установите tesseract-lang")) : L("не найден");
  fill(slot, section(L("Распознавание текста"), form([
    [L("Движок"), h("div", {}, sel, h("div", { class: "muted small" }, o.active ? L("сейчас работает: ") + names[o.active] : L("ни одного движка: установите Tesseract")))],
    ["Tesseract", h("div", { style: "width:100%" }, pathField(exe, "open", L("Программа tesseract")), h("div", { class: "muted small" }, langs))],
  ])));
}

// access from the phone / other computers: only set up on this computer
async function renderRemote(slot) {
  const r = await api("remote");
  const pw = h("input", { type: "password", placeholder: r.has_password ? L("задан, введите новый чтобы сменить") : L("не короче 6 символов"), autocomplete: "new-password" });
  const msg = h("span", { class: "status" });
  const put = async body => {
    msg.textContent = ""; msg.className = "status";
    try { await api("remote", { method: "PUT", body }); }
    catch (e) { msg.textContent = e.message; msg.className = "status err"; return; }
    setTimeout(() => renderRemote(slot), body.on !== undefined ? 900 : 0);  // the server moves to the new address first
  };
  const on = h("input", { type: "checkbox", checked: r.on, onchange: () => put({ on: on.checked }) });
  const ts = r.tailscale;
  const tsLine = !ts.installed ? h("span", {}, L("не установлен · "), h("a", { href: "https://tailscale.com/download", target: "_blank" }, L("скачать")))
    : !ts.running ? L("установлен, но не подключён: откройте Tailscale и войдите")
    : L("подключён") + (ts.name ? " · " + ts.name : "");
  const links = r.addresses.length ? h("div", { class: "addrs" }, ...r.addresses.map(a =>
    h("div", {}, h("span", { class: "muted small" }, a.kind === "tailscale" ? "Tailscale" : "Wi-Fi"), h("code", {}, a.url))))
    : h("span", { class: "muted" }, r.on ? "…" : L("выключено"));
  const sec = section(L("Доступ с других устройств"), form([
    [L("Пароль"), h("div", { class: "pathrow" }, pw, h("button", { type: "button", class: "btn", onclick: () => pw.value && put({ password: pw.value }) }, L("Сохранить")))],
    [L("Доступ"), h("label", { class: "check" }, on, h("span", {}, L("Открыть для телефона и других компьютеров")))],
    ["Tailscale", h("span", {}, tsLine)],
    [L("Адреса"), links],
  ]), h("div", { class: "actions" }, msg));
  fill(slot, sec);
}

// all upscaled textures, before / after. Filters (original size, model,
// marked), marks: a set to redo with another model
const MODEL_SHORT = { waifu2x: "waifu2x", cugan: "CUGAN", "anime-video": "ESRGAN", anime: "ESRGAN+", resize: L("без ИИ"), "?": "?" };
// the gallery's sort and filters: sizes and models (several at once) and
// the marked ones; the counts come from the server with every page
const hdGroups = (res = { sizes: [], models: [] }) => [
  { id: "size", label: L("Исходный размер"), multi: true, options: res.sizes.map(([k, n]) => [k, k, n]) },
  { id: "model", label: L("Чем увеличено"), multi: true, options: res.models.map(([k, n]) => [k, MODEL_SHORT[k] || k, n]) },
  { id: "marked", label: L("Отметки"), options: [["", L("Все")], ["1", L("Только отмеченные")]] }];
const hdView = viewControls({ key: "hdgallery", groups: hdGroups(), sorts: [["size", L("Размер"), "desc"], ["name", L("Имя файла"), "asc"], ["model", L("Модель"), "asc"]] },
  () => hdGallery({ q: hdQ }));
let hdQ = "";
async function hdGallery(f = {}) {
  const v = hdView.st;
  f = { page: 0, q: hdQ, ...f, size: v.f.size.join(","), model: v.f.model.join(","), marked: v.f.marked === "1", sort: v.sort, dir: v.dir };
  hdQ = f.q;
  let m = $("#hd-gallery");
  if (!m) { m = h("div", { id: "hd-gallery", class: "modal" }); document.body.append(m); m.onclick = () => { m.hidden = true; }; }
  const st = await api("hd");
  const qs = new URLSearchParams({ offset: f.page * 60, limit: 60, q: f.q, size: f.size, model: f.model, marked: f.marked ? "1" : "",
                                  sort: f.sort, dir: f.dir });
  const res = await api("hd/gallery?" + qs);
  hdView.setOptions(hdGroups(res));
  const marks = await api("hd/marks");
  const again = patch => hdGallery({ ...f, page: 0, ...patch });
  const find = h("input", { type: "search", placeholder: L("Имя файла"), value: f.q });
  find.onchange = () => again({ q: find.value.trim() });
  const markFilter = async value => { await api("hd/marks", { body: { filter: f, value } }); hdGallery(f); };
  const ver = Date.now();
  const thumb = (n, which) => h("img", { src: `/api/hd/thumb?name=${encodeURIComponent(n)}&which=${which}&v=${ver}`, loading: "lazy" });
  const card = it => {
    const box = h("input", { type: "checkbox", checked: it.marked, title: L("Отметить"), onclick: e => e.stopPropagation() });
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
  } }, L("Пересчитать отмеченные"));
  const go = n => hdGallery({ ...f, page: n });
  fill(m, h("div", { class: "box wide", onclick: e => e.stopPropagation() },
    h("h2", {}, L("Галерея HD"), h("span", { class: "muted small" }, `${res.total}`), h("span", { class: "sp" }),
      h("button", { class: "icon-btn", title: L("Закрыть"), onclick: () => { m.hidden = true; } }, icon("close"))),
    h("div", { class: "hdgal" },
      h("div", { class: "toolbar" },
        h("div", { class: "searchrow grow" }, h("div", { class: "search grow" }, icon("search"), find), h("span", { class: "tools-inline" }, ...hdView.buttons)),
        h("button", { class: "btn", onclick: () => markFilter(true), title: L("Отметить все текстуры, что подходят под фильтр") }, L("Отметить все {0}", res.total)),
        h("button", { class: "btn", onclick: () => markFilter(false), title: L("Снять отметку с текстур под фильтром") }, L("Снять"))),
      hdView.chips,
      pager(res.total, f.page, go, 60),
      res.items.length ? h("div", { class: "hdgrid" }, ...res.items.map(card)) : h("p", { class: "muted" }, L("Ничего нет")),
      pager(res.total, f.page, go, 60)),
    h("div", { class: "hdbar" }, h("span", {}, L("Отмечено: "), cnt), h("span", { class: "sp" }), rmodel, rscale, redo)));
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
      h("button", { class: "btn", onclick: back }, L("Назад")),
      h("button", { class: "icon-btn", title: L("Закрыть"), onclick: () => { m.hidden = true; } }, icon("close"))),
    h("div", { class: "hdcmp" }, h("div", { class: "muted small labels" }, h("span", {}, L("до")), h("span", {}, L("после"))), view,
      h("div", { class: "actions" }, msg, model, scale,
        h("button", { class: "btn primary", "data-job": true, onclick: async () => {
          msg.textContent = L("Считаю…");
          await api("run/hd", { body: { names: [it.name], model: model.value, scale: +scale.value } });
          waitJob(() => { msg.textContent = ""; it.hw = it.w * +scale.value; it.hh = it.h * +scale.value; hdCompare(it, st, back); });
        } }, L("Пересчитать"))))));
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
    fig(L("Переведено"), `${pct(done, total)}%`, L("{0} из {1} строк", done.toLocaleString(I18N.lang), total.toLocaleString(I18N.lang)), true),
    fig(L("Проверено"), `${pct(checked, total)}%`, L("{0} строк", checked.toLocaleString(I18N.lang))),
    fig(L("Файлов готово"), filesDone, L("из {0}", sum.length)));
  const open = sum.filter(e => e.done < e.total).sort((a, b) => (b.total - b.done) - (a.total - a.done));
  const left = total - done;
  progress.querySelector(".finding").textContent = left
    ? L("Осталось {0} строк в {1} файлах; больше всего в {2}: {3}.", left.toLocaleString(I18N.lang), open.length, open[0].name || String(open[0].entry).padStart(4, "0"), open[0].total - open[0].done)
    : (checked < total ? L("Всё переведено; не проверено ещё {0} строк.", (total - checked).toLocaleString(I18N.lang)) : L("Всё переведено и проверено."));
  const next = sum.find(e => e.done < e.total) || sum.find(e => (e.checked || 0) < e.total);
  if (next) {
    go.hidden = false;
    go.textContent = next.done < next.total ? L("Продолжить: {0}", next.name || String(next.entry).padStart(4, "0")) : L("Проверять дальше");
    go.onclick = () => { show("texts"); openEntry(next.entry); };
  }
  // one cell per file: the deeper the orange, the more is translated; green when checked
  const level = e => !e.total || !e.done ? "" : (e.checked || 0) === e.total ? "c4" : e.done === e.total ? "c3" : e.done / e.total >= .5 ? "c2" : "c1";
  const key = (cls, label) => h("span", {}, h("i", { class: "cells-key " + cls, style: `background:${{ "": "var(--fill-2)", c1: "color-mix(in srgb, var(--accent) 35%, var(--card-2))", c3: "var(--accent)", c4: "var(--positive)" }[cls]}` }), label);
  fill(map, h("div", { class: "cover" },
    h("div", { class: "cover-head" }, h("h2", {}, L("Файлы игры")),
      h("div", { class: "cover-key" }, key("", L("не тронут")), key("c1", L("начат")), key("c3", L("переведён")), key("c4", L("проверен")))),
    h("div", { class: "cells" }, ...sum.map(e => h("button", {
      class: level(e), title: L("{0} · {1} из {2} · проверено {3}\n{4}", e.name || String(e.entry).padStart(4, "0"), e.done, e.total, e.checked || 0, e.preview),
      "aria-label": L("{0}: {1} из {2}", e.name || e.entry, e.done, e.total),
      onclick: () => { show("texts"); openEntry(e.entry); } })))));
}

// before an upscale run: which model, how big, which original sizes (and on
// a redo, which of the current results); the count updates as you choose
// what a run would take with no choices made, fetched while the HD tab
// is open, so the dialog opens at once at its full size
const hdPickCache = {};
const pickUrl = (redo, sizes = [], made = []) => `hd/pick?redo=${redo ? 1 : ""}&sizes=${sizes.join(",")}&models=${made.join(",")}`;
const prefetchPick = () => [false, true].forEach(redo => api(pickUrl(redo)).then(r => { hdPickCache[redo] = r; }).catch(() => {}));

async function hdRunDialog(redo, st, run) {
  let m = $("#hd-run");
  if (!m) { m = h("div", { id: "hd-run", class: "modal" }); document.body.append(m); m.onclick = () => { m.hidden = true; }; }
  const model = h("select", {}, ...st.models.map(x => h("option", { value: x.id, disabled: !x.ok, selected: x.id === st.hd.model }, x.name)));
  const scale = h("select", {}, ...[2, 3, 4].map(n => h("option", { value: n, selected: n === (st.hd.scale || 3) }, "×" + n)));
  let sizes = [], made = [];
  const count = h("span", { class: "muted" });
  const go = h("button", { class: "btn primary" }, redo ? L("Пересчитать") : L("Увеличить"));
  const sizeBox = h("div", { class: "chips" }), madeBox = h("div", { class: "chips" });
  const chips = (box, items, chosen, label, set) => fill(box, ...items.map(([k, n]) => {
    const c = h("input", { type: "checkbox", checked: chosen.includes(k) });
    c.onchange = () => { set(c.checked ? [...chosen, k] : chosen.filter(x => x !== k)); };
    return h("label", { class: "chip" + (chosen.includes(k) ? " on" : "") }, c, h("span", {}, label(k)), h("span", { class: "muted small num" }, n));
  }));
  const paint = r => {
    chips(sizeBox, r.sizes, sizes, k => k, v => { sizes = v; refresh(); });
    if (redo) chips(madeBox, r.models, made, k => k === "-" ? L("ещё не увеличены") : (MODEL_SHORT[k] || k), v => { made = v; refresh(); });
    count.textContent = L("Будет обработано: {0}", r.count.toLocaleString(I18N.lang)) + (sizes.length ? "" : L(" (все размеры)"));
    go.disabled = !r.count;
  };
  const refresh = async () => {
    const r = await api(pickUrl(redo, sizes, made));
    if (!sizes.length && !made.length) hdPickCache[redo] = r;
    paint(r);
  };
  go.onclick = () => {
    m.hidden = true;
    run("hd", { model: model.value, scale: +scale.value, redo, sizes, models: made }, redo ? L("Пересчёт текстур") : L("Увеличение текстур"));
  };
  fill(m, h("div", { class: "box", onclick: e => e.stopPropagation() },
    h("h2", {}, redo ? L("Пересчитать текстуры") : L("Увеличить новые текстуры"), h("span", { class: "sp" }),
      h("button", { class: "icon-btn", title: L("Закрыть"), onclick: () => { m.hidden = true; } }, icon("close"))),
    form([
      [L("Модель"), model, scale],
      [L("Исходные размеры"), h("div", { style: "width:100%" }, h("div", { class: "muted small", style: "margin-bottom:6px" }, L("ничего не выбрано — все размеры")), sizeBox)],
      ...(redo ? [[L("Сейчас сделаны"), h("div", { style: "width:100%" }, h("div", { class: "muted small", style: "margin-bottom:6px" }, L("ничего не выбрано — любые")), madeBox)]] : []),
    ]),
    h("div", { class: "actions" }, count, h("button", { class: "btn", onclick: () => { m.hidden = true; } }, L("Отмена")), go)));
  if (hdPickCache[redo]) paint(hdPickCache[redo]);   // full at once; the fresh numbers follow quietly
  m.hidden = false;
  await refresh();
}

// a job's progress bar, Stop, its log (filled by openJobPanel / pollJob)
const jobPanel = () => h("div", { class: "jobpanel", hidden: true },
  h("div", { class: "jhead" }, h("span", { class: "jtitle" }), h("div", { class: "jbar" }, h("i")), h("span", { class: "jnum muted small" }),
    h("button", { class: "btn jstop", hidden: true }, L("Стоп")),
    h("button", { class: "icon-btn jtoggle", title: L("Журнал") }, "▾"), h("button", { class: "icon-btn jclose", title: L("Закрыть") }, icon("close"))),
  h("pre", { class: "log", hidden: true }));

// the movies, cleaned by Real-CUGAN at their own 480x272: settings, the
// preparation job, and a frame of any movie before / after in any mode
async function renderMovies(v) {
  const st = await api("movies");
  const total = st.movies.length;
  const on = h("input", { type: "checkbox", checked: st.settings.on });
  const mode = h("select", {}, ...st.modes.map(m => h("option", { value: m.id, selected: m.id === st.settings.mode }, L(m.name))));
  const save = async patch => { await api("movies", { method: "PUT", body: patch }); renderMovies(v); };
  on.onchange = () => save({ on: on.checked });
  mode.onchange = () => save({ mode: mode.value });
  const panel = jobPanel();
  api("job").then(j => { if (j.running && j.name === "movies") { openJobPanel(panel, L("Подготовка роликов")); jobOwner = j.name; jobNext = 0; pollJob(); } });
  const left = total - st.ready;
  // preview: one frame, original against the chosen mode
  const pick = h("select", {}, ...st.movies.map(m => h("option", { value: m.n }, L("movie{0} · {1} кадров", String(m.n).padStart(2, "0"), m.frames))));
  pick.value = state.moviePick ?? 7;
  const pos = h("input", { type: "range", min: 0, style: "flex:1" });
  pos.max = (st.movies.find(m => m.n === +pick.value) || st.movies[0]).frames - 1;  // the max before the value, or it clamps
  pos.value = state.movieFrame ?? 180;
  const at = h("span", { class: "muted small num", style: "min-width:120px;text-align:right" });
  // the frame keeps the PSP's 480:272 at any width; the split is a percentage
  const after = h("img", { class: "fill" });
  const before = h("img", { class: "fill", style: "clip-path:inset(0 50% 0 0)" });
  const bar = h("i", { class: "bar", style: "left:50%" });
  const view = h("div", { class: "slider frame" }, after, before, bar);
  const split = e => {
    const r = view.getBoundingClientRect(), p = Math.max(0, Math.min(100, (e.clientX - r.left) / r.width * 100));
    before.style.clipPath = `inset(0 ${100 - p}% 0 0)`; bar.style.left = p + "%";
  };
  view.addEventListener("pointerdown", e => { try { view.setPointerCapture(e.pointerId); } catch (err) {} split(e); });
  view.addEventListener("pointermove", e => { if (e.buttons || e.pointerType === "mouse") split(e); });
  const wait = h("span", { class: "muted small" });
  let t = null;
  const show_ = () => {
    const m = st.movies.find(x => x.n === +pick.value);
    pos.max = m.frames - 1;
    if (+pos.value > m.frames - 1) pos.value = 0;
    const sec = +pos.value * 1001 / 30000;
    at.textContent = L("кадр {0} · {1}:{2}", pos.value, Math.floor(sec / 60), (sec % 60).toFixed(1).padStart(4, "0"));
    clearTimeout(t);
    t = setTimeout(() => {
      state.moviePick = +pick.value; state.movieFrame = +pos.value;
      const q = `n=${pick.value}&frame=${pos.value}&mode=${mode.value}`;
      wait.textContent = L("считаю кадр…");
      before.src = `/api/movies/frame.png?${q}&which=orig`;
      after.onload = () => { wait.textContent = ""; };
      after.src = `/api/movies/frame.png?${q}&which=enh`;
    }, 250);
  };
  pick.onchange = show_;
  pos.oninput = show_;
  const old = v.querySelector(".movies");
  const sec = section(L("Ролики"), form([
    [L("Сборка"), h("label", { class: "switch" }, on, L("Собирать образ из улучшенных роликов")),
      h("span", { class: "muted small" }, L("субтитры рисуются поверх"))],
    [L("Режим Real-CUGAN"), mode, h("span", { class: "muted small" }, L("ролики остаются 480×272: ИИ чистит линии и блоки сжатия"))],
    [L("Подготовлено"), h("div", { class: "cov", style: "width:100%" },
      h("div", { class: "cov-top" }, h("span", {}, mode.selectedOptions[0].textContent), h("span", { class: "muted small" }, L("{0} из {1}", st.ready, total))),
      h("div", { class: "jbar" + (st.ready === total ? " full" : "") }, h("i", { style: `width:${100 * st.ready / total}%` })),
      h("div", { class: "muted small" }, left ? L("осталось {0}, около {1} мин", left, Math.max(1, Math.round(st.movies.filter(m => !m.ready).reduce((a, m) => a + m.frames, 0) / 1100))) : L("все ролики готовы")))],
  ]),
  h("div", { class: "actions" },
    h("button", { class: "btn", "data-job": true, disabled: !left, onclick: () => { openJobPanel(panel, L("Подготовка роликов")); runJob("movies", { mode: mode.value }); } },
      left ? L("Подготовить {0}", left) : L("Готово"))),
  panel,
  h("div", { class: "moviecmp" },
    h("div", { class: "row" }, pick, pos, at),
    h("div", { class: "labels muted small" }, h("span", {}, L("оригинал")), wait, h("span", {}, mode.selectedOptions[0].textContent)),
    view));
  sec.classList.add("movies");
  old ? old.replaceWith(sec) : v.append(sec);
  show_();
}

// HD textures for PPSSPP: dump while playing, upscale, done
async function renderHd(v) {
  const st = await api("hd");
  if (st.upscaler) prefetchPick();
  const scale = h("select", {}, ...[2, 3, 4].map(n => h("option", { value: n, selected: n === (st.hd.scale || 3) }, "×" + n)));
  const model = h("select", {}, ...st.models.map(m => h("option", { value: m.id, disabled: !m.ok, selected: m.id === st.hd.model }, m.name)));
  const saving = h("input", { type: "checkbox", checked: st.saving });
  saving.addEventListener("change", async () => { await api("hd", { method: "PUT", body: { saving: saving.checked } }); renderHd(v); });
  const panel = jobPanel();
  const run = (what, body, title) => { openJobPanel(panel, title); runJob(what, body); };
  // a job still running (page reloaded): show its panel again
  api("job").then(j => { if (j.running && (j.name === "hd" || j.name === "hdarchive")) { openJobPanel(panel, L("Увеличение текстур")); jobOwner = j.name; jobNext = 0; pollJob(); } });
  const left = st.total - st.done;
  // coverage: the one figure that matters is how much of what is
  // collected is HD; the two sources below it only say where it came from
  const pct = (done, total) => total ? Math.floor(100 * done / total) : 0;
  const meter = (label, done, total, hint, main) => h("div", { class: "cov" + (main ? " main" : " sub") },
    h("div", { class: "cov-top" }, h("span", {}, label),
      main ? h("span", { class: "cov-big num" }, total ? pct(done, total) + "%" : "—") : null,
      h("span", { class: "muted small num" }, total ? L("{0} из {1}", done, total) + (main ? "" : ` · ${pct(done, total)}%`) : "—")),
    h("div", { class: "jbar" + (main && total && done === total ? " full" : "") }, h("i", { style: `width:${total ? 100 * done / total : 0}%` })),
    hint ? h("div", { class: "muted small" }, hint) : null);
  const today = st.days?.[0];
  const ready = st.total > 0 && left === 0;
  const coverage = h("div", { class: "covs" },
    meter(L("Всего в HD"), st.done, st.total, ready ? L("Всё собранное увеличено, пак можно паковать") : st.total ? L("осталось увеличить: {0}", left) : null, true),
    h("div", { class: "cov-sources" },
      meter(L("Из архива игры"), st.archive_done, st.archive, st.archive ? null : L("ещё не собрано: «Собрать из архива»")),
      meter(L("Из игры (сохранено PPSSPP)"), st.dumped_done, st.dumped,
        today ? L("последняя игра {0}: +{1} новых", today[0], today[1]) + (st.days.length > 1 ? L(" · до этого {0}: +{1}", st.days[1][0], st.days[1][1]) : "") : L("поиграй с включённым сохранением"))));
  const pairs = st.samples?.length ? h("div", { class: "hdpairs" }, ...st.samples.map(n => h("div", { class: "hdpair" },
    h("img", { src: `/api/hd/img?name=${encodeURIComponent(n)}&which=orig`, loading: "lazy" }),
    h("img", { src: `/api/hd/img?name=${encodeURIComponent(n)}&which=hd`, loading: "lazy" })))) : null;
  const old = v.querySelector(".hdtex");
  if (!v.querySelector(".titlebar")) v.prepend(titlebar(L("HD-текстуры"), L("пак для PPSSPP: текстуры игры в высоком разрешении, игра не меняется")));
  const sec = section(L("Пак текстур"), form([
    ["PPSSPP", h("label", { class: "switch", title: L("Эмулятор сохраняет каждую новую текстуру, пока ты играешь. Переключай при закрытом эмуляторе.") },
      saving, L("Сохранять новые текстуры"))],
    [L("Покрытие"), coverage,
      st.frames ? h("span", { class: "muted small", title: L("Кадры роликов: у каждого свой хеш, увеличивать их бесполезно") }, L("кадры видео пропущены: {0}", st.frames)) : null],
    st.tools.some(t => !t.ok) ? [L("Нейросети"), h("div", { class: "tools" }, ...st.tools.map(t => t.ok
      ? h("span", { class: "muted small" }, t.name + " ✓")
      : h("button", { class: "btn", "data-job": true, onclick: () => run("hdtool", { tool: t.id }, L("Загрузка {0}", t.name)) }, icon("download"), L("Скачать {0}", t.name))))] : null]),
  h("div", { class: "actions" },
    h("button", { class: "btn", disabled: !st.done, onclick: () => hdGallery() }, L("Галерея")),
    h("button", { class: "btn" + (ready ? " primary" : ""), "data-job": true, disabled: !st.done, onclick: () => run("hdzip", {}, L("Пак HD-текстур")) }, L("Запаковать пак")),
    h("button", { class: "btn", "data-job": true, disabled: !st.upscaler, title: L("Посчитать текстуры прямо из файлов игры и увеличить"),
      onclick: () => run("hdarchive", { scale: +scale.value, model: model.value }, L("Текстуры из архива")) }, st.archive ? L("Обновить из архива") : L("Собрать из архива")),
    h("button", { class: "btn", "data-job": true, disabled: !st.total || !st.upscaler, onclick: () => hdRunDialog(true, st, run) }, L("Пересчитать…")),
    h("button", { class: "btn" + (ready ? "" : " primary"), "data-job": true, disabled: !left || !st.upscaler, onclick: () => hdRunDialog(false, st, run) },
      left ? L("Увеличить новые ({0})", left) : L("Увеличить новые"))),
  panel, pairs);
  sec.classList.add("hdtex");
  old ? old.replaceWith(sec) : v.append(sec);
}

async function renderPlaytest(v, before = null) {
  const pt = await api("playtest");
  const slots = h("input", { type: "text", value: pt.probe_slots.join(", ") });
  slots.addEventListener("change", () => api("playtest", { method: "PUT", body: { probe_slots: slots.value.split(",").map(x => x.trim()).filter(Boolean) } }));
  const pick = path => api("playtest", { method: "PUT", body: { state: path } }).then(() => renderPlaytest(v));
  const card = (st, label, img) => h("div", { class: "scard" + (pt.state === st ? " on" : ""), onclick: () => pick(st), title: st || "" },
    img ? h("img", { src: img }) : h("div", { class: "noimg" }, "▶"), h("div", { class: "small" }, label));
  const old = v.querySelector(".playtest");
  const sec = section(L("Проверка в игре"), form([
    pt.emulator ? null : [L("Эмулятор"), h("span", { class: "muted" }, L("не найден: укажите его в "), h("a", { href: "#", onclick: e => { e.preventDefault(); show("settings"); } }, L("Настройках")))],
    [L("Запуск"), h("div", { class: "states" }, card("", L("с начала")),
      ...pt.states.map(s => card(s.path, new Date(s.mtime * 1000).toLocaleString(I18N.lang, { dateStyle: "short", timeStyle: "short" }),
        `/api/state.jpg?path=${encodeURIComponent(s.path)}`)))],
    [L("Тестовое место"), slots],
  ]), h("div", { class: "actions" }, h("button", { class: "btn primary", "data-job": true, onclick: () => runJob("playtest") }, icon("play"), L("Проверить в игре"))));
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
  if ($("#search").value) doSearch(); else if (state.entry != null) openEntry(state.entry);
}

function renderEntries() {
  const f = $("#entry-filter").value.toLowerCase();
  const sum = k => state.summary.reduce((a, e) => a + (e[k] || 0), 0);
  $("#side-sub").textContent = L("{0} файлов · {1} из {2} строк переведено", state.summary.length, sum("done"), sum("total"));
  fill($("#texts-status"), h("span", { class: "c-done", title: L("Переведено") }, sum("done")), " / ",
    h("span", { class: "c-chk", title: L("Проверено") }, sum("checked")), " / ", h("span", { title: L("Всего") }, sum("total")));
  const { f: fl, sort, dir } = fileView.st;
  const trOf = e => !e.done ? "none" : e.done < e.total ? "part" : "full";
  const chkOf = e => (e.checked || 0) === e.total ? "yes" : "no";
  const found = state.summary.filter(e => !f || String(e.entry).includes(f) || (e.name || "").toLowerCase().includes(f) || e.preview.toLowerCase().includes(f));
  // counts next to each condition, as the other filter leaves them
  const n = (key, v, other) => found.filter(e => key(e) === v && (!fl[other.id] || other.of(e) === fl[other.id])).length;
  const TR = { id: "tr", of: trOf }, CHK = { id: "chk", of: chkOf };
  fileView.setOptions(fileGroups(
    { none: n(trOf, "none", CHK), part: n(trOf, "part", CHK), full: n(trOf, "full", CHK) },
    { no: n(chkOf, "no", TR), yes: n(chkOf, "yes", TR) }));
  const keys = { num: e => e.entry, progress: e => e.done / (e.total || 1), checked: e => (e.checked || 0) / (e.total || 1),
                 left: e => e.total - e.done, total: e => e.total };
  const list = found.filter(e => (!fl.tr || trOf(e) === fl.tr) && (!fl.chk || chkOf(e) === fl.chk))
    .sort((a, b) => byKey(keys[sort] || keys.num, dir)(a, b) || a.entry - b.entry);
  fill($("#entry-list"), ...list
    .map(e => h("li", { class: e.entry === state.entry ? "on" : "", onclick: () => { $("#search").value = ""; openEntry(e.entry); showFile(); } },
      h("div", { class: "top" }, h("span", { class: "num" }, e.name || String(e.entry).padStart(4, "0")),
        h("span", { class: "muted" }, h("span", { class: "c-done" }, e.done), " / ", h("span", { class: "c-chk" }, e.checked || 0), " / ", e.total)),
      h("div", { class: "pv" }, e.preview),
      h("div", { class: "bar", title: L("Переведено") }, h("i", { style: `width:${100 * e.done / e.total}%` })),
      h("div", { class: "bar chk", title: L("Проверено") }, h("i", { style: `width:${100 * (e.checked || 0) / e.total}%` })))));
}

// the phone shows the list or the file, never both (a navigation stack)
// a page inside a tab: the round back button and the page's own name in
// the title pill; back() returns to the tab's first page
function setBack(back, title) {
  state.back = back;
  document.body.classList.toggle("has-back", !!back);
  $("#top-title").textContent = back && title ? title : TABS.find(x => x.id === state.tab)?.title || "PSPtool";
}

function showFile(on = true) {
  $("#view-texts").classList.toggle("detail", on);
  setBack(on && phone.matches ? () => showFile(false) : null, on ? $("#texts-title").textContent : "");
  if (phone.matches) window.scrollTo(0, 0);
  requestAnimationFrame(onScroll);
  requestAnimationFrame(syncSegs);
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
    openJobPanel($("#texts-job"), L("Перевод файла {0}", String(i).padStart(4, "0")));
    await runJob("llm", { entry: i });
    waitJob(() => { refreshSummary(i); openEntry(i); });
  };
  const token = state.loading = {};
  let rows = await api("texts/" + i);
  if (state.loading !== token) return;  // another file was opened meanwhile
  rows = sortRows(rows.filter(r => rowOk(r, rowView.st.f)));
  // whole-file check: on if anything translated is unchecked, else "uncheck"
  const all = await api("texts/" + i);
  const translated = all.filter(r => r.dst), allChecked = translated.length && translated.every(r => r.checked);
  const name = state.summary?.find(e => e.entry === i)?.name || String(i).padStart(4, "0");
  $("#texts-title").textContent = name;
  if (state.back) $("#top-title").textContent = name;
  $("#texts-sub").textContent = L("{0} из {1} переведено · {2} проверено", translated.length, all.length, all.filter(r => r.dst && r.checked).length);
  const cb = $("#check-entry");
  cb.hidden = !translated.length;
  cb.lastChild.textContent = allChecked ? L("Снять проверку") : L("Проверить файл");
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
    const q = $("#search").value, f = rowView.st.f;
    if (!q) return state.entry != null && openEntry(state.entry);
    const token = state.loading = {};
    const rows = sortRows(await api(`search?${new URLSearchParams({ q, in: f.in || "any", tr: f.tr || "", src: f.src || "", chk: f.chk || "" })}`));
    if (state.loading !== token) return;
    $("#texts-title").textContent = L("Поиск");
    $("#texts-sub").textContent = L("«{0}»: {1} строк", q, rows.length);
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
    rows.length ? null : h("p", { class: "muted" }, L("Ничего нет")));
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
      meter.textContent = ta.value ? L("{0} / {1} байт · системный шрифт", n, UTF8_MAX) : "";
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
        msg.textContent = L("Нет в шрифте: ") + e.error.replace(/^.*no glyph for /, "");
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
  const ta = h("textarea", { spellcheck: "true", placeholder: L("Перевод") });
  ta.value = r.dst || "";
  const pv = preview(r, ta);
  const mt = r.mt ? h("span", { class: "badge mt", title: L("Машинный перевод") }, "LLM") : null;
  const chk = iconBtn("check", L("Отметить как проверенное"), async () => {
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
    chk.title = r.checked ? L("Проверено. Нажми, чтобы снять") : L("Отметить как проверенное"); };
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
  const more = h("button", { type: "button", class: "more", title: L("Все значки"), onclick: () => {
    more.remove(); palette.append(...state.icons.filter(c => !used.includes(c)).map(iconBtnFor));
  } }, "+");
  if (state.icons.length > used.length) palette.append(more);
  const dups = r.dups > 1 ? iconBtn("all", L("Записать этот перевод во все повторы строки, заменив их перевод ({0})", r.dups), async ev => {
    await flush();
    const b = ev.currentTarget;
    const res = await api("propagate", { body: { src: r.src, dst: ta.value } });
    b.title = L("Записано: {0}", res.count);
    for (const v of rowViews) if (v.r !== r && v.r.src === r.src) v.set(ta.value);
    refreshSummary(r.entry);
  }, `×${r.dups}`) : null;
  const toggleIcons = state.icons.length ? iconBtn("icon", L("Значки кнопок"), () => { palette.hidden = !palette.hidden; }) : null;
  if (r.dst) pv.update();
  const head = h("div", { class: "head" }, h("span", {}, `${state.summary.find(e => e.entry === r.entry)?.name || String(r.entry).padStart(4, "0")} · ${r.id}`), mt, h("span", { class: "sp" }),
      iconBtn("spark", L("Перевести эту строку через LLM"), async ev => {
        const b = ev.currentTarget; b.disabled = true; b.classList.add("busy");
        await flush();
        const res = await api("llm/row", { body: { entry: r.entry, id: r.id } }).catch(e => ({ error: e.message }));
        b.disabled = false; b.classList.remove("busy");
        if (res.error) { pv.msg.textContent = res.error; return; }
        ta.value = res.dst; pv.update();
        const ex = res.examples || [];
        fill(samples, ex.length ? L("По образцу проверенных: {0}", ex.length) : L("Похожих проверенных строк нет"));
        samples.title = ex.map(([a, b]) => `${a} → ${b}`).join("\n");
        samples.hidden = false;
        if (!head.querySelector(".mt")) head.insertBefore(h("span", { class: "badge mt", title: L("Машинный перевод") }, "LLM"), head.children[1]);
      }),
      r.utf8 || r.sub ? null : iconBtn("eye", L("Показать в игре: подставить этот перевод на тестовое место и запустить"), async () => {
        if (!ta.value) { pv.msg.textContent = L("Нечего показывать: перевод пустой"); return; }
        await flush();
        openJobPanel($("#texts-job"), L("Проверка в игре"));
        runJob("playtest", { probe: ta.value });
      }),
      r.ref ? iconBtn("copy", L("Вставить подсказку в перевод"), () => { ta.value = r.ref; ta.dispatchEvent(new Event("input")); }) : null,
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
  const ttf = h("input", { type: "text", value: st.ttf || "", placeholder: L("/путь/к/шрифту.ttf") });
  const idx = h("input", { type: "number", value: st.index ?? 0, min: 0, style: "width:80px" });
  const px = h("input", { type: "number", value: st.px ?? 14, min: 8, max: 24, style: "width:80px" });
  const chars = h("textarea", { rows: 3 }); chars.value = st.chars || "";
  const ascii = h("input", { type: "checkbox" }); ascii.checked = st.redraw_ascii !== false;
  const track = h("input", { type: "number", value: st.tracking ?? 1, min: 0, max: 4, style: "width:80px" });
  jobLog = h("pre", { class: "log" });
  const cells = Object.entries(p.font?.cells || {}).filter(([c]) => parseInt(c, 16) >= 0x5e);
  fill(v, titlebar(L("Шрифт"), L("кириллица в шрифте игры: какой шрифт, какого размера и в какие ячейки")),
    section(L("Шрифт"), form([
      [L("Файл шрифта"), pathField(ttf, "open", L("Шрифт (.ttf, .otf, .ttc)"))],
      [L("Начертание"), idx, h("span", { class: "muted small" }, L("номер в .ttc"))],
      [L("Размер"), px, h("span", { class: "muted small" }, "px")],
      [L("Интервал"), track, h("span", { class: "muted small" }, L("px между буквами"))],
      [L("Буквы"), chars],
      [L("Латиница"), h("label", { class: "switch" }, ascii, L("перерисовать тем же шрифтом"))],
    ]), h("div", { class: "actions" }, h("button", { class: "btn primary", "data-job": true, onclick: async () => {
      await runJob("font", { ttf: ttf.value, index: +idx.value, px: +px.value, chars: chars.value, redraw_ascii: ascii.checked, tracking: +track.value });
      waitJob(async () => { state.project = await api("project"); renderFont(); });
    } }, L("Собрать"))), jobLog),
    cells.length ? section(L("Новые знаки · {0}", cells.length), h("div", { class: "glyphs", style: "padding:12px" },
      ...cells.map(([c, ch]) => h("div", { class: "glyph", title: c },
        h("img", { src: `/api/glyph/${c}.png?new=1&t=${Date.now()}`, alt: ch }), h("div", {}, ch))))) : null);
}

// ---- LLM ------------------------------------------------------------------

async function renderLLM() {
  const v = $("#view-llm");
  const s = await api("llm/settings");
  const gl = await api("glossary");
  const batch = h("input", { type: "number", value: s.batch, min: 1, max: 100, style: "width:80px" });
  const lang = h("input", { type: "text", value: s.target_lang });
  const gloss = h("textarea", { rows: 10, placeholder: L("黒崎一護 / Ichigo Kurosaki → Ичиго Куросаки") });
  gloss.value = gl.text;
  const status = h("span", { class: "status" });
  const save = () => Promise.all([
    api("llm/settings", { method: "PUT", body: { batch: +batch.value, target_lang: lang.value } }),
    api("glossary", { method: "PUT", body: { text: gloss.value } })]);
  const limit = h("input", { type: "number", value: 50, min: 1, style: "width:100px" });
  jobLog = h("pre", { class: "log" });
  // autosave: every field, a moment after the last change
  let timer = null;
  const autosave = () => {
    clearTimeout(timer);
    status.textContent = ""; status.className = "status";
    timer = setTimeout(async () => { await save(); status.textContent = L("Сохранено"); }, 500);
  };
  for (const el of [batch, lang, gloss]) { el.addEventListener("input", autosave); el.addEventListener("change", autosave); }
  const prov = s.provider === "anthropic" ? "Anthropic · " + s.anthropic.model : L("OpenAI-совместимый") + " · " + s.openai.model;
  fill(v, titlebar("LLM", L("перевод строк языковой моделью: язык и глоссарий")),
    section(L("Перевод"), form([
      [L("Модель"), h("span", {}, prov, " · ", h("a", { href: "#", onclick: e => { e.preventDefault(); show("settings"); } }, L("изменить в Настройках")))],
      [L("Язык"), lang], [L("Строк за запрос"), batch], [L("Глоссарий"), gloss]]),
      h("div", { class: "actions" }, status, limit, h("span", { class: "muted small" }, L("строк")),
        h("button", { class: "btn primary", "data-job": true, onclick: async () => { await save(); runJob("llm", { limit: +limit.value }); } }, icon("spark"), L("Перевести"))),
      jobLog));
}

// ---- settings: the app as a whole, whatever project is open ------------

async function renderSettings(v) {
  const theme = pref("psptool.theme", "system"), lang = pref("psptool.lang", "system");
  const themeSeg = h("div", { class: "seg" }, ...[["system", L("Как в системе")], ["light", L("Светлая")], ["dark", L("Тёмная")]]
    .map(([k, label]) => h("button", { type: "button", "data-v": k, class: k === theme ? "on" : "" }, label)));
  seg(themeSeg, k => { try { localStorage.setItem("psptool.theme", k); } catch (e) {} applyTheme(k); });
  const sysLang = LANGS.find(l => l[0] === pickLang("system"))?.[1] || "English";
  const langSel = h("select", {}, h("option", { value: "system" }, L("Как в системе ({0})", sysLang)),
    ...LANGS.map(([code, name]) => h("option", { value: code }, name)));
  langSel.value = lang;
  // a new language: the page reloads in it (the dictionary loads before the app)
  langSel.onchange = () => { try { localStorage.setItem("psptool.lang", langSel.value); } catch (e) {} location.reload(); };
  // the colour: the PSP's twelve, or the month's (the console's own default)
  const accent = pref("psptool.accent", "month");
  const caption = h("div", { class: "muted small" });
  const nameOf = i => L("{0} · {1}", L(MONTHS[i]), L(ACCENTS[i][1]));
  const paintCaption = choice => {
    caption.textContent = choice === "month" ? L("По месяцу, как на PSP: сейчас {0}", nameOf(accentIndex("month"))) : nameOf(+choice);
  };
  const swatches = h("div", { class: "swatches", role: "radiogroup", "aria-label": L("Цвет") });
  const pick = choice => {
    try { localStorage.setItem("psptool.accent", choice); } catch (e) {}
    applyAccent(choice);
    swatches.querySelectorAll("button").forEach(b => b.setAttribute("aria-checked", b.dataset.v === String(choice) ? "true" : "false"));
    paintCaption(choice);
  };
  fill(swatches, h("button", { type: "button", class: "swatch month", "data-v": "month", role: "radio", title: L("По месяцу"), "aria-label": L("По месяцу"),
      style: `--c: ${ACCENTS[accentIndex("month")][0]}`, onclick: () => pick("month") }),
    ...ACCENTS.map(([hex], i) => h("button", { type: "button", class: "swatch", "data-v": String(i), role: "radio", title: nameOf(i), "aria-label": nameOf(i),
      style: `--c: ${hex}`, onclick: () => pick(String(i)) })));
  pick(accent);
  const wave = h("input", { type: "checkbox", checked: pref("psptool.wave", "on") !== "off" });
  wave.onchange = () => {
    try { localStorage.setItem("psptool.wave", wave.checked ? "on" : "off"); } catch (e) {}
    document.documentElement.classList.toggle("still", !wave.checked);
  };
  const llmSlot = h("div"), emuSlot = h("div"), ocrSlot = h("div"), compSlot = h("div"), remoteSlot = h("div");
  fill(v, titlebar(L("Настройки"), L("для всего приложения, не для одного проекта")),
    section(L("Внешний вид"), form([[L("Тема"), themeSeg],
      [L("Цвет"), h("div", { style: "width:100%" }, swatches, caption)],
      [L("Волна"), h("label", { class: "switch" }, wave, L("Плавная волна на фоне, как в меню PSP"))],
      [L("Язык"), langSel]])),
    llmSlot, emuSlot, ocrSlot, compSlot, remoteSlot);
  renderLlmConnection(llmSlot); renderEmulator(emuSlot); renderOcr(ocrSlot); renderComponents(compSlot);
  if (!state.project?.client_remote) renderRemote(remoteSlot);
}

// the language model: provider, key, model (stored for the app, ~/.config/psptool)
async function renderLlmConnection(slot) {
  const s = await api("llm/settings");
  const prov = h("select", {}, h("option", { value: "anthropic" }, "Anthropic"), h("option", { value: "openai" }, L("OpenAI-совместимый")));
  prov.value = s.provider;
  const a = s.anthropic, o = s.openai;
  const aKey = h("input", { type: "password", value: a.api_key, placeholder: a.has_key ? L("из окружения") : "sk-ant-…", autocomplete: "off" });
  const aModel = h("input", { type: "text", value: a.model });
  const aEffort = h("select", {}, ...[["low", L("низкое")], ["medium", L("среднее")], ["high", L("высокое")], ["xhigh", L("очень высокое")], ["max", L("максимум")]]
    .map(([val, label]) => h("option", { value: val }, label)));
  aEffort.value = a.effort || "medium";
  const oUrl = h("input", { type: "text", value: o.base_url, list: "llm-urls" });
  const urls = h("datalist", { id: "llm-urls" }, ...["https://api.openai.com/v1", "https://openrouter.ai/api/v1", "http://localhost:11434/v1", "http://localhost:1234/v1"].map(u => h("option", { value: u })));
  const oKey = h("input", { type: "password", value: o.api_key, placeholder: L("не нужен для локальных"), autocomplete: "off" });
  const oModel = h("input", { type: "text", value: o.model });
  const status = h("span", { class: "status" });
  const aForm = form([[L("Ключ API"), aKey], [L("Модель"), aModel], [L("Усилие"), aEffort]]);
  const oForm = form([[L("Адрес"), oUrl, urls], [L("Ключ API"), oKey], [L("Модель"), oModel]]);
  const sync = () => { aForm.hidden = prov.value !== "anthropic"; oForm.hidden = prov.value !== "openai"; };
  prov.onchange = sync; sync();
  const save = () => api("llm/settings", { method: "PUT", body: { provider: prov.value,
    anthropic: { api_key: aKey.value, model: aModel.value, effort: aEffort.value },
    openai: { api_key: oKey.value, base_url: oUrl.value, model: oModel.value } } });
  let timer = null;
  for (const el of [prov, aKey, aModel, aEffort, oUrl, oKey, oModel]) el.addEventListener("change", () => {
    clearTimeout(timer); status.className = "status";
    timer = setTimeout(async () => { await save(); status.textContent = L("Сохранено"); }, 300);
  });
  fill(slot, section(L("Языковая модель"), form([[L("Провайдер"), prov]]), aForm, oForm,
    h("div", { class: "actions" }, status,
      h("button", { class: "btn", onclick: async () => {
        await save(); status.textContent = L("Проверка…"); status.className = "status";
        const r = await api("llm/test", { body: {} });
        status.textContent = r.ok ? L("Подключено") : r.reply; status.className = "status" + (r.ok ? "" : " err");
      } }, L("Проверить")))));
}

// PPSSPP: where the emulator is (for "Проверить в игре")
async function renderEmulator(slot) {
  const r = await api("emulator");
  const emu = h("input", { type: "text", value: r.emulator, placeholder: "/Applications/PPSSPPSDL.app/Contents/MacOS/PPSSPPSDL" });
  emu.addEventListener("change", () => api("emulator", { method: "PUT", body: { emulator: emu.value } }));
  fill(slot, section(L("Эмулятор"), form([[
    "PPSSPP", h("div", { style: "width:100%" }, pathField(emu, "open", L("Эмулятор PPSSPP (.app)")),
      r.emulator ? null : h("div", { class: "muted small" }, L("не найден: ppsspp.org")))]])));
}

// what the app uses besides itself: the upscalers (downloadable), ffmpeg, OCR
async function renderComponents(slot) {
  const c = await api("components");
  const panel = jobPanel();
  const ok = (name, path, hint) => [name, path ? h("span", { class: "muted small", style: "overflow-wrap:anywhere" }, "✓ " + path)
    : h("span", { class: "muted" }, hint)];
  fill(slot, section(L("Компоненты"), form([
    ...c.tools.map(tool => [tool.name, tool.ok ? h("span", { class: "muted small" }, L("✓ установлен"))
      : h("button", { class: "btn", "data-job": true, onclick: async () => {
          openJobPanel(panel, L("Загрузка {0}", tool.name)); await runJob("hdtool", { tool: tool.id }); waitJob(() => renderComponents(slot));
        } }, icon("download"), L("Скачать"))]),
    ok("ffmpeg", c.ffmpeg, L("не найден: установите ffmpeg")),
    ok("Tesseract", c.tesseract, L("не найден: необязательно на macOS")),
  ]), panel));
}

// ---- textures -------------------------------------------------------------

async function loadTextures(page = 0) {
  if (typeof page !== "number") page = 0;
  state.txPage = page;
  const { f, sort, dir } = txView.st, q = $("#tx-find").value.trim();
  const res = await api("textures?" + new URLSearchParams({ filter: f.show || "ref", q, sort, dir, offset: page * PAGE, limit: PAGE }));
  if (res.counts) txView.setOptions(txGroups(res.counts));
  if (!res.indexed) {
    $("#tx-status").textContent = "";
    fill($("#tx-grid"), h("div", { class: "muted" }, L("Каталог ещё не собран: нажми «Обновить каталог».")));
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
      t.edited ? h("span", { class: "badge ok" }, "RU") : t.ref ? h("span", { class: "badge" }, L("текст")) : null));
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
      h("a", { class: "dl glass-clear", href: file, download: name, title: L("Скачать PNG"), onclick: e => e.stopPropagation() }, icon("download")))
      : h("div", { class: "pic empty" }, L("нет")));
  const scale = t.w <= 128 && t.h <= 128 ? 3 : 2;
  const file = h("input", { type: "file", accept: "image/png", hidden: true, onchange: async () => {
    if (file.files[0]) texEditor(t, file.files[0]);
  } });
  const close = () => { m.hidden = true; };
  fill(m, h("div", { class: "box", onclick: e => e.stopPropagation() },
    h("h2", {}, `${t.id}`, h("span", { class: "muted small" }, `${t.w}×${t.h}`), h("span", { class: "sp" }),
      h("button", { class: "btn", onclick: () => texAuto(t) }, icon("spark"), L("Автоперевод")),
      h("button", { class: "btn primary", onclick: () => file.click() }, L("Загрузить PNG")), file,
      t.edited ? h("button", { class: "btn", onclick: () => texEditor(t, `/api/texture/${t.id}.png?which=edit&v=${Date.now()}`) }, L("Редактировать")) : null,
      t.edited ? h("button", { class: "btn", onclick: async () => { await api(`texture/${t.id}`, { method: "DELETE" }); t.edited = false; texDetail(t); loadTextures(state.txPage); } }, L("Сбросить")) : null,
      h("button", { class: "icon-btn", title: L("Закрыть"), onclick: close }, icon("close"))),
    h("div", { class: "cmp" },
      fig(L("Оригинал"), `/api/texture/${t.id}.png?scale=${scale}`, `/api/texture/${t.id}.png`, t.id + ".png"),
      fig(L("Подсказка"), state.project.meta.ref_iso ? `/api/texture/${t.id}.png?which=ref&scale=${scale}` : null,
        `/api/texture/${t.id}.png?which=ref`, t.id + "_ref.png"),
      fig(L("Перевод"), t.edited ? `/api/texture/${t.id}.png?which=edit&v=${Date.now()}` : null,
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
  const note = h("input", { type: "text", value: layout.note || "", placeholder: L("Уточнение: например, коротко, заглавными") });
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
    const dst = h("input", { type: "text", value: b.dst || "", placeholder: L("Перевод") });
    dst.oninput = () => { b.dst = dst.value; redraw(); };
    const fillc = h("input", { type: "color", value: b.fill || "#ffffff", title: L("Буквы") });
    fillc.oninput = () => { b.fill = fillc.value; redraw(); };
    const out = h("input", { type: "color", value: b.outline || "#000000", title: L("Обводка") });
    out.oninput = () => { b.outline = out.value; redraw(); };
    const ow = h("input", { type: "number", value: b.outline ? b.ow : 0, min: 0, max: 4, step: 0.5, title: L("Обводка, px"), style: "width:56px" });
    ow.oninput = () => { const v = +ow.value; if (v) { b.ow = v; b.outline = out.value; } else b.outline = null; redraw(); };
    const size = h("input", { type: "number", value: b.size || "", min: 4, max: 64, step: 0.5, placeholder: L("авто"), title: L("Размер, px"), style: "width:64px" });
    size.oninput = () => { b.size = +size.value || null; redraw(); };
    const swap = h("button", { class: "icon-btn", title: L("Поменять цвета местами"), onclick: () => {
      const f = fillc.value; fillc.value = out.value; out.value = f; b.fill = fillc.value; if (b.outline) b.outline = out.value; redraw();
    } }, "⇄");
    const again = iconBtn("spark", L("Перевести заново"), async ev => {
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
    msg.textContent = L("Ищу текст и перевожу…");
    const r = await api(`texture/${t.id}/auto`, { body: { note: note.value, font: font.value } }).catch(e => ({ error: e.message }));
    if (r.boxes) layout = r;
    msg.textContent = r.error || (layout.boxes.length ? "" : L("Текст не найден"));
    rows(); overlays(); redraw();
  };
  font.onchange = redraw;
  note.onchange = () => { layout.note = note.value; };
  fill(m, h("div", { class: "box wide", onclick: e => e.stopPropagation() },
    h("h2", {}, L("Автоперевод"), h("span", { class: "muted small" }, t.id), h("span", { class: "sp" }),
      h("button", { class: "btn", onclick: () => texDetail(t) }, L("Назад")),
      h("button", { class: "icon-btn", title: L("Закрыть"), onclick: () => { m.hidden = true; } }, icon("close"))),
    h("div", { class: "auto" },
      h("div", {}, stage),
      h("div", { class: "aside" },
        h("div", { class: "row" }, note, font, h("button", { class: "btn", onclick: find }, icon("spark"), layout.boxes.length ? L("Заново") : L("Найти и перевести"))),
        list,
        h("div", { class: "actions" }, msg,
          h("button", { class: "btn primary", onclick: async () => {
            layout.note = note.value; layout.font = font.value;
            await fetch(`/api/texture/${t.id}/render.png`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ layout, save: true }) });
            t.edited = true; loadTextures(state.txPage); texDetail(t);
          } }, L("Сохранить")))))));
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
  const undoBtn = iconBtn("undo", L("Отменить (Ctrl+Z)"), () => doUndo());
  undoBtn.disabled = true;
  const targetSeg = h("div", { class: "seg" }, h("button", { "data-v": "pic", class: "on" }, L("Картинка")), h("button", { "data-v": "under" }, L("Подложка")));
  const toolSeg = h("div", { class: "seg" }, h("button", { "data-v": "move", class: "on" }, L("Двигать")), h("button", { "data-v": "erase" }, L("Ластик")));
  const underSeg = h("div", { class: "seg" }, h("button", { "data-v": "jp", class: "on" }, L("Оригинал")),
    hasRef ? h("button", { "data-v": "ref" }, L("Подсказка")) : null);

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
      h("button", { class: "btn", onclick: () => texDetail(t) }, L("Отмена")),
      h("button", { class: "btn primary", onclick: apply }, L("Применить")),
      h("button", { class: "icon-btn", title: L("Закрыть"), onclick: close }, icon("close"))),
    h("div", { class: "editor" },
      h("div", { class: "stage" }, cv),
      h("div", { class: "form" },
        h("label", {}, L("Инструмент")), h("div", { class: "f" }, toolSeg),
        h("label", {}, L("Ластик")), h("div", { class: "f" }, brush, brushNum),
        h("label", {}, L("Стирать")), h("div", { class: "f" }, targetSeg),
        h("label", {}, L("Масштаб")), h("div", { class: "f" }, scale, scaleNum),
        h("label", {}, ""), h("div", { class: "f" },
          h("button", { class: "btn", onclick: () => fit(false) }, L("Вписать")),
          h("button", { class: "btn", onclick: () => fit(true) }, L("Заполнить")),
          h("button", { class: "btn", onclick: () => { st.s = 1; redraw(); } }, "1:1")),
        h("label", {}, L("Позиция")), h("div", { class: "f" }, pos),
        h("label", {}, L("Подложка")), h("div", { class: "f" }, underSeg),
        h("label", {}, L("Прозрачность")), h("div", { class: "f" }, under),
        h("label", {}, ""), h("div", { class: "f" }, h("label", { class: "switch" }, keep, L("оставить под картинкой"))),
        h("label", {}, L("Сглаживание")), h("div", { class: "f" }, h("label", { class: "switch" }, smooth, L("при масштабе")))))));
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
  const { f: fl, sort, dir } = cmView.st, f = $("#cm-find").value.trim();
  const show = { unsure: g => g.unsure || g.dup, icons: g => isIcon(g), all: () => true };
  const found = charmap.filter(g => !f || g.ch === f || g.code.toString(16) === f.toLowerCase().replace(/^0x/, ""));
  cmView.setOptions(cmGroups(Object.fromEntries(Object.entries(show).map(([k, fn]) => [k, found.filter(fn).length]))));
  const list = found.filter(show[fl.show] || show.unsure)
    .sort(sort === "char" ? byKey(g => g.ch || "\uffff", dir) : byKey(g => g.code, dir));
  $("#cm-status").textContent = L("{0} из {1}", list.length, charmap.length);
  const go = n => { renderCharmap(n); window.scrollTo(0, 0); };
  fill($("#cm-pager"), ...[pager(list.length, page, go)].filter(Boolean));
  fill($("#glyphs"), ...list.slice(page * PAGE, (page + 1) * PAGE).map(g => {
    const card = h("div", { class: "glyph" + (g.unsure || g.dup ? " unsure" : ""),
      title: g.dup ? L("Этот же символ у ") + g.dup.map(c => c.toString(16).padStart(4, "0")).join(", ") : "" });
    const draw = () => {
      const isIcon = !g.ch && !g.editing;
      const inp = h("input", { value: g.ch, maxlength: 2 });
      inp.addEventListener("change", async () => { g.editing = false; await setChar(g, inp.value); card.classList.remove("unsure"); inp.classList.add("saved"); });
      const keep = iconBtn("icon", isIcon ? L("Значок, остаётся как есть. Нажми, чтобы задать символ") : L("Значок: оставить как есть"), async () => {
        if (isIcon) { g.editing = true; draw(); card.querySelector("input").focus(); return; }
        g.editing = false; await setChar(g, ""); card.classList.remove("unsure"); draw();
      });
      if (isIcon) keep.classList.add("on");
      fill(card, 
        h("img", { src: `/api/glyph/${g.code.toString(16)}.png`, loading: "lazy", alt: g.ch }),
        h("div", { class: "code" }, g.code.toString(16).padStart(4, "0"), g.dup ? h("span", { class: "dupmark" }, " = " + g.dup.map(c => c.toString(16)).join(",")) : null),
        h("div", { class: "edit" }, isIcon ? h("span", { class: "isicon" }, L("значок")) : inp, keep));
    };
    draw();
    return card;
  }));
}

// ---- motion ---------------------------------------------------------------

// segmented controls: one glass thumb that slides to the chosen segment
// (works for every .seg, also the ones built later)
function syncSeg(sg) {
  let t = sg.querySelector(":scope > .thumb");
  if (!t) { t = document.createElement("i"); t.className = "thumb"; sg.prepend(t); }
  const on = sg.querySelector(":scope > button.on");
  if (!on || !on.offsetWidth) { t.style.opacity = 0; return; }
  const first = !t.style.width;
  if (first) t.style.transition = "none";  // appear in place, slide afterwards
  t.style.opacity = 1;
  t.style.width = on.offsetWidth + "px";
  t.style.transform = `translateX(${on.offsetLeft - 2}px)`;
  if (first) requestAnimationFrame(() => { t.style.transition = ""; });
}
const syncSegs = () => document.querySelectorAll(".seg").forEach(syncSeg);
new MutationObserver(ms => {
  const segs = new Set();
  for (const m of ms) {
    if (m.type === "attributes") { const sg = m.target.closest?.(".seg"); if (sg) segs.add(sg); continue; }
    for (const n of m.addedNodes) if (n.nodeType === 1) {
      if (n.matches(".seg")) segs.add(n);
      n.querySelectorAll(".seg").forEach(x => segs.add(x));
    }
  }
  if (segs.size) requestAnimationFrame(() => segs.forEach(syncSeg));
}).observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ["class"] });
window.addEventListener("resize", () => requestAnimationFrame(syncSegs));

// a critically damped spring (Apple's damping 1.0, response in seconds),
// started from the current value with the gesture's velocity
function spring(from, to, velocity, onFrame, onDone, response = 0.35, damping = 1) {
  const w = 2 * Math.PI / response;
  let x = from, v = velocity, last = performance.now();
  const step = now => {
    const dt = Math.min(0.032, (now - last) / 1000); last = now;
    const a = -w * w * (x - to) - 2 * damping * w * v;
    v += a * dt; x += v * dt;
    if (Math.abs(x - to) < 0.5 && Math.abs(v) < 20) { onFrame(to); onDone?.(); return; }
    onFrame(x); requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}
// where a flick would come to rest (Apple's projection, scroll-like decay)
const project = (v, rate = 0.998) => (v / 1000) * rate / (1 - rate);

// sheets on the phone: drag the top of a sheet down to close it; it follows
// the finger 1:1, resists going up, and the release velocity decides
document.addEventListener("pointerdown", e => {
  if (!phone.matches) return;
  const box = e.target.closest(".modal > .box");
  if (!box || e.target.closest("button, input, select, textarea, a, label, canvas, .slider, .abox")) return;
  if (!e.target.closest(".box > h2")) return;   // the title bar is the grabber (no scrolling there)
  const modal = box.parentElement, start = e.clientY, hist = [[e.timeStamp, 0]];
  let dy = 0;
  try { box.setPointerCapture(e.pointerId); } catch (err) {}
  box.style.animation = "none";
  const move = ev => {
    const raw = ev.clientY - start;
    dy = raw > 0 ? raw : -12 * (1 - Math.exp(raw / 60));  // rubber band upwards
    box.style.transform = `translateY(${dy}px)`;
    modal.style.backgroundColor = `rgba(0,0,0,${0.5 * Math.max(0, 1 - dy / box.offsetHeight)})`;
    hist.push([ev.timeStamp, dy]); if (hist.length > 6) hist.shift();
  };
  const up = () => {
    box.removeEventListener("pointermove", move); box.removeEventListener("pointerup", up); box.removeEventListener("pointercancel", up);
    const [t0, y0] = hist[0], [t1, y1] = hist[hist.length - 1];
    const v = t1 > t0 ? (y1 - y0) / (t1 - t0) * 1000 : 0;   // px/s
    const h = box.offsetHeight;
    const set = y => { box.style.transform = `translateY(${y}px)`; modal.style.backgroundColor = `rgba(0,0,0,${0.5 * Math.max(0, 1 - y / h)})`; };
    const reset = () => { box.style.transform = ""; box.style.animation = ""; modal.style.backgroundColor = ""; };
    if (dy + project(v) > h * 0.35 && v > -200) {
      spring(dy, h + 20, Math.max(v, 600), set, () => { modal.click(); reset(); }, 0.3);
    } else {
      spring(dy, 0, v, set, reset, 0.35);
    }
  };
  box.addEventListener("pointermove", move);
  box.addEventListener("pointerup", up);
  box.addEventListener("pointercancel", up);
});

// ---- Liquid Glass -----------------------------------------------------------

const GLASS = "#sidebar, #tabbar, .modal > .box, .mpick-pop";  // big panels; small controls keep plain blur
const noGlass = matchMedia("(prefers-reduced-transparency: reduce)");
// refraction needs SVG filters in backdrop-filter: Chromium has them, Safari not
const canBend = /Chrome\//.test(navigator.userAgent) && CSS.supports("backdrop-filter", "blur(1px)");
const glassDefs = (() => {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("aria-hidden", "true");
  svg.style.cssText = "position:absolute;width:0;height:0;overflow:hidden";
  document.body.append(svg);
  return svg;
})();
let glassN = 0;

// a displacement map for a w x h panel with corner radius r: inside a bezel
// along the edge the backdrop is pulled inwards (R = x, G = y, 128 = none),
// growing towards the rim, so the edge magnifies and bends like thick glass
function lensMap(w, h, r, bezel) {
  const k = 0.5, W = Math.max(2, Math.round(w * k)), H = Math.max(2, Math.round(h * k));
  const c = document.createElement("canvas"); c.width = W; c.height = H;
  const ctx = c.getContext("2d"), img = ctx.createImageData(W, H), d = img.data;
  const rr = Math.min(r, w / 2, h / 2);
  for (let j = 0; j < H; j++) for (let i = 0; i < W; i++) {
    const x = (i + 0.5) / k, y = (j + 0.5) / k;
    // distance to the rounded-rect edge and the direction to the centre
    const qx = Math.max(rr - x, 0, x - (w - rr)), qy = Math.max(rr - y, 0, y - (h - rr));
    let dist, nx, ny;
    if (qx > 0 && qy > 0) {
      const l = Math.hypot(qx, qy); dist = rr - l; nx = (x < w / 2 ? 1 : -1) * qx / l; ny = (y < h / 2 ? 1 : -1) * qy / l;
    } else {
      const dx = Math.min(x, w - x), dy = Math.min(y, h - y);
      if (dx < dy) { dist = dx; nx = x < w / 2 ? 1 : -1; ny = 0; } else { dist = dy; nx = 0; ny = y < h / 2 ? 1 : -1; }
    }
    const t = Math.max(0, 1 - dist / bezel), m = t * t * (3 - 2 * t);   // smooth, strongest at the rim
    const o = (j * W + i) * 4;
    d[o] = 128 + nx * m * 127; d[o + 1] = 128 + ny * m * 127; d[o + 2] = 128; d[o + 3] = 255;
  }
  ctx.putImageData(img, 0, 0);
  return c.toDataURL();
}

function bend(el) {
  if (!canBend || noGlass.matches) { el.style.removeProperty("backdrop-filter"); return; }
  const w = Math.round(el.offsetWidth), h = Math.round(el.offsetHeight);
  if (w < 20 || h < 20) return;
  const key = w + "x" + h;
  if (el.dataset.lens === key) return;
  el.dataset.lens = key;
  const id = el.dataset.lensId || (el.dataset.lensId = "lg" + (++glassN));
  const r = parseFloat(getComputedStyle(el).borderTopLeftRadius) || 0;
  const bezel = Math.min(26, Math.max(10, Math.min(w, h) * 0.18));
  let f = glassDefs.querySelector("#" + id);
  if (!f) { f = document.createElementNS("http://www.w3.org/2000/svg", "filter"); f.id = id; glassDefs.append(f); }
  f.setAttribute("x", 0); f.setAttribute("y", 0); f.setAttribute("width", w); f.setAttribute("height", h);
  f.setAttribute("filterUnits", "userSpaceOnUse"); f.setAttribute("primitiveUnits", "userSpaceOnUse");
  f.setAttribute("color-interpolation-filters", "sRGB");
  f.innerHTML = `<feImage href="${lensMap(w, h, r, bezel)}" x="0" y="0" width="${w}" height="${h}" preserveAspectRatio="none" result="map"/>
    <feDisplacementMap in="SourceGraphic" in2="map" scale="${Math.round(bezel * 1.6)}" xChannelSelector="R" yChannelSelector="G"/>`;
  // the lens, then the panel's own blur and colour (--glass-blur)
  const own = getComputedStyle(el).getPropertyValue("--glass-blur").trim() || "blur(16px) saturate(185%) brightness(1.04)";
  el.style.backdropFilter = `url(#${id}) ${own}`;
}
const glassSize = new ResizeObserver(es => es.forEach(e => {
  clearTimeout(e.target._bendT);
  e.target._bendT = setTimeout(() => bend(e.target), 140);
}));
const watchGlass = root => {
  const els = root.matches?.(GLASS) ? [root] : [];
  root.querySelectorAll?.(GLASS).forEach(x => els.push(x));
  els.forEach(el => { if (!el.dataset.glass) { el.dataset.glass = 1; glassSize.observe(el); } });
};
new MutationObserver(ms => ms.forEach(m => m.addedNodes.forEach(n => n.nodeType === 1 && watchGlass(n))))
  .observe(document.body, { childList: true, subtree: true });
noGlass.addEventListener("change", () => document.querySelectorAll(GLASS).forEach(el => { delete el.dataset.lens; bend(el); }));

// the tab bar's lens: it sits under the chosen tab, flows to the next one
// with a stretch, can be held and dragged across the tabs (iOS 26)
let lensX = null;
function placeLens(animate = true) {
  const bar = $("#tabbar"), on = bar.querySelector("button.on");
  let lens = bar.querySelector(":scope > .lens");
  if (!lens) { lens = h("i", { class: "lens" }); bar.prepend(lens); }
  if (!on || !on.offsetWidth) { lens.style.opacity = 0; return; }
  lens.style.opacity = 1;
  const x = on.offsetLeft, w = on.offsetWidth;
  lens.style.width = w + "px";
  const from = lensX ?? x;
  lensX = x;
  if (!animate || from === x || matchMedia("(prefers-reduced-motion: reduce)").matches) { lens.style.translate = x + "px 0"; return; }
  // a liquid move: it stretches on the way and settles with a spring
  lens.animate([{ translate: from + "px 0", scale: "1 1" }, { translate: (from + x) / 2 + "px 0", scale: "1.25 0.92", offset: 0.4 },
                { translate: x + "px 0", scale: "1 1" }], { duration: 480, easing: "cubic-bezier(.2,.9,.25,1)" });
  lens.style.translate = x + "px 0";
}
(() => {
  const bar = $("#tabbar");
  let held = null;
  bar.addEventListener("pointerdown", e => {
    const b = e.target.closest("button"), lens = bar.querySelector(":scope > .lens");
    if (!b || !lens) return;
    held = { start: e.clientX, moved: false, x0: lensX ?? b.offsetLeft, w: lens.offsetWidth, id: e.pointerId };
    lens.classList.add("held");
  });
  bar.addEventListener("pointermove", e => {
    if (!held) return;
    const dx = e.clientX - held.start;
    if (!held.moved && Math.abs(dx) > 6) {   // a drag, not a tap: keep the finger's events from here on
      held.moved = true;
      try { bar.setPointerCapture(held.id); } catch (err) {}
    }
    if (!held.moved) return;
    const max = bar.clientWidth - held.w - 5, x = Math.max(5, Math.min(max, held.x0 + dx));
    const lens = bar.querySelector(":scope > .lens");
    lens.getAnimations().forEach(a => a.cancel());
    lens.style.translate = x + "px 0"; lensX = x;
  });
  const drop = e => {
    if (!held) return;
    const lens = bar.querySelector(":scope > .lens");
    lens.classList.remove("held");
    if (held.moved) {   // the tab under the lens' centre wins
      e.preventDefault();
      const c = (lensX ?? 0) + held.w / 2;
      const target = [...bar.querySelectorAll("button")].reduce((a, b) =>
        Math.abs(b.offsetLeft + b.offsetWidth / 2 - c) < Math.abs(a.offsetLeft + a.offsetWidth / 2 - c) ? b : a);
      held = null;
      target.click();
      requestAnimationFrame(() => placeLens(true));
      return;
    }
    held = null;
  };
  bar.addEventListener("pointerup", drop);
  bar.addEventListener("pointercancel", drop);
})();

// the bar changes size (minimised, rotated): the lens follows without a move
new ResizeObserver(() => placeLens(false)).observe($("#tabbar"));

// scrolling down tucks the tab bar away a little, scrolling up brings it back
let lastY = 0;
window.addEventListener("scroll", () => {
  if (!phone.matches) return;
  const y = window.scrollY, bar = $("#tabbar");
  if (y > 80 && y - lastY > 6) bar.classList.add("mini");
  else if (lastY - y > 6 || y < 40) bar.classList.remove("mini");
  lastY = y;
}, { passive: true });

// the sidebar folds to its icons and back (remembered); ⌃⌘S as on macOS
function setRail(on, animate = true) {
  const main = document.querySelector("main"), side = $("#sidebar");
  const from = main.getBoundingClientRect().left;
  // the panel's lens map is rebuilt once it has its new width; meanwhile plain blur
  if (animate) { side.style.backdropFilter = getComputedStyle(side).getPropertyValue("--glass-blur").trim(); delete side.dataset.lens; }
  document.body.classList.toggle("rail", on);
  // the page takes its new width at once (one layout) and slides into it
  // on the compositor: FLIP instead of animating a width on every frame
  const dx = from - main.getBoundingClientRect().left;
  if (animate && dx && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
    main.animate([{ transform: `translateX(${dx}px)` }, { transform: "none" }], { duration: 450, easing: "cubic-bezier(.2,.9,.25,1)" });
  }
  const t = $("#side-toggle"), label = on ? L("Развернуть панель") : L("Свернуть панель");
  t.title = label + " (⌃⌘S)";
  t.setAttribute("aria-label", label);
  t.lastChild.textContent = label;
  try { localStorage.setItem("psptool.rail", on ? "1" : ""); } catch (e) {}
}
document.addEventListener("keydown", e => {
  if (e.ctrlKey && e.metaKey && e.key.toLowerCase() === "s") { e.preventDefault(); setRail(!document.body.classList.contains("rail")); }
});

// once the page scrolls under the top bar it turns to glass and shows the
// title (iOS: clear over the large title); sheets do the same for their title
const onScroll = () => {
  // the large title on screen (a hidden one, e.g. the file's while the list shows, has no box)
  const h1 = [...document.querySelectorAll(".view:not([hidden]) .titlebar h1")].find(e => e.offsetParent);
  const under = h1 ? h1.getBoundingClientRect().bottom < (phone.matches ? 60 : 10) : window.scrollY > 36;
  document.body.classList.toggle("scrolled", under);
  document.body.classList.toggle("moved", window.scrollY > 2);
};
window.addEventListener("scroll", () => requestAnimationFrame(onScroll), { passive: true });
document.addEventListener("scroll", e => {
  const box = e.target.closest?.(".modal > .box");
  if (box) box.classList.toggle("scrolled", box.scrollTop > 4);
}, { capture: true, passive: true });

// ---- boot -----------------------------------------------------------------

// the lines of a file (and the search over all files): independent
// conditions that combine, where to search, and the order
const rowOk = (r, f) => (!f.tr || (f.tr === "empty" ? !r.dst : !!r.dst))
  && (!f.src || (f.src === "mt" ? r.dst && r.mt : r.dst && !r.mt))
  && (!f.chk || (f.chk === "yes" ? r.dst && r.checked : r.dst && !r.checked));
const rowView = viewControls({ key: "rows", sorts: [["order", L("По порядку"), "asc"], ["len", L("Длина оригинала"), "desc"],
    ["src", L("Оригинал, А–Я"), "asc"], ["dst", L("Перевод, А–Я"), "asc"]],
  groups: [
    { id: "tr", label: L("Перевод"), options: [["", L("Все строки")], ["empty", L("Без перевода")], ["done", L("С переводом")]] },
    { id: "src", label: L("Кто перевёл"), options: [["", L("Все")], ["mt", "LLM"], ["manual", L("Вручную")]] },
    { id: "chk", label: L("Проверка"), options: [["", L("Все")], ["no", L("Не проверены")], ["yes", L("Проверенные")]] },
    { id: "in", label: L("Искать в"), token: L("Искать в"), def: "any", options: [["any", L("Везде")], ["src", L("Оригинале")], ["ref", L("Подсказке")], ["dst", L("Переводе")]] },
  ] }, () => $("#search").value ? doSearch() : state.entry != null && openEntry(state.entry));
function sortRows(rows) {
  const { sort, dir } = rowView.st;
  if (sort === "order" && dir === "asc") return rows;
  const keys = { order: (r, i) => i, len: r => (r.src || "").length, src: r => r.src || "", dst: r => r.dst || "\uffff" };
  const idx = new Map(rows.map((r, i) => [r, i]));
  const k = keys[sort] || keys.order;
  return [...rows].sort((a, b) => byKey(r => k(r, idx.get(r)), dir)(a, b) || idx.get(a) - idx.get(b));
}
fill($("#row-tools"), ...rowView.buttons);
fill($("#row-tokens"), rowView.chips);
// the file list: sort and filter (two independent conditions)
const fileGroups = (tr = {}, chk = {}) => [
  { id: "tr", label: L("Перевод"), token: L("Перевод"), options: [["", L("Все")], ["none", L("Не начатые"), tr.none], ["part", L("В работе"), tr.part], ["full", L("Переведённые"), tr.full]] },
  { id: "chk", label: L("Проверка"), token: L("Проверка"), options: [["", L("Все")], ["no", L("Не проверены"), chk.no], ["yes", L("Проверенные"), chk.yes]] }];
const fileView = viewControls({ key: "files", groups: fileGroups(), sorts: [["num", L("Номер файла"), "asc"], ["progress", L("Переведено, %"), "desc"],
  ["checked", L("Проверено, %"), "desc"], ["left", L("Осталось перевести"), "desc"], ["total", L("Строк в файле"), "desc"]] }, () => renderEntries());
fill($("#entry-tools"), ...fileView.buttons);
fill($("#entry-tokens"), fileView.chips);
const cmGroups = (n = {}) => [{ id: "show", label: L("Показать"), def: "unsure", options: [["unsure", L("Сомнительные"), n.unsure],
  ["icons", L("Значки"), n.icons], ["all", L("Все символы"), n.all]] }];
const cmView = viewControls({ key: "charmap", groups: cmGroups(), sorts: [["code", L("Код"), "asc"], ["char", L("Символ"), "asc"]] }, () => renderCharmap());
fill($("#cm-tools"), ...cmView.buttons);
fill($("#cm-tokens"), cmView.chips);
// textures: what to show (with the counts the server gives) and the order
const txGroups = (n = {}) => [{ id: "show", label: L("Показать"), def: "ref", options: [["ref", L("С текстом"), n.ref], ["todo", L("Ещё не переведённые"), n.todo],
  ["edited", L("Переведённые"), n.edited], ["all", L("Все текстуры"), n.all]] }];
const txView = viewControls({ key: "textures", groups: txGroups(), sorts: [["num", L("Номер файла"), "asc"], ["size", L("Размер"), "desc"]] }, () => loadTextures());
fill($("#tx-tools"), ...txView.buttons);
fill($("#tx-tokens"), txView.chips);
$("#tx-find").addEventListener("input", () => { clearTimeout(searchTimer); searchTimer = setTimeout(loadTextures, 300); });
$("#tx-index").addEventListener("click", async () => { await runJob("textures"); waitJob(loadTextures); });
document.addEventListener("keydown", e => { if (e.key === "Escape") $("#tx-detail").hidden = true; });
translatePage();
drawIcons();
placeChrome();
$("#side-settings").addEventListener("click", () => show("settings"));
// ⌘, opens Settings (macOS); "Как в системе" follows the system's switch
document.addEventListener("keydown", e => { if ((e.metaKey || e.ctrlKey) && e.key === ",") { e.preventDefault(); show("settings"); } });
matchMedia("(prefers-color-scheme: light)").addEventListener("change", () => applyTheme(pref("psptool.theme", "system")));
watchGlass(document.body);
$("#side-toggle").addEventListener("click", () => setRail(!document.body.classList.contains("rail")));
try { setRail(localStorage.getItem("psptool.rail") === "1", false); } catch (e) { setRail(false, false); }
onScroll();
phone.addEventListener("change", () => requestAnimationFrame(() => placeLens(false)));
$("#texts-back").addEventListener("click", () => showFile(false));
$("#top-back").addEventListener("click", () => state.back?.());
$("#play").addEventListener("click", () => runJob("playtest"));
$("#jobbar").addEventListener("click", showJobLog);
$("#entry-filter").addEventListener("input", renderEntries);
$("#search").addEventListener("input", doSearch);
$("#cm-find").addEventListener("input", renderCharmap);
window.addEventListener("beforeunload", () => { if (pending.size) flush(); });

(async () => {
  state.project = await api("project");
  let tab = "project";
  try { tab = localStorage.getItem("psptool.tab") || "project"; } catch (e) {}
  const feats = state.project.plugin?.features || [];
  const t = TABS.find(x => x.id === tab);
  if (!t || (!state.project.open && tab !== "settings") || (t.feature && !feats.includes(t.feature))) tab = "project";
  show(tab);
  pollJob();
})();
