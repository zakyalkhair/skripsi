"""Model graf dalam memori + filter. Tidak ada properti ontologi baru: field turunan
(kode_kab kejadian, tingkat lokasi) dihitung di adapter.py."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

JENIS = ("banjir", "longsor", "cuaca", "karhutla", "gempa", "erupsi")


@dataclass(frozen=True)
class Filter:
    jenis: frozenset[str] | None = None  # None = semua jenis; frozenset() = tidak ada yang dipilih
    dari: date | None = None
    sampai: date | None = None

    def jenis_ok(self, j: str) -> bool:
        return self.jenis is None or j in self.jenis

    def tanggal_ok(self, d: date) -> bool:
        return (self.dari is None or d >= self.dari) and (self.sampai is None or d <= self.sampai)

    def tumpang_tindih(self, mulai: date, akhir: date) -> bool:
        """Interval kejadian [mulai, akhir] beririsan dengan rentang filter."""
        return (self.sampai is None or mulai <= self.sampai) and (self.dari is None or akhir >= self.dari)

    def as_dict(self) -> dict:
        return {"jenis": sorted(self.jenis) if self.jenis is not None else None,
                "dari": self.dari.isoformat() if self.dari else None,
                "sampai": self.sampai.isoformat() if self.sampai else None}


@dataclass
class Graph:
    tweets: dict[str, dict] = field(default_factory=dict)
    mentions: dict[str, dict] = field(default_factory=dict)
    events: dict[str, dict] = field(default_factory=dict)
    locations: dict[str, dict] = field(default_factory=dict)
    affected: dict[str, dict] = field(default_factory=dict)
    needs: dict[str, dict] = field(default_factory=dict)
    orgs: dict[str, dict] = field(default_factory=dict)
    # relasi (arah lihat adapter.REL)
    m_tweets: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    m_event: dict[str, str] = field(default_factory=dict)
    m_locs: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    m_affected: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    m_needs: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    m_evac: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    ao_loc: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    loc_parent: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    org_handles: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    org_deployed: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    org_parent: dict[str, str] = field(default_factory=dict)
    gazetteer: dict[str, dict] = field(default_factory=dict)  # gazetteer lokal: tingkat, kode_kab
