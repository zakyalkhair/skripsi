import { h, reducedMotion } from "../dom";
import { angka, rentang, tgl, waktu } from "../format";
import { JENIS, LABEL, LABEL_PENDEK, STATUS_LABEL, TINGKAT_LABEL } from "../jenis";
import { kelasOf } from "../map/legend";
import type { Jenis, KabAgregat, KabKejadian, KabTitik, Kejadian, Ringkasan, Wilayah } from "../types";
import { dampakGroups, dampakQty, dampakText, factBlock, kebutuhanGroups, kronologiList, lembagaBlock, tweetFold, type TweetMap } from "./facts";
import type { KebGrup } from "../types";
import { onPreview } from "./preview";
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
  onJenis(j: Jenis): void;
  onTab(tab: PanelTab): void;
  /** Pratinjau hover (hanya tampilan, tanpa mengubah state/URL). */
  onPreviewProv?(kode: string | null): void;
  onPreviewJenis?(j: Jenis | null): void;
  onPreviewLokasi?(ids: string[] | null): void;
  onPreviewEnd?(): void;
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
// status ambang disembunyikan (desain)
export const statusBadge = (st: string) => h("span", { class: `status status--${st === "ya" ? "ya" : "tidak"}`,
  title: "Status ambang bencana (ya/tidak) — bukan status berlangsung/selesai" }, STATUS_LABEL[st] ?? "Status tidak tersedia");

const KRONO_NOTE = "Cadangan otomatis tanpa LLM: satu baris per tanggal dari cuplikan tweet (laporan situasi Modul 4.3 belum tersambung).";
const grupAtr = (gs: KebGrup[] | undefined, atr: string): KebGrup[] =>
  (gs ?? []).map((g) => ({ ...g, baris: g.baris.filter((b) => b.atribusi === atr), ringkas: null })).filter((g) => g.baris.length);
const ringkasBox = (t: string) => h("div", { class: "ringkas", title: "Ringkasan otomatis (dummy) dari data dasbor — belum dari laporan situasi LLM" }, h("p", { class: "ringkas-x" }, t));
const fakta = (ds: { label?: string; jumlah: number | null; satuan: string | null; kelas: string | null; status: string | null; objek?: string | null }[]) =>
  ds.slice(0, 3).map((x) => `${dampakText(x as never)} ${dampakQty(x as never)}`).join("; ");
function ringkasKab(d: KabKejadian): string {
  const j = [...new Set(d.kejadian.map((k) => LABEL_PENDEK[k.jenis]))].join(", ");
  const dampak = d.kejadian.flatMap((k) => k.dampak), org = [...new Set(d.kejadian.flatMap((k) => k.lembaga.map((l) => l.nama_kanonik)))];
  return `${d.kejadian.length} kejadian (${j}) dilaporkan di ${d.nama}.` + (dampak.length ? ` Dampak yang dilaporkan antara lain: ${fakta(dampak)} (per laporan, tidak dijumlahkan).` : " Belum ada dampak yang dilaporkan.")
    + (org.length ? ` Penanganan oleh ${org.join(", ")}.` : "");
}
function ringkasLokasi(r: Ringkasan): string {
  const ini = r.kejadian.flatMap((k) => k.dampak.filter((x) => x.atribusi === "lokasi_ini"));
  return `${r.lokasi.nama} disebut dalam ${r.jumlah_laporan} laporan pada ${r.kejadian.length} kejadian (${rentang(r.tanggal_awal, r.tanggal_akhir)}).`
    + (ini.length ? ` Dampak di lokasi ini: ${fakta(ini)}.` : " Belum ada dampak yang dilaporkan khusus untuk lokasi ini.");
}

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
    this.hd.onPreviewEnd?.(); // elemen lama hilang tanpa pointerleave: jangan tinggalkan pratinjau
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
    const BATAS = 12;
    const ol = h("ol", { class: "rank" }, ...rows.map((x, i) => {
      const k = nama.get(x.kode_kab);
      return h("li", {}, h("button", { type: "button", class: "rank-btn", onclick: () => this.hd.onKab(x.kode_kab),
        "aria-label": `${k?.nama ?? x.kode_kab}: ${x.jumlah_kejadian} kejadian, ${x.jumlah_laporan} laporan. Buka wilayah.` },
        h("span", { class: "rank-name" }, h("span", {}, k?.nama ?? x.kode_kab), h("small", {}, k?.provinsi ?? "")),
        h("span", { class: "rank-bar", "aria-hidden": "true" }, h("i", { "data-k": kelasOf(x.jumlah_kejadian), style: `width:${(x.jumlah_kejadian / max) * 100}%` })),
        h("span", { class: "rank-n" }, h("b", {}, angka(x.jumlah_kejadian)), h("small", {}, `${angka(x.jumlah_laporan)} laporan`)),
        ico("chevRight", 14, "rank-go")), i >= BATAS ? h("span", { hidden: true, class: "rank-cut" }) : null);
    }));
    ol.querySelectorAll<HTMLElement>(".rank-cut").forEach((c) => { c.parentElement!.hidden = true; c.remove(); });
    const more = rows.length > BATAS ? h("button", { type: "button", class: "btn btn--ghost btn--block", onclick: () => {
      ol.querySelectorAll<HTMLElement>("li[hidden]").forEach((li) => (li.hidden = false)); more!.remove(); } }, `Tampilkan semua ${angka(rows.length)} kab/kota`) : null;
    return h("div", {}, h("p", { class: "psec-note" }, "Diurutkan dari jumlah kejadian terbanyak"), ol, more);
  }

  // ------------------------------------------------------------- nasional
  nasional(agg: KabAgregat, wil: Wilayah, scope: string, ctx: EmptyCtx,
    perJenisSemua: KabAgregat["ringkasan"]["per_jenis"] | null = null, dipilih: ReadonlySet<Jenis> = new Set(JENIS)): void {
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
        kpi("Kejadian", r.jumlah_kejadian, "Kejadian (DisasterEvent) unik yang periodenya beririsan dengan rentang tanggal"),
        kpi("Tweet sumber unik", r.jumlah_tweet, "Tweet unik yang melaporkan laporan kejadian pada rentang tanggal"),
        kpi("Kab/kota", r.jumlah_kab, "Kab/kota dengan minimal satu kejadian yang sesuai filter")),
      (perJenisSemua ?? r.per_jenis) ? this.jenisCard((perJenisSemua ?? r.per_jenis)!, dipilih) : null,
      r.jumlah_kejadian === 0 ? this.empty(ctx) : h("div", {},
        provRows.length ? section("Provinsi",
          h("ul", { class: "provs" }, ...provRows.map(([kode, p]) => h("li", {}, this.pv(h("button", { type: "button", class: "prov-btn", onclick: () => this.hd.onProv(kode) },
            h("span", { class: "prov-name" }, provNama.get(kode) ?? kode),
            h("span", { class: "prov-n" }, `${angka(p.n)} kejadian | ${angka(p.kab)} kab/kota`), ico("chevRight", 14, "rank-go")),
            () => this.hd.onPreviewProv?.(kode), () => this.hd.onPreviewProv?.(null)))))) : null)), "nasional");
  }

  /** Kartu "Kejadian per jenis bencana" (opsi desain Figma): ikon, laporan, batang, jumlah & persen; klik = filter jenis. */
  private jenisCard(pj: NonNullable<KabAgregat["ringkasan"]["per_jenis"]>, dipilih: ReadonlySet<Jenis>): HTMLElement {
    // Urutan & angka selalu dari data SEMUA jenis (posisi tetap); saat memfilter, jenis yang tidak dipilih dipudarkan.
    const rows = JENIS.map((j) => ({ j, ...(pj[j] ?? { kejadian: 0, laporan: 0 }) })).sort((a, b) => b.kejadian - a.kejadian);
    const total = rows.reduce((a, r) => a + r.kejadian, 0);
    const max = Math.max(1, ...rows.map((r) => r.kejadian));
    const pudar = (j: Jenis) => dipilih.size < JENIS.length && !dipilih.has(j);
    return h("section", { class: "psec jcard" },
      h("h3", { class: "psec-t" }, "Kejadian per jenis bencana"),
      h("p", { class: "psec-note" }, "Jumlah kejadian unik pada rentang tanggal aktif · arahkan kursor ke baris untuk melihatnya di peta"),
      h("div", { class: "jcomp", "aria-hidden": "true" }, ...rows.filter((r) => r.kejadian).map((r) =>
        h("i", { class: pudar(r.j) ? "is-pudar" : "", style: `flex:${r.kejadian};background:var(--j-${r.j})`, title: `${LABEL_PENDEK[r.j]}: ${r.kejadian}` }))),
      h("ul", { class: "jrows" }, ...rows.map((r) => h("li", {}, this.pv(h("div", { class: `jrow${r.kejadian ? "" : " is-nol"}${pudar(r.j) ? " is-pudar" : ""}`,
        tabindex: "0", "aria-label": `${LABEL[r.j]}: ${r.kejadian} kejadian, ${r.laporan} laporan.` },
        h("span", { class: "jrow-ic", style: `--jc:var(--j-${r.j})` }, ico(`j_${r.j}` as never, 18)),
        h("span", { class: "jrow-mid" },
          h("span", { class: "jrow-top" }, h("b", {}, LABEL[r.j] === "Kebakaran Hutan dan Lahan" ? "Karhutla" : LABEL[r.j]),
            h("small", {}, r.kejadian ? `${angka(r.laporan)} laporan` : "belum dilaporkan")),
          h("span", { class: "jrow-bar" }, r.kejadian ? h("i", { style: `width:${(r.kejadian / max) * 100}%;background:var(--j-${r.j})` }) : null)),
        h("span", { class: "jrow-n" }, h("b", {}, angka(r.kejadian)), h("small", {}, r.kejadian && total ? `${Math.round((100 * r.kejadian) / total)}%` : "—")),
        ), () => this.hd.onPreviewJenis?.(r.j), () => this.hd.onPreviewJenis?.(null))))),
      h("p", { class: "fblock-note" }, "Satu kejadian dihitung pada satu jenis. Jenis tanpa laporan tetap ditampilkan agar terlihat tidak ada data, bukan nol kejadian sesungguhnya."));
  }

  // ------------------------------------------------------------- provinsi
  prov(agg: KabAgregat, wil: Wilayah, kode: string, scope: string, ctx: EmptyCtx): void {
    const r = agg.ringkasan;
    const nama = wil.provinsi.find((p) => p.kode_prov === kode)?.nama ?? kode;
    const adaData = wil.kab.some((k) => k.kode_prov === kode && k.ada_data);
    this.show(h("div", {},
      h("header", { class: "phead" }, h("p", { class: "peyebrow" }, "Provinsi"), h("h2", { class: "ptitle" }, nama), h("p", { class: "psub" }, scope)),
      h("div", { class: "kpis" },
        kpi("Kejadian", r.jumlah_kejadian, "Kejadian unik di kab/kota provinsi ini yang periodenya beririsan dengan rentang"),
        kpi("Tweet sumber unik", r.jumlah_tweet),
        kpi("Kab/kota", r.jumlah_kab, "Kab/kota di provinsi ini dengan minimal satu kejadian")),
      r.jumlah_kejadian === 0
        ? (adaData ? this.empty(ctx) : h("div", { class: "pstate" }, h("p", { class: "pstate-t" }, "Belum ada data untuk provinsi ini."),
          h("p", {}, "Provinsi ini berada di luar cakupan data yang tersedia.")))
        : section("Kab/kota dengan kejadian", this.rankList(agg, wil))), `prov:${kode}`);
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
    this.show(h("div", {},
      h("header", { class: "phead" }, h("h2", { class: "ptitle" }, d.nama), h("p", { class: "psub" }, prov)),
      h("div", { class: "kpis kpis--4" },
        kpi("Kejadian", d.kejadian.length, "Kejadian unik yang periodenya beririsan dengan rentang"),
        kpi("Laporan", lap, "Laporan kejadian (EventMention) bertanggal di dalam rentang"),
        kpi("Tweet unik", tweetUnik ?? "–"),
        kpi("Lokasi", t ? t.titik.length : "–", "Lokasi unik (gazetteer_id) yang dapat dipetakan")),
      t && t.laporan_tanpa_titik > 0
        ? h("p", { class: "note" }, `${angka(t.laporan_tanpa_titik)} laporan hanya menyebut wilayah kab/kota (tanpa lokasi rinci) sehingga tidak tampil sebagai penanda.`) : null,
      kosong ?? h("div", {},
        ringkasBox(ringkasKab(d)),
        h("p", { class: "cards-hint" }, "*Arahkan kursor ke kartu untuk melihat lokasinya di peta; klik untuk menyorotnya."),
        h("div", { class: "cards", role: "list", "aria-label": "Kejadian bencana" }, ...d.kejadian.map((k) => this.card(k, d.tweets))))), `kab:${d.kode_kab}`);
  }

  private askBtn(ev: EventRef): HTMLElement {
    return h("button", { type: "button", class: "ask-btn", onclick: () => this.hd.onAsk(ev),
      "aria-label": `Tanyakan tentang kejadian ini: ${ev.nama}` }, ico("sparkle", 13), "Tanyakan tentang kejadian ini");
  }

  /** Kartu kejadian (desain Figma). Lokasi: `lok` = fokus lokasi (hitungan "x dari y", fakta "di lokasi ini"). */
  private card(k: Kejadian, tw: TweetMap): HTMLElement {
    const on = this.sorot === k.event_id;
    const bisa = k.lokasi_ids.length > 0;
    const hit = h("button", { type: "button", class: "card-hit", "aria-pressed": String(on), disabled: !bisa,
      onclick: () => this.toggle(k.event_id) },
      h("span", { class: "card-top" }, jenisTag(k.jenis),
        h("span", { class: "card-state" }, ico("target", 13), "Disorot"),
        h("span", { class: "card-badge" }, `${angka(k.jumlah_laporan_periode)} laporan`)),
      h("span", { class: "card-t" }, k.nama),
      h("span", { class: "sr-only" }, bisa ? ". Sorot lokasi kejadian ini di peta." : ". Tidak ada lokasi yang dapat dipetakan pada rentang ini."));
    const tws = [...new Set(k.laporan.flatMap((m) => m.tweet_ids))];
    const det = h("details", { class: "card-more" },
      h("summary", {}, h("span", {}, "Detail kejadian"), ico("chevDown", 15, "more-chev")),
      k.kronologi?.length ? h("section", { class: "fblock krono-box" }, h("h4", { class: "fblock-t" }, "Kronologi Kejadian"), kronologiList(k.kronologi),
        h("p", { class: "fblock-note" }, KRONO_NOTE)) : null,
      factBlock("Dampak kejadian", dampakGroups(k.dampak, tw, { scope: true }), "Belum ada dampak yang dilaporkan", undefined, k.dampak.length, true),
      factBlock("Kebutuhan", kebutuhanGroups(k.kebutuhan_grup ?? [], tw), "Belum ada kebutuhan yang dilaporkan", undefined, (k.kebutuhan_grup ?? []).length, true),
      factBlock("Penanganan", k.lembaga.map((l) => lembagaBlock(l, tw)), "Belum ada penanganan yang dilaporkan"),
      tweetFold("Sumber laporan", tws, tw),
      h("div", { class: "card-foot" }, this.askBtn({ event_id: k.event_id, nama: k.nama, jenis: k.jenis })));
    if (this.openDetails.has(k.event_id)) det.open = true;
    det.addEventListener("toggle", () => { det.open ? this.openDetails.add(k.event_id) : this.openDetails.delete(k.event_id); });
    const periodeBeda = k.jumlah_laporan_periode !== k.jumlah_laporan_total;
    const bits = [`${k.dampak.length} dampak`, `${(k.kebutuhan_grup ?? []).length} kebutuhan`, `${k.lembaga.length} lembaga`].join(" | ");
    const el = h("article", { class: `card${on ? " is-sorot" : ""}${this.sorot && !on ? " is-redup" : ""}${bisa ? "" : " is-static"}`,
      "data-lok": k.lokasi_ids.join(" "),
      role: "listitem", "data-event": k.event_id },
      hit,
      h("dl", { class: "card-meta" },
        h("div", {}, h("dt", {}, "Mulai"), h("dd", {}, tgl(k.start_time))),
        h("div", {}, h("dt", {}, "Laporan terakhir"), h("dd", {}, tgl(k.end_time)))),
      h("p", { class: "card-counts" }, h("b", {}, angka(k.jumlah_laporan_periode)), " laporan · ", h("b", {}, angka(k.jumlah_tweet_periode)), " tweet unik"),
      periodeBeda ? h("p", { class: "card-scope" }, `Pada rentang ini; ${angka(k.jumlah_laporan_total)} laporan sepanjang data.`) : null,
      k.lokasi.length ? h("p", { class: "card-locs" }, ico("target", 13, "loc-ic"), ...k.lokasi.map((l, i) => [i ? ", " : "",
        h("button", { type: "button", class: "linkish", onclick: () => this.hd.onTitik(l.gazetteer_id) }, l.nama)]).flat())
        : h("p", { class: "card-locs muted" }, "Tidak ada lokasi rinci pada rentang ini"),
      h("p", { class: "card-sum" }, bits),
      det);
    el.addEventListener("click", (e) => {
      if (!bisa || (e.target as Element).closest("button, a, details")) return;
      if (window.getSelection()?.toString()) return;
      this.toggle(k.event_id);
    });
    this.cards.set(k.event_id, el);
    if (bisa) onPreview(el, () => this.hd.onPreviewLokasi?.(k.lokasi_ids), () => this.hd.onPreviewLokasi?.(null));
    return el;
  }

  /** Pasang pratinjau hover/fokus pada elemen dan kembalikan elemen itu (untuk dirangkai di h()). */
  private pv<T extends HTMLElement>(el: T, on: () => void, off: () => void): T { onPreview(el, on, off); return el; }

  /** Hover penanda di peta: tandai kartu kejadian yang memuat lokasi itu. */
  previewCards(gid: string | null): void {
    for (const el of this.cards.values()) el.classList.toggle("is-pv", !!gid && (el.dataset.lok ?? "").split(" ").includes(gid));
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
  lokasi(r: Ringkasan, kabNama: string | null, _kabSaatIni: string | null, _kabLokasi: string | null): void {
    const L = r.lokasi;
    const tw = r.tweet_map ?? {};
    const tweets = h("details", { class: "psec psec--fold tfold tfold--card" },
      h("summary", { class: "psec-t" }, h("span", { class: "tfold-t" }, "Tweet yang menyebut lokasi ini"), h("span", { class: "ftag ftag--count" }, `${r.tweets.length} tweet`), ico("chevDown", 14, "fsrc-chev")),
      r.tweets.length ? h("ol", { class: "tweets" }, ...r.tweets.map((t) => h("li", { class: "tweet", id: `tw-${t.tweet_id}` },
        h("div", { class: "tweet-h" }, h("span", {}, waktu(t.upload)), h("span", { class: "tweet-id" }, `ID ${t.tweet_id}`)),
        h("blockquote", { class: "tweet-x", lang: "id" }, t.text ?? "Teks tidak tersedia"),
        t.url ? h("a", { class: "tweet-a", href: t.url, target: "_blank", rel: "noopener noreferrer" }, "Buka tweet asli", ico("external", 13))
          : h("span", { class: "tweet-na" }, "Tautan sumber tidak tersedia")))) : none("Tidak ada tweet pada rentang ini"));
    this.show(h("div", {},
      h("button", { type: "button", class: "back", onclick: () => this.hd.onBack() }, ico("arrowLeft", 15), kabNama ?? "Kembali"),
      h("header", { class: "phead" },
        h("h2", { class: "ptitle" }, L.nama),
        h("p", { class: "psub" }, `${TINGKAT_LABEL[L.tingkat] ?? L.tingkat} · ${(L.admin_path ?? "Jalur administratif tidak tersedia").split(" > ").join(" › ")}`),
        L.latitude !== null ? h("p", { class: "coord", title: "Koordinat entri gazetteer; bukan titik pusat atau batas bencana" },
          `${L.latitude!.toFixed(4)}, ${L.longitude!.toFixed(4)}`) : null),
      h("div", { class: "kpis kpis--lok" },
        kpi("Kejadian", r.kejadian.length, "Kejadian yang laporannya menyebut lokasi ini"),
        kpi("Laporan", r.jumlah_laporan, `Laporan kejadian unik yang menyebut lokasi ini (${r.jumlah_tweet} tweet unik)`),
        kpi("Periode laporan", rentang(r.tanggal_awal, r.tanggal_akhir))),
      r.jumlah_laporan === 0 && !r.kejadian.length ? h("div", { class: "pstate pstate--compact" }, h("p", {}, "Tidak ada laporan untuk lokasi ini yang sesuai dengan filter yang dipilih.")) : null,
      r.kejadian.length ? ringkasBox(ringkasLokasi(r)) : null,
      r.kejadian.length ? h("div", { class: "cards" },
        ...r.kejadian.map((k) => {
          const ini = k.dampak.filter((d) => d.atribusi === "lokasi_ini");
          const menyebut = k.laporan.filter((m) => m.relasi !== "evakuasi").length;
          const evak = k.laporan.length - menyebut;
          const rel = [menyebut ? `Disebut dalam ${angka(menyebut)} dari ${angka(k.jumlah_laporan_kejadian)} laporan kejadian ini` : null,
            evak ? `tujuan evakuasi dalam ${angka(evak)} laporan` : null].filter(Boolean).join("; ");
          const nKeb = grupAtr(k.kebutuhan_grup, "lokasi_ini").length;
          return h("article", { class: "card evgroup is-static", "data-event": k.event_id },
            h("div", { class: "card-top" }, jenisTag(k.jenis), h("span", { class: "card-badge" }, `${angka(k.laporan.length)} dari ${angka(k.jumlah_laporan_kejadian)} laporan`)),
            h("p", { class: "card-t" }, k.nama),
            h("dl", { class: "card-meta" },
              h("div", {}, h("dt", {}, "Mulai"), h("dd", {}, tgl(k.start_time))),
              h("div", {}, h("dt", {}, "Laporan terakhir"), h("dd", {}, tgl(k.end_time)))),
            h("div", { class: "evgroup-m" }, h("span", {}, k.nama_kab ?? "Kab/kota tidak tersedia")),
            rel ? h("p", { class: "evgroup-rel" }, `${rel}.`) : null,
            h("p", { class: "card-sum" }, `${ini.length} dampak | ${nKeb} kebutuhan | ${k.penanganan.length} lembaga di lokasi ini`),
            h("details", { class: "card-more" },
              h("summary", {}, h("span", {}, "Detail kejadian"), ico("chevDown", 15, "more-chev")),
              factBlock("Dampak di lokasi ini", dampakGroups(ini, tw, { scope: false }), "Belum ada dampak yang dilaporkan di lokasi ini", undefined, ini.length, true),
              factBlock("Kebutuhan di lokasi ini", kebutuhanGroups(grupAtr(k.kebutuhan_grup, "lokasi_ini"), tw), "Belum ada kebutuhan yang dilaporkan di lokasi ini", undefined, nKeb, true),
              factBlock("Penanganan", k.penanganan.map((l) => lembagaBlock(l, tw)), "Belum ada penanganan yang dilaporkan"),
              k.evakuasi.length ? factBlock("Evakuasi", k.evakuasi.map((e) => h("li", { class: "fact" },
                h("span", { class: "fact-main" }, h("span", { class: "fact-what" },
                  e.tujuan.some((t) => t.gazetteer_id === L.gazetteer_id) ? "Lokasi ini menjadi tujuan evakuasi" : `Evakuasi ke ${e.tujuan.map((t) => t.nama).join(", ") || "tujuan tidak disebutkan"}`)),
                h("span", { class: "fact-meta" }, h("span", { class: "ftag ftag--plain" }, e.asal.length ? `asal: ${e.asal.map((a) => a.nama).join(", ")}` : "asal tidak disebutkan"),
                  h("span", { class: "dchip" }, h("b", {}, tgl(e.tanggal_lokal)), h("span", {}, e.tweet_ids.join(", ") || e.mention_id))))), null) : null,
              tweetFold("Laporan yang merujuk lokasi ini", [...new Set(k.laporan.flatMap((m) => m.tweet_ids))], tw),
              h("div", { class: "card-foot" }, this.askBtn({ event_id: k.event_id, nama: k.nama, jenis: k.jenis }))));
        })) : null,
      r.lembaga_dikerahkan.length ? section("Lembaga yang dikerahkan ke lokasi ini",
        h("p", { class: "psec-note" }, "Dicatat pada tingkat lokasi; tidak tertaut ke laporan atau kejadian tertentu."),
        h("ul", { class: "facts" }, ...r.lembaga_dikerahkan.map((l) => lembagaBlock(l, tw)))) : null,
      tweets), `lokasi:${L.gazetteer_id}`);
  }
}
