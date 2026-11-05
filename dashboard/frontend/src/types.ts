/** Kontrak respons API (sama untuk DATA_SOURCE=file dan neo4j). */
export type Jenis = "banjir" | "longsor" | "cuaca" | "karhutla" | "gempa" | "erupsi";

export interface LokRef { gazetteer_id: string; nama: string }

export interface Wilayah {
  provinsi: { kode_prov: string; nama: string }[];
  kab: { kode_kab: string; nama: string; kode_prov: string; provinsi: string; ada_data: boolean }[];
  dataset: { sumber: string; label: string; keterangan: string | null; contoh: boolean; rentang: { awal: string | null; akhir: string | null } };
}

export interface KabAgregat {
  kab: { kode_kab: string; jumlah_kejadian: number; jumlah_laporan: number; jumlah_tweet: number }[];
  ringkasan: { jumlah_kejadian: number; jumlah_laporan: number; jumlah_tweet: number; jumlah_kab: number };
}

export interface Dampak { id: string; kelas: string | null; status: string | null; jumlah: number | null; satuan: string | null; lokasi: LokRef[]; event_id: string | null }
export interface Kebutuhan { id: string; kategori: string | null; item: string | null; status: string | null; lokasi: LokRef | null; event_id: string | null }
export interface Lembaga { id: string; nama_kanonik: string | null; wilayah: string | null; tingkat: string | null; peran: string[]; induk: string | null }

export interface Kejadian {
  event_id: string; nama: string; jenis: Jenis; status: "ya" | "tidak" | string;
  start_time: string; end_time: string; kode_kab: string | null;
  jumlah_laporan_periode: number; jumlah_tweet_periode: number; jumlah_laporan_total: number; jumlah_tweet_total: number;
  lokasi_ids: string[]; lokasi: LokRef[]; dampak: Dampak[]; kebutuhan: Kebutuhan[]; lembaga: Lembaga[];
}
export interface KabKejadian { kode_kab: string; nama: string; kejadian: Kejadian[] }

export interface Titik {
  gazetteer_id: string; nama: string; tingkat: string; admin_path: string | null;
  latitude: number; longitude: number; kode_kab_lokasi: string | null; nama_kab_lokasi: string | null; di_luar_kab: boolean;
  jenis: Jenis[]; jumlah_laporan: number; event_ids: string[]; tanggal_awal: string | null; tanggal_akhir: string | null;
}
export interface KabTitik { kode_kab: string; titik: Titik[]; laporan_tanpa_titik: number }

export interface Ringkasan {
  lokasi: { gazetteer_id: string; nama: string; tingkat: string; admin_path: string | null; kode_kab_lokasi: string | null; latitude: number | null; longitude: number | null };
  jumlah_laporan: number; jumlah_tweet: number; tanggal_awal: string | null; tanggal_akhir: string | null; jenis: Jenis[];
  kejadian: { event_id: string; nama: string; jenis: Jenis; status: string; start_time: string; end_time: string; kode_kab: string | null; nama_kab: string | null;
    laporan: { mention_id: string; tanggal_lokal: string; jenis: Jenis; tweet_ids: string[] }[] }[];
  tweets: { tweet_id: string; upload: string; text: string | null; url: string | null; mention_ids: string[] }[];
  dampak_lokasi: Dampak[]; dampak_tanpa_lokasi: Dampak[]; kebutuhan_lokasi: Kebutuhan[]; kebutuhan_tanpa_lokasi: Kebutuhan[];
  lembaga: Lembaga[];
  evakuasi_ke_sini: { mention_id: string; event_id: string; asal: LokRef[] }[];
  evakuasi_dari_sini: { mention_id: string; tujuan: LokRef[] }[];
}

export interface Histogram { minggu: { mulai: string; total: number; per_jenis: Partial<Record<Jenis, number>> }[]; rentang: { awal: string | null; akhir: string | null } }
