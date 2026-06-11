import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY", "")
DEEPSEEK_API_KEY  = os.getenv("DEEPSEEK_API_KEY", "")
DOUBAO_API_KEY    = os.getenv("DOUBAO_API_KEY", "")
DOUBAO_MODEL_ID   = os.getenv("DOUBAO_MODEL_ID", "doubao-pro-32k-241215")
SPORTTERY_COOKIE  = os.getenv("SPORTTERY_COOKIE", "")

INITIAL_BALANCE   = 1000
MIN_BET           = 10
MAX_BET_RATIO     = 0.30      # 单场最多押当前余额的30%
BET_DEADLINE_HOURS = 12       # 比赛前12小时截止下注

DB_PATH = "data/worldcup.db"

SPORTTERY_MATCH_API = (
    "https://webapi.sporttery.cn/gateway/jc/football/getMatchListV1.qry"
    "?clientCode=3001&matchStatus=0&pageSize=50&startPage=1&typeId=1"
)
SPORTTERY_RESULT_API = (
    "https://webapi.sporttery.cn/gateway/jc/football/getMatchResultV1.qry"
    "?clientCode=3001&pageSize=50&startPage=1&typeId=1"
)
SPORTTERY_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.sporttery.cn/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

MODELS = ["Claude", "DeepSeek", "豆包", "ChatGPT"]
