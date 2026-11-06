import { h } from "../dom";
import { addDays, rentang, tgl } from "../format";
import { ico } from "./icons";

const PRESETS: { label: string; days: number | null }[] = [
  { label: "7 hari terakhir", days: 7 },
  { label: "30 hari terakhir", days: 30 },
  { label: "Seluruh periode", days: null },
];

/** Kontrol rentang tanggal di bilah atas. Satu sumber kebenaran tetap di store;
 * linimasa di bawah hanya menampilkan & mengubah nilai yang sama. */
export class DateRange {
  readonly el: HTMLElement;
  private trigger: HTMLButtonElement;
  private label: HTMLSpanElement;
  private pop: HTMLElement;
  private inDari: HTMLInputElement;
  private inSampai: HTMLInputElement;
  private txtDari: HTMLElement;
  private txtSampai: HTMLElement;
  private presetBtns: HTMLButtonElement[];
  private domain: [string, string] | null = null;
  private value: [string | null, string | null] = [null, null];

  constructor(private onChange: (dari: string | null, sampai: string | null) => void) {
    this.label = h("span", { class: "dr-label" }, "Seluruh periode");
    this.trigger = h("button", { type: "button", class: "tb-field dr-trigger", "aria-haspopup": "dialog", "aria-expanded": "false",
      "aria-controls": "dr-pop", onclick: () => this.toggle() },
      ico("calendar", 16), h("span", { class: "sr-only" }, "Rentang tanggal: "), this.label, ico("chevDown", 14, "dr-chev"));
    const field = (id: string, text: string) => {
      const input = h("input", { type: "date", id, class: "dr-input", "aria-describedby": `${id}-txt` });
      const txt = h("span", { class: "dr-txt", id: `${id}-txt`, "aria-live": "polite" });
      input.addEventListener("change", () => this.fromInputs());
      return { input, txt, el: h("label", { class: "dr-field", for: id }, h("span", { class: "dr-flabel" }, text), input, txt) };
    };
    const a = field("dr-dari", "Dari"), b = field("dr-sampai", "Sampai");
    this.inDari = a.input; this.inSampai = b.input; this.txtDari = a.txt; this.txtSampai = b.txt;
    this.presetBtns = PRESETS.map((p) => h("button", { type: "button", class: "seg-btn", "data-preset": p.days ?? "all",
      "aria-pressed": "false", onclick: () => this.preset(p.days) }, p.label));
    this.pop = h("div", { class: "dr-pop float-card", id: "dr-pop", role: "dialog", "aria-label": "Pilih rentang tanggal", hidden: true },
      h("div", { class: "seg seg--block", role: "group", "aria-label": "Rentang cepat" }, ...this.presetBtns),
      h("div", { class: "dr-fields" }, a.el, b.el),
      h("p", { class: "dr-note" }, "Kejadian ikut dihitung bila periodenya beririsan dengan rentang; laporan dan linimasa memakai tanggal laporan."));
    this.el = h("div", { class: "dr" }, this.trigger, this.pop);
    document.addEventListener("pointerdown", (e) => { if (!this.pop.hidden && !this.el.contains(e.target as Node)) this.close(false); });
    this.el.addEventListener("keydown", (e) => { if (e.key === "Escape" && !this.pop.hidden) { e.stopPropagation(); this.close(true); } });
  }

  get isOpen(): boolean { return !this.pop.hidden; }

  setDomain(awal: string | null, akhir: string | null): void {
    this.domain = awal && akhir ? [awal, akhir] : null;
    for (const inp of [this.inDari, this.inSampai]) { inp.min = awal ?? ""; inp.max = akhir ?? ""; }
    this.render();
  }

  setRange(dari: string | null, sampai: string | null): void {
    this.value = [dari, sampai];
    this.render();
  }

  private render(): void {
    if (!this.domain) return;
    const a = this.value[0] ?? this.domain[0], b = this.value[1] ?? this.domain[1];
    const all = !this.value[0] && !this.value[1];
    this.label.textContent = rentang(a, b);
    this.trigger.classList.toggle("is-active", !all);
    this.trigger.title = all ? "Seluruh periode data" : "Rentang tanggal aktif";
    this.inDari.value = a; this.inSampai.value = b;
    this.txtDari.textContent = tgl(a); this.txtSampai.textContent = tgl(b);
    const days = Math.round((Date.parse(b) - Date.parse(a)) / 86400000) + 1;
    for (const btn of this.presetBtns) {
      const p = btn.dataset.preset;
      btn.setAttribute("aria-pressed", String(all ? p === "all" : b === this.domain[1] && String(days) === p));
    }
  }

  private toggle(): void { this.isOpen ? this.close(true) : this.open(); }

  private open(): void {
    this.pop.hidden = false;
    this.trigger.setAttribute("aria-expanded", "true");
    this.presetBtns.find((b) => b.getAttribute("aria-pressed") === "true")?.focus();
  }

  close(focus: boolean): void {
    if (this.pop.hidden) return;
    this.pop.hidden = true;
    this.trigger.setAttribute("aria-expanded", "false");
    if (focus) this.trigger.focus();
  }

  private emit(a: string, b: string): void {
    if (!this.domain) return;
    if (a > b) [a, b] = [b, a];
    if (a < this.domain[0]) a = this.domain[0];
    if (b > this.domain[1]) b = this.domain[1];
    const full = a === this.domain[0] && b === this.domain[1];
    this.onChange(full ? null : a, full ? null : b);
  }

  private fromInputs(): void {
    if (!this.domain) return;
    this.emit(this.inDari.value || this.domain[0], this.inSampai.value || this.domain[1]);
  }

  private preset(days: number | null): void {
    if (!this.domain) return;
    if (days === null) this.emit(this.domain[0], this.domain[1]);
    else this.emit(addDays(this.domain[1], -(days - 1)), this.domain[1]);
  }
}
