"""
APScheduler 定时任务：
  - 每小时同步一次竞彩赔率和赛程
  - 每30分钟检查一次「比赛前12h内未下注」的赛事，触发模型下注
  - 每30分钟检查一次已结束比赛，自动结算
"""

import logging
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from database import upsert_match, get_unbet_matches_within
from odds.fetcher import fetch_matches
from engine.bet_manager import run_bets_for_match
from engine.settlement import auto_settle

logger = logging.getLogger(__name__)
scheduler = BlockingScheduler(timezone="Asia/Shanghai")


def job_sync_odds():
    """同步最新赛程和赔率到数据库。"""
    logger.info("[SYNC] Fetching matches from sporttery...")
    matches = fetch_matches()
    for m in matches:
        upsert_match(m)
    logger.info("[SYNC] Upserted %d matches.", len(matches))


def job_place_bets():
    """对12h内开赛且尚未下注的比赛，触发四个模型下注。"""
    from config import BET_DEADLINE_HOURS
    matches = get_unbet_matches_within(BET_DEADLINE_HOURS)
    if not matches:
        logger.info("[BET] No matches to bet on right now.")
        return
    for match in matches:
        logger.info("[BET] Processing match: %s vs %s", match["home_team"], match["away_team"])
        run_bets_for_match(match)


def job_settle():
    """自动结算已开奖的比赛。"""
    logger.info("[SETTLE] Checking for results...")
    auto_settle()


def start():
    scheduler.add_job(job_sync_odds,  IntervalTrigger(hours=1),   id="sync_odds",   replace_existing=True)
    scheduler.add_job(job_place_bets, IntervalTrigger(minutes=30), id="place_bets",  replace_existing=True)
    scheduler.add_job(job_settle,     IntervalTrigger(minutes=30), id="settle",      replace_existing=True)

    # 启动时立刻执行一次
    job_sync_odds()
    job_place_bets()
    job_settle()

    logger.info("Scheduler started. Press Ctrl+C to stop.")
    scheduler.start()
