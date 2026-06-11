"""为一场比赛并发调用四个模型并保存下注记录。"""

import logging
import concurrent.futures
from database import save_bet, get_balance, get_bets_for_match
from config import MODELS

logger = logging.getLogger(__name__)


def _agent_module(model_name: str):
    import importlib
    mapping = {
        "Claude":   "agents.claude_agent",
        "DeepSeek": "agents.deepseek_agent",
        "豆包":     "agents.doubao_agent",
        "ChatGPT":  "agents.chatgpt_agent",
    }
    return importlib.import_module(mapping[model_name])


def run_bets_for_match(match: dict):
    """并发让四个模型对同一场比赛下注。跳过已出局或已下注的模型。"""
    match_code = match["match_code"]
    existing = {b["model_name"] for b in get_bets_for_match(match_code)}

    tasks = []
    for model in MODELS:
        if model in existing:
            logger.info("%s already bet on %s, skipping.", model, match_code)
            continue
        balance = get_balance(model)
        if balance <= 0:
            logger.info("%s is eliminated, skipping.", model)
            continue
        tasks.append(model)

    if not tasks:
        logger.info("No pending bets for match %s", match_code)
        return

    def call_model(model_name: str):
        try:
            mod = _agent_module(model_name)
            result = mod.decide(match)
            if result:
                bet_on, amount = result
                odds_map = {
                    "home": match["home_odds"],
                    "draw": match["draw_odds"],
                    "away": match["away_odds"],
                }
                odds = odds_map[bet_on]
                save_bet(match_code, model_name, bet_on, amount, odds)
                logger.info(
                    "✅ %s → %s %d 币 @ %.2f (返还 %.2f)",
                    model_name, bet_on, amount, odds, amount * odds,
                )
            else:
                logger.warning("⚠️  %s returned no valid bet.", model_name)
        except Exception as e:
            logger.error("❌ %s error: %s", model_name, e)

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(call_model, tasks))
