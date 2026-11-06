import { h } from "../dom";
import { ico, type IconName } from "./icons";

export type ToastKind = "ok" | "err" | "info";
export interface ToastOpts { kind?: ToastKind; ms?: number; detail?: string; action?: { label: string; fn: () => void } }
export interface ToastHandle { close(): void; update(msg: string, o?: ToastOpts): void }

const ICON: Record<ToastKind, IconName> = { ok: "check", err: "alert", info: "info" };

/** Notifikasi singkat. Wilayah status (polite) untuk info/sukses, alert untuk galat. */
export class Toasts {
  readonly el: HTMLElement;
  private polite: HTMLElement;
  private assertive: HTMLElement;

  constructor() {
    this.polite = h("div", { class: "toasts-col", role: "status", "aria-live": "polite" });
    this.assertive = h("div", { class: "toasts-col", role: "alert", "aria-live": "assertive" });
    this.el = h("div", { class: "toasts" }, this.assertive, this.polite);
  }

  show(msg: string, o: ToastOpts = {}): ToastHandle {
    const t = h("div", { class: "toast" });
    let timer = 0;
    const close = () => { window.clearTimeout(timer); t.classList.add("is-out"); window.setTimeout(() => t.remove(), 180); };
    const fill = (m: string, oo: ToastOpts) => {
      const kind = oo.kind ?? "info";
      t.className = `toast toast--${kind}`;
      t.replaceChildren(...[
        ico(ICON[kind], 16, "toast-ic"),
        h("div", { class: "toast-b" }, h("p", { class: "toast-m" }, m), oo.detail ? h("p", { class: "toast-d" }, oo.detail) : null),
        oo.action ? h("button", { type: "button", class: "toast-act", onclick: () => { oo.action!.fn(); close(); } }, oo.action.label) : null,
        h("button", { type: "button", class: "toast-x", "aria-label": "Tutup notifikasi", onclick: close }, ico("close", 14))].filter((x): x is HTMLElement => !!x));
      window.clearTimeout(timer);
      const ms = oo.ms ?? (kind === "err" ? 7000 : 4200);
      if (ms > 0) timer = window.setTimeout(close, ms);
      (kind === "err" ? this.assertive : this.polite).append(t);
    };
    fill(msg, o);
    return { close, update: (m, oo = {}) => fill(m, oo) };
  }
}
