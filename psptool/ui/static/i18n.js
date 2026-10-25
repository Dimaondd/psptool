// Interface language and theme, settled before the app draws anything.
// Strings are written in Russian (the source language) and looked up in
// i18n/<lang>.js: L("Готово") -> "Done"; L("{0} из {1}", a, b) fills in
// the numbers. A string without a translation stays as it is. (L, not t:
// the app has plenty of local variables called t.)
const LANGS = [
  ["en", "English"], ["ru", "Русский"], ["es", "Español"], ["pt-BR", "Português (Brasil)"],
  ["fr", "Français"], ["de", "Deutsch"], ["zh-Hans", "简体中文"], ["ja", "日本語"],
];
const I18N = { lang: "ru", dict: {} };

function pref(key, fallback) {
  try { return localStorage.getItem(key) || fallback; } catch (e) { return fallback; }
}

// "system": the browser's language when we have it, else English
function pickLang(want) {
  if (want && want !== "system") return want;
  for (const l of navigator.languages || [navigator.language || "en"]) {
    const low = l.toLowerCase();
    if (low.startsWith("zh")) return "zh-Hans";
    if (low.startsWith("pt")) return "pt-BR";
    const hit = LANGS.find(([code]) => code.toLowerCase() === low.split("-")[0]);
    if (hit) return hit[0];
  }
  return "en";
}

function L(s, ...args) {
  const out = (I18N.lang !== "ru" && I18N.dict[s]) || s;
  return args.length ? out.replace(/\{(\d+)\}/g, (m, i) => (args[i] ?? "")) : out;
}

// the static page: elements marked data-i18n (text) and data-i18n-attr="title,placeholder"
function translatePage(root = document) {
  root.querySelectorAll("[data-i18n]").forEach(el => {
    for (const n of el.childNodes) if (n.nodeType === 3 && n.textContent.trim()) n.textContent = n.textContent.replace(n.textContent.trim(), L(n.textContent.trim()));
  });
  root.querySelectorAll("[data-i18n-attr]").forEach(el => {
    for (const a of el.dataset.i18nAttr.split(",")) if (el.getAttribute(a)) el.setAttribute(a, L(el.getAttribute(a)));
  });
}

// the theme: "system" follows prefers-color-scheme (CSS), else forced
function applyTheme(theme) {
  const root = document.documentElement;
  if (theme === "light" || theme === "dark") root.dataset.theme = theme; else delete root.dataset.theme;
  const light = theme === "light" || (theme !== "dark" && matchMedia("(prefers-color-scheme: light)").matches);
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", light ? "#f2f2f7" : "#0b0b0d");
  if (typeof ACCENTS !== "undefined") applyAccent(pref("psptool.accent", "month"));
}

// The accent: the PSP's twelve theme colours, one per month (the XMB
// changed its colour every month unless you picked one). "month" follows
// the calendar like the console did.
const ACCENTS = [
  ["#b9bfca", "Серебро"], ["#e3b23c", "Золото"], ["#9fcd3f", "Лайм"], ["#ef7fb1", "Розовый"],
  ["#3fbb6c", "Зелёный"], ["#a77de2", "Сиреневый"], ["#2fc4c8", "Бирюзовый"], ["#4aa6f2", "Голубой"],
  ["#4c6ff0", "Синий"], ["#8c5ad8", "Фиолетовый"], ["#c48b4a", "Бронзовый"], ["#e4474f", "Красный"],
];
const MONTHS = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"];
const accentIndex = (choice = pref("psptool.accent", "month")) => choice === "month" ? new Date().getMonth() : Math.max(0, Math.min(11, +choice || 0));

// relative luminance of #rrggbb
function luma(hex) {
  const c = [1, 3, 5].map(i => parseInt(hex.substr(i, 2), 16) / 255).map(v => v <= .03928 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4);
  return .2126 * c[0] + .7152 * c[1] + .0722 * c[2];
}

// the accent and what goes with it: the ink on it (dark on light colours,
// white on dark ones) and, in the light theme, a deeper shade for text
function applyAccent(choice) {
  const hex = ACCENTS[accentIndex(choice)][0], root = document.documentElement.style;
  const light = document.documentElement.dataset.theme === "light" ||
    (document.documentElement.dataset.theme !== "dark" && matchMedia("(prefers-color-scheme: light)").matches);
  const l = luma(hex);
  root.setProperty("--accent", light && l > .35 ? `color-mix(in srgb, ${hex} 72%, #000)` : hex);
  root.setProperty("--accent-raw", hex);
  root.setProperty("--accent-ink", l > .32 ? "#14110b" : "#ffffff");
}

I18N.lang = pickLang(pref("psptool.lang", "system"));
document.documentElement.lang = I18N.lang;
applyTheme(pref("psptool.theme", "system"));
applyAccent(pref("psptool.accent", "month"));
document.documentElement.classList.toggle("still", pref("psptool.wave", "on") === "off");
// the dictionary loads before app.js runs (parser-blocking on purpose)
if (I18N.lang !== "ru") document.write(`<script src="i18n/${I18N.lang}.js"><\/script>`);
