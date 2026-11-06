import type { Jenis } from "./types";

export const JENIS: Jenis[] = ["banjir", "longsor", "cuaca", "karhutla", "gempa", "erupsi"];

export const LABEL: Record<Jenis, string> = {
  banjir: "Banjir", longsor: "Tanah Longsor", cuaca: "Cuaca Ekstrem",
  karhutla: "Kebakaran Hutan dan Lahan", gempa: "Gempabumi", erupsi: "Erupsi Gunung Api",
};
export const LABEL_PENDEK: Record<Jenis, string> = {
  banjir: "Banjir", longsor: "Longsor", cuaca: "Cuaca ekstrem", karhutla: "Karhutla", gempa: "Gempabumi", erupsi: "Erupsi",
};

/** Warna kategorikal dibaca dari token CSS --j-* agar satu sumber kebenaran. */
export function warna(j: Jenis): string {
  return getComputedStyle(document.documentElement).getPropertyValue(`--j-${j}`).trim() || "#666";
}

export const STATUS_LABEL: Record<string, string> = {
  ya: "Memenuhi ambang bencana",
  tidak: "Belum memenuhi ambang bencana",
};
export const KEBUTUHAN_STATUS: Record<string, string> = { demanded: "Diminta", supplied: "Telah dipasok" };
export const TINGKAT_LABEL: Record<string, string> = {
  desa: "Desa/kelurahan", kecamatan: "Kecamatan", gunung: "Gunung", jembatan: "Jembatan", jalan: "Jalan",
  bangunan: "Bangunan", kabupaten: "Kabupaten/kota", "tidak diketahui": "Jenis lokasi tidak diketahui",
};
