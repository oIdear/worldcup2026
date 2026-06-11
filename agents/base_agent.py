"""公共 Prompt 模板与响应解析逻辑。"""

import json
import re
import logging
from database import get_all_balances

logger = logging.getLogger(__name__)

BET_OPTIONS = {"主胜": "home", "平局": "draw", "客胜": "away"}


def build_prompt(model_name: str, match: dict) -> str:
    balances = get_all_balances()
    balance = next((b["balance"] for b in balances if b["model_name"] == model_name), 0)

    ranked = sorted(balances, key=lambda x: x["balance"], reverse=True)
    ranking_lines = []
    for i, b in enumerate(ranked, 1):
        status = "（已出局）" if b["is_eliminated"] else ""
        marker = " ← 你" if b["model_name"] == model_name else ""
        ranking_lines.append(f"  {i}. {b['model_name']}：{int(b['balance'])} 虚拟币{status}{marker}")
    ranking_text = "\n".join(ranking_lines)

    from database import get_conn
    with get_conn() as conn:
        remaining = conn.execute(
            "SELECT COUNT(*) FROM matches WHERE status = 'pending'"
        ).fetchone()[0]

    return f"""你是一名足球分析师，正在参与一场AI模型世界杯竞猜大战。

【赛事规则】
- 参赛选手：Claude、DeepSeek、豆包、ChatGPT，共4支AI
- 每人初始资金 1000 虚拟币，谁最终余额最高谁获胜
- 余额归零即永久出局，无法翻盘
- 当前你是：{model_name}

【对手实时排名】
{ranking_text}

【当前比赛】
主队：{match['home_team']} vs 客队：{match['away_team']}
赛事阶段：{match.get('round', '世界杯')}
开赛时间：{match['kickoff_time']}

【竞彩赔率（欧赔）】
主队胜：{match['home_odds']} | 平局：{match['draw_odds']} | 客队胜：{match['away_odds']}

【你的当前余额】{int(balance)} 虚拟币（余额归零即永久出局）
【本届剩余场次】约 {remaining} 场

请根据以上信息做出下注决策。

只返回如下 JSON，不要有任何其他文字：
{{"bet": "主胜|平局|客胜", "amount": 整数}}

要求：
- amount 必须是 10 到 {int(balance)}（全部余额）之间的整数，由你自由决定
- bet 必须是"主胜"、"平局"或"客胜"三者之一"""


def parse_response(raw: str, balance: float) -> tuple[str, int] | None:
    """解析模型返回的 JSON，返回 (bet_on, amount) 或 None。"""
    raw = raw.strip()
    match = re.search(r'\{.*?\}', raw, re.S)
    if not match:
        logger.warning("No JSON found in response: %s", raw[:200])
        return None
    try:
        data = json.loads(match.group())
        bet_cn = data.get("bet", "").strip()
        amount = int(data.get("amount", 0))
        bet_on = BET_OPTIONS.get(bet_cn)
        if not bet_on:
            logger.warning("Unknown bet value: %s", bet_cn)
            return None
        amount = max(10, min(amount, int(balance)))
        return bet_on, amount
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("Parse error: %s | raw: %s", e, raw[:200])
        return None
