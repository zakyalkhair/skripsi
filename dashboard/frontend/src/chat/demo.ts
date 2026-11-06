/**
 * Layanan ringkasan DUMMY (sementara, sampai endpoint GraphRAG tersedia).
 * Tidak memahami pertanyaan: hanya merangkum data dasbor yang sesuai konteks (wilayah, filter, kejadian)
 * dari endpoint yang sudah ada. Semua angka & sitasi berasal dari respons backend — tidak ada yang dikarang.
 */
import { qs } from "../api";
import { tgl } from "../format";
import { JENIS, LABEL_PENDEK } from "../jenis";
import type { Jenis, KabAgregat, KabKejadian, Ringkasan, TweetInfo, Wilayah } from "../types";
import type { ChatAnswer, ChatContext, ChatService, Citation } from "./service";

const PREFIX = "Jawaban contoh (dummy): ringkasan otomatis dari data dasbor, belum dari GraphRAG — isi pertanyaan belum dianalisis.";

async function get<T>(url: string, signal: AbortSignal): Promise<T> {
  const r = await fetch(url, { signal, headers: { Accept: "application/json" } });
  if (!r.ok) throw new Error(`Data tidak dapat dimuat (HTTP ${r.status})`);
  return r.json() as Promise<T>;
}

const jenisSet = (c: ChatContext) => new Set<Jenis>(c.filter.jenis ?? JENIS);
const q = (c: ChatContext) => ({ jenis: jenisSet(c), dari: c.filter.dari, sampai: c.filter.sampai });

function cite(tw: Record<string, TweetInfo>, lap: { tweet_ids: string[]; mention_id: string; tanggal_lokal: string }[], eid: string, out: Citation[]): void {
  for (const m of lap) for (const t of m.tweet_ids) {
    if (out.length >= 6 || out.some((x) => x.tweet_id === t)) continue;
    out.push({ tweet_id: t, event_id: eid, mention_id: m.mention_id, tanggal: m.tanggal_lokal, teks: tw[t]?.text ?? null, url: tw[t]?.url ?? null });
  }
}

export function demoChatService(): ChatService {
  return {
    available: true,
    name: "dummy (ringkasan data dasbor)",
    async ask(_question, ctx, _history, signal): Promise<ChatAnswer> {
      const w = ctx.wilayah, lines: string[] = [PREFIX], cites: Citation[] = [];
      if (w.gazetteer_id) {
        const r = await get<Ringkasan>(`/api/titik/${encodeURIComponent(w.gazetteer_id)}/ringkasan${qs(q(ctx))}`, signal);
        const ks = ctx.event_id ? r.kejadian.filter((k) => k.event_id === ctx.event_id) : r.kejadian;
        lines.push(`${r.lokasi.nama}: ${r.jumlah_laporan} laporan dari ${r.jumlah_tweet} tweet menyebut lokasi ini, terkait ${ks.length} kejadian.`);
        for (const k of ks) {
          const d = (k.dampak ?? []).filter((x) => x.atribusi === "lokasi_ini");
          lines.push(`• ${k.nama} (${LABEL_PENDEK[k.jenis]}, ${tgl(k.start_time)}–${tgl(k.end_time)})${d.length ? ": " + d.map((x) => `${x.kelas ?? "objek"} ${x.status ?? ""} ${x.jumlah ?? "(jumlah tidak disebutkan)"} ${x.satuan ?? ""}`.replace(/\s+/g, " ").trim()).join("; ") : ": belum ada dampak yang dilaporkan di lokasi ini"}.`);
          cite(r.tweet_map ?? {}, k.laporan ?? [], k.event_id, cites);
        }
      } else if (w.kode_kab) {
        const d = await get<KabKejadian>(`/api/kab/${w.kode_kab}/kejadian${qs(q(ctx))}`, signal);
        const ks = ctx.event_id ? d.kejadian.filter((k) => k.event_id === ctx.event_id) : d.kejadian;
        lines.push(ctx.event_id ? `Kejadian terpilih di ${d.nama}:` : `${d.nama}: ${ks.length} kejadian sesuai filter.`);
        for (const k of ks) {
          const dampak = k.dampak.map((x) => `${x.kelas ?? "objek"} ${x.status ?? ""} ${x.jumlah ?? "(jumlah tidak disebutkan)"} ${x.satuan ?? ""} (${tgl(x.sumber?.[0]?.tanggal_lokal)})`.replace(/\s+/g, " ").trim());
          const need = k.kebutuhan.map((x) => x.item ?? "item tidak disebutkan");
          lines.push(`• ${k.nama} (${LABEL_PENDEK[k.jenis]}): ${k.jumlah_laporan_periode} laporan, ${k.jumlah_tweet_periode} tweet unik.` +
            (dampak.length ? ` Dampak: ${dampak.join("; ")}.` : " Belum ada dampak yang dilaporkan.") +
            (need.length ? ` Kebutuhan: ${need.join(", ")}.` : "") +
            (k.lembaga.length ? ` Penanganan: ${k.lembaga.map((l) => l.nama_kanonik).join(", ")}.` : ""));
          cite(d.tweets ?? {}, k.laporan ?? [], k.event_id, cites);
        }
        if (ks.length) lines.push("Angka dari laporan berbeda tidak dijumlahkan.");
      } else {
        const prov = w.kode_prov && ctx.scope === "terpilih" ? w.kode_prov : null;
        const [a, wil] = await Promise.all([get<KabAgregat>(`/api/kab-agregat${qs(q(ctx), { prov })}`, signal), get<Wilayah>("/api/wilayah", signal)]);
        const nama = new Map(wil.kab.map((k) => [k.kode_kab, k.nama]));
        const r = a.ringkasan;
        lines.push(`${w.nama ?? "Seluruh data"}: ${r.jumlah_kejadian} kejadian, ${r.jumlah_laporan} laporan, ${r.jumlah_tweet} tweet unik di ${r.jumlah_kab} kab/kota.`);
        const top = [...a.kab].filter((x) => x.jumlah_kejadian).sort((x, y) => y.jumlah_kejadian - x.jumlah_kejadian).slice(0, 5);
        if (top.length) lines.push("Kab/kota dengan kejadian terbanyak: " + top.map((x) => `${nama.get(x.kode_kab) ?? x.kode_kab} (${x.jumlah_kejadian})`).join(", ") + ".");
        lines.push("Pilih kab/kota atau lokasi untuk ringkasan dengan sumber tweet.");
      }
      if (lines.length === 1) lines.push("Tidak ada data yang sesuai konteks dan filter.");
      return { text: lines.join("\n\n"), citations: cites };
    },
  };
}
