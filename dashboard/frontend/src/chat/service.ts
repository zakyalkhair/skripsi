/**
 * Antarmuka layanan tanya jawab "Asisten Situasi Bencana".
 *
 * STATUS BACKEND: backend dasbor saat ini TIDAK menyediakan endpoint tanya jawab (QA/GraphRAG).
 * Karena itu layanan bawaan adalah `unavailableChatService`, yang selalu menolak dengan
 * `ChatUnavailableError` — tidak ada permintaan jaringan, tidak ada jawaban atau sitasi buatan.
 *
 * Untuk menghubungkan backend kelak, buat implementasi `ChatService` (mis. memanggil endpoint
 * yang benar-benar ada) lalu daftarkan dengan `setChatService()`. Sitasi harus berasal dari
 * respons backend (ID tweet / kejadian / laporan nyata), tidak pernah dibuat di frontend.
 */
import type { Jenis } from "../types";

export type ChatScope = "terpilih" | "semua";

/** Konteks yang menyertai pertanyaan (tanpa data pribadi; tidak pernah ditulis ke URL). */
export interface ChatContext {
  scope: ChatScope;
  wilayah: { tingkat: "nasional" | "prov" | "kab" | "lokasi"; kode_prov: string | null; kode_kab: string | null; gazetteer_id: string | null; nama: string | null };
  filter: { jenis: Jenis[] | null; dari: string | null; sampai: string | null };
  event_id: string | null;
}

export interface ChatTurn { role: "user" | "assistant"; text: string }

/** Rujukan sumber jawaban — hanya dari backend. */
export interface Citation {
  tweet_id: string;
  event_id?: string | null;
  mention_id?: string | null;
  tanggal?: string | null; // tanggal laporan/unggah (ISO)
  teks?: string | null;
  url?: string | null;
}

export interface ChatAnswer { text: string; citations: Citation[] }

export class ChatUnavailableError extends Error {
  constructor(message = "Layanan tanya jawab belum tersedia di backend.") { super(message); this.name = "ChatUnavailableError"; }
}

export interface ChatService {
  /** false = belum ada backend; UI menampilkan keadaan "belum tersedia" secara terbuka. */
  readonly available: boolean;
  readonly name: string;
  ask(question: string, ctx: ChatContext, history: ChatTurn[], signal: AbortSignal): Promise<ChatAnswer>;
}

export const unavailableChatService: ChatService = {
  available: false,
  name: "tidak tersedia",
  async ask() {
    throw new ChatUnavailableError("Backend dasbor belum menyediakan endpoint tanya jawab (GraphRAG).");
  },
};

let current: ChatService = unavailableChatService;
const listeners = new Set<(s: ChatService) => void>();

export function chatService(): ChatService { return current; }

/** Daftarkan implementasi layanan (null = kembali ke "tidak tersedia"). */
export function setChatService(s: ChatService | null): void {
  current = s ?? unavailableChatService;
  for (const l of listeners) l(current);
}

export function onChatService(l: (s: ChatService) => void): () => void { listeners.add(l); return () => listeners.delete(l); }

/** Validasi bentuk sitasi dari layanan: buang entri tanpa ID tweet yang sah (tidak pernah dilengkapi/dikarang). */
export function cleanCitations(c: unknown): Citation[] {
  if (!Array.isArray(c)) return [];
  return c.filter((x): x is Citation => !!x && typeof x === "object" && typeof (x as Citation).tweet_id === "string" && (x as Citation).tweet_id.trim() !== "")
    .map((x) => ({ tweet_id: x.tweet_id, event_id: typeof x.event_id === "string" ? x.event_id : null, mention_id: typeof x.mention_id === "string" ? x.mention_id : null,
      tanggal: typeof x.tanggal === "string" ? x.tanggal : null, teks: typeof x.teks === "string" ? x.teks : null,
      url: typeof x.url === "string" && /^https:\/\//.test(x.url) ? x.url : null }));
}
