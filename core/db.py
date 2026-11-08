"""
SQLite storage for things users create: monthly targets and saved forecast runs.

One short-lived connection per call (Streamlit reruns scripts on many threads,
so a module-level connection isn't safe).
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).resolve().parent.parent / "database" / "insightsphere.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS targets (
    dataset_digest TEXT NOT NULL,
    month TEXT NOT NULL,              -- YYYY-MM
    revenue_target REAL NOT NULL,
    PRIMARY KEY (dataset_digest, month)
);
CREATE TABLE IF NOT EXISTS forecast_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    dataset_name TEXT NOT NULL,
    dataset_digest TEXT NOT NULL,
    metric TEXT NOT NULL,
    grain TEXT NOT NULL,
    horizon INTEGER NOT NULL,
    model TEXT NOT NULL,
    mape REAL,
    params_json TEXT NOT NULL,
    results_json TEXT NOT NULL
);
"""


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.executescript(SCHEMA)
    return conn


# ----------------------------------------------------------
# Targets
# ----------------------------------------------------------

def load_targets(digest: str, path: Path = DB_PATH) -> pd.DataFrame:
    with closing(connect(path)) as conn:
        return pd.read_sql_query(
            "SELECT month, revenue_target FROM targets WHERE dataset_digest = ? ORDER BY month",
            conn, params=(digest,),
        )


def save_targets(digest: str, targets: pd.DataFrame, path: Path = DB_PATH) -> None:
    rows = [
        (digest, str(r.month), float(r.revenue_target))
        for r in targets.itertuples(index=False)
        if pd.notna(r.revenue_target)
    ]
    with closing(connect(path)) as conn, conn:
        conn.execute("DELETE FROM targets WHERE dataset_digest = ?", (digest,))
        conn.executemany("INSERT INTO targets VALUES (?, ?, ?)", rows)


# ----------------------------------------------------------
# Forecast runs
# ----------------------------------------------------------

def save_run(*, dataset_name: str, dataset_digest: str, metric: str, grain: str,
             horizon: int, model: str, mape: float | None, params: dict,
             results: dict, path: Path = DB_PATH) -> int:
    with closing(connect(path)) as conn, conn:
        cur = conn.execute(
            "INSERT INTO forecast_runs (created_at, dataset_name, dataset_digest, metric, grain,"
            " horizon, model, mape, params_json, results_json) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (datetime.now().isoformat(timespec="seconds"), dataset_name, dataset_digest, metric,
             grain, horizon, model, mape, json.dumps(params), json.dumps(results)),
        )
        return int(cur.lastrowid)


def list_runs(path: Path = DB_PATH) -> pd.DataFrame:
    with closing(connect(path)) as conn:
        return pd.read_sql_query(
            "SELECT id, created_at, dataset_name, metric, grain, horizon, model, mape"
            " FROM forecast_runs ORDER BY created_at DESC, id DESC",
            conn,
        )


def get_run(run_id: int, path: Path = DB_PATH) -> dict | None:
    with closing(connect(path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM forecast_runs WHERE id = ?", (run_id,)).fetchone()
    if row is None:
        return None
    out = dict(row)
    out["params"] = json.loads(out.pop("params_json"))
    out["results"] = json.loads(out.pop("results_json"))
    return out


def delete_runs(run_ids, path: Path = DB_PATH) -> None:
    ids = [int(i) for i in run_ids]
    if not ids:
        return
    with closing(connect(path)) as conn, conn:
        conn.executemany("DELETE FROM forecast_runs WHERE id = ?", [(i,) for i in ids])
