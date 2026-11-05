/**
 * Penyajian fakta berpusat-kejadian (dampak, kebutuhan, penanganan, sumber laporan).
 * Prinsip: setiap fakta tampil apa adanya bersama tanggal & laporan sumbernya; angka dari laporan
 * berbeda TIDAK pernah dijumlahkan; informasi yang tidak ada ditulis "belum dilaporkan", bukan nol.
 */
import { h } from "../dom";
import { angka, tgl, waktu } from "../format";
import { KEBUTUHAN_STATUS } from "../jenis";
import type { Dampak, KebGrup, Kebutuhan, Kronologi, Laporan, Lembaga, LokRef, Sumber, TweetInfo } from "../types";
import { ico, type IconName } from "./icons";

export type TweetMap = Record<string, TweetInfo>;

export function dampakText(d: Dampak): string {
  return d.label ?? `${d.objek ?? d.kelas ?? "objek tidak disebutkan"} ${d.status ?? ""}`.trim();
}
export function dampakQty(d: Dampak): string {
  return d.jumlah !== null && d.jumlah !== undefined ? `${angka(d.jumlah)}${d.satuan ? ` ${d.satuan}` : ""}` : "jumlah tidak disebutkan";
}

const locNames = (ls: LokRef[]) => ls.map((l) => l.nama).join(", ");

/** Tweet sumber: waktu unggah, ID, teks, tautan (bila ada). */
export function tweetBox(tid: string, tw: TweetMap): HTMLElement {
  const t = tw[tid];
  if (!t) return h("div", { class: "stw stw--na" }, h("span", { class: "stw-id" }, `ID ${tid}`), " · teks tweet tidak tersedia pada rentang ini");
  return h("div", { class: "stw" },
    h("div", { class: "stw-h" }, h("span", {}, waktu(t.upload)), h("span", { class: "stw-id" }, `ID ${tid}`)),
    h("p", { class: "stw-x", lang: "id" }, t.text ?? "Teks tidak tersedia"),
    t.url ? h("a", { class: "tweet-a", href: t.url, target: "_blank", rel: "noopener noreferrer" }, "Buka tweet asli", ico("external", 13))
      : h("span", { class: "tweet-na" }, "Tautan sumber tidak tersedia"));
}

/** Satu rujukan sumber yang dapat dibuka: "7 Sep 2026 · tw_2106" → teks tweet-nya. */
function sumberToggle(s: Sumber, tw: TweetMap): HTMLElement {
  const ids = s.tweet_ids.length ? s.tweet_ids : [];
  return h("details", { class: "fsrc", "data-mention": s.mention_id },
    h("summary", { "aria-label": `Sumber: ${tgl(s.tanggal_lokal)}, tweet ${ids.join(", ") || "tidak tersedia"} (laporan ${s.mention_id}). Tampilkan tweet.` },
      h("span", { class: "fsrc-d" }, tgl(s.tanggal_lokal)), h("span", { class: "fsrc-id" }, ids.join(", ") || s.mention_id), ico("chevDown", 12, "fsrc-chev")),
    h("div", { class: "fsrc-body" }, ...(ids.length ? ids.map((t) => tweetBox(t, tw)) : [h("p", { class: "muted small" }, "Tidak ada tweet tertaut")])));
}

export function sumberList(src: Sumber[] | undefined, tw: TweetMap): HTMLElement | null {
  if (!src || !src.length) return null;
  return h("div", { class: "fsrcs" }, h("span", { class: "fsrcs-l" }, src.length > 1 ? `Dilaporkan ${src.length}×:` : "Dilaporkan:"), ...src.map((s) => sumberToggle(s, tw)));
}

/** Label atribusi untuk tampilan tanpa fokus lokasi (kartu kab/kota). */
function scopeTag(atribusi: Dampak["atribusi"], lokasi: LokRef[]): HTMLElement {
  if (atribusi === "kejadian" || !lokasi.length)
    return h("span", { class: "ftag ftag--ev", title: "Disebut dalam laporan kejadian ini tanpa lokasi tertentu" }, "Tingkat kejadian");
  return h("span", { class: "ftag" }, ico("target", 11), locNames(lokasi));
}

export function dampakItem(d: Dampak, tw: TweetMap, withScope: boolean): HTMLElement {
  return h("li", { class: "fact", "data-id": d.id },
    h("span", { class: "fact-main" }, h("span", { class: "fact-what" }, dampakText(d)), h("b", { class: `fact-qty${d.jumlah == null ? " is-na" : ""}` }, dampakQty(d))),
    withScope ? h("span", { class: "fact-scope" }, scopeTag(d.atribusi, d.lokasi)) : d.atribusi === "lokasi_lain" && d.lokasi.length
      ? h("span", { class: "fact-scope" }, h("span", { class: "ftag" }, ico("target", 11), locNames(d.lokasi))) : null,
    sumberList(d.sumber, tw));
}

export function kebutuhanItem(k: Kebutuhan, tw: TweetMap, withScope: boolean): HTMLElement {
  const lok = k.lokasi ? [k.lokasi] : [];
  return h("li", { class: "fact", "data-id": k.id },
    h("span", { class: "fact-main" }, h("span", { class: "fact-what" }, k.item ?? "item tidak disebutkan"),
      h("span", { class: `need need--${k.status}` }, KEBUTUHAN_STATUS[k.status ?? ""] ?? "Status tidak tersedia")),
    h("span", { class: "fact-scope" }, k.kategori ? h("span", { class: "ftag ftag--plain" }, k.kategori) : null,
      withScope ? scopeTag(k.atribusi, lok) : k.atribusi === "lokasi_lain" && lok.length ? h("span", { class: "ftag" }, ico("target", 11), locNames(lok)) : null),
    sumberList(k.sumber, tw));
}

export function lembagaItem(l: Lembaga, tw: TweetMap): HTMLElement {
  return h("li", { class: "fact", "data-id": l.id },
    h("span", { class: "fact-main" }, h("span", { class: "fact-what" }, l.nama_kanonik ?? "Nama tidak tersedia"), l.tingkat ? h("span", { class: "lvl" }, l.tingkat) : null),
    h("span", { class: "fact-scope" }, ...[...l.peran, l.induk ? `Bagian dari ${l.induk}` : ""].filter(Boolean).map((p) => h("span", { class: "ftag ftag--plain" }, p))),
    sumberList(l.sumber, tw));
}

/** Sub-bagian fakta dengan keadaan kosong ringkas ("Belum ada … yang dilaporkan"). */
export function factBlock(title: string, items: HTMLElement[], emptyText: string | null, note?: string, n?: number, raw = false): HTMLElement | null {
  if (!items.length && emptyText === null) return null;
  const count = n ?? items.length;
  return h("section", { class: "fblock" },
    h("h4", { class: "fblock-t" }, title, count ? h("span", { class: "fblock-n" }, String(count)) : null),
    note ? h("p", { class: "fblock-note" }, note) : null,
    items.length ? (raw ? h("div", { class: "fgroups" }, ...items) : h("ul", { class: "facts" }, ...items)) : h("p", { class: "fempty" }, emptyText));
}

/** Daftar laporan sumber (EventMention) beserta tweet-nya. */
export function laporanList(lap: Laporan[], tw: TweetMap, opts: { relasi?: boolean } = {}): HTMLElement {
  return h("ol", { class: "srcl" }, ...lap.map((m) => h("li", { class: "srcl-i", "data-mention": m.mention_id },
    h("details", { class: "srcl-d" },
      h("summary", {},
        h("span", { class: "m-date" }, tgl(m.tanggal_lokal)),
        h("span", { class: "srcl-id" }, `Laporan ${m.mention_id}`),
        opts.relasi && m.relasi === "evakuasi" ? h("span", { class: "ftag ftag--plain" }, "tujuan evakuasi") : null,
        m.lokasi && m.lokasi.length ? h("span", { class: "srcl-loc" }, locNames(m.lokasi)) : null,
        h("span", { class: "srcl-n" }, `${m.tweet_ids.length} tweet`), ico("chevDown", 12, "fsrc-chev")),
      h("div", { class: "fsrc-body" }, ...m.tweet_ids.map((t) => tweetBox(t, tw)))))));
}

// --------------------------------------------------------------------------- tampilan sesuai desain (kelompok)
export const KELAS_UI: Record<string, string> = { manusia: "Manusia", rumah: "Rumah", pelayanan_dasar: "Pelayanan dasar",
  prasarana_vital: "Prasarana vital", sosial_ekonomi: "Sosial ekonomi", lainnya: "Lainnya" };
export const KATEGORI_UI: Record<string, string> = { makanan: "Makanan", air_bersih_sanitasi: "Air bersih & sanitasi",
  kesehatan_obat: "Kesehatan & obat", hunian_tenda: "Hunian & tenda", sandang_selimut: "Sandang & selimut", evakuasi_sar: "Evakuasi & SAR",
  logistik_lain: "Logistik lain", psikososial: "Psikososial", dana: "Dana", lainnya: "Lainnya" };
const kelasIc = (k: string | null) => (`k_${k && k in KELAS_UI ? k : "lainnya"}`) as IconName;
const katIc = (k: string | null) => (`n_${k && k in KATEGORI_UI && k !== "lainnya" ? k : "logistik_lain"}`) as IconName;

const locChip = (l: LokRef | null, ev = false) => l ? h("span", { class: "ftag" }, ico("target", 11), l.nama)
  : ev ? h("span", { class: "ftag ftag--ev", title: "Disebut dalam laporan tanpa lokasi tertentu" }, "Tingkat kejadian") : null;
const srcs = (src: Sumber[] | undefined, tw: TweetMap) => (src ?? []).map((s) => sumberToggle(s, tw));

/** Dampak dikelompokkan per kelas AffectedObject; setiap angka = satu laporan (tidak dijumlahkan). */
export function dampakGroups(ds: Dampak[], tw: TweetMap, opts: { scope: boolean }): HTMLElement[] {
  const by = new Map<string, Dampak[]>();
  for (const d of ds) { const k = d.kelas && d.kelas in KELAS_UI ? d.kelas : "lainnya"; by.set(k, [...(by.get(k) ?? []), d]); }
  return Object.keys(KELAS_UI).filter((k) => by.has(k)).map((k) => h("div", { class: "fgroup", "data-kelas": k },
    h("p", { class: "fgroup-h" }, ico(kelasIc(k), 15), KELAS_UI[k]),
    h("ul", { class: "facts" }, ...by.get(k)!.map((d) => h("li", { class: "fact", "data-id": d.id },
      h("span", { class: "fact-main" }, h("span", { class: "fact-what" }, dampakText(d)), h("b", { class: `fact-qty${d.jumlah == null ? " is-na" : ""}` }, dampakQty(d))),
      h("span", { class: "fact-meta" }, ...(d.lokasi.length ? d.lokasi.map((l) => locChip(l)) : [opts.scope || d.atribusi === "kejadian" ? locChip(null, true) : null]),
        ...srcs(d.sumber, tw)))))));
}

/** Kebutuhan per kategori → per item → baris per lokasi dengan status penyaluran (dihitung backend). */
export function kebutuhanGroups(gs: KebGrup[], tw: TweetMap): HTMLElement[] {
  const by = new Map<string, KebGrup[]>();
  for (const g of gs) { const k = g.kategori && g.kategori in KATEGORI_UI ? g.kategori : "lainnya"; by.set(k, [...(by.get(k) ?? []), g]); }
  return Object.keys(KATEGORI_UI).filter((k) => by.has(k)).map((k) => h("div", { class: "fgroup", "data-kategori": k },
    h("p", { class: "fgroup-h" }, ico(katIc(k), 15), KATEGORI_UI[k]),
    ...by.get(k)!.map((g) => h("div", { class: "fact fact--need" },
      h("span", { class: "fact-main" }, h("span", { class: "fact-what" }, g.item ?? "item tidak disebutkan"), g.ringkas ? h("span", { class: "ftag ftag--plain" }, g.ringkas) : null),
      ...g.baris.map((b) => h("div", { class: "need-row" },
        b.status === "supplied"
          ? h("span", { class: "need need--supplied" }, ico("check", 11), b.lembaga.length ? `Disalurkan · ${b.lembaga.join(", ")}` : "Disalurkan")
          : h("span", { class: "need need--demanded" }, "Diminta"),
        h("span", { class: "fact-meta" }, locChip(b.lokasi, true), ...srcs(b.sumber, tw))))))));
}

/** Penanganan: lembaga + aksi spesifik (properti relasi HANDLES/DEPLOYED_TO) + lokasi + tanggal & tweet. */
export function lembagaBlock(l: Lembaga, tw: TweetMap): HTMLElement {
  const aksi = l.aksi ?? [];
  return h("li", { class: "fact", "data-id": l.id },
    h("span", { class: "fact-main" }, h("span", { class: "fact-what" }, l.nama_kanonik ?? "Nama tidak tersedia"), l.tingkat ? h("span", { class: "lvl" }, l.tingkat) : null),
    ...(aksi.length ? aksi.map((a) => h("span", { class: "aksi-row" }, h("span", { class: "aksi-t" }, a.aksi),
      h("span", { class: "fact-meta" }, locChip(a.lokasi), a.tanggal ? h("span", { class: "fsrc-d" }, tgl(a.tanggal)) : null, a.tweet_id ? h("span", { class: "fsrc-id" }, a.tweet_id) : null)))
      : [h("span", { class: "fact-scope" }, ...l.peran.map((p) => h("span", { class: "ftag ftag--plain" }, p)))]),
    l.induk ? h("span", { class: "fblock-note" }, `Bagian dari ${l.induk}`) : null,
    aksi.length ? null : sumberList(l.sumber, tw));
}

/** Kronologi per tanggal. Saat ini cadangan tanpa LLM (cuplikan tweet); kelak laporan situasi Modul 4.3. */
export function kronologiList(ks: Kronologi[]): HTMLElement {
  return h("ol", { class: "krono" }, ...ks.map((k) => h("li", { class: "krono-i" },
    h("span", { class: "krono-d" }, tgl(k.tanggal)),
    h("span", { class: "krono-x" }, k.teks || "Teks tidak tersedia", ...k.tweet_ids.map((t) => h("span", { class: "fsrc-id" }, ` [${t}]`))))));
}
