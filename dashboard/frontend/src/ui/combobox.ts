import { h, icon } from "../dom";
import type { Wilayah } from "../types";

type Opt = Wilayah["kab"][number];

/** Combobox ARIA 1.2 (input + listbox) untuk memilih kab/kota. */
export class Combobox {
  readonly el: HTMLElement;
  private input: HTMLInputElement;
  private list: HTMLUListElement;
  private clear: HTMLButtonElement;
  private opts: Opt[] = [];
  private shown: (Opt | null)[] = [];
  private active = -1;
  private value: string | null = null;

  constructor(id: string, label: string, placeholder: string, private onPick: (kode: string | null) => void) {
    this.input = h("input", { id: `${id}-input`, class: "combo-input", type: "text", role: "combobox", autocomplete: "off",
      "aria-autocomplete": "list", "aria-expanded": "false", "aria-controls": `${id}-list`, placeholder, "aria-label": label });
    this.list = h("ul", { id: `${id}-list`, class: "combo-list", role: "listbox", "aria-label": label, hidden: true });
    this.clear = h("button", { type: "button", class: "combo-clear", "aria-label": "Kembali ke seluruh wilayah", hidden: true,
      onclick: () => { this.onPick(null); this.input.focus(); } }, "×");
    this.el = h("div", { class: "combo" },
      icon("combo-icon", '<circle cx="7" cy="7" r="4.6" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M10.5 10.5 14 14" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>'),
      this.input, this.clear, this.list);
    this.input.addEventListener("focus", () => { this.input.select(); this.open(""); });
    this.input.addEventListener("input", () => this.open(this.input.value));
    this.input.addEventListener("keydown", (e) => this.key(e));
    this.input.addEventListener("blur", () => window.setTimeout(() => this.close(true), 120));
  }

  setOptions(o: Opt[]): void {
    this.opts = [...o].sort((a, b) => Number(b.ada_data) - Number(a.ada_data) || a.nama.localeCompare(b.nama, "id"));
    this.setValue(this.value);
  }

  setValue(kode: string | null): void {
    this.value = kode;
    const o = this.opts.find((x) => x.kode_kab === kode);
    if (document.activeElement !== this.input) this.input.value = o ? o.nama : "";
    this.clear.hidden = !kode;
  }

  private open(q: string): void {
    const n = q.trim().toLowerCase();
    const hits = this.opts.filter((o) => !n || o.nama.toLowerCase().includes(n) || o.provinsi.toLowerCase().includes(n) || o.kode_kab.startsWith(n));
    this.shown = [null, ...hits.slice(0, 60)];
    this.list.replaceChildren(...this.shown.map((o, i) => {
      const li = h("li", { id: `${this.list.id}-${i}`, role: "option", class: "combo-opt", "aria-selected": String((o?.kode_kab ?? null) === this.value),
        onmousedown: (e: Event) => { e.preventDefault(); this.pick(i); } },
        o ? h("span", { class: "combo-name" }, o.nama) : h("span", { class: "combo-name" }, "Seluruh wilayah (peta nasional)"),
        o ? h("span", { class: "combo-meta" }, o.provinsi, o.ada_data ? h("span", { class: "combo-has" }, "ada data") : null) : null);
      return li;
    }));
    if (hits.length === 0) this.list.append(h("li", { class: "combo-empty", role: "presentation" }, "Tidak ada kab/kota yang cocok"));
    this.list.hidden = false;
    this.input.setAttribute("aria-expanded", "true");
    this.setActive(this.shown.length > 1 && n ? 1 : -1);
  }

  private close(restore = false): void {
    this.list.hidden = true;
    this.input.setAttribute("aria-expanded", "false");
    this.input.removeAttribute("aria-activedescendant");
    if (restore) this.setValue(this.value);
  }

  private setActive(i: number): void {
    this.active = i;
    [...this.list.children].forEach((c, j) => c.classList.toggle("is-active", j === i));
    if (i >= 0) {
      this.input.setAttribute("aria-activedescendant", `${this.list.id}-${i}`);
      (this.list.children[i] as HTMLElement | undefined)?.scrollIntoView({ block: "nearest" });
    } else this.input.removeAttribute("aria-activedescendant");
  }

  private pick(i: number): void {
    const o = this.shown[i];
    this.close();
    this.input.blur();
    this.onPick(o ? o.kode_kab : null);
  }

  private key(e: KeyboardEvent): void {
    if (e.key === "ArrowDown") { e.preventDefault(); if (this.list.hidden) this.open(this.input.value); this.setActive(Math.min(this.active + 1, this.shown.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); this.setActive(Math.max(this.active - 1, 0)); }
    else if (e.key === "Enter") { e.preventDefault(); if (this.active >= 0) this.pick(this.active); }
    else if (e.key === "Escape") { this.close(true); this.input.blur(); }
  }
}
