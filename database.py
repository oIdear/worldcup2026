import sqlite3
import os
from config import DB_PATH, MODELS, INITIAL_BALANCE


def get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS matches (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        match_code    TEXT UNIQUE NOT NULL,
        home_team     TEXT NOT NULL,
        away_team     TEXT NOT NULL,
        kickoff_time  DATETIME NOT NULL,
        round         TEXT,
        home_odds     REAL,
        draw_odds     REAL,
        away_odds     REAL,
        result        TEXT,
        status        TEXT DEFAULT 'pending',
        created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS bets (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        match_code      TEXT NOT NULL,
        model_name      TEXT NOT NULL,
        bet_on          TEXT NOT NULL,
        amount          INTEGER NOT NULL,
        odds_at_bet     REAL NOT NULL,
        potential_return REAL NOT NULL,
        profit_loss     REAL DEFAULT 0,
        is_settled      INTEGER DEFAULT 0,
        created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(match_code, model_name)
    );

    CREATE TABLE IF NOT EXISTS balances (
        model_name              TEXT PRIMARY KEY,
        balance                 REAL DEFAULT 1000,
        total_bets              INTEGER DEFAULT 0,
        wins                    INTEGER DEFAULT 0,
        losses                  INTEGER DEFAULT 0,
        best_win                REAL DEFAULT 0,
        worst_loss              REAL DEFAULT 0,
        max_consecutive_wins    INTEGER DEFAULT 0,
        current_consecutive     INTEGER DEFAULT 0,
        is_eliminated           INTEGER DEFAULT 0,
        updated_at              DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    for model in MODELS:
        c.execute(
            "INSERT OR IGNORE INTO balances (model_name, balance) VALUES (?, ?)",
            (model, INITIAL_BALANCE),
        )

    conn.commit()
    conn.close()


def get_all_balances() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM balances ORDER BY balance DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_balance(model_name: str) -> float:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT balance FROM balances WHERE model_name = ?", (model_name,)
        ).fetchone()
        return row["balance"] if row else 0.0


def get_bets_for_match(match_code: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM bets WHERE match_code = ?", (match_code,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_pending_matches() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM matches WHERE status = 'pending' ORDER BY kickoff_time"
        ).fetchall()
        return [dict(r) for r in rows]


def get_unbet_matches_within(hours: int) -> list[dict]:
    """比赛在 hours 小时内开始且尚未对所有模型完成下注的赛事。"""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT m.*
            FROM matches m
            WHERE m.status = 'pending'
              AND m.home_odds > 0
              AND datetime(m.kickoff_time) <= datetime('now', ? || ' hours')
              AND datetime(m.kickoff_time) > datetime('now')
            ORDER BY m.kickoff_time
        """, (str(hours),)).fetchall()
        return [dict(r) for r in rows]


def upsert_match(match: dict):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO matches
                (match_code, home_team, away_team, kickoff_time, round,
                 home_odds, draw_odds, away_odds)
            VALUES (:match_code, :home_team, :away_team, :kickoff_time, :round,
                    :home_odds, :draw_odds, :away_odds)
            ON CONFLICT(match_code) DO UPDATE SET
                home_odds    = excluded.home_odds,
                draw_odds    = excluded.draw_odds,
                away_odds    = excluded.away_odds,
                kickoff_time = excluded.kickoff_time
        """, match)
        conn.commit()


def save_bet(match_code: str, model_name: str, bet_on: str,
             amount: int, odds: float):
    potential = round(amount * odds, 2)
    with get_conn() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO bets
                (match_code, model_name, bet_on, amount, odds_at_bet, potential_return)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (match_code, model_name, bet_on, amount, odds, potential))
        conn.execute("""
            UPDATE balances SET balance = balance - ?, total_bets = total_bets + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE model_name = ?
        """, (amount, model_name))
        conn.commit()


def settle_match(match_code: str, result: str):
    """result: 'home' | 'draw' | 'away'"""
    with get_conn() as conn:
        conn.execute(
            "UPDATE matches SET result = ?, status = 'finished' WHERE match_code = ?",
            (result, match_code),
        )
        bets = conn.execute(
            "SELECT * FROM bets WHERE match_code = ? AND is_settled = 0",
            (match_code,),
        ).fetchall()

        for bet in bets:
            bet = dict(bet)
            won = bet["bet_on"] == result
            profit = (bet["potential_return"] - bet["amount"]) if won else -bet["amount"]

            conn.execute("""
                UPDATE bets SET profit_loss = ?, is_settled = 1
                WHERE id = ?
            """, (profit, bet["id"]))

            if won:
                conn.execute("""
                    UPDATE balances
                    SET balance = balance + ?,
                        wins = wins + 1,
                        best_win = MAX(best_win, ?),
                        current_consecutive = current_consecutive + 1,
                        max_consecutive_wins = MAX(max_consecutive_wins, current_consecutive + 1),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE model_name = ?
                """, (bet["potential_return"], profit, bet["model_name"]))
            else:
                conn.execute("""
                    UPDATE balances
                    SET losses = losses + 1,
                        worst_loss = MIN(worst_loss, ?),
                        current_consecutive = 0,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE model_name = ?
                """, (profit, bet["model_name"]))

            bal = conn.execute(
                "SELECT balance FROM balances WHERE model_name = ?",
                (bet["model_name"],),
            ).fetchone()
            if bal and bal["balance"] <= 0:
                conn.execute(
                    "UPDATE balances SET is_eliminated = 1, balance = 0 WHERE model_name = ?",
                    (bet["model_name"],),
                )

        conn.commit()
