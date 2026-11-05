const BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];

export const parseDate = (s: string): Date => new Date(`${s.slice(0, 10)}T00:00:00`);
export const iso = (d: Date): string =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
export const addDays = (s: string, n: number): string => {
  const d = parseDate(s);
  d.setDate(d.getDate() + n);
  return iso(d);
};

export function tgl(s: string | null | undefined, withYear = true): string {
  if (!s) return "Tidak tersedia";
  const d = parseDate(s);
  return `${d.getDate()} ${BULAN[d.getMonth()]}${withYear ? ` ${d.getFullYear()}` : ""}`;
}

export function rentang(a: string | null | undefined, b: string | null | undefined): string {
  if (!a || !b) return "Tidak tersedia";
  if (a === b) return tgl(a);
  const da = parseDate(a), db = parseDate(b);
  if (da.getFullYear() === db.getFullYear() && da.getMonth() === db.getMonth()) return `${da.getDate()} – ${tgl(b)}`;
  return `${tgl(a, da.getFullYear() !== db.getFullYear())} – ${tgl(b)}`;
}

export function waktu(s: string): string {
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return s;
  const off = s.match(/([+-]\d{2}):?(\d{2})$/);
  const hh = s.slice(11, 13), mm = s.slice(14, 16);
  const zona = off ? (off[1] === "+07" ? "WIB" : off[1] === "+08" ? "WITA" : off[1] === "+09" ? "WIT" : `UTC${off[1]}`) : "";
  return `${tgl(s.slice(0, 10))}, ${hh}.${mm} ${zona}`.trim();
}

export const angka = (n: number): string => n.toLocaleString("id-ID");
export const plural = (n: number, kata: string): string => `${angka(n)} ${kata}`;
