import L from "./leaflet";
import "leaflet.markercluster";
import "leaflet/dist/leaflet.css";
import "leaflet.markercluster/dist/MarkerCluster.css";
import type { Titik } from "../types";
import { reducedMotion, esc } from "../dom";
import { angka } from "../format";
import { kelasOf } from "./legend";
import { markerAria, markerHtml, markerKey, markerTooltip } from "./marker";

const INDONESIA: L.LatLngBoundsLiteral = [[-10.9, 95.2], [5.9, 140.9]];

export interface MapHandlers {
  onKab(kode: string): void;
  onTitik(gid: string): void;
  onBackground(): void;
}

interface KabProps { kode_kab: string; nama: string; provinsi: string }

export class MapView {
  readonly map: L.Map;
  private kabLayers = new Map<string, L.Path & { feature: GeoJSON.Feature<GeoJSON.Geometry, KabProps> }>();
  private counts = new Map<string, number>();
  private cakupan = new Set<string>();
  private selectedKab: string | null = null;
  private cluster: L.MarkerClusterGroup;
  private markers = new Map<string, { m: L.Marker; key: string; t: Titik }>();
  private sorot: Set<string> | null = null;
  private selectedTitik: string | null = null;
  private flightToken = 0;
  private padTL = L.point(16, 64);
  private padBR = L.point(16, 16);
  private home: L.LatLngBounds = L.latLngBounds(INDONESIA);

  constructor(el: HTMLElement, private h: MapHandlers) {
    this.map = L.map(el, {
      zoomSnap: 0.25, zoomDelta: 0.5, minZoom: 4, maxZoom: 16, zoomControl: false, attributionControl: true,
      worldCopyJump: false, maxBounds: [[-20, 85], [15, 150]], preferCanvas: false,
      fadeAnimation: !reducedMotion(), zoomAnimation: !reducedMotion(), markerZoomAnimation: !reducedMotion(),
    });
    L.control.zoom({ position: "topright", zoomInTitle: "Perbesar", zoomOutTitle: "Perkecil" }).addTo(this.map);
    this.map.attributionControl.setPrefix(false);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19, className: "basemap",
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> · Batas: Kemendagri 2020 (disederhanakan)',
    }).addTo(this.map);
    this.map.createPane("kab").style.zIndex = "410";
    this.map.createPane("prov").style.zIndex = "420";
    this.map.getPane("prov")!.style.pointerEvents = "none";
    this.map.fitBounds(INDONESIA, { animate: false });
    this.map.on("click", () => this.h.onBackground());
    // Enter/Spasi pada penanda atau klaster yang difokus = klik (Leaflet hanya memberi tabindex)
    el.addEventListener("keydown", (e) => {
      const t = (e.target as HTMLElement).closest<HTMLElement>(".leaflet-marker-icon");
      if (t && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); t.click(); }
    });

    this.cluster = L.markerClusterGroup({
      maxClusterRadius: 34, showCoverageOnHover: false, spiderfyOnMaxZoom: true, zoomToBoundsOnClick: true,
      animate: !reducedMotion(), spiderfyDistanceMultiplier: 1.4, removeOutsideVisibleBounds: true,
      iconCreateFunction: (c) => {
        const kids = c.getAllChildMarkers();
        const n = kids.length; // satu penanda = satu lokasi unik
        const hot = this.sorot ? kids.some((m) => this.sorot!.has((m.options as { gid?: string }).gid ?? "")) : false;
        return L.divIcon({
          className: `pm-cluster-wrap${this.sorot ? (hot ? " is-sorot" : " is-redup") : ""}`,
          html: `<span class="pm-cluster" role="img" aria-label="${n} lokasi berdekatan; tekan untuk memperbesar">${n}<small>lokasi</small></span>`,
          iconSize: L.point(44, 44),
        });
      },
    });
    this.cluster.on("clustermouseover", (e: L.LeafletEvent) => {
      const c = (e as unknown as { layer: L.MarkerCluster }).layer;
      c.bindTooltip(`${c.getChildCount()} lokasi berdekatan<br><span class="tip-meta">Klik untuk memperbesar</span>`, {
        direction: "top", offset: L.point(0, -20), className: "pm-tip", opacity: 1,
      }).openTooltip();
    });
    this.map.addLayer(this.cluster);
  }

  setPadding(tl: [number, number], br: [number, number]): void {
    this.padTL = L.point(tl);
    this.padBR = L.point(br);
  }

  setGeo(kab: GeoJSON.FeatureCollection, prov: GeoJSON.FeatureCollection): void {
    L.geoJSON(prov, { pane: "prov", interactive: false, style: { className: "prov", weight: 1, fill: false } }).addTo(this.map);
    L.geoJSON(kab as GeoJSON.FeatureCollection<GeoJSON.Geometry, KabProps>, {
      pane: "kab",
      style: () => ({ className: "kab", weight: 0.6, fillOpacity: 1 }),
      onEachFeature: (f, layer) => {
        const p = f.properties as KabProps;
        const path = layer as L.Path & { feature: GeoJSON.Feature<GeoJSON.Geometry, KabProps> };
        this.kabLayers.set(p.kode_kab, path);
        this.bindKabTip(path);
        path.on("mouseover", () => { if (p.kode_kab !== this.selectedKab) { path.getElement()?.classList.add("is-hover"); path.bringToFront(); } });
        path.on("mouseout", () => path.getElement()?.classList.remove("is-hover"));
        path.on("click", (e) => { L.DomEvent.stop(e); this.h.onKab(p.kode_kab); });
      },
    }).addTo(this.map);
    this.restyle();
  }

  private bindKabTip(path: L.Path & { feature: GeoJSON.Feature<GeoJSON.Geometry, KabProps> }): void {
    const p = path.feature.properties;
    path.bindTooltip(() => {
      const n = this.counts.get(p.kode_kab) ?? 0;
      const val = this.cakupan.has(p.kode_kab) || n > 0
        ? `<div class="tip-row"><span>Kejadian bencana</span><b>${angka(n)}</b></div>`
        : `<div class="tip-meta">Di luar cakupan data</div>`;
      return `<div class="tip-title">${esc(p.nama)}</div><div class="tip-sub">${esc(p.provinsi)}</div>${val}`;
    }, { sticky: true, direction: "top", offset: L.point(0, -12), className: "pm-tip", opacity: 1 });
  }

  /** Bingkai "nasional": cakupan data (kab/kota yang punya data) dengan konteks sekitarnya;
   * seluruh Indonesia bila cakupan kosong. Hindari peta terlalu jauh untuk data yang terpusat. */
  setHome(kodes: string[]): void {
    const bs = kodes.map((k) => this.kabLayers.get(k)).filter(Boolean).map((l) => (l as unknown as L.Polygon).getBounds());
    if (bs.length) {
      const b = bs.reduce((a, x) => a.extend(x), L.latLngBounds(bs[0].getSouthWest(), bs[0].getNorthEast()));
      this.home = b.pad(0.9);
    }
    if (!this.selectedKab) this.map.fitBounds(this.home, { paddingTopLeft: this.padTL, paddingBottomRight: this.padBR, animate: false });
  }

  showIndonesia(): void {
    void this.fly(L.latLngBounds(INDONESIA), 0.8);
  }

  kabName(kode: string): string | null {
    return this.kabLayers.get(kode)?.feature.properties.nama ?? null;
  }

  setCounts(counts: Map<string, number>, cakupan: Set<string>): void {
    this.counts = counts;
    this.cakupan = cakupan;
    this.restyle();
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

  /** Sorot poligon segera, lalu animasikan kamera. Resolve true bila penerbangan tidak tergantikan. */
  focusKab(kode: string): Promise<boolean> {
    const layer = this.kabLayers.get(kode);
    if (this.selectedKab && this.selectedKab !== kode) {
      const prev = this.kabLayers.get(this.selectedKab);
      if (prev) this.bindKabTip(prev);
    }
    this.selectedKab = kode;
    this.restyle();
    if (!layer) return Promise.resolve(true);
    layer.unbindTooltip();
    layer.bringToFront();
    const bounds = (layer as unknown as L.Polygon).getBounds();
    return this.fly(bounds, 0.8);
  }

  national(): Promise<boolean> {
    if (this.selectedKab) {
      const prev = this.kabLayers.get(this.selectedKab);
      if (prev) this.bindKabTip(prev);
    }
    this.selectedKab = null;
    this.selectedTitik = null;
    this.sorot = null;
    this.clearMarkers();
    this.restyle();
    return this.fly(this.home, 0.75);
  }

  private fly(bounds: L.LatLngBounds, duration: number): Promise<boolean> {
    const token = ++this.flightToken;
    const opts = { paddingTopLeft: this.padTL, paddingBottomRight: this.padBR, maxZoom: 12 };
    return new Promise((resolve) => {
      const done = () => resolve(token === this.flightToken);
      if (reducedMotion()) {
        this.map.fitBounds(bounds, { ...opts, animate: false });
        return requestAnimationFrame(done);
      }
      this.map.once("moveend", done);
      this.map.flyToBounds(bounds, { ...opts, duration, easeLinearity: 0.3 });
    });
  }

  // ------------------------------------------------------------------ penanda
  setTitik(titik: Titik[], animateIn: boolean): void {
    const next = new Map(titik.map((t) => [t.gazetteer_id, t]));
    const remove: L.Marker[] = [];
    for (const [gid, rec] of this.markers) {
      if (!next.has(gid)) { remove.push(rec.m); this.markers.delete(gid); }
    }
    this.cluster.removeLayers(remove);
    const add: L.Marker[] = [];
    let changed = false;
    const order = [...titik].sort((a, b) => b.latitude - a.latitude);
    order.forEach((t, i) => {
      const key = markerKey(t);
      const rec = this.markers.get(t.gazetteer_id);
      if (rec) {
        rec.t = t;
        if (rec.key !== key) { rec.key = key; rec.m.setIcon(this.icon(t, -1)); changed = true; }
        rec.m.setTooltipContent(markerTooltip(t));
        return;
      }
      const m = L.marker([t.latitude, t.longitude], {
        icon: this.icon(t, animateIn ? i : -1), keyboard: true, riseOnHover: true, title: "",
        gid: t.gazetteer_id,
      } as L.MarkerOptions & { gid: string });
      m.bindTooltip(markerTooltip(t), { direction: "top", offset: L.point(0, -17), className: "pm-tip", opacity: 1 });
      m.on("click", (e) => { L.DomEvent.stop(e); this.h.onTitik(t.gazetteer_id); });
      m.on("add", () => this.decorate(t.gazetteer_id));
      this.markers.set(t.gazetteer_id, { m, key, t });
      add.push(m);
    });
    this.cluster.addLayers(add);
    if (changed) this.cluster.refreshClusters();
    for (const gid of this.markers.keys()) this.decorate(gid);
    if (animateIn) {
      const c = this.map.getContainer();
      c.classList.add("pm-entering");
      window.setTimeout(() => {
        c.classList.remove("pm-entering");
        // ikon baru setelah ini (zoom/klaster) tidak dianimasikan ulang
        for (const rec of this.markers.values()) rec.m.getElement()?.querySelector(".pm-mk")?.removeAttribute("style");
      }, 900);
    }
  }

  private icon(t: Titik, i: number): L.DivIcon {
    return L.divIcon({
      className: "pm-marker",
      html: i >= 0 ? markerHtml(t).replace('class="pm-mk', `style="--i:${Math.min(i, 14)}" class="pm-mk`) : markerHtml(t),
      iconSize: L.point(34, 34), iconAnchor: L.point(17, 17), tooltipAnchor: L.point(0, 0),
    });
  }

  private decorate(gid: string): void {
    const rec = this.markers.get(gid);
    const el = rec?.m.getElement();
    if (!rec || !el) return;
    el.setAttribute("aria-label", markerAria(rec.t));
    el.setAttribute("data-gid", gid);
    el.classList.toggle("is-selected", gid === this.selectedTitik);
    el.classList.toggle("is-sorot", !!this.sorot && this.sorot.has(gid));
    el.classList.toggle("is-redup", !!this.sorot && !this.sorot.has(gid));
    el.setAttribute("aria-pressed", String(gid === this.selectedTitik));
    if (!el.dataset.bound) {
      el.dataset.bound = "1";
      el.addEventListener("focus", () => rec.m.openTooltip());
      el.addEventListener("blur", () => rec.m.closeTooltip());
    }
  }

  clearMarkers(): void {
    this.cluster.clearLayers();
    this.markers.clear();
  }

  setSorot(ids: string[] | null): void {
    this.sorot = ids ? new Set(ids) : null;
    for (const gid of this.markers.keys()) this.decorate(gid);
    this.cluster.refreshClusters();
  }

  setSelectedTitik(gid: string | null, reveal = false): void {
    this.selectedTitik = gid;
    for (const id of this.markers.keys()) this.decorate(id);
    const rec = gid ? this.markers.get(gid) : null;
    if (rec && reveal) {
      // hanya geser bila lokasi tidak terlihat jelas; buka klaster bila perlu
      this.cluster.zoomToShowLayer(rec.m, () => this.decorate(gid!));
    }
  }

  titikVisible(gid: string): boolean {
    const rec = this.markers.get(gid);
    return !!rec && this.map.getBounds().pad(-0.08).contains(rec.m.getLatLng());
  }

  invalidate(): void { this.map.invalidateSize({ pan: false }); }
}
