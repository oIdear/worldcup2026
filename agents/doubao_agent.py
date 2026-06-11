import logging
from openai import OpenAI
from config import DOUBAO_API_KEY, DOUBAO_MODEL_ID
from agents.base_agent import build_prompt, parse_response
from database import get_balance

logger = logging.getLogger(__name__)

MODEL_NAME = "豆包"


def decide(match: dict) -> tuple[str, int] | None:
    balance = get_balance(MODEL_NAME)
    if balance <= 0:
        logger.info("豆包 is eliminated.")
        return None

    prompt = build_prompt(MODEL_NAME, match)
    try:
        client = OpenAI(
            api_key=DOUBAO_API_KEY,
            base_url="https://ark.cn-beijing.volces.com/api/v3",
        )
        resp = client.chat.completions.create(
            model=DOUBAO_MODEL_ID,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.choices[0].message.content
        logger.info("豆包 raw: %s", raw)
        return parse_response(raw, balance)
    except Exception as e:
        logger.error("豆包 API error: %s", e)
        return None
