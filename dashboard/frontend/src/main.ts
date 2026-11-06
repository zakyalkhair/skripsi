import "@fontsource-variable/plus-jakarta-sans";
import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/map.css";
import "./styles/panel.css";
import "./styles/timeline.css";
import "./styles/chat.css";
import "./styles/ui.css";

import { api, API_VERSI, ApiError, isAbort, PESAN_VERSI, type Cakupan, type Query } from "./api";
import { ChatView, type ChatCtxInfo } from "./chat/chat";
import { setChatService, type ChatScope } from "./chat/service";
import { demoChatService } from "./chat/demo";
import { h } from "./dom";
import { downloadData, saveBlob } from "./export/data";
import { exportPng, type Crop } from "./export/png";
import { rentang } from "./format";
import { JENIS, LABEL_PENDEK } from "./jenis";
import { buildLegend } from "./map/legend";
import { MapView, type Pad } from "./map/map";
import { filterKey, Store, type State } from "./store";
import type { KabAgregat, KabKejadian, KabTitik, Wilayah } from "./types";
import { buildToolbar } from "./ui/filters";
import { ico } from "./ui/icons";
import { Panel, type EventRef, type PanelTab } from "./ui/panel";
import { Timeline, type TlScope } from "./ui/timeline";
import { Toasts } from "./ui/toast";
import { parseUrl, UrlSync, type UrlState } from "./url";

const store = new Store();
const q = (s: Pick<State, "jenis" | "dari" | "sampai">): Query => ({ jenis: s.jenis, dari: s.dari, sampai: s.sampai });
const cakupan = (s: State): Cakupan => ({ prov: s.prov, kab: s.kab, lokasi: s.lokasi });
const GAP = 12, PEEK = 60;
const mq = window.matchMedia("(max-width: 820px)");
const isMobile = () => mq.matches;

let wil: Wilayah;
let agg: KabAgregat | null = null;
let kejadian: KabKejadian | null = null;
let titik: KabTitik | null = null;
let lokasiNama: string | null = null;
let kabNames = new Map<string, Wilayah["kab"][number]>();
let provNames = new Map<string, string>();
let markersShown = false;
let booting = true;
let cekSorotUrl = false; // kejadian dari tautan: diperiksa setelah data kab/kota pertama dimuat

// ------------------------------------------------------------------ preferensi tampilan (per tata letak)
interface Ui { panel: boolean; tl: boolean; lg: boolean }
const uiKey = () => (isMobile() ? "psb-ui-m1" : "psb-ui-d1");
function loadUi(): Ui {
  const def: Ui = isMobile() ? { panel: false, tl: false, lg: false } : { panel: true, tl: true, lg: true };
  try { return { ...def, ...JSON.parse(localStorage.getItem(uiKey()) ?? "{}") }; } catch { return def; }
}
let ui = loadUi();
const saveUi = () => { try { localStorage.setItem(uiKey(), JSON.stringify(ui)); } catch { /* mode privat */ } };

// ------------------------------------------------------------------ kerangka
const app = document.getElementById("app")!;
const live = h("p", { class: "sr-only", "aria-live": "polite", id: "live" });
const toasts = new Toasts();
const srcBadge = h("span", { class: "src", tabindex: 0, "aria-label": "Data contoh" }, h("i", { "aria-hidden": "true" }), h("span", { class: "src-t" }, "Data contoh"));
const caption = h("p", { class: "hdr-sub" }, "Laporan kejadian bencana dari unggahan X berbahasa Indonesia");

// --- aksi header: bagikan & ekspor
const shareBtn = h("button", { type: "button", class: "hbtn", title: "Salin tautan ke tampilan ini (wilayah, filter, rentang, kejadian, lokasi)",
  "aria-label": "Bagikan Tampilan", onclick: () => void share() }, ico("link", 16), h("span", { class: "hbtn-t" }, "Bagikan Tampilan"));
const exportBtn = h("button", { type: "button", class: "hbtn", id: "export-btn", "aria-haspopup": "menu", "aria-expanded": "false", "aria-controls": "export-menu",
  "aria-label": "Ekspor", title: "Ekspor data atau peta", onclick: () => setMenu(exportBtn.getAttribute("aria-expanded") !== "true") },
  ico("download", 16), h("span", { class: "hbtn-t" }, "Ekspor"), ico("chevDown", 14, "hbtn-chev"));
const menuItem = (icon: Parameters<typeof ico>[0], title: string, sub: string, fn: () => void) =>
  h("button", { type: "button", role: "menuitem", class: "menu-i", tabindex: -1, onclick: () => { setMenu(false, true); fn(); } },
    ico(icon, 17), h("span", { class: "menu-t" }, h("b", {}, title), h("small", {}, sub)));
const menu = h("div", { class: "menu float-card", id: "export-menu", role: "menu", "aria-labelledby": "export-btn", hidden: true },
  menuItem("table", "Ekspor Data (CSV)", "Arsip .zip: tabel CSV ternormalisasi + manifest", () => void exportData()),
  menuItem("image", "Ekspor Peta (PNG)", "Peta terlihat, legenda, filter, dan keterangan", () => void exportMap()));
const header = h("header", { class: "hdr" },
  h("div", { class: "hdr-brand" }, h("span", { class: "mark", "aria-hidden": "true" }), h("div", { class: "hdr-text" }, h("h1", { class: "hdr-title" }, "Peta Situasi Bencana"), caption)),
  h("div", { class: "hdr-meta" }, srcBadge, shareBtn, h("div", { class: "hmenu" }, exportBtn, menu)));

function setMenu(open: boolean, focusBtn = false): void {
  exportBtn.setAttribute("aria-expanded", String(open));
  menu.hidden = !open;
  if (open) (menu.querySelector(".menu-i") as HTMLElement).focus();
  else if (focusBtn) exportBtn.focus();
}
menu.addEventListener("keydown", (e) => {
  const items = [...menu.querySelectorAll<HTMLElement>(".menu-i")];
  const i = items.indexOf(document.activeElement as HTMLElement);
  if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); items[(i + (e.key === "ArrowDown" ? 1 : -1) + items.length) % items.length].focus(); }
  else if (e.key === "Home" || e.key === "End") { e.preventDefault(); items[e.key === "Home" ? 0 : items.length - 1].focus(); }
  else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); setMenu(false, true); }
  else if (e.key === "Tab") setMenu(false);
});
document.addEventListener("pointerdown", (e) => { if (!menu.hidden && !(e.target as Element).closest(".hmenu")) setMenu(false); });

const toolbar = buildToolbar(store, (kode) => goKab(kode));
const busy = h("span", { class: "busy", role: "status", "aria-label": "Memuat data", hidden: true });
const crumbs = h("nav", { class: "crumbs", "aria-label": "Posisi geografis" });
const crumbsWrap = h("div", { class: "crumbs-wrap" }, crumbs, busy);
const mapEmpty = h("div", { class: "map-empty float-card", hidden: true });
const legend = buildLegend((open) => setUi({ lg: open }));
const timeline = new Timeline((dari, sampai) => store.set({ dari, sampai }), (open) => setUi({ tl: open }));

const headCtx = h("span", { class: "panel-ctx" });
const minBtn = h("button", { type: "button", class: "icon-btn panel-min", "aria-controls": "panel", onclick: (e: Event) => { e.stopPropagation(); setUi({ panel: !ui.panel }); } });
const headAsk = h("button", { type: "button", class: "head-ask", "aria-label": "Tanya AI — buka Asisten Situasi Bencana",
  onclick: (e: Event) => { e.stopPropagation(); openChat(); } }, ico("sparkle", 14), h("span", {}, "Tanya AI"));
const panelHead = h("div", { class: "panel-head" }, h("span", { class: "panel-grip", "aria-hidden": "true" }), headCtx,
  h("span", { class: "panel-tabs-slot" }), headAsk, minBtn);
panelHead.addEventListener("click", () => { if (isMobile()) setUi({ panel: !ui.panel }); });
const panel = new Panel({
  onKab: (k) => goKab(k),
  onProv: (p) => goProv(p),
  onTitik: (g) => store.set({ lokasi: g }),
  onSorot: (e) => store.set({ sorot: e }),
  onBack: () => store.set({ lokasi: null }),
  onReset: () => store.set({ jenis: new Set(JENIS), dari: null, sampai: null }),
  onAllDates: () => store.set({ dari: null, sampai: null }),
  onAllJenis: () => store.set({ jenis: new Set(JENIS) }),
  onAsk: (ev) => askEvent(ev),
  onTab: (t) => onTab(t),
}, panelHead);
const chat = new ChatView((scope, ev) => chatCtx(scope, ev), () => panel.setTab("detail", true));
panel.chatBox.append(chat.el);

const tabCtx = h("span", { class: "tab-ctx" });
const panelTab = h("button", { type: "button", class: "panel-tab float-card", "aria-controls": "panel", "aria-expanded": "false",
  onclick: () => setUi({ panel: true }) }, ico("panel", 16), h("span", { class: "tab-t" }, "Rincian"), tabCtx);
const fab = h("button", { type: "button", class: "fab-ai", "aria-label": "Tanya AI — buka Asisten Situasi Bencana", onclick: () => openChat() },
  ico("sparkle", 17), h("span", {}, "Tanya AI"));

const mapEl = h("div", { class: "map", id: "map", role: "application",
  "aria-label": "Peta kab/kota. Untuk navigasi papan ketik gunakan kolom pencarian wilayah atau daftar kab/kota di panel rincian." });
const ws = h("main", { class: "workspace", id: "workspace" }, mapEl, toolbar.el, crumbsWrap, mapEmpty, legend.el, timeline.el, panel.el, panelTab, fab, toasts.el);
const shareDlg = h("dialog", { class: "dlg float-card", "aria-labelledby": "share-t" });
app.append(header, ws, live, shareDlg);
app.removeAttribute("aria-busy");

const mapView = new MapView(mapEl, ws, {
  onKab: (k) => goKab(k),
  onTitik: (g) => store.set({ lokasi: g }),
  onBackground: () => { toolbar.closePopovers(); if (store.state.kab || store.state.prov) goKab(null); },
  onHome: () => { if (store.state.kab || store.state.prov) goKab(null); else void mapView.national(); },
});

const urlSync = new UrlSync(store, (st, invalid) => applyUrl(st, invalid));
if (import.meta.env.DEV) (window as unknown as { __psb: unknown }).__psb = { map: mapView.map, view: mapView, store, setChatService, chat };

// ------------------------------------------------------------------ tata letak mengambang
function pads(): Pad {
  const top = toolbar.el.offsetTop + toolbar.el.offsetHeight + GAP + crumbsWrap.offsetHeight + GAP;
  if (isMobile()) return { top, left: GAP, right: GAP + 44, bottom: (ui.panel ? panel.el.offsetHeight : PEEK) + GAP };
  return {
    top, left: GAP + 4,
    right: ui.panel ? panel.el.offsetWidth + GAP * 2 : GAP + 56,
    bottom: ui.tl ? timeline.height() + GAP * 2 : GAP * 2 + 8,
  };
}
function syncTop(): void { ws.style.setProperty("--tb-h", `${toolbar.el.offsetHeight}px`); }

function applyUi(): void {
  const mobile = isMobile();
  ws.classList.toggle("panel-collapsed", !ui.panel);
  ws.classList.toggle("tl-collapsed", !ui.tl);
  ws.classList.toggle("lg-collapsed", !ui.lg);
  legend.setOpen(ui.lg);
  timeline.setOpen(ui.tl);
  panel.el.inert = !ui.panel && !mobile;
  panel.body.inert = !ui.panel;
  panel.chatBox.inert = !ui.panel;
  panel.tablist.inert = !ui.panel;
  headAsk.inert = ui.panel || !mobile;
  panelTab.inert = ui.panel || mobile;
  fab.inert = ui.panel || mobile;
  panelTab.setAttribute("aria-expanded", String(ui.panel));
  minBtn.setAttribute("aria-expanded", String(ui.panel));
  const label = ui.panel ? "Sembunyikan panel" : "Tampilkan panel";
  minBtn.setAttribute("aria-label", label);
  minBtn.title = label;
  minBtn.replaceChildren(ico(mobile ? (ui.panel ? "chevDown" : "chevUp") : "chevRight", 16));
}

function setUi(patch: Partial<Ui>, mapMode: "none" | "pan" | "refit" = "refit"): void {
  if (isMobile()) { // di layar sempit legenda & linimasa saling bergantian agar peta tetap lapang
    if (patch.tl) patch.lg = false;
    if (patch.lg) patch.tl = false;
  }
  ui = { ...ui, ...patch };
  saveUi();
  applyUi();
  mapView.setPadding(pads(), mapMode);
}

new ResizeObserver(() => { syncTop(); mapView.setPadding(pads(), "none"); }).observe(toolbar.el);
window.addEventListener("resize", () => { mapView.invalidate(); mapView.setPadding(pads(), "none"); });
mq.addEventListener("change", () => { ui = loadUi(); applyUi(); mapView.invalidate(); mapView.setPadding(pads(), "none"); });
// papan ketik virtual (iOS tidak mendukung interactive-widget): angkat lembar bawah di atas papan ketik
const vv = window.visualViewport;
if (vv) {
  const onVV = () => { const kb = Math.max(0, window.innerHeight - vv.height - vv.offsetTop); ws.style.setProperty("--kb", `${kb > 80 ? Math.round(kb) : 0}px`); };
  vv.addEventListener("resize", onVV);
  vv.addEventListener("scroll", onVV);
}
syncTop();
applyUi();

// ------------------------------------------------------------------ navigasi
function goKab(kode: string | null): void {
  toolbar.closePopovers();
  const s = store.state;
  if (kode === s.kab && !s.lokasi && (kode || !s.prov)) return;
  store.set({ kab: kode, prov: kode ? kode.slice(0, 2) : null, lokasi: null, sorot: null });
}
function goProv(kode: string): void {
  toolbar.closePopovers();
  const s = store.state;
  if (s.prov === kode && !s.kab) return;
  store.set({ prov: kode, kab: null, lokasi: null, sorot: null });
}

function announce(t: string): void { live.textContent = ""; window.setTimeout(() => (live.textContent = t), 30); }

const kabNama = (k: string | null) => (k ? kabNames.get(k)?.nama ?? k : null);
const provNama = (p: string | null) => (p ? provNames.get(p) ?? p : null);

function context(): string {
  const s = store.state;
  if (s.lokasi && lokasiNama) return lokasiNama;
  if (s.kab) return kabNama(s.kab)!;
  if (s.prov) return `Provinsi ${provNama(s.prov)}`;
  return agg ? `${agg.ringkasan.jumlah_kejadian} kejadian · ${agg.ringkasan.jumlah_kab} kab/kota` : "Sebaran kejadian";
}
function renderContext(): void { const c = context(); tabCtx.textContent = c; headCtx.textContent = c; }

function renderCrumbs(): void {
  const s = store.state;
  const items: HTMLElement[] = [h("button", { type: "button", class: "crumb", onclick: () => goKab(null), "aria-current": store.view === "nasional" ? "page" : null }, "Indonesia")];
  if (s.prov) items.push(h("button", { type: "button", class: "crumb", "aria-current": store.view === "prov" ? "page" : null, onclick: () => goProv(s.prov!),
    title: `Tampilkan Provinsi ${provNama(s.prov)}` }, provNama(s.prov)));
  if (s.kab) items.push(h("button", { type: "button", class: "crumb", "aria-current": store.view === "kab" ? "page" : null, onclick: () => store.set({ lokasi: null }) }, kabNama(s.kab)));
  if (s.lokasi) items.push(h("span", { class: "crumb crumb--leaf", "aria-current": "page" }, lokasiNama ?? "Lokasi"));
  crumbs.replaceChildren(h("ol", {}, ...items.map((i) => h("li", {}, i))));
  renderContext();
}

const jenisText = (s: State) => (s.jenis.size === JENIS.length ? "Semua jenis" : s.jenis.size === 0 ? "Tidak ada jenis" : JENIS.filter((x) => s.jenis.has(x)).map((x) => LABEL_PENDEK[x]).join(", "));
const periodeText = (s: State) => (s.dari || s.sampai ? rentang(s.dari ?? wil.dataset.rentang.awal, s.sampai ?? wil.dataset.rentang.akhir)
  : `seluruh periode (${rentang(wil.dataset.rentang.awal, wil.dataset.rentang.akhir)})`);
function filterText(s: State): string {
  const d = s.dari || s.sampai ? rentang(s.dari ?? wil.dataset.rentang.awal, s.sampai ?? wil.dataset.rentang.akhir) : "seluruh periode";
  return `${jenisText(s)} | ${d}`;
}
const legendText = (s: State) => filterText(s);
const emptyCtx = () => ({ jenisKosong: store.state.jenis.size === 0, adaTanggal: !!(store.state.dari || store.state.sampai) });

function tlScope(s: State): TlScope {
  if (s.lokasi) { const n = lokasiNama ?? "lokasi terpilih"; return { label: n, detail: `Hanya laporan kejadian yang menyebut ${n}` }; }
  if (s.kab) { const n = kabNama(s.kab)!; return { label: n, detail: `Laporan kejadian di ${n}` }; }
  if (s.prov) { const n = `Provinsi ${provNama(s.prov)}`; return { label: n, detail: `Laporan kejadian di ${n}` }; }
  return { label: "Nasional", detail: "Seluruh laporan kejadian" };
}

// ------------------------------------------------------------------ pemuatan data
let pending = 0;
function loading<T>(p: Promise<T>): Promise<T> {
  pending++; busy.hidden = false;
  return p.finally(() => { if (--pending === 0) busy.hidden = true; });
}

async function loadAgregat(): Promise<void> {
  const s = store.state;
  try { agg = await loading(api.agregat(q(s))); } catch (e) { if (!isAbort(e)) showError(e); return; }
  const adaData = new Set(wil.kab.filter((k) => k.ada_data).map((k) => k.kode_kab));
  mapView.setCounts(new Map(agg.kab.map((r) => [r.kode_kab, r.jumlah_kejadian])), adaData);
  legend.update(legendText(s), !!s.kab);
  const empty = agg.ringkasan.jumlah_kejadian === 0;
  mapEmpty.hidden = !empty;
  if (empty) mapEmpty.replaceChildren(panel.empty(emptyCtx(), true));
  if (store.view === "nasional") panel.nasional(agg, wil, filterText(s), emptyCtx());
  else if (store.view === "kab" && kejadian) renderKab();
  renderContext();
}

async function loadHistogram(): Promise<void> {
  const s = store.state;
  try {
    const d = await api.histogram(q(s), cakupan(s));
    timeline.setData(d, tlScope(store.state));
  } catch (e) { if (!isAbort(e)) showError(e); }
}

async function loadProv(fresh: boolean): Promise<void> {
  const s = store.state;
  const p = s.prov!;
  if (fresh) {
    panel.skeleton(`prov:${p}`);
    void mapView.focusProv(p);
    legend.update(legendText(s), false);
  }
  try {
    const a = await loading(api.agregatProv(q(s), p));
    if (store.state.prov !== p || store.state.kab) return;
    panel.prov(a, wil, p, filterText(store.state), emptyCtx());
    renderContext();
    if (fresh) announce(`Provinsi ${provNama(p)}: ${a.ringkasan.jumlah_kejadian} kejadian.`);
  } catch (e) { if (!isAbort(e)) showError(e); }
}

function renderKab(): void {
  const s = store.state;
  if (!kejadian || store.view !== "kab") return;
  const row = agg?.kab.find((r) => r.kode_kab === s.kab);
  const k = kabNames.get(s.kab!);
  panel.kab(kejadian, titik, row ? row.jumlah_tweet : 0, k?.provinsi ?? "", s.sorot, emptyCtx(), !!k?.ada_data);
}

async function loadKab(fresh: boolean): Promise<void> {
  const s = store.state;
  const kode = s.kab!;
  if (fresh && !s.lokasi) panel.skeleton(`kab:${kode}`);
  const flight = fresh ? mapView.focusKab(kode) : Promise.resolve(true);
  let k: KabKejadian, t: KabTitik;
  try { [k, t] = await loading(Promise.all([api.kejadian(kode, q(s)), api.titik(kode, q(s))])); }
  catch (e) { if (!isAbort(e)) showError(e); return; }
  if (store.state.kab !== kode) return;
  kejadian = k; titik = t;
  if (store.state.sorot && !k.kejadian.some((x) => x.event_id === store.state.sorot)) {
    if (cekSorotUrl) urlSync.replace(() => store.set({ sorot: null }));
    else store.set({ sorot: null });
    if (cekSorotUrl) invalidToast(["kejadian"]);
    else announce("Kejadian yang disorot tidak sesuai filter baru; sorotan dihapus.");
  }
  cekSorotUrl = false;
  if (store.view === "kab") {
    try { renderKab(); } catch (e) { showError(e); } // galat tampilan panel tidak menghentikan penanda peta
  }
  if (store.state.lokasi && !lokasiNama) {
    lokasiNama = t.titik.find((x) => x.gazetteer_id === store.state.lokasi)?.nama ?? null;
    if (lokasiNama) { renderCrumbs(); timeline.setScope(tlScope(store.state)); }
  }
  const ok = await flight;
  if (!ok || store.state.kab !== kode) return;
  mapView.setTitik(t.titik, fresh || !markersShown);
  markersShown = true;
  const sor = store.state.sorot ? k.kejadian.find((x) => x.event_id === store.state.sorot) : null;
  mapView.setSorot(sor ? sor.lokasi_ids : null);
  mapView.setSelectedTitik(store.state.lokasi);
  if (fresh && store.state.lokasi) mapView.focusTitik(store.state.lokasi); // tautan/riwayat langsung ke lokasi
  legend.update(legendText(store.state), true);
  if (fresh) announce(`${k.nama}: ${k.kejadian.length} kejadian, ${t.titik.length} lokasi.`);
}

async function loadLokasi(): Promise<void> {
  const s = store.state;
  const gid = s.lokasi!;
  panel.skeleton(`lokasi:${gid}`);
  try {
    const r = await loading(api.ringkasan(gid, q(s)));
    if (store.state.lokasi !== gid) return;
    lokasiNama = r.lokasi.nama;
    const kl = r.lokasi.kode_kab_lokasi;
    panel.lokasi(r, kabNama(store.state.kab), store.state.kab, kl ? kabNama(kl) : null);
    renderCrumbs();
    timeline.setScope(tlScope(store.state));
    chat.refresh();
    announce(`${r.lokasi.nama}: ${r.jumlah_laporan} laporan dari ${r.jumlah_tweet} tweet.`);
  } catch (e) {
    if (isAbort(e)) return;
    if (e instanceof ApiError && e.status === 404 && store.state.lokasi === gid) {
      urlSync.replace(() => store.set({ lokasi: null }));
      invalidToast(["lokasi"]);
      return;
    }
    showError(e);
  }
}

function showError(e: unknown): void {
  console.warn(e);
  panel.error(e instanceof Error ? e.message : "Kesalahan tidak diketahui", () => refresh());
}

function geoLoad(fresh: boolean): void {
  const s = store.state;
  if (s.kab) void loadKab(fresh);
  else if (s.prov) void loadProv(fresh);
  else {
    if (fresh && !booting) void mapView.national();
    legend.update(legendText(s), false);
    if (agg) panel.nasional(agg, wil, filterText(s), emptyCtx());
    if (fresh && !booting) announce("Peta nasional");
  }
  if (s.lokasi) void loadLokasi();
}

function refresh(): void {
  void loadAgregat();
  void loadHistogram();
  geoLoad(false);
}

// ------------------------------------------------------------------ reaksi state
store.on((s, prev) => {
  toolbar.sync();
  timeline.setRange(s.dari, s.sampai);
  document.body.dataset.view = store.view;
  panel.setDetailLabel(store.view);
  if (booting) { renderCrumbs(); return; }
  const fChanged = filterKey(s) !== filterKey(prev);
  const jChanged = [...s.jenis].sort().join() !== [...prev.jenis].sort().join();
  const kabChanged = s.kab !== prev.kab, provChanged = s.prov !== prev.prov, lokChanged = s.lokasi !== prev.lokasi;
  if (lokChanged) lokasiNama = s.lokasi ? titik?.titik.find((x) => x.gazetteer_id === s.lokasi)?.nama ?? null : null;
  renderCrumbs();
  if (fChanged) mapView.clearHover();

  if (kabChanged || provChanged) {
    kejadian = null; titik = null; markersShown = false;
    if (chat.eventRef) chat.setEvent(null); // konteks kejadian milik wilayah sebelumnya
    void loadHistogram();
    if (s.kab) void loadKab(true);
    else if (s.prov) void loadProv(true);
    else geoLoad(true);
  } else if (lokChanged || jChanged) void loadHistogram();
  if (fChanged) {
    void loadAgregat();
    if (!kabChanged && !provChanged) { if (s.kab) void loadKab(false); else if (s.prov) void loadProv(false); }
    if (s.lokasi && !lokChanged) void loadLokasi();
  }
  if (lokChanged) {
    mapView.setSelectedTitik(s.lokasi);
    if (s.lokasi) {
      if (!ui.panel) setUi({ panel: true }, "none"); // memilih lokasi = meminta rincian
      panel.setTab("detail");
      mapView.setPadding(pads(), "none");
      mapView.focusTitik(s.lokasi);
      void loadLokasi();
    } else if (s.kab && !kabChanged) renderKab();
  }
  if (s.sorot !== prev.sorot) {
    panel.setSorot(s.sorot);
    const ev = s.sorot ? kejadian?.kejadian.find((x) => x.event_id === s.sorot) : null;
    mapView.setSorot(ev ? ev.lokasi_ids : null);
  }
  chat.refresh();
});

window.addEventListener("keydown", (e) => {
  if (e.key !== "Escape" || e.defaultPrevented) return;
  if ((e.target as HTMLElement).closest("input, textarea, .dr, .menu, dialog, .chat")) return;
  if (toolbar.isPopoverOpen()) { toolbar.closePopovers(); return; }
  const s = store.state;
  if (s.sorot) store.set({ sorot: null });
  else if (s.lokasi) store.set({ lokasi: null });
  else if (s.kab) goProv(s.kab.slice(0, 2));
  else if (s.prov) goKab(null);
});

// ------------------------------------------------------------------ URL (tautan berbagi, Back/Forward)
const PARAM_LABEL: Record<string, string> = {
  jenis: "jenis bencana", dari: "tanggal awal", sampai: "tanggal akhir", rentang: "rentang tanggal",
  prov: "provinsi", kab: "kab/kota", lokasi: "lokasi", kejadian: "kejadian",
};
function invalidToast(invalid: string[]): void {
  if (!invalid.length) return;
  const names = [...new Set(invalid.map((x) => PARAM_LABEL[x] ?? x))].join(", ");
  toasts.show("Sebagian parameter tautan tidak valid dan diabaikan.", { kind: "info", detail: `Diabaikan: ${names}.`, ms: 6500 });
}

/** Parameter URL -> state yang sah (tidak dikenal/di luar data = diabaikan & dilaporkan). */
function validateUrl(p: Partial<UrlState>, invalid: string[]): State {
  const out: State = { jenis: p.jenis ?? new Set(JENIS), dari: null, sampai: null, prov: null, kab: null, lokasi: null, sorot: null };
  const aw = wil.dataset.rentang.awal, ak = wil.dataset.rentang.akhir;
  let dari = p.dari ?? null, sampai = p.sampai ?? null;
  if (aw && ak && ((dari && dari > ak) || (sampai && sampai < aw))) { invalid.push("rentang"); dari = sampai = null; }
  if (aw && dari && dari <= aw) dari = null;   // dijepit ke domain data; batas domain = tanpa batas
  if (ak && sampai && sampai >= ak) sampai = null;
  out.dari = dari; out.sampai = sampai;
  if (p.kab) {
    if (kabNames.has(p.kab)) { out.kab = p.kab; out.prov = p.kab.slice(0, 2); if (p.prov && p.prov !== out.prov) invalid.push("prov"); }
    else invalid.push("kab");
  }
  if (!out.kab && p.prov) { if (provNames.has(p.prov)) out.prov = p.prov; else invalid.push("prov"); }
  if (p.lokasi) out.lokasi = p.lokasi; // keberadaannya diperiksa ke backend saat dimuat
  if (p.sorot) { if (out.kab) out.sorot = p.sorot; else invalid.push("kejadian"); }
  return out;
}

function applyUrl(st: Partial<UrlState>, invalid: string[]): void {
  const next = validateUrl(st, invalid);
  if (next.lokasi && !next.kab) { next.lokasi = null; invalid.push("lokasi"); }
  if (next.sorot) {
    const samaData = next.kab === store.state.kab && filterKey(next) === filterKey(store.state);
    if (!samaData) cekSorotUrl = true; // diperiksa setelah data kab/kota baru dimuat
    else if (kejadian && !kejadian.kejadian.some((x) => x.event_id === next.sorot)) { next.sorot = null; invalid.push("kejadian"); }
  }
  store.set(next);
  invalidToast(invalid);
}

// ------------------------------------------------------------------ bagikan & ekspor
function wilayahLabel(s: State): string {
  if (s.kab) { const k = kabNames.get(s.kab); return k ? `${k.nama}, ${k.provinsi}` : s.kab; }
  if (s.prov) return `Provinsi ${provNama(s.prov)}`;
  return "Indonesia";
}
const slugOf = (t: string) => t.toLowerCase().normalize("NFKD").replace(/[^\w\s-]/g, "").trim().replace(/[\s_]+/g, "-").slice(0, 60) || "peta";

async function share(): Promise<void> {
  const url = urlSync.shareUrl();
  try {
    if (!navigator.clipboard?.writeText) throw new Error("Clipboard API tidak tersedia");
    await navigator.clipboard.writeText(url);
    toasts.show("Tautan tampilan disalin.", { kind: "ok", detail: "Tautan memuat wilayah, filter jenis, rentang tanggal, kejadian, dan lokasi yang dipilih." });
  } catch {
    openShareDialog(url);
  }
}

function openShareDialog(url: string): void {
  const input = h("input", { class: "dlg-input", type: "text", readonly: true, value: url, "aria-label": "Tautan tampilan" });
  shareDlg.replaceChildren(
    h("h2", { class: "dlg-t", id: "share-t" }, "Salin tautan tampilan"),
    h("p", { class: "dlg-d" }, "Peramban tidak mengizinkan penyalinan otomatis. Pilih tautan di bawah lalu salin secara manual (Ctrl+C / ⌘C)."),
    input,
    h("div", { class: "dlg-acts" },
      h("button", { type: "button", class: "btn btn--ghost", onclick: () => { input.focus(); input.select(); } }, ico("copy", 15), "Pilih tautan"),
      h("button", { type: "button", class: "btn", onclick: () => shareDlg.close() }, "Tutup")));
  shareDlg.showModal();
  input.focus();
  input.select();
}

async function exportData(): Promise<void> {
  const s = store.state;
  const t = toasts.show("Menyiapkan ekspor data…", { kind: "info", ms: 0 });
  try {
    const r = await downloadData(api.eksporUrl(q(s), cakupan(s)));
    t.update("Data diekspor.", { kind: "ok", detail: `${r.filename} — tabel CSV (UTF-8) dan manifest.json. Data dari laporan media sosial, bukan data resmi BNPB.`, ms: 6500 });
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) t.update("Tidak ada data untuk diekspor.", { kind: "info", detail: e.message, ms: 6000 });
    else t.update("Ekspor data gagal.", { kind: "err", detail: e instanceof Error ? e.message : undefined, action: { label: "Coba lagi", fn: () => void exportData() } });
  }
}

/** Seluruh kanvas peta. Panel, asisten, dan kontrol mengambang tidak digambar, sehingga bagian peta yang
 * tertutup panel (mis. ujung timur Indonesia pada tampilan nasional) tetap ikut terekspor. */
function cropRect(): Crop {
  const c = mapEl.getBoundingClientRect();
  return { x: 0, y: 0, w: c.width, h: c.height };
}

async function exportMap(): Promise<void> {
  const s = store.state;
  const t = toasts.show("Menyiapkan gambar peta…", { kind: "info", ms: 0 });
  try {
    const sor = s.sorot ? kejadian?.kejadian.find((x) => x.event_id === s.sorot) : null;
    const wl = wilayahLabel(s);
    const res = await exportPng(mapView, cropRect(), {
      wilayah: wl, periode: periodeText(s), jenis: jenisText(s), sorot: sor ? sor.nama : null, lokasi: s.lokasi ? lokasiNama : null,
      kabMode: !!s.kab, contoh: wil.dataset.contoh, dataset: wil.dataset.label, slug: slugOf(s.lokasi && lokasiNama ? lokasiNama : s.kab ? kabNama(s.kab)! : s.prov ? `provinsi ${provNama(s.prov)}` : "indonesia"),
    });
    saveBlob(res.blob, res.filename);
    t.update("Peta diekspor (PNG).", { kind: "ok", ms: 7000,
      detail: res.peta === "lengkap" ? res.filename : `${res.filename} — peta dasar OpenStreetMap tidak disertakan karena server ubin tidak mengizinkan akses lintas-origin (CORS). Hal ini dicantumkan pada gambar.` });
  } catch (e) {
    t.update("Ekspor peta gagal.", { kind: "err", detail: e instanceof Error ? e.message : undefined, action: { label: "Coba lagi", fn: () => void exportMap() } });
  }
}

// ------------------------------------------------------------------ asisten
function onTab(tab: PanelTab): void {
  ws.classList.toggle("tab-chat", tab === "chat");
  if (tab === "chat") chat.refresh();
}
function openChat(): void {
  if (!ui.panel) setUi({ panel: true }, "none");
  panel.setTab("chat");
  chat.focusInput();
}
function askEvent(ev: EventRef): void {
  chat.setEvent(ev);
  openChat();
}

function chatCtx(scope: ChatScope, ev: EventRef | null): ChatCtxInfo {
  const s = store.state;
  if (scope === "semua" || !wil)
    return {
      ctx: { scope: "semua", wilayah: { tingkat: "nasional", kode_prov: null, kode_kab: null, gazetteer_id: null, nama: null }, filter: { jenis: null, dari: null, sampai: null }, event_id: null },
      label: "Seluruh Indonesia | semua jenis | seluruh periode", terpilih: undefined,
      examples: ["Wilayah mana yang paling banyak melaporkan kejadian bencana?", "Kejadian apa yang paling baru dilaporkan?", "Kebutuhan apa yang paling sering disebut dalam laporan?"],
    };
  const view = store.view;
  const nama = view === "lokasi" ? lokasiNama ?? "lokasi terpilih" : view === "kab" ? kabNama(s.kab)! : view === "prov" ? `Provinsi ${provNama(s.prov)}` : "Indonesia";
  const ctx = {
    scope, event_id: ev?.event_id ?? null,
    wilayah: { tingkat: view, kode_prov: s.prov, kode_kab: s.kab, gazetteer_id: s.lokasi, nama },
    filter: { jenis: s.jenis.size === JENIS.length ? null : JENIS.filter((j) => s.jenis.has(j)), dari: s.dari, sampai: s.sampai },
  } satisfies ChatCtxInfo["ctx"];
  const examples = ev
    ? [`Apa saja dampak yang dilaporkan untuk ${ev.nama}?`, `Kebutuhan apa yang disebut dalam laporan ${ev.nama}?`, `Lembaga apa saja yang menangani ${ev.nama}?`]
    : view === "lokasi" ? [`Apa yang dilaporkan tentang ${nama}?`, `Kejadian apa saja yang menyebut ${nama}?`, `Apakah ada kebutuhan bantuan di ${nama}?`]
    : view === "kab" ? [`Kejadian apa saja yang dilaporkan di ${nama}?`, `Dampak apa saja yang dilaporkan di ${nama}?`, `Kebutuhan apa yang dilaporkan warga ${nama}?`]
    : view === "prov" ? [`Kab/kota mana di ${nama} yang paling banyak melaporkan kejadian?`, `Kejadian apa saja yang terjadi di ${nama}?`, `Kebutuhan apa yang paling sering dilaporkan di ${nama}?`]
    : ["Wilayah mana yang paling banyak melaporkan kejadian bencana?", "Kejadian apa yang paling baru dilaporkan?", "Kebutuhan apa yang paling sering disebut dalam laporan?"];
  return { ctx, label: `${nama} | ${filterText(s)}`, examples,
    terpilih: view === "lokasi" ? "Lokasi ini" : view === "kab" ? "Kab/kota ini" : view === "prov" ? "Provinsi ini" : "Konteks terpilih" };
}

// ------------------------------------------------------------------ mulai
async function boot(): Promise<void> {
  panel.skeleton("boot");
  // tampilan awal: seluruh Indonesia sesuai ruang peta yang benar-benar terlihat
  mapView.setPadding(pads(), "none");
  void mapView.national(false);
  try {
    const [w, kab, prov] = await Promise.all([api.wilayah(), api.geo("kabkota"), api.geo("provinsi")]);
    wil = w;
    if (w.api_versi !== API_VERSI) toasts.show("Versi backend tidak cocok dengan frontend.", { kind: "info", ms: 9000, detail: PESAN_VERSI });
    setChatService(demoChatService()); // ringkasan dummy sampai endpoint GraphRAG tersedia
    kabNames = new Map(w.kab.map((k) => [k.kode_kab, k]));
    provNames = new Map(w.provinsi.map((p) => [p.kode_prov, p.nama]));
    toolbar.setWilayah(w);
    srcBadge.hidden = !w.dataset.contoh;
    srcBadge.title = w.dataset.keterangan ?? "";
    if (w.dataset.contoh) caption.textContent = "Data contoh ilustratif — bukan pemantauan bencana nyata";
    mapView.setGeo(kab, prov);
    timeline.setDomain(w.dataset.rentang.awal, w.dataset.rentang.akhir);
    timeline.setRange(null, null);
    toolbar.date.setDomain(w.dataset.rentang.awal, w.dataset.rentang.akhir);

    // status awal dari tautan (bila ada)
    const parsed = parseUrl(location.search);
    const invalid = [...parsed.invalid];
    const init = validateUrl(parsed.state, invalid);
    if (init.lokasi && !init.kab) { // tautan hanya berisi lokasi: kab/kota diturunkan dari gazetteer lokasi
      try {
        const r = await api.ringkasan(init.lokasi, q(init));
        const kk = r.lokasi.kode_kab_lokasi;
        if (kk && kabNames.has(kk)) { init.kab = kk; init.prov = kk.slice(0, 2); } else { init.lokasi = null; invalid.push("lokasi"); }
      } catch { init.lokasi = null; invalid.push("lokasi"); }
    }
    cekSorotUrl = !!init.sorot;
    store.set(init); // booting: reaksi hanya menyinkronkan kontrol
    booting = false;
    renderCrumbs();
    document.body.dataset.view = store.view;
    if (init.lokasi && !ui.panel) setUi({ panel: true }, "none");
    const first = [loadAgregat(), loadHistogram()];
    if (init.kab) void loadKab(true);
    else if (init.prov) void loadProv(true);
    if (init.lokasi) void loadLokasi();
    urlSync.start();
    invalidToast(invalid);
    await Promise.all(first);
    document.body.dataset.ready = "true";
  } catch (e) {
    booting = false;
    panel.error(e instanceof Error ? e.message : "Gagal memuat", () => location.reload());
  }
}
void boot();
