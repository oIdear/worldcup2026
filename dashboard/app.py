import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, render_template, jsonify, request
from database import get_all_balances, get_conn, settle_match

app = Flask(__name__)


def _get_stats() -> dict:
    balances = get_all_balances()
    with get_conn() as conn:
        total_matches = conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
        finished = conn.execute("SELECT COUNT(*) FROM matches WHERE status='finished'").fetchone()[0]
        pending  = total_matches - finished
        recent_bets = conn.execute("""
            SELECT b.model_name, b.bet_on, b.amount, b.profit_loss, b.is_settled,
                   m.home_team, m.away_team, m.kickoff_time, b.odds_at_bet
            FROM bets b JOIN matches m ON b.match_code = m.match_code
            ORDER BY b.created_at DESC LIMIT 20
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
    return render_template("index.html", **_get_stats())


@app.route("/api/stats")
def api_stats():
    return jsonify(_get_stats())


@app.route("/api/matches")
def api_matches():
    status_filter = request.args.get("status", "all")
    with get_conn() as conn:
        if status_filter == "no_odds":
            rows = conn.execute(
                "SELECT * FROM matches WHERE status='pending' AND home_odds=0 ORDER BY kickoff_time"
            ).fetchall()
        elif status_filter == "pending":
            rows = conn.execute(
                "SELECT * FROM matches WHERE status='pending' AND home_odds>0 ORDER BY kickoff_time"
            ).fetchall()
        elif status_filter == "finished":
            rows = conn.execute(
                "SELECT * FROM matches WHERE status='finished' ORDER BY kickoff_time DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM matches ORDER BY kickoff_time"
            ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/update_odds", methods=["POST"])
def api_update_odds():
    data = request.get_json()
    match_code = data.get("match_code", "").strip()
    try:
        home_odds = float(data.get("home_odds", 0))
        draw_odds = float(data.get("draw_odds", 0))
        away_odds = float(data.get("away_odds", 0))
    except (ValueError, TypeError):
        return jsonify({"ok": False, "error": "赔率必须是数字"}), 400

    if not match_code:
        return jsonify({"ok": False, "error": "缺少 match_code"}), 400
    if home_odds <= 1 or draw_odds <= 1 or away_odds <= 1:
        return jsonify({"ok": False, "error": "赔率必须大于 1"}), 400

    with get_conn() as conn:
        row = conn.execute(
            "SELECT home_team, away_team FROM matches WHERE match_code=?", (match_code,)
        ).fetchone()
        if not row:
            return jsonify({"ok": False, "error": f"找不到比赛 {match_code}"}), 404
        conn.execute(
            "UPDATE matches SET home_odds=?, draw_odds=?, away_odds=? WHERE match_code=?",
            (home_odds, draw_odds, away_odds, match_code)
        )
        conn.commit()

    return jsonify({
        "ok": True,
        "message": f"{row['home_team']} vs {row['away_team']} 赔率已录入",
    })


@app.route("/api/settle", methods=["POST"])
def api_settle():
    data = request.get_json()
    match_code = data.get("match_code", "").strip()
    result = data.get("result", "").strip()

    if result not in ("home", "draw", "away"):
        return jsonify({"ok": False, "error": "result 必须是 home / draw / away"}), 400

    with get_conn() as conn:
        row = conn.execute(
            "SELECT home_team, away_team, status FROM matches WHERE match_code=?",
            (match_code,)
        ).fetchone()
        if not row:
            return jsonify({"ok": False, "error": f"找不到比赛 {match_code}"}), 404
        if row["status"] == "finished":
            return jsonify({"ok": False, "error": "该比赛已结算"}), 400

    settle_match(match_code, result)
    label = {"home": "主队胜", "draw": "平局", "away": "客队胜"}[result]
    return jsonify({
        "ok": True,
        "message": f"{row['home_team']} vs {row['away_team']} 结算完成：{label}",
    })


@app.route("/api/bet", methods=["POST"])
def api_bet():
    data = request.get_json()
    match_code = data.get("match_code", "").strip()

    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM matches WHERE match_code=?", (match_code,)
        ).fetchone()
    if not row:
        return jsonify({"ok": False, "error": f"找不到比赛 {match_code}"}), 404

    row = dict(row)
    if not row.get("home_odds"):
        return jsonify({"ok": False, "error": "请先录入赔率"}), 400

    from engine.bet_manager import run_bets_for_match
    run_bets_for_match(row)
    return jsonify({"ok": True, "message": f"下注触发完成"})


if __name__ == "__main__":
    app.run(debug=False, port=5000, host="0.0.0.0")
