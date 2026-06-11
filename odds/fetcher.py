"""
竞彩足球胜平负赔率抓取模块

策略：
  1. 优先调用 sporttery.cn JSON API（需要 Cookie，可选）
  2. 失败则 fallback 到 HTML 页面抓取
  3. 以上均失败则返回空列表，由调用方决定是否手动录入
"""

import re
import json
import logging
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from config import SPORTTERY_MATCH_API, SPORTTERY_RESULT_API, SPORTTERY_HEADERS, SPORTTERY_COOKIE

logger = logging.getLogger(__name__)

RESULT_MAP = {
    "3": "home",   # 胜
    "1": "draw",   # 平
    "0": "away",   # 负
    "win":  "home",
    "draw": "draw",
    "lose": "away",
}


def _build_headers() -> dict:
    h = dict(SPORTTERY_HEADERS)
    if SPORTTERY_COOKIE:
        h["Cookie"] = SPORTTERY_COOKIE
    return h


# ── API 模式 ─────────────────────────────────────────────────────────────────

def fetch_matches_api() -> list[dict]:
    """调用 sporttery.cn 官方 JSON 接口获取近期赛事及赔率。"""
    try:
        resp = requests.get(SPORTTERY_MATCH_API, headers=_build_headers(), timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return _parse_api_response(data)
    except Exception as e:
        logger.warning("API fetch failed: %s", e)
        return []


def _parse_api_response(data: dict) -> list[dict]:
    matches = []
    try:
        items = data["value"]["matchList"]
    except (KeyError, TypeError):
        return []

    for item in items:
        try:
            odds = item.get("singleOdds") or item.get("spfOdds") or {}
            matches.append({
                "match_code":   item["matchCode"],
                "home_team":    item["homeTeamName"],
                "away_team":    item["awayTeamName"],
                "kickoff_time": _parse_time(item.get("matchDate", "")),
                "round":        item.get("leagueShortName", "世界杯"),
                "home_odds":    float(odds.get("3", 0) or 0),
                "draw_odds":    float(odds.get("1", 0) or 0),
                "away_odds":    float(odds.get("0", 0) or 0),
            })
        except Exception as e:
            logger.debug("Skip item: %s", e)
    return matches


# ── HTML 抓取模式 ─────────────────────────────────────────────────────────────

SPF_HTML_URL = "https://www.sporttery.cn/jc/jsq/zqspf/index.html"


def fetch_matches_html() -> list[dict]:
    """抓取竞彩网胜平负页面的 HTML 获取赔率。"""
    try:
        resp = requests.get(SPF_HTML_URL, headers=_build_headers(), timeout=15)
        resp.raise_for_status()
        return _parse_spf_html(resp.text)
    except Exception as e:
        logger.warning("HTML fetch failed: %s", e)
        return []


def _parse_spf_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    matches = []

    # 尝试从内嵌 JSON 数据中解析（多数页面将数据放在 window.__INITIAL_STATE__ 或类似变量中）
    scripts = soup.find_all("script")
    for script in scripts:
        text = script.string or ""
        if "matchCode" in text or "homeTeam" in text:
            found = _extract_json_from_script(text)
            if found:
                return found

    # fallback：解析 HTML 表格
    rows = soup.select("tr.match-row, tr[data-matchcode]")
    for row in rows:
        try:
            cols = row.find_all("td")
            if len(cols) < 6:
                continue
            code = row.get("data-matchcode", cols[0].get_text(strip=True))
            matches.append({
                "match_code":   code,
                "home_team":    cols[2].get_text(strip=True),
                "away_team":    cols[4].get_text(strip=True),
                "kickoff_time": _parse_time(cols[1].get_text(strip=True)),
                "round":        "世界杯",
                "home_odds":    _safe_float(cols[5].get_text(strip=True)),
                "draw_odds":    _safe_float(cols[6].get_text(strip=True)),
                "away_odds":    _safe_float(cols[7].get_text(strip=True)),
            })
        except Exception as e:
            logger.debug("Row parse error: %s", e)

    return matches


def _extract_json_from_script(text: str) -> list[dict]:
    """尝试从 script 文本提取内嵌 JSON 数据。"""
    pattern = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});', text, re.S)
    if not pattern:
        pattern = re.search(r'var\s+matchData\s*=\s*(\[.*?\]);', text, re.S)
    if not pattern:
        return []
    try:
        raw = json.loads(pattern.group(1))
        return _parse_api_response(raw) or _parse_api_response({"value": {"matchList": raw}})
    except Exception:
        return []


# ── 比赛结果查询 ─────────────────────────────────────────────────────────────

def fetch_results_api() -> list[dict]:
    """获取已结束比赛的开奖结果。返回 [{match_code, result}] 列表。"""
    try:
        resp = requests.get(SPORTTERY_RESULT_API, headers=_build_headers(), timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return _parse_results(data)
    except Exception as e:
        logger.warning("Result API failed: %s", e)
        return []


def _parse_results(data: dict) -> list[dict]:
    results = []
    try:
        items = data["value"]["matchList"]
    except (KeyError, TypeError):
        return []
    for item in items:
        raw = item.get("matchResult") or item.get("result") or ""
        result = RESULT_MAP.get(str(raw).strip().lower())
        if result:
            results.append({
                "match_code": item["matchCode"],
                "result": result,
            })
    return results


# ── 统一入口 ─────────────────────────────────────────────────────────────────

def fetch_matches() -> list[dict]:
    """尝试 API → HTML 两种方式，返回赛事+赔率列表。"""
    matches = fetch_matches_api()
    if not matches:
        logger.info("Falling back to HTML scrape...")
        matches = fetch_matches_html()
    logger.info("Fetched %d matches", len(matches))
    return matches


def fetch_results() -> list[dict]:
    return fetch_results_api()


# ── 工具函数 ─────────────────────────────────────────────────────────────────

def _parse_time(raw: str) -> str:
    """将各种时间格式统一为 ISO 字符串。"""
    raw = raw.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M", "%m-%d %H:%M"):
        try:
            dt = datetime.strptime(raw, fmt)
            if dt.year == 1900:
                dt = dt.replace(year=datetime.now().year)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return raw


def _safe_float(s: str) -> float:
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0
