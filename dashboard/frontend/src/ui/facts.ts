/**
 * Penyajian fakta berpusat-kejadian (dampak, kebutuhan, penanganan, sumber laporan).
 * Prinsip: setiap fakta tampil apa adanya bersama tanggal & laporan sumbernya; angka dari laporan
 * berbeda TIDAK pernah dijumlahkan; informasi yang tidak ada ditulis "belum dilaporkan", bukan nol.
 */
import { h } from "../dom";
import { angka, tgl, waktu } from "../format";
import { KEBUTUHAN_STATUS } from "../jenis";
import type { Dampak, KebBaris, KebGrup, Kebutuhan, Kronologi, Laporan, Lembaga, LokRef, Sumber, TweetInfo } from "../types";
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

const locChip = (l: LokRef | null, ev = false) => l ? h("span", { class: "ftag ftag--loc" }, ico("target", 11), l.nama)
  : ev ? h("span", { class: "ftag ftag--ev", title: "Disebut dalam laporan tanpa lokasi tertentu" }, "Tingkat kejadian") : null;

const srcChip = (s: Sumber, tw: TweetMap) => sumberToggle(s, tw);

/** Dampak (desain Figma): label + jumlah, ikon kelas di kanan, chip lokasi & chip tanggal·tweet. Diurutkan per kelas. */
export function dampakGroups(ds: Dampak[], tw: TweetMap, _opts: { scope: boolean }): HTMLElement[] {
  if (!ds.length) return [];
  const ord = Object.keys(KELAS_UI);
  const sorted = [...ds].sort((a, b) => ord.indexOf(a.kelas && a.kelas in KELAS_UI ? a.kelas : "lainnya") - ord.indexOf(b.kelas && b.kelas in KELAS_UI ? b.kelas : "lainnya"));
  return [h("ul", { class: "facts" }, ...sorted.map((d) => h("li", { class: "fact", "data-id": d.id, "data-kelas": d.kelas ?? "lainnya" },
    h("span", { class: "fact-main" }, h("span", { class: "fact-what" }, dampakText(d)), h("b", { class: `fact-qty${d.jumlah == null ? " is-na" : ""}` }, dampakQty(d)),
      h("span", { class: "fact-ic", title: KELAS_UI[d.kelas ?? ""] ?? "Lainnya" }, ico(kelasIc(d.kelas), 16))),
    h("span", { class: "fact-meta" }, ...(d.lokasi.length ? d.lokasi.map((l) => locChip(l)) : []),
      ...(d.sumber ?? []).map((x) => srcChip(x, tw))))))];
}

const statusChip = (b: KebBaris) => b.status === "supplied"
  ? h("span", { class: "need need--supplied" }, ico("check", 11), b.lembaga.length ? `Disalurkan · ${b.lembaga.join(", ")}` : "Disalurkan")
  : h("span", { class: "need need--demanded" }, "Diminta");

/** Kebutuhan (desain Figma): item + status penyaluran; bila beberapa lokasi: ringkasan "x dari n" + baris per lokasi. */
export function kebutuhanGroups(gs: KebGrup[], tw: TweetMap): HTMLElement[] {
  if (!gs.length) return [];
  const ord = Object.keys(KATEGORI_UI);
  const sorted = [...gs].sort((a, b) => ord.indexOf(a.kategori ?? "lainnya") - ord.indexOf(b.kategori ?? "lainnya"));
  return [h("ul", { class: "facts" }, ...sorted.map((g) => {
    const one = g.baris.length === 1 ? g.baris[0] : null;
    return h("li", { class: "fact fact--need", "data-kategori": g.kategori ?? "lainnya" },
      h("span", { class: "fact-main" }, h("span", { class: "fact-what" }, g.item ?? "item tidak disebutkan"),
        h("span", { class: "fact-right" }, one ? statusChip(one) : g.ringkas ? h("span", { class: "ftag ftag--count" }, g.ringkas) : null,
          h("span", { class: "fact-ic", title: KATEGORI_UI[g.kategori ?? ""] ?? "Lainnya" }, ico(katIc(g.kategori), 16)))),
      ...(one ? [h("span", { class: "fact-meta" }, locChip(one.lokasi), ...one.sumber.map((x) => srcChip(x, tw)))]
        : g.baris.map((b) => h("div", { class: "need-row" }, statusChip(b),
          h("span", { class: "fact-meta" }, locChip(b.lokasi), ...b.sumber.map((x) => srcChip(x, tw)))))));
  }))];
}

/** Penanganan (desain Figma): nama + tingkat; tiap aksi = pil aksi, lalu chip lokasi & chip tanggal·tweet. */
export function lembagaBlock(l: Lembaga, tw: TweetMap): HTMLElement {
  const aksi = l.aksi ?? [];
  return h("li", { class: "fact fact--org", "data-id": l.id },
    h("span", { class: "fact-main" }, h("span", { class: "fact-what org-n" }, l.nama_kanonik ?? "Nama tidak tersedia"), l.tingkat ? h("span", { class: "lvl" }, l.tingkat) : null),
    ...(aksi.length ? aksi.map((a) => h("span", { class: "aksi-row" }, h("span", { class: "aksi-pill" }, a.aksi),
      h("span", { class: "fact-meta" }, locChip(a.lokasi),
        a.tanggal || a.tweet_id ? h("span", { class: "dchip" }, a.tanggal ? h("b", {}, tgl(a.tanggal)) : null, a.tweet_id ? h("span", {}, a.tweet_id) : null) : null)))
      : [h("span", { class: "fact-scope" }, ...l.peran.map((p) => h("span", { class: "aksi-pill" }, p)))]),
    l.induk ? h("span", { class: "fblock-note" }, `Bagian dari ${l.induk}`) : null,
    aksi.length ? null : sumberList(l.sumber, tw));
}

/** Kronologi per tanggal. Saat ini cadangan tanpa LLM (cuplikan tweet); kelak laporan situasi Modul 4.3. */
export function kronologiList(ks: Kronologi[]): HTMLElement {
  const panjang = (d: string) => new Date(`${d}T00:00:00`).toLocaleDateString("id-ID", { day: "numeric", month: "long", year: "numeric" });
  return h("ol", { class: "krono" }, ...ks.map((k) => h("li", { class: "krono-i" },
    h("span", { class: "krono-d" }, panjang(k.tanggal)),
    h("span", { class: "krono-x" }, k.teks || "Teks tidak tersedia", k.tweet_ids.length ? ` [${k.tweet_ids.join(", ")}]` : ""))));
}

/** Daftar tweet sumber (desain Figma: "Sumber laporan" yang dapat dilipat). */
export function tweetFold(title: string, ids: string[], tw: TweetMap, cls = ""): HTMLElement {
  return h("details", { class: `tfold ${cls}`.trim() },
    h("summary", {}, h("span", { class: "tfold-t" }, title), h("span", { class: "ftag ftag--count" }, `${ids.length} tweet`), ico("chevDown", 14, "fsrc-chev")),
    h("ol", { class: "tfold-l" }, ...ids.map((t) => h("li", {}, tweetBox(t, tw)))));
}
