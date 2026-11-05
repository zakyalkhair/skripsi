import { h, reducedMotion } from "../dom";
import { angka, rentang, tgl, waktu } from "../format";
import { KEBUTUHAN_STATUS, LABEL_PENDEK, STATUS_LABEL, TINGKAT_LABEL } from "../jenis";
import type { Dampak, Jenis, KabAgregat, KabKejadian, KabTitik, Kebutuhan, Kejadian, Lembaga, Ringkasan, Wilayah } from "../types";

export interface PanelHandlers {
  onKab(kode: string): void;
  onTitik(gid: string): void;
  onSorot(eid: string | null): void;
  onBack(): void; // dari lokasi ke kab
  onNational(): void;
  onReset(): void;
  onAllDates(): void;
  onAllJenis(): void;
}

export interface EmptyCtx { jenisKosong: boolean; adaTanggal: boolean }

const jenisTag = (j: Jenis) => h("span", { class: "jtag", style: `--c: var(--j-${j})` }, h("i", { "aria-hidden": "true" }), LABEL_PENDEK[j]);
const stat = (label: string, value: string | number, hint?: string) =>
  h("div", { class: "stat", title: hint ?? null },
    h("span", { class: `stat-v${typeof value === "string" && value.length > 6 ? " stat-v--sm" : ""}` }, typeof value === "number" ? angka(value) : value),
    h("span", { class: "stat-l" }, label));
const section = (title: string, ...body: (Node | null | false)[]) =>
  h("section", { class: "psec" }, h("h3", { class: "psec-t" }, title), ...body);
const none = (t = "Tidak disebutkan") => h("p", { class: "muted" }, t);

function dampakText(d: Dampak): string {
  const qty = d.jumlah !== null && d.jumlah !== undefined ? `${angka(d.jumlah)}${d.satuan ? ` ${d.satuan}` : ""}` : "jumlah tidak disebutkan";
  return `${d.kelas ?? "objek tidak disebutkan"} ${d.status ?? ""}`.trim() + ` — ${qty}`;
}

function dampakList(ds: Dampak[], showLoc: boolean): HTMLElement {
  return h("ul", { class: "plist" }, ...ds.map((d) => h("li", {},
    h("span", { class: "plist-main" }, dampakText(d)),
    showLoc ? h("span", { class: "plist-sub" }, d.lokasi.length ? d.lokasi.map((l) => l.nama).join(", ") : "Tidak dapat ditautkan ke lokasi tertentu") : null)));
}

function kebutuhanList(ks: Kebutuhan[], showLoc: boolean): HTMLElement {
  return h("ul", { class: "plist" }, ...ks.map((k) => h("li", {},
    h("span", { class: "plist-main" }, `${k.item ?? "item tidak disebutkan"}`, h("span", { class: `need need--${k.status}` }, KEBUTUHAN_STATUS[k.status ?? ""] ?? "Status tidak tersedia")),
    h("span", { class: "plist-sub" }, [k.kategori ?? "", showLoc ? (k.lokasi ? k.lokasi.nama : "Tidak dapat ditautkan ke lokasi tertentu") : ""].filter(Boolean).join(" · ")))));
}

function lembagaList(ls: Lembaga[]): HTMLElement {
  return h("ul", { class: "plist" }, ...ls.map((l) => h("li", {},
    h("span", { class: "plist-main" }, l.nama_kanonik ?? "Nama tidak tersedia", l.tingkat ? h("span", { class: "lvl" }, l.tingkat) : null),
    h("span", { class: "plist-sub" }, [...l.peran, l.induk ? `Bagian dari ${l.induk}` : ""].filter(Boolean).join(" · ")))));
}

function statusBadge(st: string): HTMLElement {
  return h("span", { class: `status status--${st === "ya" ? "ya" : "tidak"}`, title: "Status ambang bencana (ya/tidak) — bukan status berlangsung/selesai" },
    STATUS_LABEL[st] ?? "Status tidak tersedia");
}

export class Panel {
  readonly el: HTMLElement;
  private body: HTMLElement;
  private key = "";
  private cards = new Map<string, HTMLElement>();

  constructor(private hd: PanelHandlers) {
    this.body = h("div", { class: "panel-body" });
    this.el = h("aside", { class: "panel", "aria-label": "Rincian", "aria-live": "off" }, this.body);
  }

  private show(node: HTMLElement, key: string, dir: "in" | "out" | "same" = "in"): void {
    const changed = key !== this.key;
    this.key = key;
    node.classList.add("panel-view");
    if (changed && !reducedMotion()) node.classList.add(`enter-${dir}`);
    this.body.replaceChildren(node);
    if (changed) this.body.scrollTop = 0;
  }

  skeleton(key: string): void {
    const sk = h("div", { class: "skel-wrap", "aria-busy": "true", "aria-label": "Memuat rincian" },
      h("div", { class: "skel skel--t" }), h("div", { class: "skel-row" }, h("div", { class: "skel skel--s" }), h("div", { class: "skel skel--s" }), h("div", { class: "skel skel--s" })),
      h("div", { class: "skel skel--c" }), h("div", { class: "skel skel--c" }));
    this.show(sk, key, "same");
  }

  error(msg: string, retry: () => void): void {
    this.show(h("div", { class: "pstate pstate--err", role: "alert" },
      h("h2", { class: "pstate-t" }, "Data tidak dapat dimuat"), h("p", {}, msg),
      h("button", { type: "button", class: "btn", onclick: retry }, "Coba lagi")), `err:${msg}`, "same");
  }

  empty(ctx: EmptyCtx): HTMLElement {
    if (ctx.jenisKosong)
      return h("div", { class: "pstate" }, h("h2", { class: "pstate-t" }, "Belum ada jenis bencana yang dipilih"),
        h("p", {}, "Pilih minimal satu jenis bencana untuk menampilkan data."),
        h("button", { type: "button", class: "btn", onclick: () => this.hd.onAllJenis() }, "Pilih semua jenis"));
    return h("div", { class: "pstate" }, h("h2", { class: "pstate-t" }, "Tidak ada laporan yang sesuai dengan filter yang dipilih."),
      h("div", { class: "pstate-actions" },
        ctx.adaTanggal ? h("button", { type: "button", class: "btn", onclick: () => this.hd.onAllDates() }, "Perluas rentang tanggal") : null,
        h("button", { type: "button", class: "btn btn--ghost", onclick: () => this.hd.onReset() }, "Atur ulang filter")));
  }

  // ------------------------------------------------------------- nasional
  nasional(agg: KabAgregat, wil: Wilayah, scope: string, ctx: EmptyCtx): void {
    const r = agg.ringkasan;
    const nama = new Map(wil.kab.map((k) => [k.kode_kab, k]));
    const rows = [...agg.kab].sort((a, b) => b.jumlah_kejadian - a.jumlah_kejadian || b.jumlah_laporan - a.jumlah_laporan);
    const max = Math.max(1, ...rows.map((x) => x.jumlah_kejadian));
    const view = h("div", {},
      h("header", { class: "phead" },
        h("p", { class: "eyebrow" }, "Ikhtisar nasional"),
        h("h2", { class: "ptitle" }, "Sebaran kejadian bencana"),
        h("p", { class: "psub" }, scope)),
      h("div", { class: "stats" },
        stat("Kejadian bencana", r.jumlah_kejadian, "Kejadian (DisasterEvent) unik yang periodenya beririsan dengan rentang tanggal"),
        stat("Tweet sumber unik", r.jumlah_tweet, "Tweet unik yang melaporkan laporan kejadian pada rentang tanggal"),
        stat("Kab/kota", r.jumlah_kab, "Kab/kota dengan minimal satu kejadian yang sesuai filter")),
      r.jumlah_kejadian === 0 ? this.empty(ctx) : h("div", {},
        section("Kab/kota dengan kejadian",
          h("ol", { class: "rank" }, ...rows.map((x) => {
            const k = nama.get(x.kode_kab);
            return h("li", {}, h("button", { type: "button", class: "rank-btn", onclick: () => this.hd.onKab(x.kode_kab),
              "aria-label": `${k?.nama ?? x.kode_kab}: ${x.jumlah_kejadian} kejadian, ${x.jumlah_laporan} laporan. Buka wilayah.` },
              h("span", { class: "rank-name" }, k?.nama ?? x.kode_kab, h("small", {}, k?.provinsi ?? "")),
              h("span", { class: "rank-bar", "aria-hidden": "true" }, h("i", { style: `width:${(x.jumlah_kejadian / max) * 100}%` })),
              h("span", { class: "rank-n" }, angka(x.jumlah_kejadian), h("small", {}, `${angka(x.jumlah_laporan)} lap.`))));
          })),
          h("p", { class: "hint" }, "Pilih kab/kota di peta atau di daftar ini untuk melihat lokasi yang dilaporkan."))));
    this.show(view, "nasional", "out");
  }

  // ------------------------------------------------------------- kabupaten
  kab(d: KabKejadian, t: KabTitik | null, tweetUnik: number | null, prov: string, sorot: string | null, ctx: EmptyCtx): void {
    this.cards.clear();
    const lap = d.kejadian.reduce((a, k) => a + k.jumlah_laporan_periode, 0);
    const view = h("div", {},
      h("header", { class: "phead" },
        h("p", { class: "eyebrow" }, prov),
        h("h2", { class: "ptitle" }, d.nama),
        h("p", { class: "psub" }, "Angka di bawah mengikuti filter jenis dan rentang tanggal.")),
      h("div", { class: "stats stats--4" },
        stat("Kejadian", d.kejadian.length, "Kejadian unik yang periodenya beririsan dengan rentang"),
        stat("Laporan", lap, "Laporan kejadian (EventMention) bertanggal di dalam rentang"),
        stat("Tweet unik", tweetUnik ?? "–"),
        stat("Lokasi", t ? t.titik.length : "–", "Lokasi unik (gazetteer_id) yang dapat dipetakan")),
      t && t.laporan_tanpa_titik > 0
        ? h("p", { class: "note" }, `${angka(t.laporan_tanpa_titik)} laporan hanya menyebut wilayah kab/kota (tanpa lokasi yang lebih rinci) sehingga tidak tampil sebagai penanda.`) : null,
      d.kejadian.length === 0 ? this.empty(ctx)
        : h("div", { class: "cards", role: "list", "aria-label": "Kejadian bencana" }, ...d.kejadian.map((k) => this.card(k, sorot === k.event_id))));
    this.show(view, `kab:${d.kode_kab}`, this.key.startsWith("lokasi") ? "out" : "in");
  }

  private card(k: Kejadian, on: boolean): HTMLElement {
    const btn = h("button", { type: "button", class: "sorot", "aria-pressed": String(on), "data-event": k.event_id,
      disabled: k.lokasi_ids.length === 0, title: k.lokasi_ids.length ? "Sorot lokasi kejadian ini di peta" : "Tidak ada lokasi yang dapat dipetakan pada rentang ini",
      onclick: () => this.hd.onSorot(btn.getAttribute("aria-pressed") === "true" ? null : k.event_id) },
      h("span", { class: "sorot-dot", "aria-hidden": "true" }), on ? "Disorot" : "Sorot");
    const periodeBeda = k.jumlah_laporan_periode !== k.jumlah_laporan_total;
    const det = h("details", { class: "card-more" },
      h("summary", {}, "Dampak, kebutuhan, dan lembaga", h("span", { class: "muted" }, " · pada rentang terpilih")),
      section("Dampak dilaporkan", k.dampak.length ? dampakList(k.dampak, true) : none()),
      section("Kebutuhan", k.kebutuhan.length ? kebutuhanList(k.kebutuhan, true) : none()),
      section("Lembaga terkait", k.lembaga.length ? lembagaList(k.lembaga) : none()));
    const summaryBits = [
      k.dampak.length ? `${k.dampak.length} dampak` : null, k.kebutuhan.length ? `${k.kebutuhan.length} kebutuhan` : null,
      k.lembaga.length ? `${k.lembaga.length} lembaga` : null].filter(Boolean).join(" · ");
    const el = h("article", { class: `card${on ? " is-sorot" : ""}`, role: "listitem", style: `--c: var(--j-${k.jenis})`, "data-event": k.event_id },
      h("header", { class: "card-h" },
        h("div", {}, jenisTag(k.jenis), h("h3", { class: "card-t" }, k.nama)), btn),
      h("dl", { class: "card-meta" },
        h("div", {}, h("dt", {}, "Mulai"), h("dd", { class: "mono" }, tgl(k.start_time))),
        h("div", {}, h("dt", {}, "Laporan terakhir"), h("dd", { class: "mono" }, tgl(k.end_time))),
        h("div", { class: "span2" }, h("dt", {}, "Status"), h("dd", {}, statusBadge(k.status)))),
      h("p", { class: "card-counts" },
        h("b", {}, angka(k.jumlah_laporan_periode)), " laporan · ", h("b", {}, angka(k.jumlah_tweet_periode)), " tweet unik",
        periodeBeda ? h("span", { class: "muted" }, ` (dari ${angka(k.jumlah_laporan_total)} laporan sepanjang data)`) : h("span", { class: "muted" }, " pada rentang ini")),
      k.lokasi.length ? h("p", { class: "card-locs" }, ...k.lokasi.map((l, i) => [i ? ", " : "",
        h("button", { type: "button", class: "linkish", onclick: () => this.hd.onTitik(l.gazetteer_id) }, l.nama)]).flat())
        : h("p", { class: "card-locs muted" }, "Tidak ada lokasi rinci pada rentang ini"),
      summaryBits ? h("p", { class: "card-sum" }, summaryBits) : null,
      det);
    this.cards.set(k.event_id, el);
    return el;
  }

  setSorot(eid: string | null): void {
    for (const [id, el] of this.cards) {
      const on = id === eid;
      el.classList.toggle("is-sorot", on);
      el.classList.toggle("is-redup", eid !== null && !on);
      const b = el.querySelector<HTMLButtonElement>(".sorot")!;
      b.setAttribute("aria-pressed", String(on));
      b.lastChild!.textContent = on ? "Disorot" : "Sorot";
    }
  }

  // ------------------------------------------------------------- lokasi
  lokasi(r: Ringkasan, kabNama: string | null, kabSaatIni: string | null): void {
    const L = r.lokasi;
    const luar = kabSaatIni && L.kode_kab_lokasi && L.kode_kab_lokasi !== kabSaatIni;
    const tw = new Map(r.tweets.map((t) => [t.tweet_id, t]));
    const view = h("div", {},
      h("button", { type: "button", class: "back", onclick: () => this.hd.onBack() }, "← ", kabNama ? `Kembali ke ${kabNama}` : "Kembali"),
      h("header", { class: "phead" },
        h("p", { class: "eyebrow" }, TINGKAT_LABEL[L.tingkat] ?? L.tingkat),
        h("h2", { class: "ptitle" }, L.nama),
        h("p", { class: "psub" }, L.admin_path ?? "Jalur administratif tidak tersedia"),
        L.latitude !== null ? h("p", { class: "coord mono", title: "Koordinat entri gazetteer; bukan titik pusat atau batas bencana" },
          `${L.latitude!.toFixed(4)}, ${L.longitude!.toFixed(4)}`) : null),
      luar ? h("p", { class: "note" }, `Lokasi ini berada di wilayah administratif lain dan dirujuk oleh laporan dari ${kabNama ?? "kab/kota terpilih"}. Penanda tetap di posisi aslinya.`) : null,
      h("div", { class: "stats" },
        stat("Laporan", r.jumlah_laporan, "Laporan kejadian unik yang menyebut lokasi ini"),
        stat("Tweet unik", r.jumlah_tweet),
        stat("Periode laporan", rentang(r.tanggal_awal, r.tanggal_akhir))),
      r.jenis.length ? h("div", { class: "jtags" }, ...r.jenis.map(jenisTag)) : null,
      r.jumlah_laporan === 0 ? h("div", { class: "pstate" }, h("p", {}, "Tidak ada laporan untuk lokasi ini yang sesuai dengan filter yang dipilih.")) : null,
      r.kejadian.length ? section(`Kejadian yang menyebut lokasi ini (${r.kejadian.length})`,
        ...r.kejadian.map((k) => h("div", { class: "evgroup", style: `--c: var(--j-${k.jenis})` },
          h("div", { class: "evgroup-h" }, jenisTag(k.jenis), h("strong", {}, k.nama)),
          h("div", { class: "evgroup-m" }, h("span", {}, k.nama_kab ?? "Kab/kota tidak tersedia"), statusBadge(k.status)),
          h("p", { class: "evgroup-d mono" }, `Mulai ${tgl(k.start_time)} · laporan terakhir ${tgl(k.end_time)}`),
          h("ol", { class: "mentions" }, ...k.laporan.map((m) => h("li", {},
            h("span", { class: "mono" }, tgl(m.tanggal_lokal)), " ",
            ...m.tweet_ids.map((t) => h("a", { class: "tref", href: `#tw-${t}` }, tw.get(t) ? `Tweet ${waktu(tw.get(t)!.upload).split(", ")[1] ?? ""}` : t)))))))) : null,
      section("Dampak di lokasi ini", r.dampak_lokasi.length ? dampakList(r.dampak_lokasi, false) : none("Tidak ada dampak yang tertaut ke lokasi ini")),
      r.dampak_tanpa_lokasi.length ? section("Dampak tingkat kejadian",
        h("p", { class: "muted small" }, "Disebut dalam laporan yang sama, tetapi tidak dapat ditautkan ke lokasi tertentu."),
        dampakList(r.dampak_tanpa_lokasi, false)) : null,
      section("Kebutuhan di lokasi ini", r.kebutuhan_lokasi.length ? kebutuhanList(r.kebutuhan_lokasi, false) : none("Tidak ada kebutuhan yang tertaut ke lokasi ini")),
      r.kebutuhan_tanpa_lokasi.length ? section("Kebutuhan tingkat kejadian",
        h("p", { class: "muted small" }, "Tidak dapat ditautkan ke lokasi tertentu."), kebutuhanList(r.kebutuhan_tanpa_lokasi, false)) : null,
      r.evakuasi_ke_sini.length || r.evakuasi_dari_sini.length ? section("Evakuasi",
        h("ul", { class: "plist" },
          ...r.evakuasi_ke_sini.map((e) => h("li", {}, h("span", { class: "plist-main" }, "Lokasi tujuan evakuasi"),
            h("span", { class: "plist-sub" }, e.asal.length ? `dari ${e.asal.map((a) => a.nama).join(", ")}` : "asal tidak disebutkan"))),
          ...r.evakuasi_dari_sini.map((e) => h("li", {}, h("span", { class: "plist-main" }, "Warga dievakuasi"),
            h("span", { class: "plist-sub" }, `ke ${e.tujuan.map((a) => a.nama).join(", ")}`))))) : null,
      section("Lembaga terkait", r.lembaga.length ? lembagaList(r.lembaga) : none()),
      section(`Tweet sumber (${r.tweets.length})`,
        r.tweets.length ? h("ol", { class: "tweets" }, ...r.tweets.map((t) => h("li", { class: "tweet", id: `tw-${t.tweet_id}` },
          h("div", { class: "tweet-h" }, h("span", { class: "mono" }, waktu(t.upload)), h("span", { class: "mono muted" }, t.tweet_id)),
          h("blockquote", { class: "tweet-x", lang: "id" }, t.text ?? "Teks tidak tersedia"),
          t.url ? h("a", { class: "tweet-a", href: t.url, target: "_blank", rel: "noopener noreferrer" }, "Buka tweet asli ↗")
            : h("span", { class: "muted small" }, "Tautan sumber tidak tersedia")))) : none("Tidak ada tweet pada rentang ini")));
    this.show(view, `lokasi:${L.gazetteer_id}`, "in");
  }
}

