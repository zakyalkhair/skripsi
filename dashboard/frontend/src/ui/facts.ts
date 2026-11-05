/**
 * Penyajian fakta berpusat-kejadian (dampak, kebutuhan, penanganan, sumber laporan).
 * Prinsip: setiap fakta tampil apa adanya bersama tanggal & laporan sumbernya; angka dari laporan
 * berbeda TIDAK pernah dijumlahkan; informasi yang tidak ada ditulis "belum dilaporkan", bukan nol.
 */
import { h } from "../dom";
import { angka, tgl, waktu } from "../format";
import { KEBUTUHAN_STATUS } from "../jenis";
import type { Dampak, Kebutuhan, Laporan, Lembaga, LokRef, Sumber, TweetInfo } from "../types";
import { ico } from "./icons";

export type TweetMap = Record<string, TweetInfo>;

export function dampakText(d: Dampak): string {
  return `${d.kelas ?? "objek tidak disebutkan"} ${d.status ?? ""}`.trim();
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

/** Satu rujukan sumber yang dapat dibuka: "9 Jan 2026 · laporan EM19" → tweet-tweetnya. */
function sumberToggle(s: Sumber, tw: TweetMap): HTMLElement {
  return h("details", { class: "fsrc" },
    h("summary", { "aria-label": `Sumber: laporan ${s.mention_id}, ${tgl(s.tanggal_lokal)}. Tampilkan tweet.` },
      h("span", { class: "fsrc-d" }, tgl(s.tanggal_lokal)), h("span", { class: "fsrc-id" }, s.mention_id), ico("chevDown", 12, "fsrc-chev")),
    h("div", { class: "fsrc-body" }, ...(s.tweet_ids.length ? s.tweet_ids.map((t) => tweetBox(t, tw)) : [h("p", { class: "muted small" }, "Tidak ada tweet tertaut")])));
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
export function factBlock(title: string, items: HTMLElement[], emptyText: string | null, note?: string): HTMLElement | null {
  if (!items.length && emptyText === null) return null;
  return h("section", { class: "fblock" },
    h("h4", { class: "fblock-t" }, title, items.length ? h("span", { class: "fblock-n" }, String(items.length)) : null),
    note ? h("p", { class: "fblock-note" }, note) : null,
    items.length ? h("ul", { class: "facts" }, ...items) : h("p", { class: "fempty" }, emptyText));
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
