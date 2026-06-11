"""
世界杯 AI 押注大战 — 主入口

用法：
  python main.py run         # 启动定时调度器（正式运行）
  python main.py dashboard   # 仅启动排行榜网页（http://localhost:5000）
  python main.py sync        # 手动同步一次赛程+赔率
  python main.py bet <match_code>         # 手动触发单场下注
  python main.py settle <match_code> <home|draw|away>  # 手动结算单场
  python main.py status      # 打印当前余额排名
  python main.py add_match   # 手动添加一场比赛（无法抓取时使用）
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
    from odds.fetcher import fetch_matches
    from database import upsert_match
    matches = fetch_matches()
    for m in matches:
        upsert_match(m)
    print(f"同步完成，共 {len(matches)} 场赛事。")


def cmd_bet(match_code: str):
    from database import get_conn
    from engine.bet_manager import run_bets_for_match
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM matches WHERE match_code = ?", (match_code,)
        ).fetchone()
    if not row:
        print(f"找不到赛事 {match_code}，请先 sync 或 add_match。")
        return
    run_bets_for_match(dict(row))
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


def cmd_add_match():
    print("手动添加比赛（用于竞彩接口无法获取时）")
    match = {
        "match_code":   input("比赛代码（唯一ID，如 WC2026_001）: ").strip(),
        "home_team":    input("主队名称: ").strip(),
        "away_team":    input("客队名称: ").strip(),
        "kickoff_time": input("开赛时间（格式 2026-06-12 22:00:00）: ").strip(),
        "round":        input("赛事阶段（如 小组赛A组）: ").strip(),
        "home_odds":    float(input("主胜赔率: ").strip()),
        "draw_odds":    float(input("平局赔率: ").strip()),
        "away_odds":    float(input("客胜赔率: ").strip()),
    }
    from database import upsert_match
    upsert_match(match)
    print(f"已添加：{match['home_team']} vs {match['away_team']}")


COMMANDS = {
    "run":       cmd_run,
    "dashboard": cmd_dashboard,
    "sync":      cmd_sync,
    "status":    cmd_status,
    "add_match": cmd_add_match,
}


if __name__ == "__main__":
    init_db()
    args = sys.argv[1:]

    if not args:
        print(__doc__)
        sys.exit(0)

    cmd = args[0]

    if cmd == "bet" and len(args) >= 2:
        cmd_bet(args[1])
    elif cmd == "settle" and len(args) >= 3:
        cmd_settle(args[1], args[2])
    elif cmd in COMMANDS:
        COMMANDS[cmd]()
    else:
        print(f"未知命令: {cmd}")
        print(__doc__)
        sys.exit(1)
