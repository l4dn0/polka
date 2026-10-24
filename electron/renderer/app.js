const api = window.polka || null;
const state = { prefs: null, page: "sort", playlist: {}, poll: 0 };

const tabsEl = document.getElementById("tabs");
const viewEl = document.getElementById("view");
const liveEl = document.getElementById("live");

function esc(value) {
  const amp = String.fromCharCode(38);
  const map = {
    "&": `${amp}amp;`,
    "<": `${amp}lt;`,
    ">": `${amp}gt;`,
    '"': `${amp}quot;`,
  };
  return String(value ?? "").replace(/[&<>"]/g, (char) => map[char] || char);
}

async function call(method, path, payload) {
  if (!api) throw new Error("Это окно Electron. В браузере движок не подключён.");
  try {
    return await (method === "GET" ? api.get(path) : api.post(path, payload));
  } catch (error) {
    throw new Error(cleanError(error));
  }
}

function cleanError(error) {
  let text = String((error && error.message) || error || "");
  text = text.replace(/^Error invoking remote method '[^']*':\s*/i, "").replace(/^(Error:\s*)+/i, "");
  if (/WinError 32|занят другим процессом/i.test(text)) {
    return "Файл занят другим процессом (возможно, антивирус проверяет скачанное). Подожди минуту и попробуй ещё раз.";
  }
  return text.length > 300 ? `${text.slice(0, 300)}…` : text || "Неизвестная ошибка.";
}

function applyTheme() {
  document.body.classList.toggle("dark", Boolean(state.prefs && state.prefs.dark));
}

// русские формы: plural(2, "трек", "трека", "треков") → «2 трека»
function plural(n, one, few, many) {
  const a = Math.abs(n) % 100, b = a % 10;
  const word = a > 10 && a < 20 ? many : b === 1 ? one : b >= 2 && b <= 4 ? few : many;
  return `${n} ${word}`;
}

async function loadPaths() {
  try { state.paths = await call("GET", "/api/paths"); } catch (_e) { state.paths = state.paths || { base: "", paths: {} }; }
  if (state.page === "playlists") renderPlaylists();
}

function watches() {
  return (state.prefs && state.prefs.watches) || [];
}

// единый набор штриховых иконок (24×24, stroke), в духе Lucide/Tabler (MIT)
const ICONS = {
  sort: "M4 7.5 12 4l8 3.5-8 3.5z M4 12l8 3.5 8-3.5 M4 16.5 12 20l8-3.5",
  youtube: "M3.5 7.2c0-1.3.9-2.3 2.2-2.4C7.6 4.6 9.8 4.5 12 4.5s4.4.1 6.3.3c1.3.1 2.2 1.1 2.2 2.4v9.6c0 1.3-.9 2.3-2.2 2.4-1.9.2-4.1.3-6.3.3s-4.4-.1-6.3-.3c-1.3-.1-2.2-1.1-2.2-2.4z M10 9v6l5-3z",
  playlists: "M4 6h11 M4 11h11 M4 16h6 M17 17.5V6.5l3.5-1 M14 17.5a1.75 1.75 0 1 0 3.5 0a1.75 1.75 0 1 0-3.5 0",
  gear: "M4 7h9 M17 7h3 M15 5v4 M4 12h3 M11 12h9 M9 10v4 M4 17h11 M19 17h1 M17 15v4",
  folder: "M3.5 7c0-.8.7-1.5 1.5-1.5h4l2 2h8c.8 0 1.5.7 1.5 1.5v8c0 .8-.7 1.5-1.5 1.5H5c-.8 0-1.5-.7-1.5-1.5z",
  search: "M10.5 4.5a6 6 0 1 0 0 12a6 6 0 1 0 0-12z M15 15l4.5 4.5",
  play: "M8 5.5v13l10.5-6.5z",
  pause: "M8.5 5.5v13 M15.5 5.5v13",
  prev: "M17.5 6v12l-8.5-6z M6.5 6v12",
  next: "M6.5 6v12l8.5-6z M17.5 6v12",
  download: "M12 4.5v10 M7.5 10.5 12 15l4.5-4.5 M5 19.5h14",
  refresh: "M19.5 11.5A7.5 7.5 0 0 0 6 7.2L4.5 9 M4.5 4.5V9H9 M4.5 12.5A7.5 7.5 0 0 0 18 16.8l1.5-1.8 M19.5 19.5V15H15",
  remove: "M6.5 6.5l11 11 M17.5 6.5l-11 11",
  open: "M13.5 4.5h6v6 M19.5 4.5 11 13 M17.5 14v4.5c0 .6-.4 1-1 1h-11c-.6 0-1-.4-1-1v-11c0-.6.4-1 1-1H10",
  plus: "M12 5v14 M5 12h14",
};

function ic(name, cls = "") {
  return `<svg class="ic ${cls}" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="${ICONS[name]}"/></svg>`;
}

function navButton(id, label, note) {
  const on = id === state.page ? "active" : "";
  const sub = note ? `<small>${esc(note)}</small>` : "";
  return `<button data-page="${esc(id)}" class="nav ${on}" type="button">${ic(id === "download" ? "youtube" : id)}<span><strong>${esc(label)}</strong>${sub}</span></button>`;
}

function renderTabs() {
  const count = watches().length;
  tabsEl.innerHTML = `
    <p class="nav-label">Каталог</p>
    ${navButton("sort", "Сортировка", "разложить альбомы")}
    ${navButton("download", "YouTube", "поиск и скачивание")}
    ${navButton("playlists", "Плейлисты", count ? `${count} в списке` : "вставь ссылку")}
`;
}

function field(label, id, value, type = "text") {
  return `<label>${esc(label)}<input id="${id}" type="${type}" value="${esc(value || "")}" /></label>`;
}

function render() {
  applyTheme();
  renderTabs();
  if (state.page === "sort") renderSort();
  else if (state.page === "download") renderDownload();
  else if (state.page === "playlists") renderPlaylists();
  else if (state.page === "settings") renderSettings();
  syncTopbar();
  applySearch();
  paintJobs();
  stagger(state.lastPage !== state.page);
  state.lastPage = state.page;
}

// появление списков с лёгкой задержкой; при перерисовке той же страницы — без анимации
function stagger(enter) {
  viewEl.classList.toggle("enter", enter);
  if (!enter) return;
  viewEl.querySelectorAll(".sr, .lst, .pl-block, .card, .track, .conn, .eline").forEach((node, index) => {
    node.style.setProperty("--i", Math.min(index, 14));
  });
}

let flashTimer = 0;
// короткое сообщение в верхней строке: исчезает через ~2.5 с или при любом другом действии
function flash(text, ms = 2500) {
  clearTimeout(flashTimer);
  liveEl.textContent = text || "";
  liveEl.dataset.flash = text ? "1" : "";
  liveEl.classList.remove("toast");
  void liveEl.offsetWidth;
  liveEl.classList.toggle("toast", Boolean(text));
  if (text) flashTimer = setTimeout(clearFlash, ms);
}

function clearFlash() {
  clearTimeout(flashTimer);
  if (liveEl.dataset.flash) {
    liveEl.textContent = "";
    liveEl.dataset.flash = "";
  }
}

document.addEventListener("pointerdown", (event) => {
  if (!event.target.closest("#root-pick, #root-dir")) clearFlash();
}, true);

function paintChromeIcons() {
  const gear = document.getElementById("gear");
  if (gear && !gear.querySelector("svg")) gear.innerHTML = ic("gear");
  const pick = document.getElementById("root-pick");
  if (pick && !pick.querySelector("svg")) pick.innerHTML = `${ic("folder")}Обзор`;
}

function syncTopbar() {
  paintChromeIcons();
  const root = document.getElementById("root-dir");
  if (root && document.activeElement !== root) root.value = (state.prefs && state.prefs.catalog) || "";
  if (root) root.title = root.value ? `Корневая папка: ${root.value}` : "Корневая папка не выбрана";
  const gear = document.getElementById("gear");
  if (gear) gear.classList.toggle("active", state.page === "settings");
}

async function setRoot(value) {
  const catalog = String(value || "").trim();
  if (state.prefs && catalog === (state.prefs.catalog || "")) return;
  try {
    state.prefs = await call("POST", "/api/prefs", { catalog });
    flash(catalog ? "Корневая папка сохранена." : "");
  } catch (error) {
    flash(error.message, 5000);
  }
  render();
}

function matches(node, query) {
  return node.textContent.toLowerCase().includes(query);
}

function applySearch() {
  const query = (state.query || "").trim().toLowerCase();
  viewEl.querySelectorAll(".card").forEach((node) => {
    node.hidden = Boolean(query) && !matches(node, query);
  });
  viewEl.querySelectorAll(".embed-row").forEach((row) => {
    const head = row.querySelector(".embed-copy");
    const headHit = !query || (head && matches(head, query));
    let anyTrack = false;
    row.querySelectorAll(".eline").forEach((line) => {
      const hit = headHit || matches(line, query);
      line.hidden = !hit;
      anyTrack = anyTrack || hit;
    });
    row.hidden = Boolean(query) && !headHit && !anyTrack;
  });
  viewEl.querySelectorAll(".grid > label, .grid > .row, .actions > label.check").forEach((node) => {
    if (state.page === "settings") node.hidden = Boolean(query) && !matches(node, query);
  });
}

function renderSort() {
  const prefs = state.prefs || {};
  viewEl.innerHTML = `
    <section class="panel">
      <h2>Сортировка</h2>
      <p class="hint">Жанр, поджанр, группа, альбом. Новая пластинка группы ложится в уже существующую папку.</p>
      <div class="grid">
        <div class="row">
          ${field("Откуда альбомы", "source", prefs.source)}
          <button class="btn" id="pick-source" type="button">${ic("folder")}Обзор</button>
        </div>
        <p class="hint">Каталог: ${prefs.catalog ? `<strong>${esc(prefs.catalog)}</strong>` : "не выбран"} — корневая папка задаётся сверху.</p>
      </div>
      <div class="actions">
        <label class="check"><input id="move" type="checkbox" ${prefs.move ? "checked" : ""}/> Переносить, иначе копировать</label>
        <label class="check"><input id="unclear" type="checkbox" ${prefs.place_unclear ? "checked" : ""}/> Неясные в Other</label>
      </div>
      <div class="actions">
        <button class="btn accent" id="scan" type="button">Разобрать</button>
        <button class="btn accent" id="apply" type="button">Разложить по папкам</button>
      </div>
      <p id="sort-status">${esc(state.sortStatus || "Выбери папки.")}</p>
      <div class="results" id="sort-results"></div>
    </section>`;
  bindFolder("pick-source", "source");
  document.getElementById("scan").onclick = () => startSort(false);
  document.getElementById("apply").onclick = () => startSort(true);
  paintResults(state.results || []);
}

function paintResults(results) {
  const box = document.getElementById("sort-results");
  if (!box) return;
  box.innerHTML = results.map((item) => {
    const year = item.year ? ` (${esc(item.year)})` : "";
    return `<article class="card"><div><strong>${esc(item.artist)} — ${esc(item.album)}${year}</strong><span>${esc(item.main)} / ${esc(item.sub)} · ${esc(item.placed)}</span></div></article>`;
  }).join("");
}

async function rememberPaths() {
  const source = document.getElementById("source");
  if (!source) return;
  state.prefs = await call("POST", "/api/prefs", {
    source: source.value.trim(),
    move: document.getElementById("move").checked,
    place_unclear: document.getElementById("unclear").checked,
  });
}

async function startSort(place) {
  await rememberPaths();
  document.body.classList.add("busy");
  liveEl.textContent = place ? "Сортирую…" : "Смотрю…";
  try {
    await call("POST", "/api/sort", {
      source: state.prefs.source,
      catalog: state.prefs.catalog,
      place,
    });
    pollSort();
  } catch (error) {
    document.body.classList.remove("busy");
    liveEl.textContent = "";
    const status = document.getElementById("sort-status");
    if (status) status.textContent = error.message;
  }
}

function pollSort() {
  clearInterval(state.poll);
  state.poll = setInterval(async () => {
    try {
      const job = await call("GET", "/api/sort");
      state.sortStatus = job.status;
      state.results = job.results || [];
      const status = document.getElementById("sort-status");
      if (status) status.textContent = job.status || "";
      paintResults(state.results);
      if (!job.busy) {
        clearInterval(state.poll);
        document.body.classList.remove("busy");
        liveEl.textContent = "";
      }
    } catch (error) {
      clearInterval(state.poll);
      document.body.classList.remove("busy");
      liveEl.textContent = "";
    }
  }, 700);
}

const YT_FORMATS = [
  ["mp3", "mp3"], ["m4a", "m4a"], ["aac", "aac"], ["opus", "opus"], ["ogg", "ogg (vorbis)"],
  ["flac", "flac"], ["wav", "wav"], ["alac", "alac"], ["best", "как есть (без перекодирования)"],
];

async function saveDownloadPrefs(patch) {
  const url = document.getElementById("url");
  const keep = url ? url.value : "";
  try {
    state.prefs = await call("POST", "/api/prefs", patch);
  } catch (error) {
    flash(error.message, 5000);
  }
  render();
  const again = document.getElementById("url");
  if (again) again.value = keep;
}

function localLists() {
  return (state.prefs && state.prefs.lists) || [];
}

function renderDownload() {
  const prefs = state.prefs || {};
  const search = state.yt || { query: "", rows: [] };
  let results = "";
  if (search.loading) results = `<p class="hint">Ищу «${esc(search.query)}»…</p><div class="sr-list">${"<div class=\"sr skel\"><i></i><b></b></div>".repeat(5)}</div>`;
  else if (search.error) results = `<p class="sr-err">${esc(search.error)}</p>`;
  else if (search.rows.length) { results = `<div class="sr-list ${search.fresh ? "fresh" : ""}">${search.rows.map((row, index) => ytRow(row, index)).join("")}</div>`; search.fresh = false; }
  const lists = localLists();
  viewEl.innerHTML = `
    <section class="panel yt-panel">
      <h2>YouTube</h2>
      <div class="yt-search">
        <input id="yt-q" type="search" placeholder="Найти на YouTube: исполнитель, альбом, трек…" value="${esc(search.query || "")}" spellcheck="false" />
        <button class="btn accent" id="yt-go" type="button">${ic("search")}Найти</button>
      </div>
      ${results}
      <details class="yt-dl" ${state.dlOpen ? "open" : ""}>
        <summary>Скачать по ссылке</summary>
        <div class="yt-dl-row">
          <input id="url" placeholder="Ссылка на видео или плейлист" />
          <button class="btn accent" id="go" type="button">${ic("download")}Скачать</button>
        </div>
        <div class="yt-dl-row yt-opts">
          <div class="seg" role="radiogroup" aria-label="Что скачивать">
            ${[["video", "Видео"], ["playlist", "Плейлист"]].map(([value, label]) => `<button type="button" role="radio" data-kind="${value}" aria-checked="${(prefs.youtube_kind || "video") === value}" class="${(prefs.youtube_kind || "video") === value ? "on" : ""}">${label}</button>`).join("")}
          </div>
          <label class="check yt-split" title="Разбить на треки по главам видео; выключено — один целый файл"><input id="split" type="checkbox" ${prefs.youtube_split !== false ? "checked" : ""}/><span>На треки</span></label>
          <select id="format" title="Формат">${YT_FORMATS.map(([fmt, label]) => `<option value="${fmt}" ${(prefs.youtube_format || "mp3") === fmt ? "selected" : ""}>${label}</option>`).join("")}</select>
        </div>
        <p class="hint yt-where">Кладу в: <code>${prefs.catalog ? esc(prefs.catalog) + " / Скачанное с YouTube" : "корневая папка не выбрана"}</code></p>
      </details>
      <p id="dl-status" class="hint">${esc(state.downloadStatus || "")}</p>
      <h3 class="conn-title">Мои плейлисты</h3>
      <p class="hint">Локальные списки Полки (плейлисты на YouTube без входа менять нельзя).</p>
      <div class="lists">${lists.length ? lists.map(listHtml).join("") : `<p class="hint">Пока нет. Добавь трек из поиска — «Новый плейлист…».</p>`}</div>
    </section>`;
  document.querySelector(".yt-dl").ontoggle = (event) => { state.dlOpen = event.target.open; };
  document.getElementById("go").onclick = startDownload;
  viewEl.querySelectorAll("[data-kind]").forEach((node) => {
    node.onclick = () => saveDownloadPrefs({ youtube_kind: node.dataset.kind });
  });
  document.getElementById("split").onchange = (event) => saveDownloadPrefs({ youtube_split: event.target.checked });
  document.getElementById("format").onchange = (event) => saveDownloadPrefs({ youtube_format: event.target.value });
  const q = document.getElementById("yt-q");
  q.addEventListener("keydown", (event) => { if (event.key === "Enter") ytSearch(q.value); });
  document.getElementById("yt-go").onclick = () => ytSearch(q.value);
  viewEl.querySelectorAll("[data-add]").forEach((node) => {
    node.onchange = () => addToList(Number(node.dataset.add), node.value, node);
  });
  viewEl.querySelectorAll("[data-dl]").forEach((node) => {
    node.onclick = () => downloadUrls([node.dataset.dl]);
  });
  viewEl.querySelectorAll("[data-list-dl]").forEach((node) => {
    const list = lists[Number(node.dataset.listDl)];
    node.onclick = () => list && downloadUrls(list.items.map((item) => item.url));
  });
  viewEl.querySelectorAll("[data-list-drop]").forEach((node) => {
    node.onclick = () => saveLists(lists.filter((_l, index) => index !== Number(node.dataset.listDrop)));
  });
  viewEl.querySelectorAll("[data-item-drop]").forEach((node) => {
    node.onclick = () => {
      const [li, id] = [Number(node.dataset.list), node.dataset.itemDrop];
      const next = lists.map((list, index) => index === li ? { ...list, items: list.items.filter((item) => item.id !== id) } : list);
      saveLists(next);
    };
  });
}

function ytRow(row, index) {
  const lists = localLists();
  const tracked = watches().filter((w) => !lists.some((l) => l.watch === w.url));
  const options = [
    `<option value="">В плейлист…</option>`,
    ...lists.map((list, li) => `<option value="l${li}">${esc(list.name)} (${list.items.length})</option>`),
    ...tracked.map((w) => `<option value="w${esc(w.url)}">${esc(w.name || "Плейлист")} · отслеживаемый</option>`),
    `<option value="new">Новый плейлист…</option>`,
  ].join("");
  return `<article class="sr" style="--i:${Math.min(index, 16)}">
    ${row.thumb ? `<img src="${esc(row.thumb)}" alt="" loading="lazy" />` : `<div class="sr-ph"></div>`}
    <div class="sr-copy">
      <strong title="${esc(row.title)}">${esc(row.title)}</strong>
      <span>${esc(row.channel || "")}${row.duration ? ` · ${esc(row.duration)}` : ""}${row.downloaded ? " · скачано" : ""}</span>
    </div>
    <div class="sr-act">
      <button class="icon-btn" type="button" data-ext="${esc(row.url)}" title="Открыть на YouTube" aria-label="Открыть">${ic("open")}</button>
      <select class="sr-add" data-add="${index}">${options}</select>
      <button class="icon-btn" type="button" data-dl="${esc(row.url)}" title="Скачать" aria-label="Скачать">${ic("download")}</button>
    </div>
  </article>`;
}

function listHtml(list, li) {
  return `<article class="lst">
    <div class="lst-head"><strong>${esc(list.name)}</strong><span>${plural(list.items.length, "трек", "трека", "треков")}${list.watch ? " · связан с отслеживаемым" : ""}</span>
      <button class="btn small" type="button" data-list-dl="${li}" ${list.items.length ? "" : "disabled"}>${ic("download")}Скачать всё</button>
      <button class="btn small" type="button" data-list-drop="${li}">${ic("remove")}Удалить</button></div>
    ${list.items.map((item) => `<div class="lst-item"><span>${esc(item.title)}</span><small>${esc(item.duration || "")}</small>
      <button class="lst-x" type="button" data-list="${li}" data-item-drop="${esc(item.id)}" aria-label="Убрать">${ic("remove")}</button></div>`).join("")}
  </article>`;
}

async function saveLists(lists) {
  state.prefs = await call("POST", "/api/prefs", { lists });
  render();
}

async function addToList(index, target, select) {
  const row = (state.yt && state.yt.rows || [])[index];
  if (!row || !target) return;
  const lists = localLists().map((list) => ({ ...list, items: [...list.items] }));
  let li = -1;
  if (target === "new") {
    const name = await askName();
    if (!name) { select.value = ""; return; }
    lists.push({ name, watch: "", items: [] });
    li = lists.length - 1;
  } else if (target.startsWith("w")) {
    const url = target.slice(1);
    const watch = watches().find((w) => w.url === url);
    lists.push({ name: (watch && watch.name) || "Плейлист", watch: url, items: [] });
    li = lists.length - 1;
  } else {
    li = Number(target.slice(1));
  }
  const list = lists[li];
  if (!list.items.some((item) => item.id === row.id)) list.items.push(row);
  await saveLists(lists);
  flash(`Добавлено в «${list.name}».`);
}

function askName() {
  // prompt() в Electron не работает — маленькое окно ввода
  return new Promise((resolve) => {
    const box = document.createElement("div");
    box.className = "ask";
    box.innerHTML = `<div class="ask-card"><label>Название плейлиста<input id="ask-name" value="Мой плейлист" /></label>
      <div class="actions"><button class="btn accent" id="ask-ok" type="button">Создать</button><button class="btn" id="ask-no" type="button">Отмена</button></div></div>`;
    document.body.appendChild(box);
    const input = box.querySelector("#ask-name");
    input.select();
    const done = (value) => { box.remove(); resolve(value); };
    box.querySelector("#ask-ok").onclick = () => done(input.value.trim());
    box.querySelector("#ask-no").onclick = () => done("");
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") done(input.value.trim());
      if (event.key === "Escape") done("");
    });
  });
}

async function ytSearch(raw) {
  const query = String(raw || "").trim();
  if (!query) return;
  const token = (state.ytToken || 0) + 1;
  state.ytToken = token;
  state.yt = { query, rows: [], loading: true, error: "" };
  render();
  try {
    const data = await call("GET", `/api/yt_search?q=${encodeURIComponent(query)}`);
    if (token !== state.ytToken) return;
    state.yt = { query, rows: data.rows || [], loading: false, fresh: true, error: (data.rows || []).length ? "" : "Ничего не нашлось." };
  } catch (error) {
    if (token !== state.ytToken) return;
    state.yt = { query, rows: [], loading: false, error: error.message };
  }
  if (state.page === "download") render();
}

// без корневой папки не качаем: подсвечиваем поле в верхней панели
function needRoot() {
  if ((state.prefs && String(state.prefs.catalog || "").trim())) return false;
  flash("Не выбрана корневая папка", 4000);
  const root = document.getElementById("root-dir");
  const box = root && root.closest(".root-box");
  if (box) {
    box.classList.remove("pulse");
    void box.offsetWidth;
    box.classList.add("pulse");
    setTimeout(() => box.classList.remove("pulse"), 2600);
  }
  if (root) root.focus();
  return true;
}

function rootError(error) {
  if (/корневая папка/i.test(error.message)) { needRoot(); return true; }
  return false;
}

async function downloadUrls(urls) {
  if (needRoot()) return;
  const status = document.getElementById("dl-status");
  try {
    await call("POST", "/api/download", { urls, kind: "1", format: (state.prefs || {}).youtube_format || "mp3", split: (state.prefs || {}).youtube_split !== false });
    if (status) status.textContent = `Скачиваю: ${urls.length}. Уже скачанные пропускаются (downloaded.json).`;
    document.body.classList.add("busy");
    pollDownload();
  } catch (error) {
    if (!rootError(error) && status) status.textContent = error.message;
  }
}

async function startDownload() {
  if (needRoot()) return;
  const url = document.getElementById("url").value.trim();
  document.body.classList.add("busy");
  liveEl.textContent = "Скачиваю…";
  try {
    await call("POST", "/api/download", {
      url,
      kind: (state.prefs || {}).youtube_kind === "playlist" ? "2" : "1",
      format: document.getElementById("format").value,
      split: document.getElementById("split").checked,
    });
    pollDownload();
  } catch (error) {
    document.body.classList.remove("busy");
    liveEl.textContent = "";
    if (!rootError(error)) document.getElementById("dl-status").textContent = error.message;
  }
}

const JOB_ICONS = { "готово": "✓", "уже есть": "=", "ошибка": "!", "недоступно": "⊘" };

function jobsPanel(current) {
  const items = ((current.progress || {}).items || []).filter((it) => it.title);
  const base = ((state.prefs || {}).catalog || "").replace(/[\\/]+$/, "");
  const rel = (path) => (base && path.startsWith(base) ? path.slice(base.length + 1) : path);
  const rows = items.map((it) => {
    const st = it.state || "";
    const done = ["готово", "уже есть"].includes(st);
    const bad = ["ошибка", "недоступно"].includes(st);
    return `<li class="job-item ${bad ? "bad" : done ? "ok" : "run"}">
      <span class="ji-ic">${JOB_ICONS[st] || `<i class="ji-spin"></i>`}</span>
      <span class="ji-main"><strong title="${esc(it.title)}">${esc(it.title)}</strong>
        ${it.note ? `<small class="ji-note">${esc(it.note)}</small>` : ""}
        ${it.path ? `<code class="ji-path" data-job-reveal="${esc(it.path)}" title="Открыть папку">${esc(rel(it.path))}</code>` : ""}</span>
      <span class="ji-st">${bad || done ? esc(st) : `${esc(st)} · ${Math.round(Number(it.percent) || 0)}%`}</span>
    </li>`;
  }).join("");
  return `<div class="job-panel">
    ${rows ? `<ol class="job-items">${rows}</ol>` : `<p class="hint">Пока ничего не начато.</p>`}
    <button class="linkish job-log-btn" type="button" id="jobs-log">${state.jobsLog ? "скрыть лог" : "лог"}</button>
    ${state.jobsLog ? `<pre class="log job-log">${esc(current.log || "")}</pre>` : ""}
  </div>`;
}

// полоска «Загрузки» внизу экранов YouTube и Плейлисты
function paintJobs(job) {
  const box = document.getElementById("jobs");
  if (!box) return;
  state.job = job || state.job;
  const current = state.job;
  const show = current && (current.busy || current.progress) && !state.jobsClosed && ["download", "playlists"].includes(state.page);
  box.hidden = !show || !(current.busy || (current.progress && current.progress.stage));
  if (box.hidden) return;
  const pr = current.progress || {};
  const stage = current.busy ? (pr.stage || "готовлюсь") : (pr.stage || "готово");
  const counter = pr.total ? `${pr.item}/${pr.total}` : (current.batch && current.batch[1] > 1 ? `${current.batch[0]}/${current.batch[1]}` : "");
  const pct = Math.max(0, Math.min(100, Number(pr.percent) || 0));
  const notes = [];
  if (pr.chapters && current.busy) notes.push(plural(pr.chapters, "глава", "главы", "глав"));
  if (pr.skipped) notes.push(`пропущено (уже есть): ${pr.skipped}`);
  if ((pr.whole || []).length) notes.push(`нет таймкодов — скачан целиком: ${pr.whole.map(esc).join(", ")}`);
  const failed = stage === "ошибка";
  box.className = `jobs ${current.busy ? "run" : failed ? "bad" : "ok"}`;
  box.innerHTML = `
    <div class="job-ic">${ic(current.busy ? "download" : failed ? "remove" : "download")}</div>
    <div class="job-main">
      <div class="job-line">
        <strong title="${esc(pr.title || current.label || "")}">${esc(pr.title || current.label || "Скачивание")}</strong>
        <span class="job-meta">${counter ? `<b>${counter}</b> · ` : ""}${esc(stage)}${current.busy && stage === "скачиваю" ? ` · <b>${pct.toFixed(0)}%</b>` : ""}</span>
      </div>
      <div class="job-bar"><i style="width:${failed ? 100 : current.busy ? pct : 100}%"></i></div>
      ${pr.error ? `<p class="job-note bad">${esc(pr.error)}</p>` : notes.length ? `<p class="job-note">${notes.join(" · ")}</p>` : ""}
    </div>
    <button class="icon-btn job-more" type="button" id="jobs-more" title="${state.jobsOpen ? "Свернуть" : "Подробнее"}" aria-expanded="${state.jobsOpen ? "true" : "false"}">${ic("next")}</button>
    ${current.busy ? "" : `<button class="icon-btn" type="button" id="jobs-close" title="Скрыть" aria-label="Скрыть">${ic("remove")}</button>`}
    ${state.jobsOpen ? jobsPanel(current) : ""}`;
  box.classList.toggle("open", !!state.jobsOpen);
  const toggle = () => { state.jobsOpen = !state.jobsOpen; paintJobs(); };
  box.querySelector(".job-main").onclick = toggle;
  document.getElementById("jobs-more").onclick = toggle;
  const logBtn = document.getElementById("jobs-log");
  if (logBtn) logBtn.onclick = () => { state.jobsLog = !state.jobsLog; paintJobs(); };
  box.querySelectorAll("[data-job-reveal]").forEach((node) => {
    node.onclick = () => api && api.reveal && api.reveal(node.dataset.jobReveal);
  });
  const pre = box.querySelector(".job-log");
  if (pre) pre.scrollTop = pre.scrollHeight;
  const close = document.getElementById("jobs-close");
  if (close) close.onclick = () => { state.jobsClosed = true; box.hidden = true; };
}

function pollDownload() {
  clearInterval(state.poll);
  state.jobsClosed = false;
  state.poll = setInterval(async () => {
    const job = await call("GET", "/api/download");
    paintJobs(job);
    state.downloadStatus = job.status;
    state.downloadLog = job.log;
    const status = document.getElementById("dl-status");
    const log = document.getElementById("dl-log");
    if (status) status.textContent = job.status || "";
    if (log) {
      log.hidden = !job.log;
      log.textContent = job.log || "";
      log.scrollTop = log.scrollHeight;
    }
    if (!job.busy) {
      clearInterval(state.poll);
      loadPaths();
      document.body.classList.remove("busy");
      liveEl.textContent = "";
    }
  }, 700);
}

function linkFields() {
  return [...document.querySelectorAll(".pl-url")];
}

function linkFieldHtml(value) {
  return `<input class="pl-url" placeholder="https://www.youtube.com/playlist?list=…" value="${esc(value)}" />`;
}

function bindLinkField(node) {
  node.addEventListener("input", growLinkFields);
  node.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      addWatch();
    }
  });
}

function normalizeDrafts(values) {
  const out = values.filter((value) => value.trim());
  out.push("");
  return out;
}

function growLinkFields() {
  const box = document.getElementById("pl-fields");
  if (!box) return;
  let fields = linkFields();
  // убрать лишние пустые поля в конце, оставить ровно одно пустое
  while (fields.length > 1 && !fields[fields.length - 1].value.trim() && !fields[fields.length - 2].value.trim()) {
    const extra = fields.pop();
    if (document.activeElement === extra) fields[fields.length - 1].focus();
    extra.remove();
  }
  const last = fields[fields.length - 1];
  if (last && last.value.trim()) {
    box.insertAdjacentHTML("beforeend", linkFieldHtml(""));
    bindLinkField(box.lastElementChild);
  }
}

async function addWatch() {
  const values = linkFields().map((node) => node.value.trim()).filter(Boolean);
  const urls = [...new Set(values.filter((value) => /^https?:\/\//.test(value)))];
  const skipped = values.filter((value) => !/^https?:\/\//.test(value)).length;
  const note = document.getElementById("pl-note");
  if (!urls.length) {
    if (note) note.textContent = "Нужна ссылка, которая начинается с http.";
    return;
  }
  const list = watches().filter((item) => !urls.includes(item.url));
  urls.forEach((url) => list.push({ url, name: url.includes("list=LL") ? "Понравившиеся" : "", mode: "folder" }));
  state.prefs = await call("POST", "/api/prefs", { watches: list, watch_enabled: true });
  state.focus = list.length - 1;
  state.page = "playlists";
  linkFields().forEach((node) => { node.value = ""; });
  render();
  const after = document.getElementById("pl-note");
  if (after) after.textContent = `Добавлено: ${urls.length}` + (skipped ? `, пропущено (не ссылки): ${skipped}` : "");
}

function renderPlaylists() {
  const drafts = normalizeDrafts(linkFields().length ? linkFields().map((node) => node.value) : (state.linkDrafts || []));
  state.linkDrafts = [""];
  const list = watches();
  viewEl.innerHTML = `
    <section class="panel">
      <h2>Плейлисты</h2>
      <p class="hint">Каждая ссылка становится своей карточкой, как вставка в чате. Можно следить сразу за несколькими.</p>
      <div class="embeds">
        ${list.length ? list.map((entry, index) => embedHtml(entry, index)).join("") : `<p class="hint">Пока пусто. Вставь ссылку ниже — для следующей появится новое поле.</p>`}
      </div>
      <div class="addbar newlink">
        <div class="pl-links"><span class="pl-cap">Новый плейлист</span><div id="pl-fields">${drafts.map(linkFieldHtml).join("")}</div></div>
        <button class="btn accent" id="add-pl" type="button">${ic("plus")}Добавить</button>
      </div>
      <p id="pl-note"></p>
    </section>`;
  document.getElementById("add-pl").onclick = addWatch;
  linkFields().forEach(bindLinkField);
  viewEl.querySelectorAll("[data-open]").forEach((node) => {
    node.onclick = () => api && api.open(node.dataset.open);
  });
  viewEl.querySelectorAll("[data-refresh]").forEach((node) => {
    node.onclick = () => loadPlaylist(Number(node.dataset.refresh), true);
  });
  viewEl.querySelectorAll("[data-run]").forEach((node) => {
    node.onclick = async () => {
      const index = Number(node.dataset.run);
      const item = watches()[index];
      if (!item || needRoot()) return;
      try {
        await call("POST", "/api/playlist_run", { url: item.url });
        deckNote(index, "Скачиваю только новые видео — ход внизу.");
        document.body.classList.add("busy");
        pollDownload();
      } catch (error) {
        if (!rootError(error)) deckNote(index, error.message);
      }
    };
  });
  viewEl.querySelectorAll("[data-drop]").forEach((node) => {
    node.onclick = () => removeWatch(Number(node.dataset.drop));
  });
  viewEl.querySelectorAll("[data-mode]").forEach((node) => {
    node.onchange = async () => {
      const index = Number(node.dataset.mode);
      const next = watches();
      if (!next[index]) return;
      next[index].mode = node.value;
      state.prefs = await call("POST", "/api/prefs", { watches: next });
    };
  });
  viewEl.querySelectorAll("[data-content]").forEach((node) => {
    node.onchange = async () => {
      const next = watches();
      const index = Number(node.dataset.content);
      if (!next[index]) return;
      next[index].content = node.value;
      state.prefs = await call("POST", "/api/prefs", { watches: next });
      renderPlaylists();
    };
  });
  viewEl.querySelectorAll("[data-reveal]").forEach((node) => {
    node.onclick = (event) => {
      event.stopPropagation();
      const base = (state.paths || {}).base || "";
      const rel = node.dataset.reveal;
      const full = /^([a-z]:[\\/]|\/)/i.test(rel) ? rel : `${base}${base.includes("\\") ? "\\" : "/"}${base.includes("\\") ? rel.replace(/\//g, "\\") : rel}`;
      if (api && api.reveal) api.reveal(full);
    };
  });
  viewEl.querySelectorAll("[data-name]").forEach((node) => {
    const edit = () => {
      const index = Number(node.dataset.name);
      const entry = watches()[index];
      if (!entry || node.querySelector("input")) return;
      const before = node.textContent;
      node.innerHTML = `<input class="name-edit" value="${esc(before)}" aria-label="Название плейлиста" />`;
      const input = node.querySelector("input");
      input.focus();
      input.select();
      let done = false;
      const finish = async (save) => {
        if (done) return;
        done = true;
        const value = input.value.trim();
        if (save && value && value !== before) {
          const next = watches();
          next[index].name = value;
          state.prefs = await call("POST", "/api/prefs", { watches: next });
          flash(`Переименовано: ${value}`);
        }
        renderPlaylists();
      };
      input.onkeydown = (event) => {
        if (event.key === "Enter") { event.preventDefault(); finish(true); }
        if (event.key === "Escape") { event.preventDefault(); finish(false); }
      };
      input.onblur = () => finish(true);
    };
    node.onclick = edit;
    node.onkeydown = (event) => { if (event.key === "Enter") edit(); };
  });
  viewEl.querySelectorAll("[data-split]").forEach((node) => {
    node.onchange = async () => {
      const next = watches();
      const index = Number(node.dataset.split);
      if (!next[index]) return;
      next[index].split = node.checked;
      state.prefs = await call("POST", "/api/prefs", { watches: next });
    };
  });
  viewEl.querySelectorAll("[data-toggle]").forEach((node) => {
    node.onclick = () => toggleDeck(Number(node.dataset.toggle));
  });
  viewEl.querySelectorAll("[data-step]").forEach((node) => {
    node.onclick = () => stepDeck(Number(node.dataset.step), Number(node.dataset.delta));
  });
  viewEl.querySelectorAll(".eline").forEach((node) => {
    node.onclick = () => playAt(Number(node.dataset.list), Number(node.dataset.pick));
  });
  viewEl.querySelectorAll(".seek").forEach((node) => {
    node.oninput = () => scrub(Number(node.dataset.seek), Number(node.value), false);
    node.onchange = () => scrub(Number(node.dataset.seek), Number(node.value), true);
  });
  viewEl.querySelectorAll(".vol-slider").forEach((node) => {
    node.oninput = () => setVolume(Number(node.value));
  });
  markDeck();
  if (!state.paths) { state.paths = { base: "", paths: {} }; loadPaths(); }
  list.forEach((entry, index) => {
    const cached = state.playlist[entry.url];
    if (!cached || (!cached.loaded && !cached.loading)) loadPlaylist(index);
  });
}

function embedHtml(entry, index) {
  const cached = state.playlist[entry.url] || {};
  const rows = cached.rows || [];
  const cover = (rows[0] && rows[0].thumb) || "";
  const title = entry.name || cached.title || "Плейлист";
  const content = ["tracks", "albums"].includes(entry.content) ? entry.content : "auto";
  const owner = cached.owner || "YouTube";
  const mode = entry.mode === "sort" ? "sort" : "folder";
  return `<div class="embed-row pl-block" data-row="${index}">
    <aside class="plist-set">
      <h3>Плейлист</h3>
      <label>Куда класть
        <select data-mode="${index}">
          <option value="folder" ${mode === "folder" ? "selected" : ""}>Отдельная папка</option>
          <option value="sort" ${mode === "sort" ? "selected" : ""}>В каталог по жанрам</option>
        </select>
      </label>
      <label>Что внутри
        <select data-content="${index}" title="Авто: если все видео короче 15 минут — это отдельные треки">
          <option value="auto" ${content === "auto" ? "selected" : ""}>Авто</option>
          <option value="albums" ${content === "albums" ? "selected" : ""}>Альбомы целиком</option>
          <option value="tracks" ${content === "tracks" ? "selected" : ""}>Отдельные треки</option>
        </select>
      </label>
      <label class="check yt-split pl-split" title="${content === "tracks" ? "Для отдельных треков главы не режутся — каждый трек целиком" : "Разбить на треки по главам видео; выключено — один целый файл"}"><input type="checkbox" data-split="${index}" ${entry.split !== false ? "checked" : ""} ${content === "tracks" ? "disabled" : ""}/><span>На треки</span></label>
      <p class="plist-name" data-name="${index}" tabindex="0" title="Нажми, чтобы переименовать">${esc(title)}</p>
      <p data-deck-status="${index}">${esc(cached.status || "")}</p>
      <div class="actions">
        <button class="btn" type="button" data-run="${index}">${ic("download")}Скачать новые</button>
        <button class="btn" type="button" data-refresh="${index}">${ic("refresh")}Обновить</button>
        <button class="btn" type="button" data-drop="${index}">${ic("remove")}Убрать</button>
      </div>
    </aside>
    <article class="embed">
      <div class="embed-top">
        ${cover ? `<img src="${esc(cover)}" alt="" />` : `<div class="embed-cover"></div>`}
        <div class="embed-copy">
          <h3>${esc(title)}</h3>
          <p>${esc(owner)}</p>
          <button class="icon-btn" type="button" data-open="${esc(entry.url)}" title="Открыть на YouTube" aria-label="Открыть">${ic("open")}</button>
        </div>
        <span class="yt-mark">YouTube</span>
      </div>
      <div class="transport">
        <button class="skip back" type="button" data-step="${index}" data-delta="-1" aria-label="Назад">${ic("prev")}</button>
        <button class="skip" type="button" data-step="${index}" data-delta="1" aria-label="Дальше">${ic("next")}</button>
        <button class="play" type="button" data-toggle="${index}" aria-label="Слушать">${ic("play", "i-play")}${ic("pause", "i-pause")}</button>
      </div>
      <div class="seek-row">
        <span data-now="${index}">0:00</span>
        <input class="seek" data-seek="${index}" type="range" min="0" max="1000" value="0" aria-label="Время" />
        <span data-end="${index}">0:00</span>
      </div>
      <label class="vol-row">Громкость
        <input class="vol-slider" type="range" min="0" max="100" value="${Math.round(deck.volume * 100)}" aria-label="Громкость" />
      </label>
    </article>
    <section class="embed-list">
      <h3>Видео в плейлисте${rows.length ? ` · ${rows.length}` : ""}</h3>
        <div class="embed-tracks">
        ${rows.length ? rows.map((row, rowIndex) => embedTrack(row, index, rowIndex)).join("") : `<p class="embed-wait">${esc(cached.status || "Загружаю…")}</p>`}
        </div>
    </section>
  </div>`;
}

function embedTrack(row, listIndex, index) {
  const where = ((state.paths || {}).paths || {})[row.id];
  return `<button class="eline" type="button" data-list="${listIndex}" data-pick="${index}">
    <span class="num">${index + 1}</span>
    <span class="ename"><strong>${esc(row.title)}</strong><small>${esc(row.channel || "")}</small>${where ? `<code class="epath" data-reveal="${esc(where)}" title="Показать в папке">${esc(where)}</code>` : ""}</span>
    <span class="etime">${esc(row.duration || "")}</span>
  </button>`;
}

const deck = { list: -1, index: 0, playing: false, busy: false, token: 0, volume: 0.4, seeking: false };

function clock(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return "0:00";
  const whole = Math.floor(seconds);
  const mins = Math.floor(whole / 60);
  const hours = Math.floor(mins / 60);
  const sec = String(whole % 60).padStart(2, "0");
  if (hours) return `${hours}:${String(mins % 60).padStart(2, "0")}:${sec}`;
  return `${mins}:${sec}`;
}

function playlistRows(listIndex) {
  const item = watches()[listIndex];
  if (!item || !state.playlist[item.url]) return [];
  return state.playlist[item.url].rows || [];
}

function markDeck() {
  document.querySelectorAll(".eline").forEach((node) => {
    const on = Number(node.dataset.list) === deck.list && Number(node.dataset.pick) === deck.index && deck.list >= 0;
    node.classList.toggle("on", on);
    node.classList.toggle("live", on && deck.playing);
  });
  document.querySelectorAll(".play").forEach((node) => {
    node.classList.toggle("paused", deck.playing && Number(node.dataset.toggle) === deck.list);
  });
}

function deckNote(listIndex, text) {
  const node = document.querySelector(`[data-deck-status="${listIndex}"]`);
  if (node) node.textContent = text;
}

async function playAt(listIndex, rowIndex) {
  const rows = playlistRows(listIndex);
  if (!rows.length) return;
  const index = (rowIndex + rows.length) % rows.length;
  const row = rows[index];
  const token = ++deck.token;
  deck.list = listIndex;
  deck.index = index;
  deck.playing = true;
  deck.busy = true;
  markDeck();
  const node = document.querySelector(`.eline[data-list="${listIndex}"][data-pick="${index}"]`);
  if (node) node.scrollIntoView({ block: "nearest" });
  deckNote(listIndex, "Открываю звук…");
  const audio = document.getElementById("deck");
  audio.volume = deck.volume;
  try {
    const data = await call("POST", "/api/stream", { url: row.url });
    if (token !== deck.token || !deck.playing) return;
    audio.src = data.url;
    await audio.play();
    if (token !== deck.token || !deck.playing) {
      audio.pause();
      return;
    }
    deckNote(listIndex, row.title);
  } catch (error) {
    if (token !== deck.token) return;
    deck.playing = false;
    markDeck();
    deckNote(listIndex, error.message);
  } finally {
    if (token === deck.token) deck.busy = false;
  }
}

function toggleDeck(listIndex) {
  const audio = document.getElementById("deck");
  if (deck.list === listIndex && (deck.playing || deck.busy)) {
    deck.token += 1;
    deck.playing = false;
    deck.busy = false;
    audio.pause();
    markDeck();
    return;
  }
  if (deck.list === listIndex && audio.src && audio.paused) {
    audio.volume = deck.volume;
    audio.play().then(() => {
      deck.playing = true;
      markDeck();
    }).catch((error) => deckNote(listIndex, error.message));
    return;
  }
  playAt(listIndex, deck.list === listIndex ? deck.index : 0);
}

function setVolume(percent) {
  deck.volume = Math.min(1, Math.max(0, percent / 100));
  const audio = document.getElementById("deck");
  if (audio) audio.volume = deck.volume;
  document.querySelectorAll(".vol-slider").forEach((node) => {
    node.value = String(Math.round(deck.volume * 100));
  });
}

function scrub(listIndex, value, commit) {
  if (deck.list !== listIndex) return;
  const audio = document.getElementById("deck");
  if (!audio || !audio.duration) return;
  deck.seeking = !commit;
  const at = (value / 1000) * audio.duration;
  const now = document.querySelector(`[data-now="${listIndex}"]`);
  if (now) now.textContent = clock(at);
  if (commit) {
    audio.currentTime = at;
    deck.seeking = false;
  }
}

function stepDeck(listIndex, delta) {
  const base = deck.list === listIndex ? deck.index : 0;
  playAt(listIndex, base + delta);
}

async function removeWatch(index) {
  const list = watches().filter((_item, itemIndex) => itemIndex !== index);
  state.prefs = await call("POST", "/api/prefs", { watches: list });
  render();
}

async function loadPlaylist(index, force) {
  const item = watches()[index];
  if (!item) return;
  const current = state.playlist[item.url];
  if (!force && current && (current.loaded || current.loading)) return;
  state.playlist[item.url] = { ...(current || {}), loading: true, loaded: false, status: "Загружаю…" };
  document.body.classList.add("busy");
  liveEl.textContent = "Открываю плейлист…";
  try {
    const data = await call("POST", "/api/playlist", { url: item.url });
    const got = (data.rows || []).filter((row) => row.downloaded).length;
    state.playlist[item.url] = {
      title: data.title,
      owner: data.owner || "YouTube",
      rows: data.rows || [],
      status: `${(data.rows || []).length} видео, скачано ${got}, ${plural((data.rows || []).length - got, "новое", "новых", "новых")}`,
      loaded: true,
      loading: false,
    };
    if (data.title && !item.name) {
      item.name = data.title;
      state.prefs = await call("POST", "/api/prefs", { watches: watches() });
    }
  } catch (error) {
    state.playlist[item.url] = {
      title: item.name || "Плейлист",
      owner: "YouTube",
      rows: [],
      status: error.message,
      loaded: true,
      loading: false,
    };
  } finally {
    document.body.classList.remove("busy");
    if (!watches().some((entry) => state.playlist[entry.url] && state.playlist[entry.url].loading)) {
      liveEl.textContent = "";
    }
    if (state.page === "playlists") renderPlaylists();
  }
}

function renderSettings() {
  const prefs = state.prefs || {};
  viewEl.innerHTML = `
    <section class="panel">
      <h2>Настройки</h2>
      <p class="hint">Ключи необязательны. Файл polka-prefs.json лежит рядом с программой.</p>
      <div class="grid">
        <div class="row">
          ${field("Cookies для понравившихся", "cookies", prefs.cookies)}
          <button class="btn" id="pick-cookies" type="button">${ic("folder")}Обзор</button>
        </div>
      </div>
      <div class="actions">
        <label class="check"><input id="show-log" type="checkbox" ${prefs.show_log ? "checked" : ""}/> Показывать лог поиска</label>
        <label class="check"><input id="tags" type="checkbox" ${prefs.tag_files ? "checked" : ""}/> Писать теги, если их нет</label>
        <label class="check"><input id="covers" type="checkbox" ${prefs.fetch_covers ? "checked" : ""}/> Скачивать обложку, если её нет</label>
        <label class="check"><input id="dark" type="checkbox" ${prefs.dark ? "checked" : ""}/> Тёмная тема</label>
      </div>
      <button class="btn accent" id="save" type="button">Сохранить</button>
      <p id="save-status"></p>
      <h3 class="conn-title">Подключения</h3>
      <p class="hint">Нужны только для поиска жанров. «Подключить» откроет браузер; статус обновится сам.</p>
      <div class="conns" id="conns"><p class="hint">Проверяю…</p></div>
    </section>`;
  paintConnections();
  document.getElementById("pick-cookies").onclick = async () => {
    const file = await api.file();
    if (file) document.getElementById("cookies").value = file;
  };
  document.getElementById("dark").onchange = (event) => {
    document.body.classList.toggle("dark", event.target.checked);
  };
  document.getElementById("save").onclick = async () => {
    state.prefs = await call("POST", "/api/prefs", {
      cookies: document.getElementById("cookies").value.trim(),
      show_log: document.getElementById("show-log").checked,
      tag_files: document.getElementById("tags").checked,
      fetch_covers: document.getElementById("covers").checked,
      dark: document.getElementById("dark").checked,
    });
    applyTheme();
    document.getElementById("save-status").textContent = "Сохранено.";
  };
}

const SERVICES = {
  lastfm: { name: "Last.fm", keyLabel: "API key", secretLabel: "Shared secret" },
  discogs: { name: "Discogs", keyLabel: "Consumer Key", secretLabel: "Consumer Secret" },
};

async function paintConnections(note) {
  const box = document.getElementById("conns");
  if (!box) return;
  let data;
  try {
    data = await call("GET", "/api/auth");
  } catch (error) {
    box.innerHTML = `<p class="hint">${esc(error.message)}</p>`;
    return;
  }
  state.auth = data;
  box.innerHTML = Object.keys(SERVICES).map((id) => connCard(id, data[id] || {}, note && note.id === id ? note.text : "")).join("");
  box.querySelectorAll("[data-connect]").forEach((node) => { node.onclick = () => startConnect(node.dataset.connect); });
  box.querySelectorAll("[data-logout]").forEach((node) => {
    node.onclick = async () => {
      await call("POST", "/api/auth/logout", { service: node.dataset.logout });
      paintConnections();
    };
  });
  box.querySelectorAll("[data-keys]").forEach((node) => {
    node.onclick = async () => {
      const id = node.dataset.keys;
      try {
        await call("POST", "/api/auth/keys", {
          service: id,
          key: document.getElementById(`${id}-key`).value,
          secret: document.getElementById(`${id}-secret`).value,
        });
        paintConnections({ id, text: "Ключи сохранены." });
      } catch (error) {
        paintConnections({ id, text: error.message });
      }
    };
  });
  const personal = document.getElementById("discogs-personal-save");
  if (personal) {
    personal.onclick = async () => {
      try {
        await call("POST", "/api/auth/discogs_token", { token: document.getElementById("discogs-personal").value });
        paintConnections({ id: "discogs", text: "Токен принят." });
      } catch (error) {
        paintConnections({ id: "discogs", text: error.message });
      }
    };
  }
}

function connCard(id, info, note) {
  const meta = SERVICES[id];
  let state_;
  if (info.connected) {
    state_ = `<span class="conn-state on">подключён как <strong>${esc(info.user || "пользователь")}</strong>${info.method ? ` · ${esc(info.method)}` : ""}</span>
      <button class="linkish" type="button" data-logout="${id}">отключить</button>`;
  } else if (info.has_keys) {
    state_ = `<span class="conn-state">не подключён</span>
      <button class="linkish" type="button" data-connect="${id}">подключить</button>`;
  } else {
    state_ = `<span class="conn-state">не подключён — нужны ключи приложения</span>`;
  }
  const personal = id === "discogs" && !info.connected ? `
      <div class="conn-row">
        <label>или личный токен<input id="discogs-personal" type="password" placeholder="Settings → Developers → Generate token" /></label>
        <button class="btn small" id="discogs-personal-save" type="button">Войти токеном</button>
      </div>` : "";
  return `<div class="conn">
    <div class="conn-head"><span class="conn-name">${meta.name}</span>${state_}</div>
    <details class="conn-keys" ${info.has_keys || !note ? "" : "open"}>
      <summary>свои ключи${info.own_keys ? " · заданы" : ""}</summary>
      <p class="conn-warn">Ключи берутся здесь: <a href="#" data-ext="${esc(info.help)}">${esc(info.help)}</a>. Callback URL: <code>http://127.0.0.1:47321/auth/${id}/callback</code>. Можно и через переменные POLKA_${id.toUpperCase()}_KEY / _SECRET.</p>
      <div class="conn-row">
        <label>${meta.keyLabel}<input id="${id}-key" value="${esc(info.app_key || "")}" spellcheck="false" /></label>
        <label>${meta.secretLabel}<input id="${id}-secret" type="password" placeholder="${info.own_keys ? "сохранён — оставь пустым" : ""}" /></label>
        <button class="btn small" type="button" data-keys="${id}">Сохранить</button>
      </div>
      ${personal}
    </details>
    ${note || info.error ? `<p class="conn-note">${esc(note || info.error || "")}</p>` : ""}
  </div>`;
}

async function startConnect(id) {
  try {
    const data = await call("POST", "/api/auth/start", { service: id });
    if (api) api.open(data.url);
    paintConnections({ id, text: "Открыл браузер. Войди и разреши доступ — статус обновится сам." });
    const started = Date.now();
    clearInterval(state.authPoll);
    state.authPoll = setInterval(async () => {
      if (Date.now() - started > 5 * 60 * 1000 || state.page !== "settings") {
        clearInterval(state.authPoll);
        return;
      }
      const info = (await call("GET", "/api/auth"))[id] || {};
      if (info.connected || info.error) {
        clearInterval(state.authPoll);
        paintConnections();
      }
    }, 2000);
  } catch (error) {
    paintConnections({ id, text: error.message });
  }
}

viewEl.addEventListener("click", (event) => {
  const link = event.target.closest("[data-ext]");
  if (!link) return;
  event.preventDefault();
  if (api) api.open(link.dataset.ext);
});

function bindFolder(buttonId, inputId) {
  const button = document.getElementById(buttonId);
  if (!button || !api) return;
  button.onclick = async () => {
    const folder = await api.folder();
    if (folder) document.getElementById(inputId).value = folder;
  };
}

tabsEl.onclick = (event) => {
  const button = event.target.closest("button");
  if (!button) return;
  state.page = button.dataset.page;
  render();
};

async function boot() {
  if (api && api.minimize) {
    document.body.classList.add("electron");
    document.getElementById("win-min").onclick = () => api.minimize();
    document.getElementById("win-max").onclick = () => api.maximize();
    document.getElementById("win-close").onclick = () => api.close();
  }
  const rootInput = document.getElementById("root-dir");
  rootInput.addEventListener("change", () => setRoot(rootInput.value));
  rootInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") rootInput.blur();
  });
  document.getElementById("root-pick").onclick = async () => {
    if (!api) return;
    const folder = await api.folder();
    if (folder) setRoot(folder);
  };
  document.getElementById("search").addEventListener("input", (event) => {
    state.query = event.target.value;
    applySearch();
  });
  document.getElementById("gear").onclick = () => {
    state.page = "settings";
    render();
  };
  const audio = document.getElementById("deck");
  if (audio) {
    audio.volume = deck.volume;
    audio.onended = () => {
      if (deck.list >= 0 && deck.playing) playAt(deck.list, deck.index + 1);
    };
    audio.ontimeupdate = () => {
      if (deck.seeking || deck.list < 0) return;
      const now = document.querySelector(`[data-now="${deck.list}"]`);
      const end = document.querySelector(`[data-end="${deck.list}"]`);
      const seek = document.querySelector(`.seek[data-seek="${deck.list}"]`);
      if (now) now.textContent = clock(audio.currentTime);
      if (end && Number.isFinite(audio.duration)) end.textContent = clock(audio.duration);
      if (seek && audio.duration) seek.value = String(Math.round((audio.currentTime / audio.duration) * 1000));
    };
  }
  const banner = document.createElement("p");
  banner.className = "banner";
  try {
    state.prefs = await call("GET", "/api/prefs");
  } catch (error) {
    state.prefs = {
      source: "", catalog: "", download_dir: "", move: true, place_unclear: false,
      youtube_format: "mp3", youtube_kind: "video", youtube_split: true, watches: [], lists: [], tag_files: true, fetch_covers: true, dark: false,
    };
    viewEl.before(banner);
    banner.innerHTML = api
      ? `Движок не ответил: ${esc(error.message)}`
      : `Так выглядит окно Electron. <a href="/polka.zip">Скачай Полку</a> и открой Polka.bat — там заработают папки, скачивание и плейлисты.`;
  }
  const startPage = new URLSearchParams(location.search).get("page");
  if (["sort", "download", "playlists", "settings"].includes(startPage)) state.page = startPage;
  render();
  if (new URLSearchParams(location.search).get("dl") === "1") { state.dlOpen = true; render(); }
  // только для скриншотов: раскрытая полоска / предупреждение о корневой папке
  if (new URLSearchParams(location.search).get("jobs") === "1") { state.jobsOpen = true; }
  if (new URLSearchParams(location.search).get("rootwarn") === "1") {
    setTimeout(() => { if (needRoot()) { const b = document.querySelector(".root-box"); if (b) b.classList.add("pulse-hold"); flash("Не выбрана корневая папка", 600000); } }, 1500);
  }
  call("GET", "/api/download").then((job) => { if (job && job.busy) { document.body.classList.add("busy"); pollDownload(); } }).catch(() => {});
  const startQuery = new URLSearchParams(location.search).get("q");
  if (startQuery && state.page === "download") ytSearch(startQuery);
}

boot();
