import "@fontsource-variable/plus-jakarta-sans";
import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/map.css";
import "./styles/panel.css";
import "./styles/timeline.css";

import { api, isAbort, type Query } from "./api";
import { h } from "./dom";
import { rentang } from "./format";
import { JENIS, LABEL_PENDEK } from "./jenis";
import { buildLegend } from "./map/legend";
import { MapView, type Pad } from "./map/map";
import { filterKey, Store, type State } from "./store";
import type { KabAgregat, KabKejadian, KabTitik, Wilayah } from "./types";
import { buildToolbar } from "./ui/filters";
import { ico } from "./ui/icons";
import { Panel } from "./ui/panel";
import { Timeline } from "./ui/timeline";

const store = new Store();
const q = (s: State): Query => ({ jenis: s.jenis, dari: s.dari, sampai: s.sampai });
const GAP = 12, PEEK = 60;
const mq = window.matchMedia("(max-width: 820px)");
const isMobile = () => mq.matches;

let wil: Wilayah;
let agg: KabAgregat | null = null;
let kejadian: KabKejadian | null = null;
let titik: KabTitik | null = null;
let lokasiNama: string | null = null;
let kabNames = new Map<string, Wilayah["kab"][number]>();
let markersShown = false;

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
const srcBadge = h("span", { class: "src", tabindex: 0 }, h("i", { "aria-hidden": "true" }), h("span", { class: "src-t" }, "Data contoh"));
const caption = h("p", { class: "hdr-sub" }, "Laporan kejadian bencana dari unggahan X berbahasa Indonesia");
const header = h("header", { class: "hdr" },
  h("div", { class: "hdr-brand" }, h("span", { class: "mark", "aria-hidden": "true" }), h("div", { class: "hdr-text" }, h("h1", { class: "hdr-title" }, "Peta Situasi Bencana"), caption)),
  h("div", { class: "hdr-meta" }, srcBadge));

const toolbar = buildToolbar(store, (kode) => goKab(kode));
const busy = h("span", { class: "busy", role: "status", "aria-label": "Memuat data", hidden: true });
const crumbs = h("nav", { class: "crumbs", "aria-label": "Posisi geografis" });
const crumbsWrap = h("div", { class: "crumbs-wrap" }, crumbs, busy);
const mapEmpty = h("div", { class: "map-empty float-card", hidden: true });
const legend = buildLegend((open) => setUi({ lg: open }));
const timeline = new Timeline((dari, sampai) => store.set({ dari, sampai }), (open) => setUi({ tl: open }));

const headCtx = h("span", { class: "panel-ctx" });
const minBtn = h("button", { type: "button", class: "icon-btn panel-min", "aria-controls": "panel", onclick: (e: Event) => { e.stopPropagation(); setUi({ panel: !ui.panel }); } });
const panelHead = h("div", { class: "panel-head" }, h("span", { class: "panel-grip", "aria-hidden": "true" }), headCtx, minBtn);
panelHead.addEventListener("click", () => { if (isMobile()) setUi({ panel: !ui.panel }); });
const panel = new Panel({
  onKab: (k) => goKab(k),
  onTitik: (g) => store.set({ lokasi: g }),
  onSorot: (e) => store.set({ sorot: e }),
  onBack: () => store.set({ lokasi: null }),
  onReset: () => store.set({ jenis: new Set(JENIS), dari: null, sampai: null }),
  onAllDates: () => store.set({ dari: null, sampai: null }),
  onAllJenis: () => store.set({ jenis: new Set(JENIS) }),
}, panelHead);
const tabCtx = h("span", { class: "tab-ctx" });
const panelTab = h("button", { type: "button", class: "panel-tab float-card", "aria-controls": "panel", "aria-expanded": "false",
  onclick: () => setUi({ panel: true }) }, ico("panel", 16), h("span", { class: "tab-t" }, "Rincian"), tabCtx);

const mapEl = h("div", { class: "map", id: "map", role: "application",
  "aria-label": "Peta kab/kota. Untuk navigasi papan ketik gunakan kolom pencarian wilayah atau daftar kab/kota di panel rincian." });
const ws = h("main", { class: "workspace", id: "workspace" }, mapEl, toolbar.el, crumbsWrap, mapEmpty, legend.el, timeline.el, panel.el, panelTab);
app.append(header, ws, live);
app.removeAttribute("aria-busy");

const mapView = new MapView(mapEl, ws, {
  onKab: (k) => goKab(k),
  onTitik: (g) => store.set({ lokasi: g }),
  onBackground: () => { toolbar.closePopovers(); if (store.state.kab) goKab(null); },
  onHome: () => { if (store.state.kab) goKab(null); else void mapView.national(); },
});
if (import.meta.env.DEV) (window as unknown as { __psb: unknown }).__psb = { map: mapView.map, store };

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
  panelTab.inert = ui.panel || mobile;
  panelTab.setAttribute("aria-expanded", String(ui.panel));
  minBtn.setAttribute("aria-expanded", String(ui.panel));
  const label = ui.panel ? "Sembunyikan panel rincian" : "Tampilkan panel rincian";
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
syncTop();
applyUi();

// ------------------------------------------------------------------ navigasi
function goKab(kode: string | null): void {
  toolbar.closePopovers();
  if (kode === store.state.kab && !store.state.lokasi) return;
  store.set({ kab: kode, lokasi: null, sorot: null });
}

function announce(t: string): void { live.textContent = ""; window.setTimeout(() => (live.textContent = t), 30); }

function context(): string {
  const s = store.state;
  if (s.lokasi && lokasiNama) return lokasiNama;
  if (s.kab) return kabNames.get(s.kab)?.nama ?? s.kab;
  return agg ? `${agg.ringkasan.jumlah_kejadian} kejadian · ${agg.ringkasan.jumlah_kab} kab/kota` : "Sebaran kejadian";
}
function renderContext(): void { const c = context(); tabCtx.textContent = c; headCtx.textContent = c; }

function renderCrumbs(): void {
  const s = store.state;
  const items: HTMLElement[] = [h("button", { type: "button", class: "crumb", onclick: () => goKab(null), "aria-current": !s.kab ? "page" : null }, "Indonesia")];
  if (s.kab) {
    const k = kabNames.get(s.kab);
    if (k?.provinsi) items.push(h("span", { class: "crumb crumb--static" }, k.provinsi));
    items.push(h("button", { type: "button", class: "crumb", "aria-current": !s.lokasi ? "page" : null, onclick: () => store.set({ lokasi: null }) }, k?.nama ?? s.kab));
  }
  if (s.lokasi) items.push(h("span", { class: "crumb crumb--leaf", "aria-current": "page" }, lokasiNama ?? "Lokasi"));
  crumbs.replaceChildren(h("ol", {}, ...items.map((i) => h("li", {}, i))));
  renderContext();
}

function filterText(s: State): string {
  const j = s.jenis.size === JENIS.length ? "Semua jenis" : s.jenis.size === 0 ? "Tidak ada jenis" : [...s.jenis].map((x) => LABEL_PENDEK[x]).join(", ");
  const d = s.dari || s.sampai ? rentang(s.dari ?? wil.dataset.rentang.awal, s.sampai ?? wil.dataset.rentang.akhir) : "seluruh periode";
  return `${j} · ${d}`;
}
const legendText = (s: State) => filterText(s);
const emptyCtx = () => ({ jenisKosong: store.state.jenis.size === 0, adaTanggal: !!(store.state.dari || store.state.sampai) });

// ------------------------------------------------------------------ pemuatan data
let pending = 0;
function loading<T>(p: Promise<T>): Promise<T> {
  pending++; busy.hidden = false;
  return p.finally(() => { if (--pending === 0) busy.hidden = true; });
}

async function loadAgregat(): Promise<void> {
  const s = store.state;
  try { agg = await loading(api.agregat(q(s))); } catch (e) { if (!isAbort(e)) showError(e); return; }
  const cakupan = new Set(wil.kab.filter((k) => k.ada_data).map((k) => k.kode_kab));
  mapView.setCounts(new Map(agg.kab.map((r) => [r.kode_kab, r.jumlah_kejadian])), cakupan);
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
    const d = await api.histogram(q(s), s.kab);
    timeline.setData(d, s.kab ? kabNames.get(s.kab)?.nama ?? s.kab : "Seluruh wilayah");
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
  if (fresh) panel.skeleton(`kab:${kode}`);
  const flight = fresh ? mapView.focusKab(kode) : Promise.resolve(true);
  let k: KabKejadian, t: KabTitik;
  try { [k, t] = await loading(Promise.all([api.kejadian(kode, q(s)), api.titik(kode, q(s))])); }
  catch (e) { if (!isAbort(e)) showError(e); return; }
  if (store.state.kab !== kode) return;
  kejadian = k; titik = t;
  if (store.state.sorot && !k.kejadian.some((x) => x.event_id === store.state.sorot)) {
    store.set({ sorot: null });
    announce("Kejadian yang disorot tidak sesuai filter baru; sorotan dihapus.");
  }
  if (store.view === "kab") renderKab();
  const ok = await flight;
  if (!ok || store.state.kab !== kode) return;
  mapView.setTitik(t.titik, fresh || !markersShown);
  markersShown = true;
  const sor = store.state.sorot ? k.kejadian.find((x) => x.event_id === store.state.sorot) : null;
  mapView.setSorot(sor ? sor.lokasi_ids : null);
  mapView.setSelectedTitik(store.state.lokasi);
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
    panel.lokasi(r, s.kab ? kabNames.get(s.kab)?.nama ?? null : null, s.kab);
    renderCrumbs();
    announce(`${r.lokasi.nama}: ${r.jumlah_laporan} laporan dari ${r.jumlah_tweet} tweet.`);
  } catch (e) { if (!isAbort(e)) showError(e); }
}

function showError(e: unknown): void {
  console.warn(e);
  panel.error(e instanceof Error ? e.message : "Kesalahan tidak diketahui", () => refresh());
}

function refresh(): void {
  const s = store.state;
  void loadAgregat();
  void loadHistogram();
  if (s.kab) void loadKab(false);
  if (s.lokasi) void loadLokasi();
}

// ------------------------------------------------------------------ reaksi state
store.on((s, prev) => {
  toolbar.sync();
  timeline.setRange(s.dari, s.sampai);
  const fChanged = filterKey(s) !== filterKey(prev);
  const kabChanged = s.kab !== prev.kab;
  const lokChanged = s.lokasi !== prev.lokasi;
  if (lokChanged && !s.lokasi) lokasiNama = null;
  if (lokChanged && s.lokasi) lokasiNama = titik?.titik.find((x) => x.gazetteer_id === s.lokasi)?.nama ?? null;
  renderCrumbs();
  document.body.dataset.view = store.view;
  if (fChanged) mapView.clearHover();

  if (kabChanged) {
    kejadian = null; titik = null; markersShown = false;
    void loadHistogram();
    if (s.kab) void loadKab(true);
    else {
      void mapView.national();
      legend.update(legendText(s), false);
      if (agg) panel.nasional(agg, wil, filterText(s), emptyCtx());
      announce("Peta nasional");
    }
  }
  if (fChanged) {
    void loadAgregat();
    if (!kabChanged) void loadHistogram();
    if (s.kab && !kabChanged) void loadKab(false);
    if (s.lokasi && !lokChanged) void loadLokasi();
  }
  if (lokChanged) {
    mapView.setSelectedTitik(s.lokasi);
    if (s.lokasi) {
      if (!ui.panel) setUi({ panel: true }, "none"); // memilih lokasi = meminta rincian
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
});

window.addEventListener("keydown", (e) => {
  if (e.key !== "Escape" || (e.target as HTMLElement).closest("input, .dr")) return;
  if (toolbar.isPopoverOpen()) { toolbar.closePopovers(); return; }
  const s = store.state;
  if (s.sorot) store.set({ sorot: null });
  else if (s.lokasi) store.set({ lokasi: null });
  else if (s.kab) goKab(null);
});

// ------------------------------------------------------------------ mulai
async function boot(): Promise<void> {
  panel.skeleton("boot");
  // tampilan awal: seluruh Indonesia sesuai ruang peta yang benar-benar terlihat
  mapView.setPadding(pads(), "none");
  void mapView.national(false);
  try {
    const [w, kab, prov] = await Promise.all([api.wilayah(), api.geo("kabkota"), api.geo("provinsi")]);
    wil = w;
    kabNames = new Map(w.kab.map((k) => [k.kode_kab, k]));
    toolbar.setWilayah(w);
    srcBadge.hidden = !w.dataset.contoh;
    srcBadge.title = w.dataset.keterangan ?? "";
    if (w.dataset.contoh) caption.textContent = "Data contoh ilustratif — bukan pemantauan bencana nyata";
    mapView.setGeo(kab, prov);
    timeline.setDomain(w.dataset.rentang.awal, w.dataset.rentang.akhir);
    timeline.setRange(null, null);
    toolbar.date.setDomain(w.dataset.rentang.awal, w.dataset.rentang.akhir);
    renderCrumbs();
    toolbar.sync();
    document.body.dataset.view = "nasional";
    await Promise.all([loadAgregat(), loadHistogram()]);
    document.body.dataset.ready = "true";
  } catch (e) {
    panel.error(e instanceof Error ? e.message : "Gagal memuat", () => location.reload());
  }
}
void boot();
