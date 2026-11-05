import { h, reducedMotion } from "../dom";
import { angka, rentang, tgl, waktu } from "../format";
import { LABEL_PENDEK, STATUS_LABEL, TINGKAT_LABEL } from "../jenis";
import { kelasOf } from "../map/legend";
import { kalimatRujukan } from "../map/marker";
import type { Jenis, KabAgregat, KabKejadian, KabTitik, Kejadian, Ringkasan, Wilayah } from "../types";
import { dampakItem, factBlock, kebutuhanItem, laporanList, lembagaItem, type TweetMap } from "./facts";
import { ico } from "./icons";

/** Kejadian yang ditanyakan ke asisten (konteks percakapan; tidak masuk URL). */
export interface EventRef { event_id: string; nama: string; jenis: Jenis }

export interface PanelHandlers {
  onKab(kode: string): void;
  onProv(kode: string): void;
  onTitik(gid: string): void;
  onSorot(eid: string | null): void;
  onBack(): void;
  onReset(): void;
  onAllDates(): void;
  onAllJenis(): void;
  onAsk(ev: EventRef): void;
  onTab(tab: PanelTab): void;
}

export type PanelTab = "detail" | "chat";
export interface EmptyCtx { jenisKosong: boolean; adaTanggal: boolean }

const jenisTag = (j: Jenis) => h("span", { class: "jtag" }, h("i", { style: `background: var(--j-${j})`, "aria-hidden": "true" }), LABEL_PENDEK[j]);
const kpi = (label: string, value: string | number, hint?: string) =>
  h("div", { class: "kpi", title: hint ?? null },
    h("span", { class: `kpi-v${typeof value === "string" && value.length > 6 ? " kpi-v--sm" : ""}` }, typeof value === "number" ? angka(value) : value),
    h("span", { class: "kpi-l" }, label));
const section = (title: string, ...body: (Node | null | false)[]) => h("section", { class: "psec" }, h("h3", { class: "psec-t" }, title), ...body);
const none = (t = "Tidak disebutkan") => h("p", { class: "muted small" }, t);
const statusBadge = (st: string) => h("span", { class: `status status--${st === "ya" ? "ya" : "tidak"}`,
  title: "Status ambang bencana (ya/tidak) — bukan status berlangsung/selesai" }, STATUS_LABEL[st] ?? "Status tidak tersedia");

/** Label tab rincian menurut tingkat tampilan. */
export const DETAIL_LABEL = { nasional: "Ringkasan", prov: "Detail Wilayah", kab: "Detail Wilayah", lokasi: "Detail Lokasi" } as const;

export class Panel {
  readonly el: HTMLElement;
  /** Isi tab rincian (dapat digulir). */
  readonly body: HTMLElement;
  /** Wadah tab Tanya AI (diisi ChatView). */
  readonly chatBox: HTMLElement;
  readonly tablist: HTMLElement;
  private tabDetail: HTMLButtonElement;
  private tabChat: HTMLButtonElement;
  private tabDetailLabel: HTMLElement;
  private tab: PanelTab = "detail";
  private key = "";
  private cards = new Map<string, HTMLElement>();
  private sorot: string | null = null;
  private openDetails = new Set<string>();
  private skelTimer = 0;

  constructor(private hd: PanelHandlers, head: HTMLElement) {
    this.tabDetailLabel = h("span", {}, DETAIL_LABEL.nasional);
    this.tabDetail = h("button", { type: "button", role: "tab", id: "tabbtn-detail", class: "ptab", "aria-controls": "tab-detail",
      "aria-selected": "true", onclick: () => this.setTab("detail", true) }, this.tabDetailLabel);
    this.tabChat = h("button", { type: "button", role: "tab", id: "tabbtn-chat", class: "ptab ptab--ai", "aria-controls": "tab-chat",
      "aria-selected": "false", tabindex: -1, onclick: () => this.setTab("chat", true) }, ico("sparkle", 14), h("span", {}, "Tanya AI"));
    this.tablist = h("div", { class: "ptabs", role: "tablist", "aria-label": "Isi panel" }, this.tabDetail, this.tabChat);
    this.tablist.addEventListener("keydown", (e) => {
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight" && e.key !== "Home" && e.key !== "End") return;
      e.preventDefault();
      const next: PanelTab = e.key === "Home" ? "detail" : e.key === "End" ? "chat" : this.tab === "detail" ? "chat" : "detail";
      this.setTab(next, true);
      (next === "detail" ? this.tabDetail : this.tabChat).focus();
    });
    this.tablist.addEventListener("click", (e) => e.stopPropagation()); // jangan ikut melipat lembar bawah
    head.querySelector(".panel-tabs-slot")!.replaceWith(this.tablist);
    this.body = h("div", { class: "panel-body", id: "tab-detail", role: "tabpanel", "aria-labelledby": "tabbtn-detail", tabindex: -1 });
    this.chatBox = h("div", { class: "panel-chat", id: "tab-chat", role: "tabpanel", "aria-labelledby": "tabbtn-chat", hidden: true });
    this.el = h("aside", { class: "panel float-card", id: "panel", "aria-label": "Panel rincian dan asisten" }, head, this.body, this.chatBox);
  }

  get activeTab(): PanelTab { return this.tab; }

  setTab(tab: PanelTab, user = false): void {
    if (tab === this.tab) { if (user) this.hd.onTab(tab); return; }
    this.tab = tab;
    const d = tab === "detail";
    this.tabDetail.setAttribute("aria-selected", String(d));
    this.tabChat.setAttribute("aria-selected", String(!d));
    this.tabDetail.tabIndex = d ? 0 : -1;
    this.tabChat.tabIndex = d ? -1 : 0;
    this.body.hidden = !d;
    this.chatBox.hidden = d;
    this.el.classList.toggle("is-chat", !d);
    this.hd.onTab(tab);
  }

  setDetailLabel(view: keyof typeof DETAIL_LABEL): void { this.tabDetailLabel.textContent = DETAIL_LABEL[view]; }

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

  private rankList(agg: KabAgregat, wil: Wilayah): HTMLElement {
    const nama = new Map(wil.kab.map((k) => [k.kode_kab, k]));
    const rows = [...agg.kab].sort((a, b) => b.jumlah_kejadian - a.jumlah_kejadian || b.jumlah_laporan - a.jumlah_laporan);
    const max = Math.max(1, ...rows.map((x) => x.jumlah_kejadian));
    return h("ol", { class: "rank" }, ...rows.map((x) => {
      const k = nama.get(x.kode_kab);
      return h("li", {}, h("button", { type: "button", class: "rank-btn", onclick: () => this.hd.onKab(x.kode_kab),
        "aria-label": `${k?.nama ?? x.kode_kab}: ${x.jumlah_kejadian} kejadian, ${x.jumlah_laporan} laporan. Buka wilayah.` },
        h("span", { class: "rank-name" }, h("span", {}, k?.nama ?? x.kode_kab), h("small", {}, k?.provinsi ?? "")),
        h("span", { class: "rank-bar", "aria-hidden": "true" }, h("i", { "data-k": kelasOf(x.jumlah_kejadian), style: `width:${(x.jumlah_kejadian / max) * 100}%` })),
        h("span", { class: "rank-n" }, h("b", {}, angka(x.jumlah_kejadian)), h("small", {}, `${angka(x.jumlah_laporan)} laporan`)),
        ico("chevRight", 14, "rank-go")));
    }));
  }

  // ------------------------------------------------------------- nasional
  nasional(agg: KabAgregat, wil: Wilayah, scope: string, ctx: EmptyCtx): void {
    const r = agg.ringkasan;
    // Provinsi dengan kejadian: setiap kejadian tercatat di tepat satu kab/kota, sehingga hitungan kejadian
    // per provinsi = jumlah kejadian kab/kota di dalamnya (tweet tidak dijumlahkan: satu tweet bisa lintas wilayah).
    const prov = new Map<string, { n: number; kab: number }>();
    for (const x of agg.kab) {
      if (!x.jumlah_kejadian) continue;
      const p = prov.get(x.kode_kab.slice(0, 2)) ?? { n: 0, kab: 0 };
      p.n += x.jumlah_kejadian; p.kab += 1;
      prov.set(x.kode_kab.slice(0, 2), p);
    }
    const provNama = new Map(wil.provinsi.map((p) => [p.kode_prov, p.nama]));
    const provRows = [...prov].sort((a, b) => b[1].n - a[1].n);
    this.show(h("div", {},
      h("header", { class: "phead" }, h("h2", { class: "ptitle" }, "Sebaran kejadian bencana"), h("p", { class: "psub" }, scope)),
      h("div", { class: "kpis" },
        kpi("Kejadian bencana", r.jumlah_kejadian, "Kejadian (DisasterEvent) unik yang periodenya beririsan dengan rentang tanggal"),
        kpi("Tweet sumber unik", r.jumlah_tweet, "Tweet unik yang melaporkan laporan kejadian pada rentang tanggal"),
        kpi("Kab/kota", r.jumlah_kab, "Kab/kota dengan minimal satu kejadian yang sesuai filter")),
      r.jumlah_kejadian === 0 ? this.empty(ctx) : h("div", {},
        provRows.length ? section("Provinsi",
          h("ul", { class: "provs" }, ...provRows.map(([kode, p]) => h("li", {}, h("button", { type: "button", class: "prov-btn", onclick: () => this.hd.onProv(kode) },
            h("span", { class: "prov-name" }, provNama.get(kode) ?? kode),
            h("span", { class: "prov-n" }, `${angka(p.n)} kejadian · ${angka(p.kab)} kab/kota`), ico("chevRight", 14, "rank-go")))))) : null,
        section("Kab/kota dengan kejadian", this.rankList(agg, wil),
          h("p", { class: "hint" }, "Klik kab/kota pada peta atau daftar ini untuk melihat lokasi yang dilaporkan.")))), "nasional");
  }

  // ------------------------------------------------------------- provinsi
  prov(agg: KabAgregat, wil: Wilayah, kode: string, scope: string, ctx: EmptyCtx): void {
    const r = agg.ringkasan;
    const nama = wil.provinsi.find((p) => p.kode_prov === kode)?.nama ?? kode;
    const adaData = wil.kab.some((k) => k.kode_prov === kode && k.ada_data);
    this.show(h("div", {},
      h("header", { class: "phead" }, h("p", { class: "peyebrow" }, "Provinsi"), h("h2", { class: "ptitle" }, nama), h("p", { class: "psub" }, scope)),
      h("div", { class: "kpis" },
        kpi("Kejadian bencana", r.jumlah_kejadian, "Kejadian unik di kab/kota provinsi ini yang periodenya beririsan dengan rentang"),
        kpi("Tweet sumber unik", r.jumlah_tweet),
        kpi("Kab/kota", r.jumlah_kab, "Kab/kota di provinsi ini dengan minimal satu kejadian")),
      r.jumlah_kejadian === 0
        ? (adaData ? this.empty(ctx) : h("div", { class: "pstate" }, h("p", { class: "pstate-t" }, "Belum ada data untuk provinsi ini."),
          h("p", {}, "Provinsi ini berada di luar cakupan data yang tersedia.")))
        : section("Kab/kota dengan kejadian", this.rankList(agg, wil),
          h("p", { class: "hint" }, "Klik kab/kota untuk melihat kejadian dan lokasi yang dilaporkan."))), `prov:${kode}`);
  }

  // ------------------------------------------------------------- kabupaten
  kab(d: KabKejadian, t: KabTitik | null, tweetUnik: number | null, prov: string, sorot: string | null, ctx: EmptyCtx, adaData: boolean): void {
    this.cards.clear();
    this.sorot = sorot;
    const lap = d.kejadian.reduce((a, k) => a + k.jumlah_laporan_periode, 0); // laporan unik per kejadian: tidak beririsan
    const kosong = d.kejadian.length === 0
      ? (adaData ? this.empty(ctx) : h("div", { class: "pstate" }, h("p", { class: "pstate-t" }, "Belum ada data untuk wilayah ini."),
        h("p", {}, "Kab/kota ini berada di luar cakupan data yang tersedia.")))
      : null;
    const luar = t ? t.titik.filter((x) => x.di_luar_kab).length : 0;
    this.show(h("div", {},
      h("header", { class: "phead" }, h("h2", { class: "ptitle" }, d.nama), h("p", { class: "psub" }, `${prov} · mengikuti filter jenis dan rentang tanggal`)),
      h("div", { class: "kpis kpis--4" },
        kpi("Kejadian", d.kejadian.length, "Kejadian unik yang periodenya beririsan dengan rentang"),
        kpi("Laporan", lap, "Laporan kejadian (EventMention) bertanggal di dalam rentang"),
        kpi("Tweet unik", tweetUnik ?? "–"),
        kpi("Lokasi", t ? t.titik.length : "–", "Lokasi unik (gazetteer_id) yang dapat dipetakan")),
      t && t.laporan_tanpa_titik > 0
        ? h("p", { class: "note" }, `${angka(t.laporan_tanpa_titik)} laporan hanya menyebut wilayah kab/kota (tanpa lokasi rinci) sehingga tidak tampil sebagai penanda.`) : null,
      luar ? h("p", { class: "note note--ref" }, ico("info", 14), `${angka(luar)} lokasi bercincin putus-putus berada di kab/kota lain; lokasi itu dirujuk oleh laporan kejadian di ${d.nama}, bukan lokasi kejadian.`) : null,
      kosong ?? h("div", {},
        h("p", { class: "cards-hint" }, "Klik kartu untuk menyorot lokasinya di peta."),
        h("div", { class: "cards", role: "list", "aria-label": "Kejadian bencana" }, ...d.kejadian.map((k) => this.card(k, d.tweets))))), `kab:${d.kode_kab}`);
  }

  private askBtn(ev: EventRef): HTMLElement {
    return h("button", { type: "button", class: "ask-btn", onclick: () => this.hd.onAsk(ev),
      "aria-label": `Tanyakan tentang kejadian ini: ${ev.nama}` }, ico("sparkle", 13), "Tanyakan tentang kejadian ini");
  }

  private card(k: Kejadian, tw: TweetMap): HTMLElement {
    const on = this.sorot === k.event_id;
    const bisa = k.lokasi_ids.length > 0;
    const hit = h("button", { type: "button", class: "card-hit", "aria-pressed": String(on), disabled: !bisa,
      onclick: () => this.toggle(k.event_id) },
      h("span", { class: "card-top" }, jenisTag(k.jenis), h("span", { class: "card-state" }, ico("target", 13), "Disorot")),
      h("span", { class: "card-t" }, k.nama),
      h("span", { class: "sr-only" }, bisa ? ". Sorot lokasi kejadian ini di peta." : ". Tidak ada lokasi yang dapat dipetakan pada rentang ini."));
    const det = h("details", { class: "card-more" },
      h("summary", {}, ico("chevRight", 13, "sum-chev"), h("span", {}, "Dampak, kebutuhan, penanganan, dan sumber")),
      h("p", { class: "card-scope" }, "Dari laporan pada rentang tanggal terpilih. Setiap angka ditampilkan per laporan, tidak dijumlahkan."),
      factBlock("Dampak kejadian", k.dampak.map((d) => dampakItem(d, tw, true)), "Belum ada dampak yang dilaporkan"),
      factBlock("Kebutuhan", k.kebutuhan.map((x) => kebutuhanItem(x, tw, true)), "Belum ada kebutuhan yang dilaporkan"),
      factBlock("Penanganan", k.lembaga.map((l) => lembagaItem(l, tw)), "Belum ada penanganan yang dilaporkan"),
      factBlock("Sumber laporan", k.laporan.length ? [laporanList(k.laporan, tw)] : [], "Tidak ada laporan pada rentang ini"));
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
      bits ? h("p", { class: "card-sum" }, bits) : h("p", { class: "card-sum" }, "Belum ada dampak, kebutuhan, atau penanganan yang dilaporkan"),
      det,
      h("div", { class: "card-foot" }, this.askBtn({ event_id: k.event_id, nama: k.nama, jenis: k.jenis })));
    // seluruh kartu dapat diklik; kontrol di dalamnya (tautan lokasi, rincian, tanya) tetap berfungsi sendiri
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
  lokasi(r: Ringkasan, kabNama: string | null, kabSaatIni: string | null, kabLokasi: string | null): void {
    const L = r.lokasi;
    const luar = !!(kabSaatIni && L.kode_kab_lokasi && L.kode_kab_lokasi !== kabSaatIni);
    const tw = r.tweet_map ?? {};
    const tweets = h("details", { class: "psec psec--fold", open: true },
      h("summary", { class: "psec-t" }, ico("chevRight", 13, "sum-chev"), `Tweet yang menyebut lokasi ini (${r.tweets.length})`),
      r.tweets.length ? h("ol", { class: "tweets" }, ...r.tweets.map((t) => h("li", { class: "tweet", id: `tw-${t.tweet_id}` },
        h("div", { class: "tweet-h" }, h("span", {}, waktu(t.upload)), h("span", { class: "tweet-id" }, `ID ${t.tweet_id}`)),
        h("blockquote", { class: "tweet-x", lang: "id" }, t.text ?? "Teks tidak tersedia"),
        t.url ? h("a", { class: "tweet-a", href: t.url, target: "_blank", rel: "noopener noreferrer" }, "Buka tweet asli", ico("external", 13))
          : h("span", { class: "tweet-na" }, "Tautan sumber tidak tersedia")))) : none("Tidak ada tweet pada rentang ini"));
    this.show(h("div", {},
      h("button", { type: "button", class: "back", onclick: () => this.hd.onBack() }, ico("arrowLeft", 15), kabNama ?? "Kembali"),
      h("header", { class: "phead" },
        luar ? h("p", { class: "peyebrow peyebrow--ref" }, "Lokasi rujukan") : null,
        h("h2", { class: "ptitle" }, L.nama),
        h("p", { class: "psub" }, `${TINGKAT_LABEL[L.tingkat] ?? L.tingkat} · ${L.admin_path ?? "Jalur administratif tidak tersedia"}`),
        L.latitude !== null ? h("p", { class: "coord", title: "Koordinat entri gazetteer; bukan titik pusat atau batas bencana" },
          `${L.latitude!.toFixed(4)}, ${L.longitude!.toFixed(4)}`) : null),
      luar ? h("p", { class: "note note--ref" }, ico("info", 14),
        `${kalimatRujukan(kabLokasi, kabNama)} Lokasi ini bukan lokasi kejadian di ${kabNama ?? "wilayah terpilih"}; penanda tetap di posisi aslinya.`) : null,
      h("div", { class: "kpis" },
        kpi("Laporan", r.jumlah_laporan, "Laporan kejadian unik yang menyebut lokasi ini"),
        kpi("Tweet unik", r.jumlah_tweet),
        kpi("Periode laporan", rentang(r.tanggal_awal, r.tanggal_akhir))),
      r.jenis.length ? h("div", { class: "jtags" }, ...r.jenis.map(jenisTag)) : null,
      r.jumlah_laporan === 0 && !r.kejadian.length ? h("div", { class: "pstate pstate--compact" }, h("p", {}, "Tidak ada laporan untuk lokasi ini yang sesuai dengan filter yang dipilih.")) : null,
      r.kejadian.length ? section(`Kejadian terkait lokasi ini (${r.kejadian.length})`,
        h("p", { class: "psec-note" }, "Dampak dan kebutuhan dikelompokkan per kejadian. \"Di lokasi ini\" = laporan menautkannya ke lokasi ini; \"tingkat kejadian\" = disebut tanpa lokasi tertentu."),
        ...r.kejadian.map((k) => {
          const ini = k.dampak.filter((d) => d.atribusi === "lokasi_ini"), ev = k.dampak.filter((d) => d.atribusi === "kejadian");
          const lain = k.dampak.filter((d) => d.atribusi === "lokasi_lain");
          const kIni = k.kebutuhan.filter((x) => x.atribusi === "lokasi_ini"), kEv = k.kebutuhan.filter((x) => x.atribusi === "kejadian");
          const kLain = k.kebutuhan.filter((x) => x.atribusi === "lokasi_lain");
          const menyebut = k.laporan.filter((m) => m.relasi !== "evakuasi").length;
          const evak = k.laporan.length - menyebut;
          const rel = [menyebut ? `Disebut dalam ${angka(menyebut)} dari ${angka(k.jumlah_laporan_kejadian)} laporan kejadian ini` : null,
            evak ? `tujuan evakuasi dalam ${angka(evak)} laporan` : null].filter(Boolean).join("; ");
          const lainBox = lain.length || kLain.length ? h("details", { class: "fother" },
            h("summary", {}, ico("chevRight", 12, "sum-chev"), `Di lokasi lain dalam kejadian ini (${lain.length + kLain.length})`),
            factBlock("Dampak di lokasi lain", lain.map((d) => dampakItem(d, tw, false)), null),
            factBlock("Kebutuhan di lokasi lain", kLain.map((x) => kebutuhanItem(x, tw, false)), null)) : null;
          return h("article", { class: "evgroup", "data-event": k.event_id },
            h("div", { class: "evgroup-h" }, jenisTag(k.jenis), h("strong", {}, k.nama)),
            h("div", { class: "evgroup-m" }, h("span", {}, k.nama_kab ?? "Kab/kota tidak tersedia"), statusBadge(k.status)),
            h("p", { class: "evgroup-d" }, `Mulai ${tgl(k.start_time)} · laporan terakhir ${tgl(k.end_time)}`),
            rel ? h("p", { class: "evgroup-rel" }, `${rel}.`) : null,
            factBlock("Dampak di lokasi ini", ini.map((d) => dampakItem(d, tw, false)), "Belum ada dampak yang dilaporkan di lokasi ini"),
            factBlock("Dampak tingkat kejadian", ev.map((d) => dampakItem(d, tw, false)), null, "Disebut dalam laporan kejadian ini tanpa lokasi tertentu."),
            factBlock("Kebutuhan di lokasi ini", kIni.map((x) => kebutuhanItem(x, tw, false)), "Belum ada kebutuhan yang dilaporkan di lokasi ini"),
            factBlock("Kebutuhan tingkat kejadian", kEv.map((x) => kebutuhanItem(x, tw, false)), null, "Tidak dapat ditautkan ke lokasi tertentu."),
            lainBox,
            factBlock("Penanganan", k.penanganan.map((l) => lembagaItem(l, tw)), "Belum ada penanganan yang dilaporkan"),
            k.evakuasi.length ? factBlock("Evakuasi", k.evakuasi.map((e) => h("li", { class: "fact" },
              h("span", { class: "fact-main" }, h("span", { class: "fact-what" },
                e.tujuan.some((t) => t.gazetteer_id === L.gazetteer_id) ? "Lokasi ini menjadi tujuan evakuasi" : `Evakuasi ke ${e.tujuan.map((t) => t.nama).join(", ") || "tujuan tidak disebutkan"}`)),
              h("span", { class: "fact-scope" }, h("span", { class: "ftag ftag--plain" }, e.asal.length ? `asal: ${e.asal.map((a) => a.nama).join(", ")}` : "asal tidak disebutkan")),
              h("span", { class: "fsrcs" }, h("span", { class: "fsrcs-l" }, "Dilaporkan:"), h("span", { class: "fsrc-d" }, tgl(e.tanggal_lokal)), h("span", { class: "fsrc-id" }, e.mention_id)))), null) : null,
            factBlock("Laporan yang merujuk lokasi ini", k.laporan.length ? [laporanList(k.laporan, tw, { relasi: true })] : [], "Tidak ada laporan pada rentang ini"),
            h("div", { class: "card-foot" }, this.askBtn({ event_id: k.event_id, nama: k.nama, jenis: k.jenis })));
        })) : null,
      r.lembaga_dikerahkan.length ? section("Lembaga yang dikerahkan ke lokasi ini",
        h("p", { class: "psec-note" }, "Dicatat pada tingkat lokasi; tidak tertaut ke laporan atau kejadian tertentu."),
        h("ul", { class: "facts" }, ...r.lembaga_dikerahkan.map((l) => lembagaItem(l, tw)))) : null,
      tweets), `lokasi:${L.gazetteer_id}`);
  }
}
