import { expect, test, type Page } from "@playwright/test";

const PNG = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=", "base64");

async function open(page: Page, errors: string[] = []) {
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  // tile OSM diganti piksel kosong: uji tidak bergantung jaringan luar
  await page.route(/tile\.openstreetmap\.org/, (r) => r.fulfill({ body: PNG, contentType: "image/png" }));
  await page.goto("/");
  await expect(page.locator("body")).toHaveAttribute("data-ready", "true");
}

const stat = (page: Page, label: string) =>
  page.locator(".panel .stat").filter({ has: page.locator(".stat-l", { hasText: new RegExp(`^${label}$`) }) }).locator(".stat-v");
const kabPath = (page: Page, kode: string) => page.locator(`path.kab[data-kode="${kode}"]`);
const clickKab = (page: Page, kode: string) => kabPath(page, kode).dispatchEvent("click");
const markers = (page: Page) => page.locator(".leaflet-marker-icon.pm-marker");
/** Lokasi unik yang tampil = penanda tunggal + isi klaster (klaster hanya untuk tampilan). */
const lokasiUnik = (page: Page) => page.evaluate(() =>
  document.querySelectorAll(".leaflet-marker-icon.pm-marker").length +
  [...document.querySelectorAll(".pm-cluster")].reduce((a, c) => a + parseInt(c.textContent ?? "0", 10), 0));

async function enterKab(page: Page, kode: string, nama: string) {
  await clickKab(page, kode);
  await expect(page.locator(".crumbs [aria-current=page]")).toHaveText(nama);
  await expect(page.locator(".panel .ptitle")).toHaveText(nama);
  await expect.poll(() => lokasiUnik(page)).toBeGreaterThan(0);
}

test("1. tampilan awal: semua kab/kota, choropleth benar, tanpa penanda", async ({ page }) => {
  const errors: string[] = [];
  await open(page, errors);
  await expect(page.locator("path.kab")).toHaveCount(514);
  await expect(page.locator('path.kab:not([data-k="na"])')).toHaveCount(7);
  const n = await page.locator('path.kab:not([data-k="na"])').evaluateAll((els) =>
    Object.fromEntries(els.map((e) => [e.getAttribute("data-kode"), Number(e.getAttribute("data-n"))])));
  expect(n).toEqual({ "3507": 3, "3508": 2, "3509": 2, "3513": 1, "3514": 3, "3515": 1, "3579": 3 });
  await expect(stat(page, "Kejadian bencana")).toHaveText("15");
  await expect(stat(page, "Tweet sumber unik")).toHaveText("31");
  await expect(stat(page, "Kab/kota")).toHaveText("7");
  await expect(markers(page)).toHaveCount(0);
  await expect(page.locator(".badge-contoh")).toHaveText("Data Contoh");
  expect(errors).toEqual([]);
});

test("2. klik kab/kota: zoom, breadcrumb, penanda, kartu kejadian", async ({ page }) => {
  await open(page);
  const w0 = (await kabPath(page, "3508").boundingBox())!.width;
  await enterKab(page, "3508", "Kab. Lumajang");
  await expect.poll(() => lokasiUnik(page)).toBe(5);
  await expect(page.locator(".card")).toHaveCount(2);
  await expect(kabPath(page, "3508")).toHaveClass(/is-selected/);
  expect((await kabPath(page, "3508").boundingBox())!.width).toBeGreaterThan(w0 * 3); // kamera memperbesar ke kab
  const card = page.locator('.card[data-event="DE01"]');
  await expect(card).toContainText("Memenuhi ambang bencana");
  await expect(card).toContainText("Laporan terakhir");
  await expect(card).toContainText("27 Jan 2026");
});

test("3. hover penanda menampilkan ringkasan; klik membuka bukti tweet", async ({ page }) => {
  await open(page);
  await enterKab(page, "3579", "Kota Batu");
  const sb = page.locator('.pm-marker[data-gid="contoh:desa/sumberbrantas"]');
  await sb.hover();
  const tip = page.locator(".leaflet-tooltip.pm-tip").last();
  await expect(tip).toContainText("Desa Sumberbrantas");
  await expect(tip).toContainText("Laporan kejadian");
  await expect(tip).toContainText("4");
  await sb.click();
  await expect(page.locator(".panel .ptitle")).toHaveText("Desa Sumberbrantas");
  await expect(stat(page, "Laporan")).toHaveText("4");
  await expect(stat(page, "Tweet unik")).toHaveText("3"); // satu tweet melaporkan dua laporan
  await expect(page.locator(".evgroup")).toHaveCount(3);
  await expect(page.locator(".tweet")).toHaveCount(3);
  await expect(page.locator(".tweet").first()).toContainText("Tautan sumber tidak tersedia");
  await expect(sb).toHaveClass(/is-selected/);
});

test("4. filter jenis memperbarui peta dan panel secara konsisten", async ({ page }) => {
  await open(page);
  await page.getByRole("button", { name: "Semua jenis" }).click();
  await expect(page.locator(".map-empty")).toContainText("Belum ada jenis bencana yang dipilih");
  await expect(stat(page, "Kejadian bencana")).toHaveText("0");
  await page.locator('.chip[data-jenis="banjir"]').click();
  await expect(stat(page, "Kejadian bencana")).toHaveText("6");
  await expect(page.locator(".map-empty")).toBeHidden();
  await expect(kabPath(page, "3507")).toHaveAttribute("data-k", "0"); // ada di cakupan, 0 sesuai filter
  await expect(kabPath(page, "3514")).toHaveAttribute("data-n", "2");
  await enterKab(page, "3508", "Kab. Lumajang");
  await expect.poll(() => lokasiUnik(page)).toBe(3);
  await expect(page.locator(".card")).toHaveCount(1);
  await page.locator('.chip[data-jenis="erupsi"]').click();
  await expect(page.locator(".card")).toHaveCount(2);
  await expect.poll(() => lokasiUnik(page)).toBe(5);
  await expect(page.locator(".crumbs [aria-current=page]")).toHaveText("Kab. Lumajang"); // cakupan dipertahankan
});

test("5. memilih dari dropdown = mengklik peta", async ({ page }) => {
  await open(page);
  const input = page.getByRole("combobox", { name: "Kabupaten/kota" });
  await input.fill("lumaj");
  await expect(page.getByRole("option").nth(1)).toContainText("Kab. Lumajang");
  await input.press("Enter");
  await expect(page.locator(".crumbs [aria-current=page]")).toHaveText("Kab. Lumajang");
  await expect.poll(() => lokasiUnik(page)).toBe(5);
  await expect(page.locator(".card")).toHaveCount(2);
  await expect(kabPath(page, "3508")).toHaveClass(/is-selected/);
});

test("6. filter tanggal & rentang cepat: semantik irisan kejadian vs tanggal laporan", async ({ page }) => {
  await open(page);
  await page.getByRole("button", { name: "7 hari" }).click(); // 12–18 Mar 2026
  await expect(stat(page, "Kejadian bencana")).toHaveText("2");
  await expect(page.locator('path.kab:not([data-k="na"]):not([data-k="0"])')).toHaveCount(1);
  await expect(page.locator("#tl-dari")).toHaveValue("2026-03-12");
  await expect(page.locator(".tl-week.is-out").first()).toBeVisible();
  await page.locator("#tl-dari").fill("2026-01-13");
  await page.locator("#tl-sampai").fill("2026-01-13");
  await page.locator("#tl-sampai").dispatchEvent("change");
  await expect(stat(page, "Kejadian bencana")).toHaveText("2"); // DE01 & DE03 beririsan
  await expect(stat(page, "Tweet sumber unik")).toHaveText("0"); // tidak ada laporan bertanggal 13 Jan
  await clickKab(page, "3508");
  await expect(page.locator(".panel .ptitle")).toHaveText("Kab. Lumajang");
  await expect(page.locator(".card")).toHaveCount(1);
  await expect(page.locator(".card")).toContainText("dari 5 laporan sepanjang data");
  await expect.poll(() => lokasiUnik(page)).toBe(0);
  await page.getByRole("button", { name: "Semua" , exact: true }).click();
  await expect.poll(() => lokasiUnik(page)).toBe(5);
});

test("7. sorot, kembali, rujukan lintas kab, dampak tanpa atribusi", async ({ page }) => {
  await open(page);
  await enterKab(page, "3579", "Kota Batu");
  const sorot = page.locator('.card[data-event="DE06"] .sorot');
  await sorot.click();
  await expect(sorot).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator('.pm-marker.is-sorot[data-gid="contoh:desa/sumberbrantas"]')).toHaveCount(1);
  await expect(page.locator('.pm-marker.is-redup[data-gid="contoh:desa/bulukerto"]')).toHaveCount(1);
  await expect(page.locator('.card[data-event="DE07"]')).toHaveClass(/is-redup/);
  await sorot.click();
  await expect(page.locator(".pm-marker.is-redup")).toHaveCount(0);
  // sorotan yang hilang karena filter dihapus dengan rapi
  await sorot.click();
  await page.locator('.chip[data-jenis="longsor"]').click();
  await expect(page.locator('.card[data-event="DE06"]')).toHaveCount(0);
  await expect(page.locator(".pm-marker.is-redup")).toHaveCount(0);
  await page.locator('.chip[data-jenis="longsor"]').click();
  await page.getByRole("button", { name: "Kembali ke peta nasional" }).click();
  await expect.poll(() => lokasiUnik(page)).toBe(0);
  await expect(page.locator(".panel .ptitle")).toHaveText("Sebaran kejadian bencana");
  await enterKab(page, "3507", "Kab. Malang");
  await page.locator('.card[data-event="DE03"] .linkish', { hasText: "Gunung Semeru" }).click();
  await expect(page.locator(".panel .ptitle")).toHaveText("Gunung Semeru");
  const semeru = page.locator('.pm-marker[data-gid="contoh:gunung/semeru"]');
  await expect(semeru.locator(".pm-mk")).toHaveClass(/is-luar/);
  await expect(semeru).toHaveClass(/is-selected/);
  await expect(page.locator(".note")).toContainText("wilayah administratif lain");
  await expect(page.locator(".evgroup")).toHaveCount(2); // kejadian Lumajang & Malang
  await page.locator(".back").click();
  await page.locator('.card[data-event="DE05"] .linkish', { hasText: "Desa Kalirejo" }).click();
  await expect(page.getByText("Tidak ada dampak yang tertaut ke lokasi ini")).toBeVisible();
  const lvl = page.locator(".psec").filter({ hasText: "Dampak tingkat kejadian" });
  await expect(lvl).toContainText("rumah rusak — 12 unit");
});

test("perubahan filter cepat tidak menghasilkan keadaan usang", async ({ page }) => {
  await open(page);
  for (const j of ["banjir", "longsor", "cuaca", "banjir", "gempa", "erupsi", "longsor"]) await page.locator(`.chip[data-jenis="${j}"]`).click();
  // akhir: banjir & longsor tetap aktif? (toggle: banjir 2x, longsor 2x -> aktif; cuaca/gempa/erupsi 1x -> nonaktif)
  await expect(page.locator('.chip[aria-pressed="true"]:not(.chip--all)')).toHaveCount(3);
  const expected = await page.evaluate(async () => (await (await fetch("/api/kab-agregat?jenis=banjir,karhutla,longsor")).json()).ringkasan.jumlah_kejadian);
  await expect(stat(page, "Kejadian bencana")).toHaveText(String(expected));
});

test("navigasi papan ketik pada penanda dan rentang", async ({ page }) => {
  await open(page);
  await enterKab(page, "3579", "Kota Batu");
  const mk = page.locator('.pm-marker[data-gid="contoh:desa/bulukerto"]');
  await mk.focus();
  await expect(page.locator(".leaflet-tooltip.pm-tip").last()).toContainText("Desa Bulukerto");
  await page.keyboard.press("Enter");
  await expect(page.locator(".panel .ptitle")).toHaveText("Desa Bulukerto");
  await page.keyboard.press("Escape");
  await expect(page.locator(".panel .ptitle")).toHaveText("Kota Batu");
  await page.locator('.tl-handle[data-side="b"]').focus();
  await page.keyboard.press("Home");
  await expect(page.locator("#tl-sampai")).toHaveValue("2026-01-08");
});

for (const w of [1440, 1024, 768, 390]) {
  test(`tata letak responsif ${w}px tanpa luapan horizontal`, async ({ page }) => {
    await page.setViewportSize({ width: w, height: w < 500 ? 844 : 900 });
    await open(page);
    await enterKab(page, "3508", "Kab. Lumajang");
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(0);
    await expect(page.locator("#map")).toBeVisible();
    const box = await page.locator("#map").boundingBox();
    expect(box!.height).toBeGreaterThan(300);
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
