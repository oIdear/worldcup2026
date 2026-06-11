"""赛后自动结算模块。"""

import logging
from database import settle_match, get_pending_matches, get_conn
from odds.fetcher import fetch_results

logger = logging.getLogger(__name__)


def auto_settle():
    """拉取竞彩开奖结果，对已结束比赛执行结算。"""
    results = fetch_results()
    if not results:
        logger.info("No new results from API.")
        return

    settled = 0
    for r in results:
        match_code = r["match_code"]
        result = r["result"]
        with get_conn() as conn:
            row = conn.execute(
                "SELECT status FROM matches WHERE match_code = ?", (match_code,)
            ).fetchone()
        if row and row["status"] == "pending":
            settle_match(match_code, result)
            logger.info("Settled %s → %s", match_code, result)
            settled += 1

    logger.info("Auto-settled %d matches.", settled)


def manual_settle(match_code: str, result: str):
    """手动结算单场比赛。result: 'home'|'draw'|'away'"""
    if result not in ("home", "draw", "away"):
        raise ValueError("result must be 'home', 'draw', or 'away'")
    settle_match(match_code, result)
    logger.info("Manually settled %s → %s", match_code, result)
