import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { inflateRawSync } from "node:zlib";
import { clickKab, current, enterKab, kpi, lokasiUnik, open, settle } from "./helpers";

type Psb = { map: L.Map; store: { state: { kab: string | null; lokasi: string | null; sorot: string | null; jenis: Set<string> } };
  setChatService: (s: unknown) => void };

/** Total laporan pada linimasa (penjumlahan batang mingguan yang sedang tampil). */
const tlTotal = (page: Page) => page.locator(".tl-week").evaluateAll((els) => els.reduce((a, e) => a + Number(e.getAttribute("data-total")), 0));

/** Isi berkas ZIP (metode deflate/stored) tanpa dependensi tambahan. */
function unzip(buf: Buffer): Record<string, string> {
  const out: Record<string, string> = {};
  let i = buf.lastIndexOf(Buffer.from([0x50, 0x4b, 0x05, 0x06]));
  const n = buf.readUInt16LE(i + 10);
  let p = buf.readUInt32LE(i + 16);
  for (let k = 0; k < n; k++) {
    const method = buf.readUInt16LE(p + 10), csize = buf.readUInt32LE(p + 20), nlen = buf.readUInt16LE(p + 28), xlen = buf.readUInt16LE(p + 30), clen = buf.readUInt16LE(p + 32);
    const local = buf.readUInt32LE(p + 42), name = buf.subarray(p + 46, p + 46 + nlen).toString("utf8");
    const lstart = local + 30 + buf.readUInt16LE(local + 26) + buf.readUInt16LE(local + 28);
    const raw = buf.subarray(lstart, lstart + csize);
    out[name] = (method === 8 ? inflateRawSync(raw) : raw).toString("utf8");
    p += 46 + nlen + xlen + clen;
  }
  return out;
}

// ------------------------------------------------------------------ A2 kursor
test("ringkasan nasional: kartu per jenis menggantikan daftar kab/kota; klik baris = filter jenis", async ({ page }) => {
  await open(page);
  await expect(page.locator(".panel .rank-btn")).toHaveCount(0);
  await expect(page.locator(".jrow")).toHaveCount(6);
  await expect(page.locator(".jrow").first()).toContainText("Banjir");
  await expect(page.locator(".jrow").first()).toContainText("6");
  await page.locator(".jrow").first().click();
  await expect(page.locator('.chip[aria-pressed="true"]:not(.chip--all)')).toHaveCount(1);
  await expect(page.locator('.chip[data-jenis="banjir"]')).toHaveAttribute("aria-pressed", "true");
});

test("kursor: elemen laporan yang dapat diklik memakai penunjuk tangan (bukan plus/crosshair)", async ({ page }) => {
  await open(page);
  const cur = (sel: string) => page.locator(sel).first().evaluate((e) => getComputedStyle(e).cursor);
  expect(await cur("path.kab")).toBe("pointer");
  expect(await cur(".jrow")).toBe("pointer");
  expect(await cur(".tl-hit")).toBe("pointer");
  expect(await cur(".tl-handle")).toBe("ew-resize");
  await enterKab(page, "3508", "Kab. Lumajang");
  expect(await cur(".leaflet-marker-icon")).toBe("pointer");
  expect(await cur(".card")).toBe("pointer");
  await page.locator('.card[data-event="DE01"] .card-more > summary').click();
  expect(await cur('.card[data-event="DE01"] .fsrc > summary')).toBe("pointer");
  const all = await page.evaluate(() => [...document.querySelectorAll("*")].map((e) => getComputedStyle(e).cursor).filter((c) => /crosshair|cell|copy|zoom-in/.test(c)).length);
  expect(all).toBe(0);
});

// ------------------------------------------------------------------ A3 tampilan nasional
test("tampilan nasional lebih dekat dari sekadar muat, tetap memuat ujung barat-timur", async ({ page }) => {
  await open(page);
  const r = await page.evaluate(() => {
    const m = (window as unknown as { __psb: Psb }).__psb.map;
    const LL = (window as unknown as { L: typeof L }).L;
    const b = LL.latLngBounds([[-11.1, 94.8], [6.2, 141.1]]);
    const c = m.getContainer().getBoundingClientRect(), p = document.querySelector(".panel")!.getBoundingClientRect();
    // zoom yang sekadar memuat Indonesia di area peta yang tidak tertutup panel
    const visible = m.getBoundsZoom(b, false, LL.point(c.right - p.left, 0));
    return { z: m.getZoom(), visible, sabang: m.getBounds().contains([5.9, 95.3]), merauke: m.getBounds().contains([-8.5, 140.4]) };
  });
  expect(r.z).toBeGreaterThan(r.visible); // lebih dekat daripada sekadar "muat" di area terlihat
  expect(r.sabang && r.merauke).toBe(true);
});

// ------------------------------------------------------------------ B4 berpusat-kejadian
test("lokasi Kec. Bangil: fakta dikelompokkan per kejadian, angka per laporan tidak dijumlahkan", async ({ page }) => {
  await open(page, [], { path: "/?kab=3514&lokasi=contoh:kec/bangil" });
  await expect(page.locator(".panel .ptitle")).toHaveText("Kec. Bangil");
  await expect(page.locator("#tabbtn-detail")).toHaveText("Detail Lokasi");
  const de09 = page.locator('.evgroup[data-event="DE09"]'), de10 = page.locator('.evgroup[data-event="DE10"]');
  for (const g of [de09, de10]) await g.locator(".card-more > summary").click(); // "Detail kejadian"
  await expect(page.locator(".evgroup")).toHaveCount(2);
  const ini09 = de09.locator(".fblock", { hasText: "Dampak di lokasi ini" });
  await expect(ini09.locator(".fact-qty")).toHaveText("350 unit");
  await expect(de10.locator(".fblock", { hasText: "Dampak di lokasi ini" }).locator(".fact-qty")).toHaveText("90 unit");
  // tidak ada angka gabungan 440 di mana pun
  await expect(page.locator(".panel")).not.toContainText("440");
  // sumber fakta: tanggal + laporan, dapat dibuka hingga tweet aslinya
  const src = ini09.locator(".fsrc").first();
  await expect(src.locator("summary")).toContainText("9 Jan 2026");
  await expect(src.locator("summary")).toContainText("T19");
  await src.locator("summary").click();
  await expect(src.locator(".stw")).toContainText("Sekitar 350 rumah terendam di Bangil");
  await expect(src.locator(".stw-id")).toHaveText("ID T19");
  await expect(de09.locator(".fblock", { hasText: "Kebutuhan di lokasi ini" })).toContainText("air bersih");
  await expect(de09.locator(".fblock", { hasText: "Penanganan" })).toContainText("BPBD");
  await expect(de10.locator(".fblock", { hasText: "Kebutuhan di lokasi ini" })).toContainText("Belum ada kebutuhan yang dilaporkan di lokasi ini");
});

test("kartu kejadian kab/kota: dampak, kebutuhan, penanganan, sumber laporan per kejadian", async ({ page }) => {
  await open(page);
  await enterKab(page, "3514", "Kab. Pasuruan");
  const c = page.locator('.card[data-event="DE09"]');
  await c.locator(".card-more > summary").click();
  const dampak = c.locator(".fblock", { hasText: "Dampak kejadian" });
  await expect(dampak.locator(".fact")).not.toHaveCount(0);
  await expect(dampak.locator(".ftag").first()).toBeVisible(); // setiap fakta berlabel lokasi atau "Tingkat kejadian"
  const sumber = c.locator(".tfold", { hasText: "Sumber laporan" });
  await expect(sumber.locator(".tfold-l > li")).toHaveCount(3);
  await sumber.locator("summary").click();
  await expect(sumber.locator(".stw").first()).toContainText("ID T");
  await expect(c.locator(".ask-btn")).toHaveText("Tanyakan tentang kejadian ini");
});

// ------------------------------------------------------------------ C5 linimasa mengikuti cakupan
test("linimasa mengikuti cakupan: nasional → provinsi → kab/kota → lokasi", async ({ page }) => {
  await open(page);
  await expect(page.locator(".tl-scope")).toHaveText("Nasional");
  const nasional = await tlTotal(page);
  expect(nasional).toBe(33);
  await page.locator(".prov-btn", { hasText: "Jawa Timur" }).click();
  await expect(page.locator(".tl-scope")).toHaveText("Provinsi Jawa Timur");
  await expect.poll(() => tlTotal(page)).toBe(33);
  await clickKab(page, "3507");
  await expect(page.locator(".tl-scope")).toHaveText("Kab. Malang");
  await expect.poll(() => tlTotal(page)).toBe(6);
  await page.locator('.card[data-event="DE03"] .linkish', { hasText: "Gunung Semeru" }).click();
  await expect(page.locator(".tl-scope")).toHaveText("Gunung Semeru");
  await expect.poll(() => tlTotal(page)).toBe(3); // hanya laporan yang menyebut Gunung Semeru
  await expect(page.locator(".tl-scope")).toHaveAttribute("title", /Hanya laporan kejadian yang menyebut Gunung Semeru.*Satuan: laporan kejadian \(EventMention\) unik/);
  // keadaan kosong yang jelas
  await page.goto("/?prov=11");
  await expect(page.locator("body")).toHaveAttribute("data-ready", "true");
  await expect(page.locator(".tl-empty")).toHaveText("Belum ada laporan kejadian untuk Provinsi Aceh pada jenis yang dipilih.");
});

test("tampilan provinsi: remah roti, panel, peta diredupkan di luar provinsi", async ({ page }) => {
  await open(page);
  await enterKab(page, "3508", "Kab. Lumajang");
  await page.locator(".crumb", { hasText: "Jawa Timur" }).click();
  await expect(current(page)).toHaveText("Jawa Timur");
  await expect(page.locator(".panel .ptitle")).toHaveText("Jawa Timur");
  await expect(kpi(page, "Kejadian")).toHaveText("15");
  await expect(page.locator(".panel .rank-btn")).toHaveCount(7);
  await expect.poll(() => lokasiUnik(page)).toBe(0);
  await expect(page.locator('path.kab[data-kode="3508"]')).not.toHaveClass(/is-dim/);
  await expect(page.locator('path.kab[data-kode="1101"]')).toHaveClass(/is-dim/);
  await expect(page).toHaveURL(/\?prov=35$/);
  await page.keyboard.press("Escape");
  await expect(current(page)).toHaveText("Indonesia");
});

// ------------------------------------------------------------------ C6 lokasi rujukan
test("lokasi rujukan: bentuk & warna tetap, cincin putus-putus, tooltip berbasis kode wilayah", async ({ page }) => {
  await open(page);
  await enterKab(page, "3507", "Kab. Malang");
  const semeru = page.locator('.pm-marker[data-gid="contoh:gunung/semeru"]');
  await expect(semeru.locator(".pm-mk")).toHaveClass(/is-luar/);
  expect(await semeru.locator(".pm-mk").evaluate((e) => getComputedStyle(e).borderTopStyle)).toBe("dashed");
  await expect(semeru).toHaveAttribute("aria-label", /Lokasi rujukan\. Lokasi berada di Kab\. Lumajang, tetapi dirujuk dalam laporan terkait Kab\. Malang\./);
  await semeru.hover();
  await expect(page.locator(".maptip")).toContainText("Lokasi berada di Kab. Lumajang, tetapi dirujuk dalam laporan terkait Kab. Malang.");
  // lokasi di dalam kab tidak bercincin
  await expect(page.locator('.pm-marker:not([data-gid="contoh:gunung/semeru"]) .pm-mk.is-luar')).toHaveCount(0);
  await expect(page.locator(".lg-mk--luar")).toContainText("bukan lokasi kejadian");
});

// ------------------------------------------------------------------ C7 warna
test("warna jenis: terpusat di token, palet kalem tetap terbedakan, ikon putih terbaca", async ({ page }) => {
  await open(page);
  const hex = await page.evaluate(() => Object.fromEntries(["banjir", "longsor", "cuaca", "karhutla", "gempa", "erupsi"].map((j) =>
    [j, getComputedStyle(document.documentElement).getPropertyValue(`--j-${j}`).trim()])));
  const lin = (c: number) => { c /= 255; return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
  const unlin = (c: number) => 255 * (c <= 0.0031308 ? 12.92 * c : 1.055 * Math.max(0, c) ** (1 / 2.4) - 0.055);
  const rgb = (h: string) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const M: Record<string, number[][]> = { // Machado dkk. 2009, keparahan 1
    deutan: [[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.01182, 0.04294, 0.968881]],
    protan: [[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]],
  };
  const sim = (c: number[], k?: string) => { if (!k) return c; const l = c.map(lin); return M[k].map((r) => unlin(r[0] * l[0] + r[1] * l[1] + r[2] * l[2])); };
  const lab = (c: number[]) => {
    const [r, g, b] = c.map(lin);
    const f = (t: number) => (t > 0.008856 ? Math.cbrt(t) : 7.787 * t + 16 / 116);
    const X = f((0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047), Y = f(0.2126 * r + 0.7152 * g + 0.0722 * b), Z = f((0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883);
    return [116 * Y - 16, 500 * (X - Y), 200 * (Y - Z)];
  };
  const de = (a: string, b: string, k?: string) => { const x = lab(sim(rgb(hex[a]), k)), y = lab(sim(rgb(hex[b]), k)); return Math.hypot(x[0] - y[0], x[1] - y[1], x[2] - y[2]); };
  const names = Object.keys(hex);
  for (let i = 0; i < names.length; i++) for (let j = i + 1; j < names.length; j++) expect(de(names[i], names[j]), `${names[i]}–${names[j]}`).toBeGreaterThan(12);
  expect(de("cuaca", "erupsi")).toBeGreaterThan(45);
  expect(de("cuaca", "erupsi", "deutan")).toBeGreaterThan(25);
  expect(de("cuaca", "erupsi", "protan")).toBeGreaterThan(25);
  // ikon putih di atas warna jenis: kontras ≥ 3:1 untuk grafis, WCAG 1.4.11 (warna bukan satu-satunya penanda — ikon selalu ada)
  const lum = (h: string) => { const [r, g, b] = rgb(h).map(lin); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
  for (const j of names) expect(1.05 / (lum(hex[j]) + 0.05), j).toBeGreaterThan(3);
  // warna yang sama dipakai chip, linimasa, dan legenda (satu sumber)
  const chipC = await page.locator('.chip[data-jenis="cuaca"]').evaluate((e) => getComputedStyle(e).getPropertyValue("--c").trim());
  expect(chipC).toBe(hex.cuaca);
  const tl = await page.locator('.tl-bar[fill="var(--j-cuaca)"]').first().evaluate((e) => getComputedStyle(e).fill);
  expect(tl).toBe(`rgb(${rgb(hex.cuaca).join(", ")})`);
});

// ------------------------------------------------------------------ chip jenis teks saja
test("chip jenis: teks saja & netral (tanpa warna jenis), aktif ditandai tebal + garis, Semua hanya aktif bila semua aktif", async ({ page }) => {
  await open(page, [], { path: "/?jenis=banjir,erupsi" });
  const done = () => page.locator(".tb-jenis").evaluate((e) => Promise.all(e.getAnimations({ subtree: true }).map((a) => a.finished)));
  await done();
  await expect(page.locator(".tb-jenis svg, .tb-jenis .chip-box")).toHaveCount(0); // tanpa kotak centang / tanda centang
  await expect(page.locator(".chip--all")).toHaveAttribute("aria-pressed", "false");
  const bg = (j: string) => page.locator(`.chip[data-jenis="${j}"]`).evaluate((e) => getComputedStyle(e).backgroundColor);
  const [banjir, erupsi, longsor, gempa] = [await bg("banjir"), await bg("erupsi"), await bg("longsor"), await bg("gempa")];
  expect(banjir).toBe(erupsi); // aktif: netral, tidak memakai warna jenis
  expect(longsor).toBe(gempa); // nonaktif: netral & seragam
  expect(banjir).not.toBe(longsor);
  const wt = (j: string) => page.locator(`.chip[data-jenis="${j}"]`).evaluate((e) => Number(getComputedStyle(e).fontWeight));
  expect(await wt("banjir")).toBeGreaterThan(await wt("longsor")); // tidak bergantung pada warna saja
  const lon = page.locator('.chip[data-jenis="longsor"]');
  const w0 = (await lon.boundingBox())!.width;
  await lon.click();
  await expect(lon).toHaveAttribute("aria-pressed", "true");
  expect(Math.abs((await lon.boundingBox())!.width - w0)).toBeLessThan(0.6); // tanpa pergeseran tata letak
  expect(await lon.evaluate((e) => getComputedStyle(e).cursor)).toBe("pointer");
  await page.locator(".chip--all").click();
  await expect(page.locator('.chip[aria-pressed="true"]')).toHaveCount(7);
  await expect(page).toHaveURL(/127\.0\.0\.1:5173\/$/);
  await page.locator(".chip--all").click(); // semua aktif → klik lagi = lepas semua
  await expect(page.locator('.chip[aria-pressed="true"]')).toHaveCount(0);
  await page.locator(".chip--all").click();
  await expect(page.locator('.chip[aria-pressed="true"]')).toHaveCount(7);
});

// ------------------------------------------------------------------ D8 URL
test("URL: dipulihkan saat dimuat, Back/Forward berfungsi, parameter tidak valid diabaikan", async ({ page }) => {
  await open(page, [], { path: "/?kab=3508&jenis=erupsi&kejadian=DE01" });
  await expect(current(page)).toHaveText("Kab. Lumajang");
  await expect(page.locator('.chip[aria-pressed="true"]:not(.chip--all)')).toHaveCount(1);
  await expect(page.locator('.chip[data-jenis="erupsi"]')).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator('.card[data-event="DE01"]')).toHaveClass(/is-sorot/);
  // navigasi geografis menambah riwayat; filter mengganti entri aktif
  await page.locator('.card[data-event="DE01"] .linkish', { hasText: "Gunung Semeru" }).click();
  await expect(page.locator(".panel .ptitle")).toHaveText("Gunung Semeru");
  await expect(page).toHaveURL(/kab=3508&lokasi=contoh%3Agunung%2Fsemeru&jenis=erupsi&kejadian=DE01/);
  await page.goBack();
  await expect(page.locator(".panel .ptitle")).toHaveText("Kab. Lumajang");
  await expect(page).toHaveURL(/\?kab=3508&jenis=erupsi&kejadian=DE01$/);
  await page.goForward();
  await expect(page.locator(".panel .ptitle")).toHaveText("Gunung Semeru");
  await page.locator('.chip[data-jenis="banjir"]').click();
  await expect(page).toHaveURL(/jenis=banjir%2Cerupsi/);
  await page.goBack(); // filter tidak menambah entri: kembali ke tampilan kab/kota
  await expect(page.locator(".panel .ptitle")).toHaveText("Kab. Lumajang");
  // muat ulang = tampilan sama
  await page.reload();
  await expect(page.locator("body")).toHaveAttribute("data-ready", "true");
  await expect(current(page)).toHaveText("Kab. Lumajang");
  // parameter tidak valid
  await page.goto("/?kab=9999&jenis=banjir,xyz&dari=2026-02-30x&kejadian=DE01");
  await expect(page.locator("body")).toHaveAttribute("data-ready", "true");
  await expect(page.locator(".toast")).toContainText("Sebagian parameter tautan tidak valid dan diabaikan.");
  await expect(page.locator(".toast")).toContainText("kab/kota");
  await expect(current(page)).toHaveText("Indonesia");
  await expect(page).toHaveURL(/\?jenis=banjir$/);
});

test("URL: transien (chat, panel, tab) tidak pernah masuk URL", async ({ page }) => {
  await open(page);
  await enterKab(page, "3508", "Kab. Lumajang");
  const url = page.url();
  await page.locator(".ptab--ai").click();
  await page.locator(".chat-input").fill("rahasia pertanyaan");
  await page.keyboard.press("Enter");
  await page.locator(".panel-min").click();
  expect(page.url()).toBe(url);
  expect(page.url()).not.toContain("rahasia");
});

test("Bagikan Tampilan: salin tautan, dan cadangan bila papan klip ditolak", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await open(page, [], { path: "/?kab=3507&jenis=cuaca" });
  await page.getByRole("button", { name: "Bagikan Tampilan" }).click();
  await expect(page.locator(".toast")).toContainText("Tautan tampilan disalin.");
  const copied = await page.evaluate(() => navigator.clipboard.readText());
  expect(copied).toBe("http://127.0.0.1:5173/?kab=3507&jenis=cuaca");
  await page.evaluate(() => { Object.defineProperty(navigator, "clipboard", { value: { writeText: () => Promise.reject(new DOMException("ditolak", "NotAllowedError")) } }); });
  await page.getByRole("button", { name: "Bagikan Tampilan" }).click();
  await expect(page.locator("dialog.dlg")).toBeVisible();
  await expect(page.locator(".dlg-input")).toHaveValue("http://127.0.0.1:5173/?kab=3507&jenis=cuaca");
  await page.getByRole("button", { name: "Tutup", exact: true }).click();
  await expect(page.locator("dialog.dlg")).toBeHidden();
});

// ------------------------------------------------------------------ D9 / D10 ekspor
test("Ekspor Data (CSV): ZIP berisi CSV ternormalisasi + manifest; tanpa data = umpan balik", async ({ page }) => {
  await open(page, [], { path: "/?kab=3514&jenis=banjir" });
  await page.getByRole("button", { name: "Ekspor", exact: true }).click();
  const dl = page.waitForEvent("download");
  await page.getByRole("menuitem", { name: /Ekspor Data \(CSV\)/ }).click();
  const d = await dl;
  expect(d.suggestedFilename()).toMatch(/^peta-situasi-bencana_kab-pasuruan_\d{8}-\d{4}\.zip$/);
  const files = unzip(readFileSync((await d.path())!));
  expect(Object.keys(files).sort()).toEqual(["dampak.csv", "kebutuhan.csv", "kejadian.csv", "laporan.csv", "manifest.json", "penanganan.csv", "tweet.csv"]);
  expect(files["kejadian.csv"].charCodeAt(0)).toBe(0xfeff); // BOM UTF-8 untuk Excel
  expect(files["dampak.csv"]).toContain('"DE09"');
  const man = JSON.parse(files["manifest.json"]);
  expect(man.catatan.join(" ")).toContain("bukan data resmi BNPB");
  expect(man.filter.jenis).toEqual(["banjir"]);
  await expect(page.locator(".toast").last()).toContainText("Data diekspor.");
  // tanpa jenis = tidak ada data
  await page.goto("/?kab=3514&jenis="); // jenis kosong (didukung eksplisit)
  await expect(page.locator("body")).toHaveAttribute("data-ready", "true");
  await expect(page.locator('.chip[aria-pressed="true"]')).toHaveCount(0);
  await page.getByRole("button", { name: "Ekspor", exact: true }).click();
  await page.getByRole("menuitem", { name: /Ekspor Data \(CSV\)/ }).click();
  await expect(page.locator(".toast").last()).toContainText("Tidak ada data untuk diekspor.");
});

test("Ekspor Peta (PNG): gambar dibuat; bila ubin menolak CORS, peta dasar tidak disertakan secara terbuka", async ({ page }) => {
  await open(page, [], { path: "/?kab=3507", tiles: "tanpa-cors" });
  await expect.poll(() => lokasiUnik(page)).toBeGreaterThan(0);
  await settle(page);
  await page.getByRole("button", { name: "Ekspor", exact: true }).click();
  const dl = page.waitForEvent("download");
  await page.getByRole("menuitem", { name: /Ekspor Peta \(PNG\)/ }).click();
  const d = await dl;
  expect(d.suggestedFilename()).toMatch(/^peta-situasi-bencana_kab-malang_\d{8}-\d{4}\.png$/);
  const buf = readFileSync((await d.path())!);
  expect(buf.subarray(1, 4).toString()).toBe("PNG");
  expect(buf.readUInt32BE(16)).toBe(1440 * 2); // lebar = kanvas peta penuh × 2
  await expect(page.locator(".toast").last()).toContainText("peta dasar OpenStreetMap tidak disertakan");
});

test("Ekspor Peta (PNG): dengan ubin CORS peta dasar disertakan", async ({ page }) => {
  await open(page);
  await page.getByRole("button", { name: "Ekspor", exact: true }).click();
  const dl = page.waitForEvent("download");
  await page.getByRole("menuitem", { name: /Ekspor Peta \(PNG\)/ }).click();
  expect((await dl).suggestedFilename()).toMatch(/_indonesia_\d{8}-\d{4}\.png$/);
  await expect(page.locator(".toast").last()).toContainText("Peta diekspor (PNG).");
  await expect(page.locator(".toast").last()).not.toContainText("tidak disertakan");
});

// ------------------------------------------------------------------ E11–13 asisten
test("asisten: tombol mengambang, tab, keadaan belum tersedia, riwayat bertahan", async ({ page }) => {
  await open(page);
  await page.evaluate(() => (window as unknown as { __psb: Psb }).__psb.setChatService(null)); // tanpa layanan
  // panel terbuka: tab tersedia, tombol mengambang tersembunyi
  await expect(page.locator(".ptab")).toHaveCount(2);
  await expect(page.locator(".fab-ai")).toBeHidden();
  await page.locator(".panel-min").click();
  const fab = page.locator(".fab-ai");
  await expect(fab).toBeVisible();
  await fab.evaluate((e) => Promise.all(e.getAnimations().map((a) => a.finished))); // transisi masuk selesai
  const fb = (await fab.boundingBox())!, vp = page.viewportSize()!;
  expect(vp.width - (fb.x + fb.width)).toBeGreaterThanOrEqual(20);
  expect(vp.height - (fb.y + fb.height)).toBeGreaterThanOrEqual(20);
  const inter = (a: { x: number; y: number; width: number; height: number }, b: typeof a) =>
    a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height;
  for (const sel of [".timeline", ".legend", ".mapnav", ".leaflet-control-attribution"]) expect(inter(fb, (await page.locator(sel).boundingBox())!), sel).toBe(false);
  await fab.click();
  await expect(page.locator("#tabbtn-chat")).toHaveAttribute("aria-selected", "true");
  await expect(page.locator(".chat-t")).toHaveText("Asisten Situasi Bencana");
  await expect(page.locator(".chat-sub")).toHaveText("Tanya jawab berdasarkan data bencana");
  await expect(page.locator(".chat-empty-t")).toHaveText("Apa yang ingin Anda ketahui?");
  await expect(page.locator(".chat-input")).toBeFocused();
  await expect(page.locator(".chat-input")).toHaveAttribute("placeholder", "Tanyakan tentang situasi bencana...");
  await expect(page.locator(".chat-disc")).toHaveText("Jawaban berdasarkan laporan media sosial, bukan data resmi BNPB.");
  await expect(page.locator(".chat-status")).toHaveText("Belum terhubung");
  // Shift+Enter = baris baru, Enter = kirim
  await page.locator(".chat-input").pressSequentially("Baris satu");
  await page.keyboard.press("Shift+Enter");
  await page.locator(".chat-input").pressSequentially("baris dua");
  await expect(page.locator(".chat-input")).toHaveValue("Baris satu\nbaris dua");
  await page.keyboard.press("Enter");
  await expect(page.locator(".msg--user")).toContainText("Baris satu");
  await expect(page.locator(".msg--na")).toContainText("Asisten belum tersedia");
  await expect(page.locator(".msg--na")).toContainText("Tidak ada jawaban yang dibuat");
  await expect(page.locator(".cite")).toHaveCount(0); // tanpa sitasi buatan
  // riwayat bertahan saat berpindah tab & saat panel dilipat
  await page.locator("#tabbtn-detail").click();
  await expect(page.locator(".panel .ptitle")).toHaveText("Sebaran kejadian bencana");
  await page.locator("#tabbtn-chat").click();
  await expect(page.locator(".msg--user")).toHaveCount(1);
  // cakupan "Seluruh Indonesia" tidak mengubah filter peta
  await page.locator('.chip[data-jenis="banjir"]').click();
  const url = page.url();
  await page.getByRole("radio", { name: "Seluruh Indonesia" }).click();
  await expect(page.locator(".chat-ctx-v")).toHaveText("Seluruh Indonesia | semua jenis | seluruh periode");
  expect(page.url()).toBe(url);
  await expect(page.locator('.chip[data-jenis="banjir"]')).toHaveAttribute("aria-pressed", "false");
});

test("asisten: 'Tanyakan tentang kejadian ini' memberi konteks kejadian", async ({ page }) => {
  await open(page);
  await enterKab(page, "3508", "Kab. Lumajang");
  await page.locator('.card[data-event="DE01"] .card-more > summary').click();
  await page.locator('.card[data-event="DE01"] .ask-btn').click();
  await expect(page.locator("#tabbtn-chat")).toHaveAttribute("aria-selected", "true");
  await expect(page.locator(".chat-ev")).toContainText("Kejadian: Erupsi Gunung Semeru — Kab. Lumajang");
  await expect(page.locator(".chat-ctx-v")).toContainText("Kab. Lumajang");
  await expect(page.locator(".chat-ex-b").first()).toContainText("Erupsi Gunung Semeru");
  // layanan bawaan sementara: ringkasan dummy dari data nyata dasbor, dengan sitasi tweet asli
  await expect(page.locator(".chat-status")).toHaveText("Mode dummy");
  await page.locator(".chat-ex-b").first().click();
  await expect(page.locator(".msg--bot").last()).toContainText("Jawaban contoh (dummy)");
  await expect(page.locator(".msg--bot").last()).toContainText("Erupsi Gunung Semeru");
  await expect(page.locator(".cite").first()).toContainText("Kejadian DE01");
  await page.locator(".chat-ev-x").click();
  await expect(page.locator(".chat-ev")).toBeHidden();
});

test("asisten: layanan terhubung — memuat, sitasi dari backend, galat & coba lagi", async ({ page }) => {
  await open(page);
  await enterKab(page, "3514", "Kab. Pasuruan");
  await page.evaluate(() => {
    let n = 0;
    (window as unknown as { __psb: Psb }).__psb.setChatService({
      available: true, name: "uji",
      ask: (q: string, ctx: { wilayah: { kode_kab: string } }) => new Promise((res, rej) => {
        n++;
        window.setTimeout(() => n === 2 ? rej(new Error("Layanan sibuk (503)"))
          : res({ text: `Jawaban uji untuk ${ctx.wilayah.kode_kab}: ${q}`, citations: [
            { tweet_id: "T19", event_id: "DE09", mention_id: "EM21", tanggal: "2026-01-09", teks: "Sekitar 350 rumah terendam di Bangil" },
            { event_id: "DE09" }, // tanpa tweet_id: dibuang, tidak dilengkapi
          ] }), 300);
      }),
    });
  });
  await page.locator(".ptab--ai").click();
  await expect(page.locator(".chat-status")).toHaveText("Terhubung");
  await page.locator(".chat-input").fill("Berapa rumah terendam?");
  await page.keyboard.press("Enter");
  await expect(page.locator(".msg.is-loading")).toBeVisible();
  await expect(page.locator(".chat-send")).toBeDisabled();
  await expect(page.locator(".msg--bot").last()).toContainText("Jawaban uji untuk 3514: Berapa rumah terendam?");
  await expect(page.locator(".cite")).toHaveCount(1);
  await expect(page.locator(".cite")).toContainText("Tweet T19");
  await expect(page.locator(".cite")).toContainText("Kejadian DE09");
  await expect(page.locator(".cite")).toContainText("9 Jan 2026");
  await page.locator(".chat-input").fill("Pertanyaan kedua");
  await page.keyboard.press("Enter");
  await expect(page.locator(".msg--err")).toContainText("Layanan sibuk (503)");
  await page.locator(".msg--err").getByRole("button", { name: "Coba lagi" }).click();
  await expect(page.locator(".msg--err")).toHaveCount(0);
  await expect(page.locator(".msg--bot").last()).toContainText("Pertanyaan kedua");
});

// ------------------------------------------------------------------ F15 tata letak sempit
test("ponsel: lembar bawah menampilkan Tanya AI; kolom chat tetap terlihat", async ({ browser }) => {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });
  const page = await ctx.newPage();
  await open(page, [], { path: "/?kab=3508" });
  await expect(page.locator(".head-ask")).toBeVisible();
  await page.locator(".head-ask").click();
  await expect(page.locator("#tabbtn-chat")).toHaveAttribute("aria-selected", "true");
  await page.locator(".panel").evaluate((e) => Promise.all(e.getAnimations().map((a) => a.finished))); // lembar selesai naik
  const inp = (await page.locator(".chat-input").boundingBox())!;
  expect(inp.y + inp.height).toBeLessThanOrEqual(844);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(0);
  await ctx.close();
});

// ------------------------------------------------------------------ server backend lama (belum dimulai ulang)
test("backend versi lama: peringatan, tetapi kartu & penanda tetap tampil", async ({ page }) => {
  await page.route(/\/api\/wilayah$/, async (r) => { const res = await r.fetch(); const j = await res.json(); delete j.api_versi; await r.fulfill({ response: res, json: j }); });
  await page.route(/\/api\/kab\/3514\/kejadian/, async (r) => {
    const res = await r.fetch(); const j = await res.json();
    delete j.tweets; for (const k of j.kejadian) delete k.laporan; // bentuk respons server lama
    await r.fulfill({ response: res, json: j });
  });
  await open(page, [], {});
  await expect(page.locator(".toast")).toContainText("Versi backend tidak cocok dengan frontend.");
  await enterKab(page, "3514", "Kab. Pasuruan");
  await expect(page.locator(".card")).toHaveCount(3);
  await expect(page.locator(".panel .skel-wrap")).toHaveCount(0);
});

// ------------------------------------------------------------------ pratinjau hover
test("pratinjau hover: provinsi, jenis, kelas legenda, kartu ↔ penanda; tanpa mengubah state/URL", async ({ page }) => {
  await open(page);
  const url0 = page.url();
  const rules = () => page.locator("#pv-rules").evaluate((e) => e.textContent ?? "").catch(() => "");
  // baris provinsi → garis tepi provinsi + kab lain dipudarkan
  const prov = page.locator(".prov-btn").first();
  await prov.hover();
  await expect(page.locator("path.prov-pv")).toHaveCount(1);
  await expect.poll(rules).toContain("data-kode^=");
  await page.mouse.move(5, 300);
  await expect(page.locator("path.prov-pv")).toHaveCount(0);
  await expect.poll(rules).toBe("");
  // baris jenis → linimasa & komposisi dipudarkan untuk jenis lain
  // klik baris jenis = filter; klik lagi = kembali ke semua jenis
  await page.locator(".jrow").first().click();
  await expect(page.locator('.chip[aria-pressed="true"]:not(.chip--all)')).toHaveCount(1);
  await page.locator(".jrow:not(.is-pudar)").first().click();
  await expect(page.locator('.chip[aria-pressed="true"]')).toHaveCount(7);
  await page.locator(".jrow").first().hover();
  await expect.poll(rules).toContain(".tl-bar:not(");
  await page.mouse.move(5, 300);
  await expect.poll(rules).toBe("");
  // kelas legenda
  await page.locator(".lg-step").nth(1).hover();
  await expect.poll(rules).toContain('data-k="2"');
  await page.mouse.move(5, 300);
  expect(page.url()).toBe(url0); // hanya tampilan
  // kab: kartu ↔ penanda
  await enterKab(page, "3507", "Kab. Malang");
  const card = page.locator(".card:not(.is-static)").first();
  const lok = (await card.getAttribute("data-lok"))!.split(" ")[0];
  await card.hover();
  await expect.poll(rules).toContain(lok);
  const other = page.locator(`.pm-marker:not([data-gid="${lok}"]) .pm-mk`).first();
  if (await other.count()) await expect.poll(() => other.evaluate((e) => Number(getComputedStyle(e).opacity))).toBeLessThan(0.5);
  await page.mouse.move(5, 300);
  await expect.poll(rules).toBe("");
  await page.locator(`.pm-marker[data-gid="${lok}"]`).hover();
  await expect(card).toHaveClass(/is-pv/);
  await expect(page.locator(".card.is-sorot")).toHaveCount(0); // klik tetap aksi utama
});
