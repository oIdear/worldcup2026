"""
世界杯 AI 押注大战 — 主入口

用法：
  python main.py run                                  # 启动定时调度器（正式运行）
  python main.py dashboard                            # 排行榜网页 http://localhost:5000
  python main.py sync                                 # 从 openfootball 同步完整赛程
  python main.py matches                              # 列出所有比赛（含赔率状态）
  python main.py update_odds <match_code> <主胜> <平局> <客胜>  # 录入竞彩赔率
  python main.py bet <match_code>                     # 手动触发单场 AI 下注
  python main.py settle <match_code> <home|draw|away> # 手动结算单场
  python main.py status                               # 打印当前余额排名
"""

import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

from database import init_db, get_all_balances


def cmd_run():
    from engine.scheduler import start
    start()


def cmd_dashboard():
    from dashboard.app import app
    app.run(debug=False, port=5000, host="0.0.0.0")


def cmd_sync():
    """从 openfootball 拉取完整世界杯赛程（不覆盖已有赔率）。"""
    from odds.fetcher import fetch_schedule
    from database import upsert_match
    matches = fetch_schedule()
    for m in matches:
        upsert_match(m)
    print(f"同步完成，共 {len(matches)} 场赛事。")
    print("提示：赛程已导入，请用 update_odds 命令补录各场竞彩赔率。")


def cmd_matches():
    """列出所有比赛，标注赔率是否已录入。"""
    from database import get_conn
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM matches ORDER BY kickoff_time"
        ).fetchall()
    if not rows:
        print("暂无赛事，请先执行 python main.py sync")
        return
    print(f"\n{'代码':<14} {'主队':<20} {'客队':<20} {'开赛时间':<20} {'赔率'}")
    print("-" * 90)
    for r in rows:
        has_odds = r["home_odds"] and r["home_odds"] > 0
        odds_str = f"{r['home_odds']:.2f}/{r['draw_odds']:.2f}/{r['away_odds']:.2f}" if has_odds else "待录入"
        status = "✓" if r["status"] == "finished" else ("📋" if has_odds else "❌")
        print(f"{status} {r['match_code']:<13} {r['home_team']:<20} {r['away_team']:<20} "
              f"{r['kickoff_time']:<20} {odds_str}")
    print()


def cmd_update_odds(match_code: str, home: str, draw: str, away: str):
    """录入指定比赛的竞彩赔率。"""
    from database import get_conn
    home_odds, draw_odds, away_odds = float(home), float(draw), float(away)
    with get_conn() as conn:
        row = conn.execute(
            "SELECT match_code, home_team, away_team FROM matches WHERE match_code = ?",
            (match_code,)
        ).fetchone()
        if not row:
            print(f"找不到比赛 {match_code}，请先执行 sync 或确认代码是否正确。")
            return
        conn.execute(
            "UPDATE matches SET home_odds=?, draw_odds=?, away_odds=? WHERE match_code=?",
            (home_odds, draw_odds, away_odds, match_code)
        )
        conn.commit()
    print(f"赔率已更新：{row['home_team']} vs {row['away_team']}  "
          f"主胜 {home_odds} | 平局 {draw_odds} | 客胜 {away_odds}")


def cmd_bet(match_code: str):
    from database import get_conn
    from engine.bet_manager import run_bets_for_match
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM matches WHERE match_code = ?", (match_code,)
        ).fetchone()
    if not row:
        print(f"找不到赛事 {match_code}。")
        return
    row = dict(row)
    if not row.get("home_odds"):
        print(f"赛事 {match_code} 尚未录入赔率，请先执行 update_odds。")
        return
    run_bets_for_match(row)
    print("下注完成。")


def cmd_settle(match_code: str, result: str):
    from engine.settlement import manual_settle
    manual_settle(match_code, result)
    print(f"结算完成：{match_code} → {result}")


def cmd_status():
    balances = get_all_balances()
    print(f"\n{'排名':<4} {'模型':<10} {'余额':>8}  {'胜':<4} {'负':<4} {'下注':<6} {'状态'}")
    print("-" * 56)
    for i, b in enumerate(balances, 1):
        status = "出局" if b["is_eliminated"] else "存活"
        profit = b["balance"] - 1000
        sign = "+" if profit >= 0 else ""
        print(
            f"  {i:<3} {b['model_name']:<10} {int(b['balance']):>6}  "
            f"{b['wins']:<4} {b['losses']:<4} {b['total_bets']:<6} {status}  "
            f"({sign}{int(profit)})"
        )
    print()


COMMANDS = {
    "run":        cmd_run,
    "dashboard":  cmd_dashboard,
    "sync":       cmd_sync,
    "matches":    cmd_matches,
    "status":     cmd_status,
}

if __name__ == "__main__":
    init_db()
    args = sys.argv[1:]

    if not args:
        print(__doc__)
        sys.exit(0)

    cmd = args[0]

    if cmd == "update_odds" and len(args) == 5:
        cmd_update_odds(args[1], args[2], args[3], args[4])
    elif cmd == "bet" and len(args) == 2:
        cmd_bet(args[1])
    elif cmd == "settle" and len(args) == 3:
        cmd_settle(args[1], args[2])
    elif cmd in COMMANDS:
        COMMANDS[cmd]()
    else:
        print(f"未知命令或参数错误: {' '.join(args)}")
        print(__doc__)
        sys.exit(1)
