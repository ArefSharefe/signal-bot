import sqlite3

DB_FILE = "signals.db"

def connect():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init():
    with connect() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT, side TEXT, strategy TEXT,
            entry REAL, stop REAL, tp REAL, leverage INTEGER,
            signal_time TEXT,
            status TEXT DEFAULT 'OPEN',
            result_pct REAL, closed_time TEXT
        )""")
        for col, typ in (
            ("ai_score", "INTEGER"), ("ai_reason", "TEXT"),
            ("score", "INTEGER"), ("timeframe", "TEXT DEFAULT '4h'"),
        ):
            try:
                c.execute(f"ALTER TABLE signals ADD COLUMN {col} {typ}")
            except sqlite3.OperationalError:
                pass
        c.execute("CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals(symbol)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_signals_status ON signals(status)")

def open_symbols():
    with connect() as c:
        rows = c.execute("SELECT symbol FROM signals WHERE status='OPEN'").fetchall()
    return {r["symbol"] for r in rows}

def get_open():
    with connect() as c:
        return c.execute("SELECT * FROM signals WHERE status='OPEN'").fetchall()

def recently_signaled(symbol, timeframe, hours=12):
    with connect() as c:
        row = c.execute(
            """SELECT 1 FROM signals
               WHERE symbol=? AND timeframe=?
                 AND datetime(signal_time) > datetime('now', ?)
               LIMIT 1""",
            (symbol, timeframe, f"-{hours} hours"),
        ).fetchone()
    return row is not None

def save_signal(s):
    with connect() as c:
        c.execute(
            """INSERT INTO signals
               (symbol, side, strategy, entry, stop, tp, leverage,
                signal_time, score, ai_score, ai_reason, timeframe)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                s["symbol"], s["side"], s["strategy"], s["entry"], s["stop"],
                s["tp"], s["leverage"], s["signal_time"], s.get("score"),
                s.get("ai_score"), s.get("ai_reason"), s.get("timeframe", "4h"),
            ),
        )

def close_signal(sig_id, status, result_pct, closed_time):
    with connect() as c:
        c.execute(
            "UPDATE signals SET status=?, result_pct=?, closed_time=? WHERE id=?",
            (status, result_pct, closed_time, sig_id),
        )

def stats_summary():
    with connect() as c:
        rows = c.execute("SELECT * FROM signals").fetchall()
    return rows