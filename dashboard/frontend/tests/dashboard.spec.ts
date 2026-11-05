import { expect, test } from "@playwright/test";
import { clickKab, current, enterKab, kabPath, kpi, lokasiUnik, markers, open, screenOf, settle, zoom } from "./helpers";

test("1. tampilan awal: Indonesia utuh, choropleth benar, satu label lokasi, tanpa penanda", async ({ page }) => {
  const errors: string[] = [];
  await open(page, errors);
  await expect(page.locator("path.kab")).toHaveCount(514);
  const n = await page.locator('path.kab:not([data-k="na"])').evaluateAll((els) =>
    Object.fromEntries(els.map((e) => [e.getAttribute("data-kode"), Number(e.getAttribute("data-n"))])));
  expect(n).toEqual({ "3507": 3, "3508": 2, "3509": 2, "3513": 1, "3514": 3, "3515": 1, "3579": 3 });
  await expect(kpi(page, "Kejadian bencana")).toHaveText("15");
  await expect(kpi(page, "Tweet sumber unik")).toHaveText("31");
  await expect(kpi(page, "Kab/kota")).toHaveText("7");
  await expect(markers(page)).toHaveCount(0);
  const b = await page.evaluate(() => {
    const m = (window as unknown as { __psb: { map: L.Map } }).__psb.map;
    return [[5.5, 95.3], [-8.4, 140.7], [-10.6, 123.4], [4.3, 117.5]].map((ll) => m.getBounds().contains(ll as [number, number]));
  });
  expect(b).toEqual([true, true, true, true]); // Aceh, Merauke, Rote, Kalimantan Utara terlihat
  await expect(page.locator(".crumbs")).toHaveText("Indonesia");
  await expect(page.getByText("Seluruh Indonesia")).toHaveCount(0);
  await expect(page.getByText("Ikhtisar nasional", { exact: false })).toHaveCount(0);
  expect(await page.evaluate(() => getComputedStyle(document.body).fontFamily)).toContain("Plus Jakarta Sans");
  expect(errors).toEqual([]);
});

test("2. hover poligon: muncul, berpindah tanpa macet, hilang di laut", async ({ page }) => {
  await open(page);
  const hoverPaths = page.locator(".leaflet-kabHover-pane path");
  const tip = page.locator(".maptip");
  const lmj = await screenOf(page, -8.13, 113.15);
  await page.mouse.move(lmj.x, lmj.y);
  await expect(tip).toBeVisible();
  await expect(tip).toContainText("Kab. Lumajang");
  await expect(hoverPaths).toHaveCount(1);
  // gerak cepat melintasi banyak poligon lalu berhenti di laut
  const a = await screenOf(page, -7.3, 111.2), z = await screenOf(page, -8.0, 114.3);
  await page.mouse.move(a.x, a.y);
  await page.mouse.move(z.x, z.y, { steps: 25 });
  await expect(hoverPaths).toHaveCount(1);
  const sea = await screenOf(page, -10.2, 112.0);
  await page.mouse.move(sea.x, sea.y, { steps: 4 });
  await expect(tip).toBeHidden();
  await expect(hoverPaths).toHaveCount(0);
  // keluar ke panel juga membersihkan hover
  await page.mouse.move(lmj.x, lmj.y);
  await expect(tip).toBeVisible();
  await page.locator(".panel .ptitle").hover();
  await expect(tip).toBeHidden();
  await expect(hoverPaths).toHaveCount(0);
});

test("3. klik kab/kota: zoom, pindah langsung antarkab, klik poligon terpilih tidak menggandakan apa pun", async ({ page }) => {
  await open(page);
  const w0 = (await kabPath(page, "3508").boundingBox())!.width;
  await enterKab(page, "3508", "Kab. Lumajang");
  await expect.poll(() => lokasiUnik(page)).toBe(5);
  await expect(page.locator(".card")).toHaveCount(2);
  expect((await kabPath(page, "3508").boundingBox())!.width).toBeGreaterThan(w0 * 3);
  await expect(page.locator(".leaflet-kabSel-pane path")).toHaveCount(2); // halo + garis seleksi
  await clickKab(page, "3508");
  await expect(current(page)).toHaveText("Kab. Lumajang");
  await expect(page.locator(".maptip")).toBeHidden();
  await enterKab(page, "3507", "Kab. Malang"); // langsung, tanpa kembali ke nasional
  await expect(kabPath(page, "3508")).not.toHaveClass(/is-selected/);
  await expect(kabPath(page, "3507")).toHaveClass(/is-selected/);
  await expect(page.locator(".panel .ptitle")).toHaveCount(1);
});

test("4. klik laut kembali ke nasional; klik panel tidak", async ({ page }) => {
  await open(page);
  await enterKab(page, "3579", "Kota Batu");
  await settle(page);
  await page.locator(".panel .kpis").click();
  await page.waitForTimeout(450);
  await expect(current(page)).toHaveText("Kota Batu");
  await page.getByRole("button", { name: "Perbesar" }).click();
  await page.waitForTimeout(450);
  await expect(current(page)).toHaveText("Kota Batu");
  await page.evaluate(() => { (window as unknown as { __psb: { map: L.Map } }).__psb.map.setView([-9.6, 112.6], 8, { animate: false }); });
  const sea = await screenOf(page, -10.2, 112.6);
  await page.mouse.click(sea.x, sea.y);
  await expect(current(page)).toHaveText("Indonesia");
  await expect.poll(() => lokasiUnik(page)).toBe(0);
  await expect(page.locator(".panel .ptitle")).toHaveText("Sebaran kejadian bencana");
});

test("5. klik penanda: pilih + zoom secukupnya; penanda dekat tidak memicu gerak ulang", async ({ page }) => {
  await open(page);
  await enterKab(page, "3579", "Kota Batu");
  await settle(page);
  const z0 = await zoom(page);
  const bulukerto = page.locator('.pm-marker[data-gid="contoh:desa/bulukerto"]');
  await bulukerto.hover();
  await expect(page.locator(".maptip")).toContainText("Desa Bulukerto");
  await expect(page.locator(".maptip")).toContainText("Laporan yang menyebut lokasi ini");
  await bulukerto.click();
  await expect(page.locator(".panel .ptitle")).toHaveText("Desa Bulukerto");
  await settle(page);
  const z1 = await zoom(page);
  expect(z1).toBeGreaterThan(z0);
  expect(z1).toBeLessThanOrEqual(13);
  await expect(bulukerto).toHaveClass(/is-selected/);
  const c1 = await page.evaluate(() => (window as unknown as { __psb: { map: L.Map } }).__psb.map.getCenter());
  await page.locator('.pm-marker[data-gid="contoh:desa/sumberbrantas"]').click();
  await expect(page.locator(".panel .ptitle")).toHaveText("Desa Sumberbrantas");
  await page.waitForTimeout(700);
  const c2 = await page.evaluate(() => (window as unknown as { __psb: { map: L.Map } }).__psb.map.getCenter());
  expect(await zoom(page)).toBe(z1);
  expect(Math.abs(c1.lat - c2.lat) + Math.abs(c1.lng - c2.lng)).toBeLessThan(1e-6);
  await expect(kpi(page, "Laporan")).toHaveText("4");
  await expect(kpi(page, "Tweet unik")).toHaveText("3"); // satu tweet melaporkan dua laporan
  await expect(page.locator(".evgroup")).toHaveCount(3);
  await expect(page.locator(".tweet")).toHaveCount(3);
  await expect(page.locator(".tweet").first()).toContainText("Tautan sumber tidak tersedia");
  await page.locator(".psec--fold > summary").click(); // bukti tweet bisa dilipat dan dibuka lagi
  await expect(page.locator(".tweet").first()).toBeHidden();
  await page.locator(".psec--fold > summary").click();
  await expect(page.locator(".tweet").first()).toBeVisible();
});

test("6. kartu kejadian: klik menyorot, klik lagi melepas, pindah kartu memindah sorotan", async ({ page }) => {
  await open(page);
  await enterKab(page, "3579", "Kota Batu");
  await expect(page.locator(".card .sorot, .card button", { hasText: /^Sorot$/ })).toHaveCount(0);
  const de06 = page.locator('.card[data-event="DE06"]');
  await de06.locator(".card-meta").click();
  await expect(de06).toHaveClass(/is-sorot/);
  await expect(de06.locator(".card-hit")).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator('.pm-marker.is-sorot[data-gid="contoh:desa/sumberbrantas"]')).toHaveCount(1);
  await expect(page.locator('.pm-marker.is-redup[data-gid="contoh:desa/bulukerto"]')).toHaveCount(1);
  await page.locator('.card[data-event="DE08"] .card-meta').click();
  await expect(de06).not.toHaveClass(/is-sorot/);
  await expect(page.locator(".pm-marker.is-sorot")).toHaveCount(2);
  await page.locator('.card[data-event="DE08"] .card-meta').click();
  await expect(page.locator(".pm-marker.is-redup, .pm-marker.is-sorot")).toHaveCount(0);
  // papan ketik: Enter pada judul kartu
  await de06.locator(".card-hit").focus();
  await page.keyboard.press("Enter");
  await expect(de06).toHaveClass(/is-sorot/);
  // sorotan yang hilang karena filter dihapus dengan rapi
  await page.locator('.chip[data-jenis="longsor"]').click();
  await expect(de06).toHaveCount(0);
  await expect(page.locator(".pm-marker.is-redup")).toHaveCount(0);
});

test("7. filter jenis konsisten di peta & panel; dropdown = klik peta", async ({ page }) => {
  await open(page);
  await page.locator(".chip--all").click();
  await expect(page.locator(".map-empty")).toBeHidden(); // panel terbuka sudah menampilkan pesan
  await expect(page.locator(".panel")).toContainText("Belum ada jenis bencana yang dipilih");
  await expect(kpi(page, "Kejadian bencana")).toHaveText("0");
  await page.locator('.chip[data-jenis="banjir"]').click();
  await expect(kpi(page, "Kejadian bencana")).toHaveText("6");
  await expect(kabPath(page, "3507")).toHaveAttribute("data-k", "0");
  await expect(kabPath(page, "3514")).toHaveAttribute("data-n", "2");
  const input = page.getByRole("combobox", { name: "Kabupaten/kota" });
  await input.fill("lumaj");
  await expect(page.getByRole("option").nth(1)).toContainText("Kab. Lumajang");
  await input.press("Enter");
  await expect(current(page)).toHaveText("Kab. Lumajang");
  await expect.poll(() => lokasiUnik(page)).toBe(3);
  await expect(page.locator(".card")).toHaveCount(1);
  await page.locator('.chip[data-jenis="erupsi"]').click();
  await expect(page.locator(".card")).toHaveCount(2);
  await expect.poll(() => lokasiUnik(page)).toBe(5);
  await expect(current(page)).toHaveText("Kab. Lumajang");
});

test("8. rentang tanggal atas & linimasa tersinkron; semantik irisan", async ({ page }) => {
  await open(page);
  await page.locator(".dr-trigger").click();
  await page.locator('.seg-btn[data-preset="7"]').click(); // 12–18 Mar 2026
  await expect(kpi(page, "Kejadian bencana")).toHaveText("2");
  await expect(page.locator(".dr-label")).toHaveText("12 – 18 Mar 2026");
  await expect(page.locator(".tl-range")).toHaveText("12 – 18 Mar 2026");
  await expect(page.locator(".tl-week.is-out").first()).toBeVisible();
  await page.locator("#dr-dari").fill("2026-01-13");
  await page.locator("#dr-sampai").fill("2026-01-13");
  await page.locator("#dr-sampai").dispatchEvent("change");
  await expect(kpi(page, "Kejadian bencana")).toHaveText("2"); // DE01 & DE03 beririsan
  await expect(kpi(page, "Tweet sumber unik")).toHaveText("0");
  await page.keyboard.press("Escape");
  await expect(page.locator(".dr-pop")).toBeHidden();
  // linimasa (papan ketik) mengubah rentang yang sama
  await page.locator('.tl-handle[data-side="b"]').focus();
  await page.keyboard.press("End");
  await expect(page.locator("#dr-sampai")).toHaveValue("2026-03-18");
  await expect(page.locator(".dr-label")).toHaveText("13 Jan – 18 Mar 2026");
  await clickKab(page, "3508");
  await expect(page.locator(".panel .ptitle")).toHaveText("Kab. Lumajang");
  await page.locator(".dr-trigger").click();
  await page.locator('.seg-btn[data-preset="all"]').click();
  await expect(page.locator(".dr-trigger")).not.toHaveClass(/is-active/);
  await expect.poll(() => lokasiUnik(page)).toBe(5);
});

test("9. panel, legenda, linimasa dapat diminimalkan; pilihan & filter tetap", async ({ page }) => {
  await open(page);
  await enterKab(page, "3508", "Kab. Lumajang");
  await page.locator('.card[data-event="DE01"] .card-meta').click();
  await page.locator(".panel-min").click();
  await expect(page.locator(".workspace")).toHaveClass(/panel-collapsed/);
  await expect(page.locator(".panel-tab")).toBeVisible();
  await expect(page.locator(".panel-tab")).toContainText("Kab. Lumajang");
  await page.locator(".lg-min").click();
  await expect(page.locator(".lg-pill")).toBeVisible();
  await page.locator(".timeline .icon-btn").click();
  await expect(page.locator(".tl-pill")).toBeVisible();
  // peta tetap dapat dipakai saat semua panel diminimalkan
  await enterKab(page, "3507", "Kab. Malang");
  await enterKab(page, "3508", "Kab. Lumajang");
  await page.locator(".panel-tab").click();
  await expect(page.locator(".workspace")).not.toHaveClass(/panel-collapsed/);
  await expect(page.locator(".panel .ptitle")).toHaveText("Kab. Lumajang");
  await page.locator(".lg-pill").click();
  await expect(page.locator(".legend")).toBeVisible();
  await page.locator(".tl-pill").click();
  await expect(page.locator(".timeline")).toBeVisible();
  // memilih lokasi saat panel diminimalkan membuka rinciannya lagi
  await page.locator(".panel-min").click();
  await page.locator('.card[data-event="DE01"] .linkish', { hasText: "Gunung Semeru" }).evaluate((b: HTMLElement) => b.click());
  await expect(page.locator(".workspace")).not.toHaveClass(/panel-collapsed/);
  await expect(page.locator(".panel .ptitle")).toHaveText("Gunung Semeru");
});

test("10. rujukan lintas kab & dampak tanpa atribusi tetap benar", async ({ page }) => {
  await open(page);
  await enterKab(page, "3507", "Kab. Malang");
  await page.locator('.card[data-event="DE03"] .linkish', { hasText: "Gunung Semeru" }).click();
  await expect(page.locator(".panel .ptitle")).toHaveText("Gunung Semeru");
  const semeru = page.locator('.pm-marker[data-gid="contoh:gunung/semeru"]');
  await expect(semeru.locator(".pm-mk")).toHaveClass(/is-luar/);
  await expect(semeru).toHaveClass(/is-selected/);
  await expect(page.locator(".panel .note--ref")).toContainText("Lokasi berada di Kab. Lumajang, tetapi dirujuk dalam laporan terkait Kab. Malang.");
  await expect(page.locator(".panel .peyebrow--ref")).toHaveText("Lokasi rujukan");
  await expect(page.locator(".evgroup")).toHaveCount(2);
  await page.locator(".back").click();
  await page.locator('.card[data-event="DE05"] .linkish', { hasText: "Desa Kalirejo" }).click();
  const g = page.locator('.evgroup[data-event="DE05"]');
  await expect(g.locator(".fblock", { hasText: "Dampak di lokasi ini" })).toContainText("Belum ada dampak yang dilaporkan di lokasi ini");
  const ev = g.locator(".fblock", { hasText: "Dampak tingkat kejadian" });
  await expect(ev.locator(".fact-what")).toHaveText("rumah rusak");
  await expect(ev.locator(".fact-qty")).toHaveText("12 unit");
  await expect(g.locator(".fblock", { hasText: "Kebutuhan tingkat kejadian" })).toContainText("terpal");
  await page.getByRole("button", { name: "Kembali ke peta nasional" }).click();
  await expect(current(page)).toHaveText("Indonesia");
});

test("11. klik cepat berulang tidak merusak pilihan", async ({ page }) => {
  await open(page);
  for (const k of ["3508", "3507", "3514", "3579"]) await clickKab(page, k);
  await expect(current(page)).toHaveText("Kota Batu");
  await expect.poll(() => lokasiUnik(page)).toBe(2);
  await expect(page.locator("path.kab.is-selected")).toHaveCount(1);
  await expect(kabPath(page, "3579")).toHaveClass(/is-selected/);
  for (const j of ["banjir", "longsor", "cuaca", "banjir", "gempa", "erupsi", "longsor"]) await page.locator(`.chip[data-jenis="${j}"]`).click();
  await expect(page.locator('.chip[aria-pressed="true"]:not(.chip--all)')).toHaveCount(3);
  const expected = await page.evaluate(async () => (await (await fetch("/api/kab/3579/kejadian?jenis=banjir,karhutla,longsor")).json()).kejadian.length);
  await expect(page.locator(".card")).toHaveCount(expected);
});

test("12. papan ketik pada penanda", async ({ page }) => {
  await open(page);
  await enterKab(page, "3579", "Kota Batu");
  const mk = page.locator('.pm-marker[data-gid="contoh:desa/bulukerto"]');
  await mk.focus();
  await expect(page.locator(".maptip")).toContainText("Desa Bulukerto");
  await page.keyboard.press("Enter");
  await expect(page.locator(".panel .ptitle")).toHaveText("Desa Bulukerto");
  await page.keyboard.press("Escape");
  await expect(page.locator(".panel .ptitle")).toHaveText("Kota Batu");
});

for (const [w, hgt] of [[1440, 900], [1024, 768], [768, 1024], [390, 844]] as const) {
  test(`tata letak ${w}px: peta penuh, tanpa luapan horizontal`, async ({ page }) => {
    await page.setViewportSize({ width: w, height: hgt });
    await open(page);
    await enterKab(page, "3508", "Kab. Lumajang");
    expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(0);
    const box = (await page.locator("#map").boundingBox())!;
    expect(box.width).toBeGreaterThanOrEqual(w - 1); // peta selebar layar; panel mengambang di atasnya
    expect(box.height).toBeGreaterThan(hgt * 0.8);
    const tb = (await page.locator(".toolbar").boundingBox())!;
    expect(tb.x + tb.width).toBeLessThanOrEqual(w);
  });
}

test("mode gerak dikurangi tetap berfungsi", async ({ browser }) => {
  const ctx = await browser.newContext({ reducedMotion: "reduce", viewport: { width: 1280, height: 800 } });
  const page = await ctx.newPage();
  await open(page);
  await enterKab(page, "3579", "Kota Batu");
  await expect.poll(() => lokasiUnik(page)).toBe(2);
  await ctx.close();
});
