import type { Histogram, Jenis, KabAgregat, KabKejadian, KabTitik, Ringkasan, Wilayah } from "./types";
import { JENIS } from "./jenis";

/** Versi kontrak API yang diharapkan frontend (sama dengan API_VERSI di backend/app/repository/base.py). */
export const API_VERSI = 4;
export const PESAN_VERSI = "Server backend masih versi lama: sebagian rincian (sumber laporan per kejadian) tidak tersedia. Pastikan proses uvicorn lama di port 8000 sudah berhenti, lalu jalankan ulang.";
/** Respons server lama dilengkapi nilai kosong agar dasbor tetap berjalan (tidak ada data yang dikarang). */
let lama = false;
export const backendLama = () => lama;

export interface Query { jenis: Set<Jenis>; dari: string | null; sampai: string | null }

/** jenis: semua dipilih -> parameter tidak dikirim (semua); kosong -> "jenis=" (tidak ada yang dipilih). */
export function qs(q: Partial<Query>, extra: Record<string, string | null | undefined> = {}): string {
  const p = new URLSearchParams();
  if (q.jenis && q.jenis.size < JENIS.length) p.set("jenis", [...q.jenis].sort().join(","));
  if (q.dari) p.set("dari", q.dari);
  if (q.sampai) p.set("sampai", q.sampai);
  for (const [k, v] of Object.entries(extra)) if (v) p.set(k, v);
  const s = p.toString();
  return s ? `?${s}` : "";
}

/** Cakupan geografis aktif (satu tingkat paling rinci yang dipilih). */
export interface Cakupan { prov?: string | null; kab?: string | null; lokasi?: string | null }
const scopeParams = (c: Cakupan) => (c.lokasi ? { lokasi: c.lokasi } : c.kab ? { kab: c.kab } : c.prov ? { prov: c.prov } : {});

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

/** Satu AbortController per kanal: permintaan baru membatalkan yang lama sehingga respons usang
 * tidak pernah menimpa pilihan filter yang lebih baru. */
const controllers = new Map<string, AbortController>();

async function get<T>(channel: string, url: string): Promise<T> {
  controllers.get(channel)?.abort();
  const ac = new AbortController();
  controllers.set(channel, ac);
  const r = await fetch(url, { signal: ac.signal, headers: { Accept: "application/json" } });
  if (!r.ok) {
    let msg = r.statusText;
    try { msg = (await r.json()).detail ?? msg; } catch { /* abaikan */ }
    throw new ApiError(r.status, msg);
  }
  const data = (await r.json()) as T;
  if (controllers.get(channel) === ac) controllers.delete(channel);
  return data;
}

export const isAbort = (e: unknown): boolean => e instanceof DOMException && e.name === "AbortError";
export const cancel = (channel: string): void => { controllers.get(channel)?.abort(); controllers.delete(channel); };

export const api = {
  wilayah: () => get<Wilayah>("wilayah", "/api/wilayah"),
  agregat: (q: Query) => get<KabAgregat>("agregat", `/api/kab-agregat${qs(q)}`),
  /** Agregat tanpa filter jenis (kunci terpisah agar tidak membatalkan permintaan utama): kartu per jenis tetap lengkap. */
  agregatSemua: (q: Query) => get<KabAgregat>("agregat-semua", `/api/kab-agregat${qs({ ...q, jenis: new Set(JENIS) })}`),
  agregatProv: (q: Query, prov: string) => get<KabAgregat>("agregat-prov", `/api/kab-agregat${qs(q, { prov })}`),
  kejadian: (kode: string, q: Query) => get<KabKejadian>("kejadian", `/api/kab/${kode}/kejadian${qs(q)}`).then((d) => {
    if (!d.tweets || d.kejadian.some((k) => !Array.isArray(k.laporan))) lama = true;
    d.tweets ??= {};
    for (const k of d.kejadian) { k.laporan ??= []; k.dampak ??= []; k.kebutuhan ??= []; k.lembaga ??= []; }
    return d;
  }),
  titik: (kode: string, q: Query) => get<KabTitik>("titik", `/api/kab/${kode}/titik${qs(q)}`),
  ringkasan: (gid: string, q: Query) => get<Ringkasan>("ringkasan", `/api/titik/${encodeURIComponent(gid)}/ringkasan${qs(q)}`).then((d) => {
    if (!d.tweet_map || !Array.isArray(d.lembaga_dikerahkan)) lama = true;
    d.tweet_map ??= {}; d.lembaga_dikerahkan ??= [];
    for (const k of d.kejadian) {
      k.laporan ??= []; k.dampak ??= []; k.kebutuhan ??= []; k.penanganan ??= []; k.evakuasi ??= [];
      k.jumlah_laporan_kejadian ??= k.laporan.length;
    }
    return d;
  }),
  histogram: (q: Query, scope: Cakupan) => get<Histogram>("histogram", `/api/histogram${qs({ jenis: q.jenis }, scopeParams(scope))}`),
  eksporUrl: (q: Query, scope: Cakupan) => `/api/ekspor${qs(q, scopeParams(scope))}`,
  geo: (name: string) => fetch(`${import.meta.env.BASE_URL}geo/${name}.geojson`).then((r) => {
    if (!r.ok) throw new ApiError(r.status, `Batas wilayah ${name} tidak dapat dimuat`);
    return r.json() as Promise<GeoJSON.FeatureCollection>;
  }),
};
