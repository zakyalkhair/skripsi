/** Layanan tanya jawab GraphRAG (Modul 4) lewat GET /api/tanya. Jawaban & sitasi hanya dari respons backend. */
import { cleanCitations, ChatUnavailableError, type ChatAnswer, type ChatContext, type ChatService } from "./service";

const PIPA = ["banjir", "longsor", "cuaca", "karhutla", "gempa", "erupsi"];

export async function graphragTersedia(): Promise<{ ok: boolean; model?: string }> {
  try {
    const r = await fetch("/api/tanya/status", { headers: { Accept: "application/json" } });
    if (!r.ok) return { ok: false };
    const j = await r.json() as { tersedia: boolean; model?: string };
    return { ok: !!j.tersedia, model: j.model };
  } catch { return { ok: false }; }
}

export function graphragChatService(model = "GraphRAG"): ChatService {
  return {
    available: true,
    name: `GraphRAG (${model})`,
    async ask(question: string, ctx: ChatContext, _history, signal: AbortSignal): Promise<ChatAnswer> {
      const p = new URLSearchParams({ q: question });
      if (ctx.scope === "terpilih") {
        const w = ctx.wilayah;
        if (w.kode_kab) p.set("kab", w.kode_kab); else if (w.kode_prov) p.set("prov", w.kode_prov);
        if (ctx.event_id) p.set("event_id", ctx.event_id);
        const j = ctx.filter.jenis;
        if (j && j.length && j.length < PIPA.length) p.set("jenis", j.join(","));
        if (ctx.filter.dari) p.set("dari", ctx.filter.dari);
        if (ctx.filter.sampai) p.set("sampai", ctx.filter.sampai);
      }
      const r = await fetch(`/api/tanya?${p}`, { signal, headers: { Accept: "application/json" } });
      if (r.status === 503) throw new ChatUnavailableError((await r.json().catch(() => ({}))).detail ?? "Layanan GraphRAG tidak tersedia.");
      if (!r.ok) throw new Error(`Gagal menjawab (HTTP ${r.status})`);
      const j = await r.json() as { text: string; citations: unknown };
      return { text: j.text, citations: cleanCitations(j.citations) };
    },
  };
}
