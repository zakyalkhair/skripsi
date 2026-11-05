import type { Jenis } from "./types";
import { JENIS } from "./jenis";

export type View = "nasional" | "kab" | "lokasi";

export interface State {
  jenis: Set<Jenis>;
  dari: string | null; // null = awal data
  sampai: string | null; // null = akhir data
  kab: string | null;
  lokasi: string | null;
  sorot: string | null; // event_id yang disorot
}

type Listener = (s: State, prev: State) => void;

export class Store {
  private s: State = { jenis: new Set(JENIS), dari: null, sampai: null, kab: null, lokasi: null, sorot: null };
  private ls = new Set<Listener>();

  get state(): State { return this.s; }
  get view(): View { return this.s.lokasi ? "lokasi" : this.s.kab ? "kab" : "nasional"; }

  set(patch: Partial<State>): void {
    const prev = this.s;
    this.s = { ...prev, ...patch };
    for (const l of this.ls) l(this.s, prev);
  }

  on(l: Listener): () => void { this.ls.add(l); return () => this.ls.delete(l); }
}

export const filterKey = (s: State): string => `${[...s.jenis].sort().join(",")}|${s.dari ?? ""}|${s.sampai ?? ""}`;
export const isDefaultFilter = (s: State): boolean => s.jenis.size === JENIS.length && !s.dari && !s.sampai;
