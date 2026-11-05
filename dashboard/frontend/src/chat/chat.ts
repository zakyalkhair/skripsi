import { h } from "../dom";
import { ico } from "../ui/icons";
import type { EventRef } from "../ui/panel";
import { citationList } from "./citations";
import {
  chatService, ChatUnavailableError, cleanCitations, onChatService,
  type ChatContext, type ChatScope, type ChatTurn, type Citation,
} from "./service";

/** Konteks pertanyaan saat ini, disusun oleh pemanggil dari state peta (bukan dari isi percakapan). */
export interface ChatCtxInfo { ctx: ChatContext; label: string; examples: string[] }

type Status = "ok" | "loading" | "error" | "unavailable";
interface Msg { id: number; role: "user" | "assistant"; text: string; status: Status; citations?: Citation[]; ctxLabel?: string; q?: string; ctx?: ChatContext }

const DISCLAIMER = "Jawaban berdasarkan laporan media sosial, bukan data resmi BNPB.";

/**
 * Tampilan "Asisten Situasi Bencana" di tab panel kanan. Riwayat percakapan disimpan di memori
 * instans ini (bertahan saat berpindah tab), tidak pernah ditulis ke URL atau penyimpanan lokal.
 */
export class ChatView {
  readonly el: HTMLElement;
  private log: HTMLElement;
  private input: HTMLTextAreaElement;
  private sendBtn: HTMLButtonElement;
  private ctxLabel: HTMLElement;
  private evChip: HTMLElement;
  private statusPill: HTMLElement;
  private radios: HTMLButtonElement[];
  private scope: ChatScope = "terpilih";
  private event: EventRef | null = null;
  private msgs: Msg[] = [];
  /** Elemen per pesan + kunci isinya: hanya pesan yang berubah yang diganti (log tidak diumumkan ulang). */
  private rendered = new Map<number, { el: HTMLElement; key: string }>();
  private seq = 0;
  private pending: AbortController | null = null;

  constructor(private getCtx: (scope: ChatScope, ev: EventRef | null) => ChatCtxInfo, private onShowDetail: () => void) {
    this.statusPill = h("span", { class: "chat-status" });
    this.ctxLabel = h("b", { class: "chat-ctx-v" });
    this.evChip = h("span", { class: "chat-ev", hidden: true });
    const radio = (v: ChatScope, label: string) => h("button", { type: "button", role: "radio", class: "seg-btn", "data-scope": v,
      "aria-checked": String(v === this.scope), tabindex: v === this.scope ? 0 : -1, onclick: () => this.setScope(v) }, label);
    this.radios = [radio("terpilih", "Konteks terpilih"), radio("semua", "Seluruh data")];
    const seg = h("div", { class: "seg chat-seg", role: "radiogroup", "aria-label": "Cakupan pertanyaan" }, ...this.radios);
    seg.addEventListener("keydown", (e) => {
      if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(e.key)) return;
      e.preventDefault();
      const next: ChatScope = this.scope === "terpilih" ? "semua" : "terpilih";
      this.setScope(next);
      this.radios.find((r) => r.dataset.scope === next)!.focus();
    });
    const head = h("header", { class: "chat-h" },
      h("div", { class: "chat-title" },
        h("span", { class: "chat-mark", "aria-hidden": "true" }, ico("sparkle", 16)),
        h("div", {}, h("h2", { class: "chat-t" }, "Asisten Situasi Bencana"), h("p", { class: "chat-sub" }, "Tanya jawab berdasarkan data bencana")),
        this.statusPill),
      h("div", { class: "chat-ctx" }, h("span", { class: "chat-ctx-l" }, "Bertanya tentang:"), this.ctxLabel, this.evChip),
      h("div", { class: "chat-scope" }, h("span", { class: "chat-scope-l", id: "chat-scope-l" }, "Cakupan"), seg,
        h("span", { class: "chat-scope-n" }, "Tidak mengubah filter peta")));
    this.log = h("div", { class: "chat-log", role: "log", "aria-live": "polite", "aria-label": "Percakapan dengan asisten", tabindex: 0 });
    this.input = h("textarea", { class: "chat-input", rows: 1, placeholder: "Tanyakan tentang situasi bencana...", "aria-label": "Pertanyaan untuk asisten",
      maxlength: 1000, enterkeyhint: "send" });
    this.sendBtn = h("button", { type: "submit", class: "chat-send", "aria-label": "Kirim pertanyaan", title: "Kirim (Enter)", disabled: true }, ico("send", 18));
    const form = h("form", { class: "chat-form" },
      h("div", { class: "chat-field" }, this.input, this.sendBtn),
      h("p", { class: "chat-disc" }, ico("info", 13), DISCLAIMER));
    form.addEventListener("submit", (e) => { e.preventDefault(); this.send(); });
    this.input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); this.send(); }
    });
    this.input.addEventListener("input", () => this.autosize());
    this.el = h("div", { class: "chat" }, head, this.log, form);
    onChatService(() => { this.renderStatus(); this.render(); });
    this.renderStatus();
    this.refresh();
  }

  focusInput(): void { this.input.focus({ preventScroll: true }); }

  /** Konteks kejadian dari tombol "Tanyakan tentang kejadian ini" (null = lepaskan). */
  setEvent(ev: EventRef | null): void {
    this.event = ev;
    if (ev) this.setScope("terpilih", false);
    this.refresh();
  }
  get eventRef(): EventRef | null { return this.event; }

  private setScope(v: ChatScope, refresh = true): void {
    this.scope = v;
    for (const r of this.radios) {
      const on = r.dataset.scope === v;
      r.setAttribute("aria-checked", String(on));
      r.tabIndex = on ? 0 : -1;
    }
    if (refresh) this.refresh();
  }

  /** Perbarui label konteks & contoh pertanyaan (dipanggil saat pilihan peta berubah). */
  refresh(): void {
    const info = this.getCtx(this.scope, this.event);
    this.ctxLabel.textContent = info.label;
    const evOn = !!this.event && this.scope === "terpilih";
    this.evChip.hidden = !evOn;
    if (evOn) this.evChip.replaceChildren(h("span", {}, `Kejadian: ${this.event!.nama}`),
      h("button", { type: "button", class: "chat-ev-x", "aria-label": "Lepaskan konteks kejadian", title: "Lepaskan konteks kejadian",
        onclick: () => this.setEvent(null) }, ico("close", 12)));
    if (!this.msgs.length) this.render();
  }

  private renderStatus(): void {
    const ok = chatService().available;
    this.statusPill.className = `chat-status${ok ? " is-ok" : ""}`;
    const dummy = chatService().name.startsWith("dummy");
    this.statusPill.className = `chat-status${ok && !dummy ? " is-ok" : ""}`;
    this.statusPill.textContent = dummy ? "Mode dummy" : ok ? "Terhubung" : "Belum terhubung";
    this.statusPill.title = ok ? `Layanan: ${chatService().name}` : "Backend belum menyediakan layanan tanya jawab (GraphRAG)";
  }

  private autosize(): void {
    this.input.style.height = "auto";
    this.input.style.height = `${Math.min(this.input.scrollHeight, 132)}px`;
    this.sendBtn.disabled = !this.input.value.trim() || !!this.pending;
  }

  send(text?: string): void {
    const q = (text ?? this.input.value).trim();
    if (!q || this.pending) return;
    const info = this.getCtx(this.scope, this.event);
    this.msgs.push({ id: ++this.seq, role: "user", text: q, status: "ok", ctxLabel: info.label });
    const bot: Msg = { id: ++this.seq, role: "assistant", text: "", status: "loading", q, ctx: info.ctx };
    this.msgs.push(bot);
    if (text === undefined) { this.input.value = ""; this.autosize(); }
    void this.run(bot);
  }

  private async run(bot: Msg): Promise<void> {
    const ac = new AbortController();
    this.pending = ac;
    bot.status = "loading"; bot.text = ""; bot.citations = undefined;
    this.render();
    const history: ChatTurn[] = this.msgs.filter((m) => m.id < bot.id && m.status === "ok").map((m) => ({ role: m.role, text: m.text }));
    try {
      const ans = await chatService().ask(bot.q!, bot.ctx!, history.slice(0, -1), ac.signal);
      const t = typeof ans?.text === "string" ? ans.text.trim() : "";
      if (!t) { bot.status = "error"; bot.text = "Layanan mengembalikan jawaban kosong."; }
      else { bot.status = "ok"; bot.text = t; bot.citations = cleanCitations(ans.citations); }
    } catch (e) {
      if (ac.signal.aborted) { bot.status = "error"; bot.text = "Permintaan dibatalkan."; }
      else if (e instanceof ChatUnavailableError || !chatService().available) bot.status = "unavailable";
      else { bot.status = "error"; bot.text = e instanceof Error && e.message ? e.message : "Kesalahan tidak diketahui."; }
    } finally {
      if (this.pending === ac) this.pending = null;
      this.render();
      this.autosize();
    }
  }

  private retry(bot: Msg): void { if (!this.pending) void this.run(bot); }

  private render(): void {
    if (!this.msgs.length) { this.rendered.clear(); this.log.replaceChildren(this.emptyState()); return; }
    this.log.querySelector(".chat-empty")?.remove();
    for (const m of this.msgs) {
      const key = `${m.status}|${m.text}|${m.citations?.length ?? 0}`;
      const cur = this.rendered.get(m.id);
      if (cur && cur.key === key) continue;
      const el = this.bubble(m);
      if (cur) cur.el.replaceWith(el); else this.log.append(el);
      this.rendered.set(m.id, { el, key });
    }
    this.log.scrollTop = this.log.scrollHeight;
  }

  private emptyState(): HTMLElement {
    const info = this.getCtx(this.scope, this.event);
    return h("div", { class: "chat-empty" },
      h("span", { class: "chat-empty-ic", "aria-hidden": "true" }, ico("sparkle", 22)),
      h("h3", { class: "chat-empty-t" }, "Apa yang ingin Anda ketahui?"),
      h("p", { class: "chat-empty-d" }, "Ajukan pertanyaan tentang kejadian, dampak, kebutuhan, atau penanganan bencana. Jawaban akan merujuk tweet dan laporan sumbernya."),
      chatService().available ? null : h("p", { class: "chat-empty-warn" }, ico("info", 14),
        "Layanan tanya jawab belum terhubung ke backend, sehingga pertanyaan belum dapat dijawab."),
      h("p", { class: "chat-ex-t" }, "Contoh pertanyaan"),
      h("div", { class: "chat-ex" }, ...info.examples.map((q) => h("button", { type: "button", class: "chat-ex-b", onclick: () => this.send(q) }, q))));
  }

  private bubble(m: Msg): HTMLElement {
    if (m.role === "user")
      return h("div", { class: "msg msg--user" }, h("div", { class: "msg-b" }, m.text), m.ctxLabel ? h("p", { class: "msg-ctx" }, `Konteks: ${m.ctxLabel}`) : null);
    if (m.status === "loading")
      return h("div", { class: "msg msg--bot is-loading", "aria-busy": "true" },
        h("div", { class: "msg-b" }, h("span", { class: "dots", "aria-hidden": "true" }, h("i", {}), h("i", {}), h("i", {})), h("span", {}, "Mencari jawaban dari data…"),
          h("button", { type: "button", class: "linkish msg-cancel", onclick: () => this.pending?.abort() }, "Batalkan")));
    if (m.status === "unavailable")
      return h("div", { class: "msg msg--bot msg--na", role: "status" },
        h("div", { class: "msg-b" },
          h("p", { class: "msg-h" }, ico("info", 15), "Asisten belum tersedia"),
          h("p", {}, "Dasbor ini belum terhubung ke layanan tanya jawab (GraphRAG) di backend, sehingga pertanyaan Anda belum dapat diproses. Tidak ada jawaban yang dibuat."),
          h("p", { class: "msg-hint" }, "Sementara itu, lihat laporan beserta sumbernya di panel rincian."),
          h("div", { class: "msg-acts" },
            h("button", { type: "button", class: "btn btn--ghost btn--sm", onclick: () => this.onShowDetail() }, "Lihat panel rincian"),
            h("button", { type: "button", class: "btn btn--ghost btn--sm", onclick: () => this.retry(m) }, ico("retry", 14), "Coba lagi"))));
    if (m.status === "error")
      return h("div", { class: "msg msg--bot msg--err", role: "alert" },
        h("div", { class: "msg-b" },
          h("p", { class: "msg-h" }, ico("alert", 15), "Jawaban tidak dapat dimuat"),
          h("p", {}, m.text),
          h("div", { class: "msg-acts" }, h("button", { type: "button", class: "btn btn--ghost btn--sm", onclick: () => this.retry(m) }, ico("retry", 14), "Coba lagi"))));
    const paras = m.text.split(/\n{2,}/).map((p) => h("p", {}, ...p.split("\n").flatMap((ln, i) => (i ? [h("br"), ln] : [ln]))));
    return h("div", { class: "msg msg--bot" },
      h("div", { class: "msg-b" }, ...paras,
        citationList(m.citations ?? []) ?? h("p", { class: "msg-nocite" }, "Jawaban ini tidak menyertakan rujukan sumber.")),
      h("p", { class: "msg-ctx" }, DISCLAIMER));
  }
}
