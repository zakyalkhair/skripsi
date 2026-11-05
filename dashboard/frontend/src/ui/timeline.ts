import { h, s, reducedMotion } from "../dom";
import { ico } from "./icons";
import { addDays, angka, iso, parseDate, rentang, tgl } from "../format";
import { JENIS, LABEL_PENDEK } from "../jenis";
import type { Histogram } from "../types";

const DAY = 86400000;
const M = { l: 26, r: 10, t: 8, b: 20 };

/** Histogram laporan kejadian per minggu (skala waktu nyata) + kuas rentang tanggal. */
export class Timeline {
  readonly el: HTMLElement;
  private svg: SVGSVGElement;
  private gBars: SVGGElement;
  private gAxis: SVGGElement;
  private selRect: SVGRectElement;
  private handles: SVGGElement[];
  private tip: HTMLElement;
  private card: HTMLElement;
  private pill: HTMLButtonElement;
  private pillTxt: HTMLElement;
  private rangeTxt: HTMLElement;
  private collapseBtn: HTMLButtonElement;
  private scope: HTMLElement;
  private summary: HTMLElement;
  private data: Histogram | null = null;
  private domain: [string, string] | null = null;
  private range: [string, string] | null = null; // pilihan aktif (selalu terisi saat ada domain)
  private w = 600;
  private hgt = 96;
  private drag: { mode: "new" | "a" | "b" | "move"; x0: number; r0: [string, string] } | null = null;
  private commitTimer = 0;

  constructor(private onRange: (dari: string | null, sampai: string | null) => void, onToggle: (open: boolean) => void) {
    this.scope = h("span", { class: "tl-scope" });
    this.rangeTxt = h("span", { class: "tl-range" });
    this.summary = h("p", { class: "sr-only", "aria-live": "polite" });
    this.svg = s("svg", { class: "tl-svg", role: "img" });
    this.gAxis = s("g", { class: "tl-axis" });
    this.gBars = s("g", { class: "tl-bars" });
    this.selRect = s("rect", { class: "tl-sel" });
    const mkHandle = (side: "a" | "b") => {
      const g = s("g", { class: "tl-handle", tabindex: 0, role: "slider", "data-side": side,
        "aria-label": side === "a" ? "Batas awal rentang tanggal" : "Batas akhir rentang tanggal" });
      g.append(s("line", { y1: M.t, y2: M.t, class: "tl-hline" }), s("rect", { class: "tl-grip", width: 8, height: 20, rx: 2.5 }));
      g.addEventListener("keydown", (e) => this.handleKey(e as KeyboardEvent, side));
      return g;
    };
    this.handles = [mkHandle("a"), mkHandle("b")];
    this.svg.append(this.gAxis, this.selRect, this.gBars, ...this.handles);
    this.tip = h("div", { class: "tl-tip", role: "tooltip", hidden: true });
    const chart = h("div", { class: "tl-chart" }, this.svg, this.tip);
    this.collapseBtn = h("button", { type: "button", class: "icon-btn", "aria-label": "Sembunyikan linimasa", title: "Sembunyikan linimasa",
      "aria-expanded": "true", "aria-controls": "tl-card", onclick: () => onToggle(false) }, ico("chevDown", 16));
    this.card = h("section", { class: "timeline float-card", id: "tl-card", "aria-labelledby": "tl-title" },
      h("header", { class: "tl-head" },
        h("div", { class: "tl-titles" }, h("h2", { id: "tl-title", class: "tl-title" }, "Jumlah laporan kejadian per minggu"), this.scope),
        h("div", { class: "tl-right" }, this.rangeTxt, this.collapseBtn)),
      chart, this.summary);
    this.pillTxt = h("span", { class: "pill-sub" });
    this.pill = h("button", { type: "button", class: "pill tl-pill", "aria-label": "Tampilkan linimasa laporan", "aria-expanded": "false",
      onclick: () => onToggle(true) }, ico("chart", 15), h("span", {}, "Linimasa"), this.pillTxt, ico("chevUp", 14));
    this.el = h("div", { class: "timeline-wrap" }, this.card, this.pill);
    this.svg.addEventListener("pointerdown", (e) => this.down(e));
    this.svg.addEventListener("pointermove", (e) => this.move(e));
    this.svg.addEventListener("pointerup", (e) => this.up(e));
    this.svg.addEventListener("pointercancel", () => { this.drag = null; this.el.classList.remove("is-dragging"); });
    this.svg.addEventListener("pointerleave", () => { if (!this.drag) this.tip.hidden = true; });
    new ResizeObserver(() => {
      const r = chart.getBoundingClientRect();
      if (r.width < 60) return; // tersembunyi
      this.w = r.width; this.hgt = Math.max(64, r.height); this.render();
    }).observe(chart);
  }

  /** Tinggi kartu saat terbuka (untuk bantalan kamera). */
  height(): number { return this.card.offsetHeight || 148; }

  setOpen(open: boolean): void {
    this.el.classList.toggle("is-collapsed", !open);
    this.card.inert = !open;
    this.pill.inert = open;
    this.collapseBtn.setAttribute("aria-expanded", String(open));
  }

  setDomain(awal: string | null, akhir: string | null): void {
    this.domain = awal && akhir ? [awal, akhir] : null;
  }

  setData(d: Histogram, scopeLabel: string): void {
    this.data = d;
    this.scope.textContent = scopeLabel;
    this.render();
  }

  setRange(dari: string | null, sampai: string | null): void {
    if (!this.domain) return;
    this.range = [dari ?? this.domain[0], sampai ?? this.domain[1]];
    const txt = !dari && !sampai ? `Seluruh periode · ${rentang(this.range[0], this.range[1])}` : rentang(this.range[0], this.range[1]);
    this.rangeTxt.textContent = txt;
    this.pillTxt.textContent = rentang(this.range[0], this.range[1]);
    this.render();
  }

  // ---------------------------------------------------------------- skala
  private x0(): number { return parseDate(this.weekStart(this.domain![0])).getTime(); }
  private x1(): number { return parseDate(this.weekStart(this.domain![1])).getTime() + 7 * DAY; }
  private weekStart(d: string): string { const t = parseDate(d); t.setDate(t.getDate() - ((t.getDay() + 6) % 7)); return iso(t); }
  private sx(t: number): number { return M.l + ((t - this.x0()) / (this.x1() - this.x0())) * (this.w - M.l - M.r); }
  private inv(px: number): string {
    const n = Math.floor(((px - M.l) / (this.w - M.l - M.r)) * ((this.x1() - this.x0()) / DAY));
    const d = addDays(this.weekStart(this.domain![0]), n);
    return d < this.domain![0] ? this.domain![0] : d > this.domain![1] ? this.domain![1] : d;
  }

  private render(): void {
    const d = this.data;
    this.svg.setAttribute("viewBox", `0 0 ${this.w} ${this.hgt}`);
    this.svg.setAttribute("width", String(this.w));
    this.svg.setAttribute("height", String(this.hgt));
    if (!d || !this.domain || !d.minggu.length) { this.gBars.replaceChildren(); this.gAxis.replaceChildren(); return; }
    const max = Math.max(1, ...d.minggu.map((w) => w.total));
    const step = max <= 4 ? 1 : max <= 10 ? 2 : Math.ceil(max / 4);
    const top = Math.ceil(max / step) * step;
    const y = (v: number) => this.hgt - M.b - (v / top) * (this.hgt - M.b - M.t);
    // sumbu
    const axis: SVGElement[] = [];
    for (let v = 0; v <= top; v += step) {
      axis.push(s("line", { x1: M.l, x2: this.w - M.r, y1: y(v), y2: y(v), class: v ? "tl-grid" : "tl-base" }));
      axis.push(Object.assign(s("text", { x: M.l - 6, y: y(v), class: "tl-ytick", "text-anchor": "end", "dominant-baseline": "central" }), { textContent: String(v) }));
    }
    const start = parseDate(this.domain[0]);
    const m = new Date(start.getFullYear(), start.getMonth(), 1);
    while (m.getTime() <= this.x1()) {
      const px = Math.max(M.l, this.sx(m.getTime()));
      if (px < this.w - M.r - 40) {
        axis.push(s("line", { x1: px, x2: px, y1: this.hgt - M.b, y2: this.hgt - M.b + 4, class: "tl-tick" }));
        axis.push(Object.assign(s("text", { x: px + 3, y: this.hgt - 6, class: "tl-xtick" }), { textContent: tgl(iso(m)).replace(/^1 /, "") }));
      }
      m.setMonth(m.getMonth() + 1);
    }
    this.gAxis.replaceChildren(...axis);
    // batang bertumpuk per jenis (tinggi = jumlah laporan, bukan kejadian)
    const [ra, rb] = this.range ?? this.domain;
    const bars: SVGElement[] = [];
    for (const wk of d.minggu) {
      const t0 = parseDate(wk.mulai).getTime();
      const xa = this.sx(t0) + 1.5, xb = this.sx(t0 + 7 * DAY) - 1.5;
      const end = addDays(wk.mulai, 6);
      const inSel = end >= ra && wk.mulai <= rb;
      const g = s("g", { class: `tl-week${inSel ? "" : " is-out"}`, "data-mulai": wk.mulai, "data-total": wk.total });
      let acc = 0;
      for (const j of JENIS) {
        const n = wk.per_jenis[j] ?? 0;
        if (!n) continue;
        const r = s("rect", { x: xa, width: Math.max(1, xb - xa), y: y(acc + n), height: Math.max(0, y(acc) - y(acc + n) - 0.5), fill: `var(--j-${j})`, class: "tl-bar" });
        g.append(r);
        acc += n;
      }
      g.append(s("rect", { x: xa - 1.5, width: xb - xa + 3, y: M.t, height: this.hgt - M.b - M.t, class: "tl-hit" }));
      bars.push(g);
    }
    this.gBars.replaceChildren(...bars);
    // seleksi
    const sa = this.sx(parseDate(ra).getTime()), sb = this.sx(parseDate(rb).getTime() + DAY);
    Object.entries({ x: sa, y: M.t - 2, width: Math.max(2, sb - sa), height: this.hgt - M.b - M.t + 2 }).forEach(([k, v]) => this.selRect.setAttribute(k, String(v)));
    this.handles.forEach((g, i) => {
      const px = i ? sb : sa;
      g.setAttribute("transform", `translate(${px},0)`);
      g.querySelector("line")!.setAttribute("y2", String(this.hgt - M.b));
      const grip = g.querySelector("rect")!;
      grip.setAttribute("x", "-5");
      grip.setAttribute("y", String((this.hgt - M.b) / 2 - 11 + M.t / 2));
      const val = i ? rb : ra;
      g.setAttribute("aria-valuetext", tgl(val));
      g.setAttribute("aria-valuemin", this.domain![0]);
      g.setAttribute("aria-valuemax", this.domain![1]);
      g.setAttribute("aria-valuenow", String(parseDate(val).getTime() / DAY));
    });
    const total = d.minggu.reduce((a, w) => a + w.total, 0);
    const sel = d.minggu.filter((w) => addDays(w.mulai, 6) >= ra && w.mulai <= rb).reduce((a, w) => a + w.total, 0);
    const label = `Histogram ${angka(total)} laporan kejadian dalam ${d.minggu.length} minggu; ${angka(sel)} laporan pada minggu yang beririsan dengan rentang ${rentang(ra, rb)}.`;
    this.svg.setAttribute("aria-label", label);
    this.summary.textContent = `Rentang dipilih: ${rentang(ra, rb)}`;
  }

  // ---------------------------------------------------------------- interaksi
  private px(e: PointerEvent): number { const r = this.svg.getBoundingClientRect(); return ((e.clientX - r.left) / r.width) * this.w; }

  private down(e: PointerEvent): void {
    if (!this.domain || e.button !== 0) return;
    const side = (e.target as Element).closest(".tl-handle")?.getAttribute("data-side") as "a" | "b" | undefined;
    const r0 = this.range ?? this.domain;
    const x = this.px(e);
    const inSel = x > this.sx(parseDate(r0[0]).getTime()) + 6 && x < this.sx(parseDate(r0[1]).getTime() + DAY) - 6;
    this.drag = { mode: side ?? (inSel && !(r0[0] === this.domain[0] && r0[1] === this.domain[1]) ? "move" : "new"), x0: x, r0: [r0[0], r0[1]] };
    this.svg.setPointerCapture(e.pointerId);
    this.el.classList.add("is-dragging");
    this.tip.hidden = true;
  }

  private move(e: PointerEvent): void {
    const x = this.px(e);
    if (!this.drag) return this.hover(e, x);
    const d = this.inv(x), { mode, r0 } = this.drag;
    if (mode === "new") { const a = this.inv(this.drag.x0); this.range = a <= d ? [a, d] : [d, a]; }
    else if (mode === "a") this.range = [d <= r0[1] ? d : r0[1], r0[1]];
    else if (mode === "b") this.range = [r0[0], d >= r0[0] ? d : r0[0]];
    else {
      const shift = Math.round((parseDate(d).getTime() - parseDate(this.inv(this.drag.x0)).getTime()) / DAY);
      const len = Math.round((parseDate(r0[1]).getTime() - parseDate(r0[0]).getTime()) / DAY);
      let a = addDays(r0[0], shift);
      if (a < this.domain![0]) a = this.domain![0];
      if (addDays(a, len) > this.domain![1]) a = addDays(this.domain![1], -len);
      this.range = [a, addDays(a, len)];
    }
    this.render();
  }

  private up(e: PointerEvent): void {
    if (!this.drag) return;
    const moved = Math.abs(this.px(e) - this.drag.x0) > 3;
    if (!moved && this.drag.mode === "new") {
      // klik satu minggu = pilih minggu itu
      const wk = (e.target as Element).closest(".tl-week")?.getAttribute("data-mulai");
      if (wk) this.range = [wk < this.domain![0] ? this.domain![0] : wk, addDays(wk, 6) > this.domain![1] ? this.domain![1] : addDays(wk, 6)];
    }
    this.drag = null;
    this.el.classList.remove("is-dragging");
    this.commit(0);
  }

  private hover(e: PointerEvent, x: number): void {
    const g = (e.target as Element).closest(".tl-week");
    if (!g || !this.data) { this.tip.hidden = true; return; }
    const wk = this.data.minggu.find((w) => w.mulai === g.getAttribute("data-mulai"));
    if (!wk) return;
    const rows = JENIS.filter((j) => wk.per_jenis[j]).map((j) => `<div class="tip-j"><i style="background:var(--j-${j})"></i>${LABEL_PENDEK[j]}<b>${wk.per_jenis[j]}</b></div>`).join("");
    this.tip.innerHTML = `<div class="tip-title">${rentang(wk.mulai, addDays(wk.mulai, 6))}</div>
      <div class="tip-row"><span>Laporan kejadian</span><b>${wk.total}</b></div>${rows || '<div class="tip-meta">Tidak ada laporan</div>'}`;
    this.tip.hidden = false;
    const tw = this.tip.offsetWidth;
    const left = Math.min(Math.max(4, (x / this.w) * this.svg.clientWidth - tw / 2), this.svg.clientWidth - tw - 4);
    this.tip.style.transform = `translate(${left}px, 0)`;
  }

  private handleKey(e: KeyboardEvent, side: "a" | "b"): void {
    if (!this.domain) return;
    const delta = { ArrowLeft: -1, ArrowRight: 1, ArrowDown: -1, ArrowUp: 1, PageDown: -7, PageUp: 7 }[e.key];
    if (!delta && e.key !== "Home" && e.key !== "End") return;
    e.preventDefault();
    const r = this.range ?? this.domain;
    const step = (delta ?? 0) * (e.shiftKey ? 7 : 1);
    let v = e.key === "Home" ? this.domain[0] : e.key === "End" ? this.domain[1] : addDays(side === "a" ? r[0] : r[1], step);
    if (v < this.domain[0]) v = this.domain[0];
    if (v > this.domain[1]) v = this.domain[1];
    this.range = side === "a" ? [v <= r[1] ? v : r[1], r[1]] : [r[0], v >= r[0] ? v : r[0]];
    this.render();
    this.commit(350);
  }

  private commit(delay: number): void {
    window.clearTimeout(this.commitTimer);
    const go = () => {
      if (!this.range || !this.domain) return;
      const [a, b] = this.range;
      const full = a === this.domain[0] && b === this.domain[1];
      this.onRange(full ? null : a, full ? null : b);
    };
    if (delay && !reducedMotion()) this.commitTimer = window.setTimeout(go, delay);
    else go();
  }
}
