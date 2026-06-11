"""Flask 排行榜 Web 服务。访问 http://localhost:5000 查看实时战况。"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, render_template, jsonify
from database import get_all_balances, get_conn

app = Flask(__name__)


def _get_stats() -> dict:
    balances = get_all_balances()

    with get_conn() as conn:
        total_matches = conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
        finished = conn.execute(
            "SELECT COUNT(*) FROM matches WHERE status = 'finished'"
        ).fetchone()[0]
        pending = total_matches - finished

        recent_bets = conn.execute("""
            SELECT b.model_name, b.bet_on, b.amount, b.profit_loss, b.is_settled,
                   m.home_team, m.away_team, m.kickoff_time, b.odds_at_bet
            FROM bets b
            JOIN matches m ON b.match_code = m.match_code
            ORDER BY b.created_at DESC
            LIMIT 20
        """).fetchall()

    return {
        "balances": balances,
        "total_matches": total_matches,
        "finished_matches": finished,
        "pending_matches": pending,
        "recent_bets": [dict(r) for r in recent_bets],
    }


@app.route("/")
def index():
    stats = _get_stats()
    return render_template("index.html", **stats)


@app.route("/api/stats")
def api_stats():
    return jsonify(_get_stats())


if __name__ == "__main__":
    app.run(debug=False, port=5000)
