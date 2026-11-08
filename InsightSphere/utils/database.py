import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime

# ==========================================================
# DATABASE CONNECTION
# ==========================================================

BASE_DIR = Path(__file__).resolve().parent.parent
DB_FOLDER = BASE_DIR / "database"
DB_FOLDER.mkdir(exist_ok=True)
DB_PATH = DB_FOLDER / "prediction_history.db"


def get_connection():
    return sqlite3.connect(str(DB_PATH))


# ==========================================================
# CREATE TABLE (+ safe migration for dataset_filename)
# ==========================================================

def create_table():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS prediction_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prediction_time TEXT,
            category TEXT,
            sub_category TEXT,
            region TEXT,
            state TEXT,
            segment TEXT,
            quantity INTEGER,
            discount REAL,
            expected_profit REAL,
            predicted_sales REAL,
            revenue_level TEXT
        )
        """
    )
    conn.commit()

    # ---- Safe, additive migration: add dataset_filename if missing ----
    # Never drops or rebuilds the table -- only ALTER TABLE ADD COLUMN,
    # which SQLite supports without touching existing rows.
    cursor.execute("PRAGMA table_info(prediction_history)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    if "dataset_filename" not in existing_columns:
        cursor.execute(
            "ALTER TABLE prediction_history ADD COLUMN dataset_filename TEXT"
        )
        conn.commit()

    conn.close()


# ==========================================================
# SAVE PREDICTION
# ==========================================================

def save_prediction(
    category,
    sub_category,
    region,
    state,
    segment,
    quantity,
    discount,
    expected_profit,
    predicted_sales,
    revenue_level,
    dataset_filename=None,
):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO prediction_history(
            prediction_time, category, sub_category, region, state, segment,
            quantity, discount, expected_profit, predicted_sales, revenue_level,
            dataset_filename
        )
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            category,
            sub_category,
            region,
            state,
            segment,
            quantity,
            discount,
            expected_profit,
            predicted_sales,
            revenue_level,
            dataset_filename,
        )
    )

    conn.commit()
    conn.close()


# ==========================================================
# LOAD HISTORY
# ==========================================================

def load_history():
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM prediction_history ORDER BY id DESC", conn)
    conn.close()
    return df


# ==========================================================
# DELETE HISTORY
# ==========================================================

def clear_history():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM prediction_history")
    conn.commit()
    conn.close()