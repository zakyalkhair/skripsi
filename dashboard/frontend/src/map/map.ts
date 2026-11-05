import L from "./leaflet";
import "leaflet.markercluster";
import "leaflet/dist/leaflet.css";
import "leaflet.markercluster/dist/MarkerCluster.css";
import type { Titik } from "../types";
import { esc, reducedMotion } from "../dom";
import { angka } from "../format";
import { iconSvg } from "../ui/icons";
import { kelasOf } from "./legend";
import { markerAria, markerHtml, markerKey, markerTooltip } from "./marker";
import { MapTip } from "./tip";

/** Batas geografis Indonesia (Sabang–Merauke, Miangas–Rote) untuk tampilan awal. */
export const INDONESIA: L.LatLngBoundsLiteral = [[-11.1, 94.8], [6.2, 141.1]];
/** Tambahan zoom tampilan nasional di atas zoom yang muat penuh di area terlihat. */
const ZOOM_NASIONAL_EKSTRA = 0.5;

/** Zoom sasaran saat memilih penanda, menurut tingkat lokasi (cukup dekat, konteks tetap terlihat). */
const ZOOM_TITIK: Record<string, number> = { desa: 12.5, jembatan: 13, bangunan: 13, jalan: 12.5, kecamatan: 12, gunung: 11.5 };

export interface MapHandlers {
  onKab(kode: string): void;
  onTitik(gid: string): void;
  onBackground(): void;
  onHome(): void;
}
export interface Pad { top: number; right: number; bottom: number; left: number }

interface KabProps { kode_kab: string; nama: string; provinsi: string }
type KabLayer = L.Path & { feature: GeoJSON.Feature<GeoJSON.Geometry, KabProps>; getBounds(): L.LatLngBounds };
type Rec = { m: L.Marker; key: string; t: Titik };

export class MapView {
  readonly map: L.Map;
  private tip: MapTip;
  private kabLayers = new Map<string, KabLayer>();
  private hoverLayer: L.GeoJSON;
  private selHalo: L.GeoJSON;
  private selLine: L.GeoJSON;
  private hoverKab: string | null = null;
  private moving = false;
  private counts = new Map<string, number>();
  private cakupan = new Set<string>();
  private selectedKab: string | null = null;
  private cluster: L.MarkerClusterGroup;
  private markers = new Map<string, Rec>();
  private sorot: Set<string> | null = null;
  private selectedTitik: string | null = null;
  private flightToken = 0;
  private pad: Pad = { top: 16, right: 16, bottom: 16, left: 16 };
  private bgTimer = 0;
  private leaveTimer = 0;
  private zoomIn!: HTMLButtonElement;
  private zoomOut!: HTMLButtonElement;

  constructor(el: HTMLElement, tipHost: HTMLElement, private h: MapHandlers) {
    const rm = reducedMotion();
    this.map = L.map(el, {
      zoomSnap: 0.25, zoomDelta: 0.5, wheelPxPerZoomLevel: 110, minZoom: 4, maxZoom: 16, zoomControl: false,
      attributionControl: true, maxBounds: [[-24, 78], [20, 158]], maxBoundsViscosity: 0.7,
      fadeAnimation: !rm, zoomAnimation: !rm, markerZoomAnimation: !rm, inertiaDeceleration: 2600,
    });
    this.tip = new MapTip(tipHost);
    this.map.attributionControl.setPrefix(false);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19, className: "basemap",
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> · Batas: Kemendagri 2020 (disederhanakan)',
    }).addTo(this.map);
    const pane = (name: string, z: number, passive: boolean) => {
      const p = this.map.createPane(name);
      p.style.zIndex = String(z);
      if (passive) p.style.pointerEvents = "none";
    };
    pane("kab", 410, false);
    pane("prov", 412, true);
    pane("kabHover", 414, true);
    pane("kabSel", 416, true);
    this.hoverLayer = L.geoJSON(undefined, { pane: "kabHover", interactive: false, style: { className: "kab-hover", weight: 1.6, fill: false } }).addTo(this.map);
    this.selHalo = L.geoJSON(undefined, { pane: "kabSel", interactive: false, style: { className: "kab-sel-halo", weight: 5, fill: false } }).addTo(this.map);
    this.selLine = L.geoJSON(undefined, { pane: "kabSel", interactive: false, style: { className: "kab-sel-line", weight: 2, fill: false } }).addTo(this.map);
    this.addNav();
    this.map.fitBounds(INDONESIA, { animate: false });

    // ---- keadaan gerak: hover & tooltip tidak pernah tertinggal selama/ sesudah kamera bergerak
    this.map.on("movestart zoomstart", () => { this.moving = true; this.clearHover(); this.tip.hide(); });
    this.map.on("moveend", () => { this.moving = false; });
    this.map.on("zoomend", () => this.syncZoomButtons());
    el.addEventListener("pointerleave", () => { this.clearHover(); this.tip.hide(); });

    // ---- klik latar (laut/luar poligon). Klik poligon & penanda dihentikan di handler masing-masing.
    // Ditunda sebentar agar klik ganda (zoom) tidak dianggap "kembali ke nasional".
    this.map.on("click", () => {
      window.clearTimeout(this.bgTimer);
      this.bgTimer = window.setTimeout(() => this.h.onBackground(), 300);
    });
    this.map.on("dblclick", () => window.clearTimeout(this.bgTimer));

    // Enter/Spasi pada penanda atau klaster yang difokus = klik (Leaflet hanya memberi tabindex)
    el.addEventListener("keydown", (e) => {
      const t = (e.target as HTMLElement).closest<HTMLElement>(".leaflet-marker-icon");
      if (t && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); t.click(); }
    });

    this.cluster = L.markerClusterGroup({
      maxClusterRadius: 36, showCoverageOnHover: false, spiderfyOnMaxZoom: true, zoomToBoundsOnClick: true,
      animate: !rm, spiderfyDistanceMultiplier: 1.5, removeOutsideVisibleBounds: true,
      iconCreateFunction: (c) => {
        const kids = c.getAllChildMarkers();
        const n = kids.length; // satu penanda = satu lokasi unik
        const hot = this.sorot ? kids.some((m) => this.sorot!.has((m.options as { gid?: string }).gid ?? "")) : false;
        return L.divIcon({
          className: `pm-cluster-wrap${this.sorot ? (hot ? " is-sorot" : " is-redup") : ""}`,
          html: `<span class="pm-cluster" role="img" aria-label="${n} lokasi berdekatan; tekan untuk memperbesar"><b>${n}</b><small>lokasi</small></span>`,
          iconSize: L.point(42, 42),
        });
      },
    });
    const clusterOf = (e: L.LeafletEvent) => ((e as unknown as { layer?: L.MarkerCluster; propagatedFrom?: L.MarkerCluster }).layer
      ?? (e as unknown as { propagatedFrom?: L.MarkerCluster }).propagatedFrom) as L.MarkerCluster | undefined;
    this.cluster.on("clustermouseover", (e) => {
      const c = clusterOf(e);
      if (!c || this.moving) return;
      const p = this.map.latLngToContainerPoint(c.getLatLng());
      this.tip.show(`cl:${L.Util.stamp(c)}`, `<div class="tt-title">${c.getChildCount()} lokasi berdekatan</div><div class="tt-hint">Klik untuk memperbesar</div>`, p.x, p.y - 20, "anchor");
    });
    this.cluster.on("clustermouseout", (e) => { const c = clusterOf(e); if (c) this.tip.hide(`cl:${L.Util.stamp(c)}`, 60); });
    this.cluster.on("clusterclick", () => this.tip.hide());
    this.map.addLayer(this.cluster);
  }

  // ------------------------------------------------------------------ kontrol peta
  private addNav(): void {
    const Nav = L.Control.extend({
      options: { position: "topright" },
      onAdd: () => {
        const box = L.DomUtil.create("div", "mapnav");
        const btn = (cls: string, label: string, icon: Parameters<typeof iconSvg>[0], fn: () => void) => {
          const b = L.DomUtil.create("button", `mapnav-btn ${cls}`, box) as HTMLButtonElement;
          b.type = "button";
          b.title = label;
          b.setAttribute("aria-label", label);
          b.innerHTML = iconSvg(icon, 18);
          L.DomEvent.on(b, "click", (ev) => { L.DomEvent.stop(ev); fn(); });
          return b;
        };
        btn("mapnav-home", "Kembali ke peta nasional", "home", () => this.h.onHome());
        L.DomUtil.create("span", "mapnav-sep", box);
        this.zoomIn = btn("", "Perbesar", "plus", () => this.map.zoomIn());
        this.zoomOut = btn("", "Perkecil", "minus", () => this.map.zoomOut());
        L.DomEvent.disableClickPropagation(box);
        L.DomEvent.disableScrollPropagation(box);
        return box;
      },
    });
    new (Nav as unknown as new () => L.Control)().addTo(this.map);
  }

  private syncZoomButtons(): void {
    const z = this.map.getZoom();
    if (this.zoomIn) this.zoomIn.disabled = z >= this.map.getMaxZoom();
    if (this.zoomOut) this.zoomOut.disabled = z <= this.map.getMinZoom();
  }

  // ------------------------------------------------------------------ poligon
  setGeo(kab: GeoJSON.FeatureCollection, prov: GeoJSON.FeatureCollection): void {
    L.geoJSON(prov, { pane: "prov", interactive: false, style: { className: "prov", weight: 0.9, fill: false } }).addTo(this.map);
    L.geoJSON(kab as GeoJSON.FeatureCollection<GeoJSON.Geometry, KabProps>, {
      pane: "kab",
      style: () => ({ className: "kab", weight: 0.6, fillOpacity: 1 }),
      onEachFeature: (f, layer) => {
        const kode = (f.properties as KabProps).kode_kab;
        const path = layer as KabLayer;
        this.kabLayers.set(kode, path);
        path.on("mouseover", (e: L.LeafletMouseEvent) => this.hoverIn(kode, e.containerPoint));
        path.on("mousemove", (e: L.LeafletMouseEvent) => {
          if (this.hoverKab !== kode) this.hoverIn(kode, e.containerPoint); // pulih setelah kamera berhenti
          else this.tip.move(`kab:${kode}`, e.containerPoint.x, e.containerPoint.y);
        });
        path.on("mouseout", () => this.hoverOut(kode));
        path.on("click", (e) => {
          L.DomEvent.stop(e);
          window.clearTimeout(this.bgTimer);
          this.clearHover();
          this.tip.hide();
          if (kode !== this.selectedKab) this.h.onKab(kode); // poligon terpilih: tidak ada navigasi ganda
        });
      },
    }).addTo(this.map);
    this.restyle();
  }

  private hoverIn(kode: string, p: L.Point): void {
    if (this.moving) return;
    if (kode === this.selectedKab) { this.clearHover(); this.tip.hide(); return; }
    this.setHover(kode);
    this.tip.show(`kab:${kode}`, this.kabTip(kode), p.x, p.y, "cursor");
  }

  private hoverOut(kode: string): void {
    if (this.hoverKab === kode) this.setHover(null);
    this.tip.hide(`kab:${kode}`, 70);
  }

  private setHover(kode: string | null): void {
    if (kode === this.hoverKab) return;
    this.hoverKab = kode;
    this.hoverLayer.clearLayers();
    const l = kode ? this.kabLayers.get(kode) : null;
    if (l) this.hoverLayer.addData(l.feature);
  }

  clearHover(): void { this.setHover(null); }

  private kabTip(kode: string): string {
    const p = this.kabLayers.get(kode)!.feature.properties;
    const n = this.counts.get(kode) ?? 0;
    const val = this.cakupan.has(kode) || n > 0
      ? `<div class="tt-row"><span>Kejadian bencana</span><b>${angka(n)}</b></div>`
      : `<div class="tt-muted">Di luar cakupan data</div>`;
    return `<div class="tt-title">${esc(p.nama)}</div><div class="tt-sub">${esc(p.provinsi)}</div>${val}<div class="tt-hint">Klik untuk membuka</div>`;
  }

  kabName(kode: string): string | null { return this.kabLayers.get(kode)?.feature.properties.nama ?? null; }

  setCounts(counts: Map<string, number>, cakupan: Set<string>): void {
    this.counts = counts;
    this.cakupan = cakupan;
    this.restyle();
    if (this.hoverKab) this.tip.update(`kab:${this.hoverKab}`, this.kabTip(this.hoverKab));
  }

  private restyle(): void {
    for (const [kode, layer] of this.kabLayers) {
      const el = layer.getElement();
      if (!el) continue;
      const n = this.counts.get(kode) ?? 0;
      el.setAttribute("data-kode", kode);
      el.setAttribute("data-n", String(n));
      el.setAttribute("data-k", this.cakupan.has(kode) || n > 0 ? String(kelasOf(n)) : "na");
      el.classList.toggle("is-selected", kode === this.selectedKab);
      el.classList.toggle("is-dim", this.selectedKab !== null && kode !== this.selectedKab);
    }
  }

  private drawSelection(kode: string | null): void {
    this.selHalo.clearLayers();
    this.selLine.clearLayers();
    const l = kode ? this.kabLayers.get(kode) : null;
    if (l) { this.selHalo.addData(l.feature); this.selLine.addData(l.feature); }
  }

  // ------------------------------------------------------------------ kamera
  setPadding(p: Pad, mode: "none" | "pan" | "refit" = "none"): void {
    const dx = ((p.right - p.left) - (this.pad.right - this.pad.left)) / 2;
    const dy = ((p.bottom - p.top) - (this.pad.bottom - this.pad.top)) / 2;
    this.pad = p;
    if (mode === "refit" && this.selectedKab && !this.selectedTitik) { void this.fly(this.kabLayers.get(this.selectedKab)!.getBounds(), 0.5, 11.5); return; }
    if (mode !== "none" && (Math.abs(dx) > 1 || Math.abs(dy) > 1))
      this.map.panBy([dx, dy], { animate: !reducedMotion(), duration: 0.32, easeLinearity: 0.35 });
  }

  /** Pilih kab/kota: garis seleksi langsung tampak, lalu kamera terbang. Resolve true bila tidak tergantikan. */
  focusKab(kode: string): Promise<boolean> {
    this.clearHover();
    this.tip.hide();
    const prev = this.selectedKab;
    this.selectedKab = kode;
    this.selectedTitik = null;
    this.sorot = null;
    this.restyle();
    this.drawSelection(kode);
    if (prev && prev !== kode) this.leaveMarkers();
    const layer = this.kabLayers.get(kode);
    return layer ? this.fly(layer.getBounds(), 0.75, 11.5) : Promise.resolve(true);
  }

  national(animate = true): Promise<boolean> {
    this.selectedKab = null;
    this.selectedTitik = null;
    this.sorot = null;
    this.restyle();
    this.drawSelection(null);
    this.leaveMarkers();
    return this.flyNational(animate ? 0.7 : 0);
  }

  /** Kamera nasional: lebih dekat dari sekadar muat di area terlihat; ujung negara boleh tertutup panel, tidak keluar peta. */
  private flyNational(duration: number): Promise<boolean> {
    const bounds = L.latLngBounds(INDONESIA);
    const pas = this.map.getBoundsZoom(bounds, false, L.point(this.pad.left + this.pad.right, this.pad.top + this.pad.bottom));
    const target = Math.min(pas + ZOOM_NASIONAL_EKSTRA, this.map.getBoundsZoom(bounds));
    // Geser dari pusat area terlihat secukupnya agar ujung barat & timur tetap di dalam peta.
    const c = this.map.project(this.offsetCenter(bounds.getCenter(), target), target);
    const barat = this.map.project(bounds.getNorthWest(), target).x, timur = this.map.project(bounds.getSouthEast(), target).x;
    const paruh = this.map.getSize().x / 2;
    c.x = timur - barat >= paruh * 2 ? (barat + timur) / 2 : Math.max(timur - paruh, Math.min(barat + paruh, c.x));
    const center = this.map.unproject(c, target);
    const token = ++this.flightToken;
    return new Promise((resolve) => {
      const done = () => resolve(token === this.flightToken);
      if (reducedMotion() || duration === 0) {
        this.map.setView(center, target, { animate: false });
        requestAnimationFrame(done);
        return;
      }
      this.map.once("moveend", done);
      this.map.flyTo(center, target, { duration, easeLinearity: 0.22 });
    });
  }

  private fly(bounds: L.LatLngBounds, duration: number, maxZoom?: number): Promise<boolean> {
    const token = ++this.flightToken;
    const opts: L.FitBoundsOptions = { paddingTopLeft: L.point(this.pad.left, this.pad.top), paddingBottomRight: L.point(this.pad.right, this.pad.bottom), maxZoom };
    return new Promise((resolve) => {
      const done = () => resolve(token === this.flightToken);
      if (reducedMotion() || duration === 0) {
        this.map.fitBounds(bounds, { ...opts, animate: false });
        requestAnimationFrame(done);
        return;
      }
      this.map.once("moveend", done);
      this.map.flyToBounds(bounds, { ...opts, duration, easeLinearity: 0.22 });
    });
  }

  private offsetCenter(ll: L.LatLng, z: number): L.LatLng {
    const s = this.map.getSize();
    const vis = L.point((this.pad.left + s.x - this.pad.right) / 2, (this.pad.top + s.y - this.pad.bottom) / 2);
    return this.map.unproject(this.map.project(ll, z).subtract(vis.subtract(s.divideBy(2))), z);
  }

  private inView(ll: L.LatLng, inset = 6): boolean {
    const p = this.map.latLngToContainerPoint(ll), s = this.map.getSize();
    return p.x > this.pad.left + inset && p.x < s.x - this.pad.right - inset && p.y > this.pad.top + inset && p.y < s.y - this.pad.bottom - inset;
  }

  // ------------------------------------------------------------------ penanda
  /** Hapus penanda kab lama dengan pudar singkat agar tidak ikut "terbang" saat kamera berpindah. */
  private leaveMarkers(): void {
    if (!this.markers.size) return;
    const c = this.map.getContainer();
    c.classList.add("pm-leaving");
    window.clearTimeout(this.leaveTimer);
    this.leaveTimer = window.setTimeout(() => this.flushLeaving(), reducedMotion() ? 0 : 170);
  }

  private flushLeaving(): void {
    if (!this.leaveTimer) return;
    window.clearTimeout(this.leaveTimer);
    this.leaveTimer = 0;
    this.clearMarkers();
    this.map.getContainer().classList.remove("pm-leaving");
  }

  setTitik(titik: Titik[], animateIn: boolean): void {
    this.flushLeaving();
    const next = new Map(titik.map((t) => [t.gazetteer_id, t]));
    const remove: L.Marker[] = [];
    for (const [gid, rec] of this.markers) if (!next.has(gid)) { remove.push(rec.m); this.markers.delete(gid); }
    if (remove.length) this.cluster.removeLayers(remove);
    const add: L.Marker[] = [];
    let changed = false;
    [...titik].sort((a, b) => b.latitude - a.latitude).forEach((t, i) => {
      const key = markerKey(t);
      const rec = this.markers.get(t.gazetteer_id);
      if (rec) {
        rec.t = t;
        if (rec.key !== key) { rec.key = key; rec.m.setIcon(this.icon(t, -1)); changed = true; }
        return;
      }
      const gid = t.gazetteer_id;
      const m = L.marker([t.latitude, t.longitude], {
        icon: this.icon(t, animateIn ? i : -1), keyboard: true, riseOnHover: true, title: "", gid,
      } as L.MarkerOptions & { gid: string });
      m.on("click", (e) => { L.DomEvent.stop(e); window.clearTimeout(this.bgTimer); this.tip.hide(); this.h.onTitik(gid); });
      m.on("mouseover", () => this.markerTip(gid));
      m.on("mouseout", () => this.tip.hide(`mk:${gid}`, 60));
      m.on("remove", () => this.tip.hide(`mk:${gid}`));
      m.on("add", () => this.decorate(gid));
      this.markers.set(gid, { m, key, t });
      add.push(m);
    });
    if (add.length) this.cluster.addLayers(add);
    if (changed) this.cluster.refreshClusters();
    for (const gid of this.markers.keys()) this.decorate(gid);
    if (animateIn && add.length) {
      const c = this.map.getContainer();
      c.classList.add("pm-entering");
      window.setTimeout(() => {
        c.classList.remove("pm-entering");
        // ikon yang dibuat ulang setelah ini (zoom/klaster) tidak dianimasikan lagi
        for (const r of this.markers.values()) r.m.getElement()?.querySelector(".pm-mk")?.removeAttribute("style");
      }, 900);
    }
  }

  private markerTip(gid: string): void {
    const rec = this.markers.get(gid);
    if (!rec || this.moving) return;
    const p = this.map.latLngToContainerPoint(rec.m.getLatLng());
    this.tip.show(`mk:${gid}`, markerTooltip(rec.t), p.x, p.y - 18, "anchor");
  }

  private icon(t: Titik, i: number): L.DivIcon {
    const html = markerHtml(t);
    return L.divIcon({
      className: "pm-marker",
      html: i >= 0 ? html.replace('class="pm-mk', `style="--i:${Math.min(i, 14)}" class="pm-mk`) : html,
      iconSize: L.point(34, 34), iconAnchor: L.point(17, 17),
    });
  }

  private decorate(gid: string): void {
    const rec = this.markers.get(gid);
    const el = rec?.m.getElement();
    if (!rec || !el) return;
    el.setAttribute("aria-label", markerAria(rec.t));
    el.setAttribute("aria-describedby", "maptip");
    el.setAttribute("data-gid", gid);
    el.setAttribute("aria-pressed", String(gid === this.selectedTitik));
    el.classList.toggle("is-selected", gid === this.selectedTitik);
    el.classList.toggle("is-sorot", !!this.sorot && this.sorot.has(gid));
    el.classList.toggle("is-redup", !!this.sorot && !this.sorot.has(gid));
    if (!el.dataset.bound) {
      el.dataset.bound = "1";
      el.addEventListener("focus", () => this.markerTip(gid));
      el.addEventListener("blur", () => this.tip.hide(`mk:${gid}`));
    }
  }

  clearMarkers(): void {
    this.tip.hide();
    this.cluster.clearLayers();
    this.markers.clear();
  }

  setSorot(ids: string[] | null): void {
    this.sorot = ids ? new Set(ids) : null;
    for (const gid of this.markers.keys()) this.decorate(gid);
    this.cluster.refreshClusters();
  }

  setSelectedTitik(gid: string | null): void {
    this.selectedTitik = gid;
    for (const id of this.markers.keys()) this.decorate(id);
  }

  /** Bawa lokasi terpilih ke tengah area peta yang terlihat; tidak bergerak bila sudah terlihat cukup dekat. */
  focusTitik(gid: string): void {
    const rec = this.markers.get(gid);
    if (!rec) return;
    const parent = this.cluster.getVisibleParent(rec.m) as L.Marker | null;
    if (parent && parent !== rec.m) { this.cluster.zoomToShowLayer(rec.m, () => this.decorate(gid)); return; }
    const ll = rec.m.getLatLng(), z = this.map.getZoom();
    const target = Math.max(z, ZOOM_TITIK[rec.t.tingkat] ?? 12);
    if (parent === rec.m && this.inView(ll) && z >= target - 0.8) return;
    if (reducedMotion()) this.map.setView(this.offsetCenter(ll, target), target, { animate: false });
    else this.map.flyTo(this.offsetCenter(ll, target), target, { duration: 0.6, easeLinearity: 0.25 });
  }

  invalidate(): void { this.map.invalidateSize({ pan: false }); }
}
