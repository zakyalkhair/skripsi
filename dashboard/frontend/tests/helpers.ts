import { expect, type Page } from "@playwright/test";

export const PNG = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=", "base64");

export interface OpenOpts { path?: string; tiles?: "cors" | "tanpa-cors" }
/** Buka dasbor. Ubin OSM diganti piksel kosong (uji tidak bergantung jaringan luar); "tanpa-cors" meniru
 * server ubin yang menolak permintaan fetch lintas-origin (gambar <img> tetap tampil). */
export async function open(page: Page, errors: string[] = [], o: OpenOpts = {}) {
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  await page.route(/tile\.openstreetmap\.org/, (r) => (o.tiles === "tanpa-cors" && r.request().resourceType() === "fetch"
    ? r.abort("accessdenied")
    : r.fulfill({ body: PNG, contentType: "image/png", headers: { "Access-Control-Allow-Origin": "*" } })));
  await page.goto(o.path ?? "/");
  await expect(page.locator("body")).toHaveAttribute("data-ready", "true");
}

export const kpi = (page: Page, label: string) =>
  page.locator(".panel .kpi").filter({ has: page.locator(".kpi-l", { hasText: new RegExp(`^${label}$`) }) }).locator(".kpi-v");
export const kabPath = (page: Page, kode: string) => page.locator(`path.kab[data-kode="${kode}"]`);
export const clickKab = (page: Page, kode: string) => kabPath(page, kode).dispatchEvent("click");
export const markers = (page: Page) => page.locator(".leaflet-marker-icon.pm-marker");
export const current = (page: Page) => page.locator(".crumbs [aria-current=page]");
/** Lokasi unik yang tampil = penanda tunggal + isi klaster (klaster hanya untuk tampilan). */
export const lokasiUnik = (page: Page) => page.evaluate(() =>
  document.querySelectorAll(".leaflet-marker-icon.pm-marker").length +
  [...document.querySelectorAll(".pm-cluster b")].reduce((a, c) => a + parseInt(c.textContent ?? "0", 10), 0));
/** Titik layar (halaman) untuk koordinat geografis, lewat peta Leaflet (mode dev). */
export const screenOf = (page: Page, lat: number, lng: number) => page.evaluate(([la, ln]) => {
  const m = (window as unknown as { __psb: { map: L.Map } }).__psb.map;
  const p = m.latLngToContainerPoint([la, ln]);
  const r = m.getContainer().getBoundingClientRect();
  return { x: r.left + p.x, y: r.top + p.y };
}, [lat, lng]);
export const zoom = (page: Page) => page.evaluate(() => (window as unknown as { __psb: { map: L.Map } }).__psb.map.getZoom());
/** Tunggu kamera benar-benar diam: tidak ada gerak yang sedang berjalan (movestart tanpa moveend) dan
 * zoom & pusat tidak berubah selama dua pemeriksaan berturut-turut. */
export async function settle(page: Page) {
  let prev = "";
  for (let i = 0; i < 60; i++) {
    const cur = await page.evaluate(() => {
      const p = (window as unknown as { __psb: { map: L.Map; view: { isMoving: boolean } } }).__psb;
      const c = p.map.getCenter();
      return p.view.isMoving ? `bergerak:${performance.now()}` : `${p.map.getZoom()}|${c.lat.toFixed(7)}|${c.lng.toFixed(7)}`;
    });
    if (cur === prev) return;
    prev = cur;
    await page.waitForTimeout(160);
  }
}

export async function enterKab(page: Page, kode: string, nama: string) {
  await clickKab(page, kode);
  await expect(current(page)).toHaveText(nama);
  await expect(page.locator(".panel .ptitle")).toHaveText(nama);
  await expect.poll(() => lokasiUnik(page)).toBeGreaterThan(0);
}
