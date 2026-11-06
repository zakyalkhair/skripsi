/**
 * Satu-satunya tooltip peta (poligon, penanda, klaster). Dikelola secara eksplisit:
 * - satu pemilik aktif (owner); hide(owner) dari pemilik lama diabaikan sehingga urutan
 *   mouseout/mouseover antar-poligon bertetangga tidak pernah membuat tooltip macet;
 * - jeda sembunyi singkat agar melintasi batas poligon tidak berkedip (konten ditukar, bukan dibuat ulang);
 * - posisi dijepit di dalam area peta dan dibalik di dekat tepi.
 */
export type TipMode = "cursor" | "anchor";

export class MapTip {
  readonly el: HTMLDivElement;
  private owner: string | null = null;
  private hideTimer = 0;
  private raf = 0;
  private next: { x: number; y: number; mode: TipMode } | null = null;

  constructor(private host: HTMLElement) {
    this.el = document.createElement("div");
    this.el.className = "maptip";
    this.el.setAttribute("role", "tooltip");
    this.el.id = "maptip";
    this.el.hidden = true;
    host.appendChild(this.el);
  }

  get current(): string | null { return this.el.hidden ? null : this.owner; }

  show(owner: string, html: string, x: number, y: number, mode: TipMode = "cursor"): void {
    window.clearTimeout(this.hideTimer);
    const appearing = this.el.hidden;
    if (owner !== this.owner || appearing) {
      this.owner = owner;
      this.el.innerHTML = html;
    }
    if (appearing) {
      this.el.hidden = false;
      this.el.classList.remove("is-in");
      void this.el.offsetWidth; // mulai ulang animasi masuk hanya saat muncul dari tersembunyi
      this.el.classList.add("is-in");
    }
    this.place(x, y, mode);
  }

  /** Perbarui isi bila pemiliknya masih aktif (mis. hitungan berubah karena filter). */
  update(owner: string, html: string): void {
    if (this.owner === owner && !this.el.hidden) this.el.innerHTML = html;
  }

  move(owner: string, x: number, y: number): void {
    if (this.owner !== owner || this.el.hidden) return;
    this.next = { x, y, mode: "cursor" };
    if (!this.raf) this.raf = requestAnimationFrame(() => {
      this.raf = 0;
      if (this.next && !this.el.hidden) this.place(this.next.x, this.next.y, this.next.mode);
    });
  }

  hide(owner?: string, delay = 0): void {
    if (owner !== undefined && owner !== this.owner) return;
    window.clearTimeout(this.hideTimer);
    const go = () => { this.el.hidden = true; this.owner = null; };
    if (delay > 0) this.hideTimer = window.setTimeout(go, delay);
    else go();
  }

  private place(x: number, y: number, mode: TipMode): void {
    const W = this.host.clientWidth, H = this.host.clientHeight;
    const w = this.el.offsetWidth, h = this.el.offsetHeight, m = 8;
    let left: number, top: number;
    if (mode === "cursor") {
      left = x + 16; top = y + 18;
      if (left + w > W - m) left = x - w - 16;
      if (top + h > H - m) top = y - h - 14;
    } else {
      left = x - w / 2; top = y - h - 12;
      if (top < m) top = y + 30;
    }
    left = Math.max(m, Math.min(left, W - w - m));
    top = Math.max(m, Math.min(top, H - h - m));
    this.el.style.transform = `translate3d(${Math.round(left)}px, ${Math.round(top)}px, 0)`;
  }
}
