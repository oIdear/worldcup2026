"""
赛程与赔率模块

赛程来源：openfootball/worldcup.json（GitHub，免费无需Key，104场全覆盖）
赔率来源：用户手动从竞彩网录入（sporttery.cn 需登录，无法自动抓取）
比赛结果：用户手动录入（python main.py settle）
"""

import logging
from datetime import datetime, timezone, timedelta

import requests

logger = logging.getLogger(__name__)

OPENFOOTBALL_URL = (
    "https://raw.githubusercontent.com/openfootball/worldcup.json"
    "/master/2026/worldcup.json"
)

# UTC+8 北京时间偏移
CST = timezone(timedelta(hours=8))

# UTC 偏移字符串 → 小时数（按长度降序排列，避免 "UTC" 匹配 "UTC-6" 的子串）
_UTC_OFFSET = {
    "UTC-8": -8, "UTC-7": -7, "UTC-6": -6, "UTC-5": -5,
    "UTC-4": -4, "UTC-3": -3, "UTC+0": 0,  "UTC+1": 1,
    "UTC+8": 8,  "UTC": 0,
}


def fetch_schedule() -> list[dict]:
    """从 openfootball 拉取完整世界杯赛程（不含赔率）。"""
    try:
        resp = requests.get(OPENFOOTBALL_URL, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return _parse_openfootball(data)
    except Exception as e:
        logger.error("Schedule fetch failed: %s", e)
        return []


def _parse_openfootball(data: dict) -> list[dict]:
    matches = []
    # 实际结构：{"name": "World Cup 2026", "matches": [...]}
    # 每条 match：{"round": "Matchday 1", "date": "2026-06-11",
    #              "time": "13:00 UTC-6", "team1": "Mexico", "team2": "South Africa", ...}
    items = data.get("matches", [])
    for seq, m in enumerate(items, 1):
        try:
            t1 = m.get("team1", "")
            t2 = m.get("team2", "")
            home = t1 if isinstance(t1, str) else t1.get("name", str(t1))
            away = t2 if isinstance(t2, str) else t2.get("name", str(t2))
            kickoff = _to_cst(m.get("date", ""), m.get("time", ""))
            matches.append({
                "match_code":   f"WC2026_{seq:03d}",
                "home_team":    home,
                "away_team":    away,
                "kickoff_time": kickoff,
                "round":        m.get("round", "世界杯"),
                "home_odds":    0.0,
                "draw_odds":    0.0,
                "away_odds":    0.0,
            })
        except Exception as e:
            logger.debug("Skip match: %s | %s", m, e)
    logger.info("Parsed %d matches from openfootball", len(matches))
    return matches


def _to_cst(date_str: str, time_str: str) -> str:
    """将比赛时间（含 UTC 偏移）转为北京时间（UTC+8）ISO 字符串。"""
    # time_str 格式例：'13:00 UTC-6'  或  '20:00'
    offset_hours = 0
    time_part = time_str.strip()
    for key, val in _UTC_OFFSET.items():
        if key in time_part:
            offset_hours = val
            time_part = time_part.replace(key, "").strip()
            break

    raw = f"{date_str} {time_part}".strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            dt_local = datetime.strptime(raw, fmt)
            dt_utc = dt_local - timedelta(hours=offset_hours)
            dt_cst = dt_utc + timedelta(hours=8)
            return dt_cst.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    # 解析失败原样返回
    return f"{date_str} {time_part}"


# 结果查询保留（手动结算，fetch_results 不再使用）
def fetch_results() -> list[dict]:
    return []
