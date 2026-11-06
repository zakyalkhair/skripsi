import { ApiError } from "../api";

/** Simpan Blob sebagai berkas unduhan (tanpa membuka jendela baru). */
export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.rel = "noopener";
  a.hidden = true;
  document.body.append(a);
  a.click();
  a.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 5000);
}

/**
 * Unduh arsip ekspor data (ZIP: CSV ternormalisasi + manifest.json) dari backend.
 * Data berasal dari endpoint /api/ekspor dengan filter & cakupan yang sama dengan tampilan;
 * frontend tidak menyusun atau mengubah isi CSV.
 */
export async function downloadData(url: string): Promise<{ filename: string; size: number }> {
  const r = await fetch(url, { headers: { Accept: "application/zip" } });
  if (!r.ok) {
    let msg = r.statusText || "Ekspor gagal";
    try { msg = (await r.json()).detail ?? msg; } catch { /* bukan JSON */ }
    throw new ApiError(r.status, msg);
  }
  const blob = await r.blob();
  const m = (r.headers.get("Content-Disposition") ?? "").match(/filename="?([^";]+)"?/);
  const filename = m ? m[1] : "peta-situasi-bencana.zip";
  saveBlob(blob, filename);
  return { filename, size: blob.size };
}
