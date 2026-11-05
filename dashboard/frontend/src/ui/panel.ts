import { h, reducedMotion } from "../dom";
import { angka, rentang, tgl, waktu } from "../format";
import { KEBUTUHAN_STATUS, LABEL_PENDEK, STATUS_LABEL, TINGKAT_LABEL } from "../jenis";
import { kelasOf } from "../map/legend";
import type { Dampak, Jenis, KabAgregat, KabKejadian, KabTitik, Kebutuhan, Kejadian, Lembaga, Ringkasan, Wilayah } from "../types";
import { ico } from "./icons";

export interface PanelHandlers {
  onKab(kode: string): void;
  onTitik(gid: string): void;
  onSorot(eid: string | null): void;
  onBack(): void;
  onReset(): void;
  onAllDates(): void;
  onAllJenis(): void;
}

export interface EmptyCtx { jenisKosong: boolean; adaTanggal: boolean }

const jenisTag = (j: Jenis) => h("span", { class: "jtag" }, h("i", { style: `background: var(--j-${j})`, "aria-hidden": "true" }), LABEL_PENDEK[j]);
const kpi = (label: string, value: string | number, hint?: string) =>
  h("div", { class: "kpi", title: hint ?? null },
    h("span", { class: `kpi-v${typeof value === "string" && value.length > 6 ? " kpi-v--sm" : ""}` }, typeof value === "number" ? angka(value) : value),
    h("span", { class: "kpi-l" }, label));
const section = (title: string, ...body: (Node | null | false)[]) => h("section", { class: "psec" }, h("h3", { class: "psec-t" }, title), ...body);
const none = (t = "Tidak disebutkan") => h("p", { class: "muted small" }, t);

function dampakText(d: Dampak): string {
  const qty = d.jumlah !== null && d.jumlah !== undefined ? `${angka(d.jumlah)}${d.satuan ? ` ${d.satuan}` : ""}` : "jumlah tidak disebutkan";
  return `${d.kelas ?? "objek tidak disebutkan"} ${d.status ?? ""}`.trim() + ` — ${qty}`;
}
const dampakList = (ds: Dampak[], showLoc: boolean) => h("ul", { class: "plist" }, ...ds.map((d) => h("li", {},
  h("span", { class: "plist-main" }, dampakText(d)),
  showLoc ? h("span", { class: "plist-sub" }, d.lokasi.length ? d.lokasi.map((l) => l.nama).join(", ") : "Tidak dapat ditautkan ke lokasi tertentu") : null)));
const kebutuhanList = (ks: Kebutuhan[], showLoc: boolean) => h("ul", { class: "plist" }, ...ks.map((k) => h("li", {},
  h("span", { class: "plist-main" }, k.item ?? "item tidak disebutkan", h("span", { class: `need need--${k.status}` }, KEBUTUHAN_STATUS[k.status ?? ""] ?? "Status tidak tersedia")),
  h("span", { class: "plist-sub" }, [k.kategori ?? "", showLoc ? (k.lokasi ? k.lokasi.nama : "Tidak dapat ditautkan ke lokasi tertentu") : ""].filter(Boolean).join(" · ")))));
const lembagaList = (ls: Lembaga[]) => h("ul", { class: "plist" }, ...ls.map((l) => h("li", {},
  h("span", { class: "plist-main" }, l.nama_kanonik ?? "Nama tidak tersedia", l.tingkat ? h("span", { class: "lvl" }, l.tingkat) : null),
  h("span", { class: "plist-sub" }, [...l.peran, l.induk ? `Bagian dari ${l.induk}` : ""].filter(Boolean).join(" · ")))));
const statusBadge = (st: string) => h("span", { class: `status status--${st === "ya" ? "ya" : "tidak"}`,
  title: "Status ambang bencana (ya/tidak) — bukan status berlangsung/selesai" }, STATUS_LABEL[st] ?? "Status tidak tersedia");

export class Panel {
  readonly el: HTMLElement;
  readonly body: HTMLElement;
  private key = "";
  private cards = new Map<string, HTMLElement>();
  private sorot: string | null = null;
  private openDetails = new Set<string>();
  private skelTimer = 0;

  constructor(private hd: PanelHandlers, head: HTMLElement) {
    this.body = h("div", { class: "panel-body", tabindex: -1 });
    this.el = h("aside", { class: "panel float-card", id: "panel", "aria-label": "Rincian" }, head, this.body);
  }

  private show(node: HTMLElement, key: string): void {
    window.clearTimeout(this.skelTimer);
    const changed = key !== this.key;
    this.key = key;
    node.classList.add("panel-view");
    if (changed && !reducedMotion()) node.classList.add("is-enter");
    this.body.replaceChildren(node);
    if (changed) this.body.scrollTop = 0;
  }

  /** Kerangka muat hanya bila pemuatan > 160 ms (mencegah kedip pada respons cepat). */
  skeleton(key: string): void {
    window.clearTimeout(this.skelTimer);
    this.skelTimer = window.setTimeout(() => {
      this.show(h("div", { class: "skel-wrap", "aria-busy": "true", "aria-label": "Memuat rincian" },
        h("div", { class: "skel skel--t" }), h("div", { class: "skel skel--s" }),
        h("div", { class: "skel-row" }, h("div", { class: "skel skel--k" }), h("div", { class: "skel skel--k" }), h("div", { class: "skel skel--k" })),
        h("div", { class: "skel skel--c" }), h("div", { class: "skel skel--c" })), key);
    }, 160);
  }

  error(msg: string, retry: () => void): void {
    this.show(h("div", { class: "pstate pstate--err", role: "alert" },
      h("h2", { class: "pstate-t" }, "Data tidak dapat dimuat"), h("p", {}, msg),
      h("button", { type: "button", class: "btn", onclick: retry }, "Coba lagi")), `err:${msg}`);
  }

  empty(ctx: EmptyCtx, compact = false): HTMLElement {
    if (ctx.jenisKosong)
      return h("div", { class: `pstate${compact ? " pstate--compact" : ""}` }, h("p", { class: "pstate-t" }, "Belum ada jenis bencana yang dipilih"),
        compact ? null : h("p", {}, "Pilih minimal satu jenis bencana untuk menampilkan data."),
        h("div", { class: "pstate-actions" }, h("button", { type: "button", class: "btn", onclick: () => this.hd.onAllJenis() }, "Pilih semua jenis")));
    return h("div", { class: `pstate${compact ? " pstate--compact" : ""}` }, h("p", { class: "pstate-t" }, "Tidak ada laporan yang sesuai dengan filter yang dipilih."),
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
    this.show(h("div", {},
      h("header", { class: "phead" }, h("h2", { class: "ptitle" }, "Sebaran kejadian bencana"), h("p", { class: "psub" }, scope)),
      h("div", { class: "kpis" },
        kpi("Kejadian bencana", r.jumlah_kejadian, "Kejadian (DisasterEvent) unik yang periodenya beririsan dengan rentang tanggal"),
        kpi("Tweet sumber unik", r.jumlah_tweet, "Tweet unik yang melaporkan laporan kejadian pada rentang tanggal"),
        kpi("Kab/kota", r.jumlah_kab, "Kab/kota dengan minimal satu kejadian yang sesuai filter")),
      r.jumlah_kejadian === 0 ? this.empty(ctx) : section("Kab/kota dengan kejadian",
        h("ol", { class: "rank" }, ...rows.map((x) => {
          const k = nama.get(x.kode_kab);
          return h("li", {}, h("button", { type: "button", class: "rank-btn", onclick: () => this.hd.onKab(x.kode_kab),
            "aria-label": `${k?.nama ?? x.kode_kab}: ${x.jumlah_kejadian} kejadian, ${x.jumlah_laporan} laporan. Buka wilayah.` },
            h("span", { class: "rank-name" }, h("span", {}, k?.nama ?? x.kode_kab), h("small", {}, k?.provinsi ?? "")),
            h("span", { class: "rank-bar", "aria-hidden": "true" }, h("i", { "data-k": kelasOf(x.jumlah_kejadian), style: `width:${(x.jumlah_kejadian / max) * 100}%` })),
            h("span", { class: "rank-n" }, h("b", {}, angka(x.jumlah_kejadian)), h("small", {}, `${angka(x.jumlah_laporan)} laporan`)),
            ico("chevRight", 14, "rank-go")));
        })),
        h("p", { class: "hint" }, "Klik kab/kota pada peta atau daftar ini untuk melihat lokasi yang dilaporkan."))), "nasional");
  }

  // ------------------------------------------------------------- kabupaten
  kab(d: KabKejadian, t: KabTitik | null, tweetUnik: number | null, prov: string, sorot: string | null, ctx: EmptyCtx, adaData: boolean): void {
    this.cards.clear();
    this.sorot = sorot;
    const lap = d.kejadian.reduce((a, k) => a + k.jumlah_laporan_periode, 0);
    const kosong = d.kejadian.length === 0
      ? (adaData ? this.empty(ctx) : h("div", { class: "pstate" }, h("p", { class: "pstate-t" }, "Belum ada data untuk wilayah ini."),
        h("p", {}, "Kab/kota ini berada di luar cakupan data yang tersedia.")))
      : null;
    this.show(h("div", {},
      h("header", { class: "phead" }, h("h2", { class: "ptitle" }, d.nama), h("p", { class: "psub" }, `${prov} · mengikuti filter jenis dan rentang tanggal`)),
      h("div", { class: "kpis kpis--4" },
        kpi("Kejadian", d.kejadian.length, "Kejadian unik yang periodenya beririsan dengan rentang"),
        kpi("Laporan", lap, "Laporan kejadian (EventMention) bertanggal di dalam rentang"),
        kpi("Tweet unik", tweetUnik ?? "–"),
        kpi("Lokasi", t ? t.titik.length : "–", "Lokasi unik (gazetteer_id) yang dapat dipetakan")),
      t && t.laporan_tanpa_titik > 0
        ? h("p", { class: "note" }, `${angka(t.laporan_tanpa_titik)} laporan hanya menyebut wilayah kab/kota (tanpa lokasi rinci) sehingga tidak tampil sebagai penanda.`) : null,
      kosong ?? h("div", {},
        h("p", { class: "cards-hint" }, "Klik kartu untuk menyorot lokasinya di peta."),
        h("div", { class: "cards", role: "list", "aria-label": "Kejadian bencana" }, ...d.kejadian.map((k) => this.card(k))))), `kab:${d.kode_kab}`);
  }

  private card(k: Kejadian): HTMLElement {
    const on = this.sorot === k.event_id;
    const bisa = k.lokasi_ids.length > 0;
    const hit = h("button", { type: "button", class: "card-hit", "aria-pressed": String(on), disabled: !bisa,
      onclick: () => this.toggle(k.event_id) },
      h("span", { class: "card-top" }, jenisTag(k.jenis), h("span", { class: "card-state" }, ico("target", 13), "Disorot")),
      h("span", { class: "card-t" }, k.nama),
      h("span", { class: "sr-only" }, bisa ? ". Sorot lokasi kejadian ini di peta." : ". Tidak ada lokasi yang dapat dipetakan pada rentang ini."));
    const det = h("details", { class: "card-more" },
      h("summary", {}, ico("chevRight", 13, "sum-chev"), h("span", {}, "Dampak, kebutuhan, dan lembaga")),
      h("p", { class: "card-scope" }, "Dari laporan pada rentang tanggal terpilih."),
      section("Dampak dilaporkan", k.dampak.length ? dampakList(k.dampak, true) : none()),
      section("Kebutuhan", k.kebutuhan.length ? kebutuhanList(k.kebutuhan, true) : none()),
      section("Lembaga terkait", k.lembaga.length ? lembagaList(k.lembaga) : none()));
    if (this.openDetails.has(k.event_id)) det.open = true;
    det.addEventListener("toggle", () => { det.open ? this.openDetails.add(k.event_id) : this.openDetails.delete(k.event_id); });
    const periodeBeda = k.jumlah_laporan_periode !== k.jumlah_laporan_total;
    const bits = [k.dampak.length ? `${k.dampak.length} dampak` : null, k.kebutuhan.length ? `${k.kebutuhan.length} kebutuhan` : null,
      k.lembaga.length ? `${k.lembaga.length} lembaga` : null].filter(Boolean).join(" · ");
    const el = h("article", { class: `card${on ? " is-sorot" : ""}${this.sorot && !on ? " is-redup" : ""}${bisa ? "" : " is-static"}`,
      role: "listitem", "data-event": k.event_id },
      hit,
      h("dl", { class: "card-meta" },
        h("div", {}, h("dt", {}, "Mulai"), h("dd", {}, tgl(k.start_time))),
        h("div", {}, h("dt", {}, "Laporan terakhir"), h("dd", {}, tgl(k.end_time)))),
      h("div", { class: "card-row" }, statusBadge(k.status),
        h("span", { class: "card-counts" }, h("b", {}, angka(k.jumlah_laporan_periode)), " laporan · ", h("b", {}, angka(k.jumlah_tweet_periode)), " tweet unik")),
      periodeBeda ? h("p", { class: "card-scope" }, `Pada rentang ini; ${angka(k.jumlah_laporan_total)} laporan sepanjang data.`) : null,
      k.lokasi.length ? h("p", { class: "card-locs" }, ico("target", 13, "loc-ic"), ...k.lokasi.map((l, i) => [i ? ", " : "",
        h("button", { type: "button", class: "linkish", onclick: () => this.hd.onTitik(l.gazetteer_id) }, l.nama)]).flat())
        : h("p", { class: "card-locs muted" }, "Tidak ada lokasi rinci pada rentang ini"),
      bits ? h("p", { class: "card-sum" }, bits) : null,
      det);
    // seluruh kartu dapat diklik; kontrol di dalamnya (tautan lokasi, rincian) tetap berfungsi sendiri
    el.addEventListener("click", (e) => {
      if (!bisa || (e.target as Element).closest("button, a, details")) return;
      if (window.getSelection()?.toString()) return; // pengguna sedang menyeleksi teks
      this.toggle(k.event_id);
    });
    this.cards.set(k.event_id, el);
    return el;
  }

  private toggle(eid: string): void { this.hd.onSorot(this.sorot === eid ? null : eid); }

  setSorot(eid: string | null): void {
    this.sorot = eid;
    for (const [id, el] of this.cards) {
      const on = id === eid;
      el.classList.toggle("is-sorot", on);
      el.classList.toggle("is-redup", eid !== null && !on);
      el.querySelector(".card-hit")!.setAttribute("aria-pressed", String(on));
    }
  }

  // ------------------------------------------------------------- lokasi
  lokasi(r: Ringkasan, kabNama: string | null, kabSaatIni: string | null): void {
    const L = r.lokasi;
    const luar = kabSaatIni && L.kode_kab_lokasi && L.kode_kab_lokasi !== kabSaatIni;
    const tw = new Map(r.tweets.map((t) => [t.tweet_id, t]));
    const tweets = h("details", { class: "psec psec--fold", open: true },
      h("summary", { class: "psec-t" }, ico("chevRight", 13, "sum-chev"), `Tweet sumber (${r.tweets.length})`),
      r.tweets.length ? h("ol", { class: "tweets" }, ...r.tweets.map((t) => h("li", { class: "tweet", id: `tw-${t.tweet_id}` },
        h("div", { class: "tweet-h" }, h("span", {}, waktu(t.upload)), h("span", { class: "tweet-id" }, `ID ${t.tweet_id}`)),
        h("blockquote", { class: "tweet-x", lang: "id" }, t.text ?? "Teks tidak tersedia"),
        t.url ? h("a", { class: "tweet-a", href: t.url, target: "_blank", rel: "noopener noreferrer" }, "Buka tweet asli", ico("external", 13))
          : h("span", { class: "tweet-na" }, "Tautan sumber tidak tersedia")))) : none("Tidak ada tweet pada rentang ini"));
    this.show(h("div", {},
      h("button", { type: "button", class: "back", onclick: () => this.hd.onBack() }, ico("arrowLeft", 15), kabNama ?? "Kembali"),
      h("header", { class: "phead" },
        h("h2", { class: "ptitle" }, L.nama),
        h("p", { class: "psub" }, `${TINGKAT_LABEL[L.tingkat] ?? L.tingkat} · ${L.admin_path ?? "Jalur administratif tidak tersedia"}`),
        L.latitude !== null ? h("p", { class: "coord", title: "Koordinat entri gazetteer; bukan titik pusat atau batas bencana" },
          `${L.latitude!.toFixed(4)}, ${L.longitude!.toFixed(4)}`) : null),
      luar ? h("p", { class: "note" }, `Lokasi ini berada di wilayah administratif lain dan dirujuk oleh laporan dari ${kabNama ?? "kab/kota terpilih"}. Penanda tetap di posisi aslinya.`) : null,
      h("div", { class: "kpis" },
        kpi("Laporan", r.jumlah_laporan, "Laporan kejadian unik yang menyebut lokasi ini"),
        kpi("Tweet unik", r.jumlah_tweet),
        kpi("Periode laporan", rentang(r.tanggal_awal, r.tanggal_akhir))),
      r.jenis.length ? h("div", { class: "jtags" }, ...r.jenis.map(jenisTag)) : null,
      r.jumlah_laporan === 0 ? h("div", { class: "pstate pstate--compact" }, h("p", {}, "Tidak ada laporan untuk lokasi ini yang sesuai dengan filter yang dipilih.")) : null,
      r.kejadian.length ? section(`Kejadian yang menyebut lokasi ini (${r.kejadian.length})`,
        ...r.kejadian.map((k) => h("div", { class: "evgroup" },
          h("div", { class: "evgroup-h" }, jenisTag(k.jenis), h("strong", {}, k.nama)),
          h("div", { class: "evgroup-m" }, h("span", {}, k.nama_kab ?? "Kab/kota tidak tersedia"), statusBadge(k.status)),
          h("p", { class: "evgroup-d" }, `Mulai ${tgl(k.start_time)} · laporan terakhir ${tgl(k.end_time)}`),
          h("ol", { class: "mentions" }, ...k.laporan.map((m) => h("li", {},
            h("span", { class: "m-date" }, tgl(m.tanggal_lokal)),
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
      tweets), `lokasi:${L.gazetteer_id}`);
  }
}
