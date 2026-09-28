import shutil
from pathlib import Path

import pandas as pd
import pytest

from modul1.io_utils import PROJECT_ROOT, load_config


@pytest.fixture
def cfg(tmp_path):
    """Config proyek dengan semua keluaran diarahkan ke folder sementara."""
    return load_config(PROJECT_ROOT / "config.yaml", tmp_path)


def make_df(rows: list[dict]) -> pd.DataFrame:
    """DataFrame minimal berformat keluaran 1.2 untuk test dedup."""
    base = {"text": "", "lang": "in", "hashtags": [], "urls": [], "is_reply": False, "coordinates": None,
            "query_id": ["q1"], "event_id": ["GP07"], "user_hash": None, "too_short": False, "drop_reason": None}
    out = []
    for r in rows:
        d = base | r
        d.setdefault("text_raw", d["text_clean"])
        out.append(d)
    df = pd.DataFrame(out)
    df["created_at"] = pd.to_datetime(df["created_at"], utc=True)
    return df
