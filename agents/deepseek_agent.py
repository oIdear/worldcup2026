import logging
from openai import OpenAI
from config import DEEPSEEK_API_KEY
from agents.base_agent import build_prompt, parse_response
from database import get_balance

logger = logging.getLogger(__name__)

MODEL_NAME = "DeepSeek"


def decide(match: dict) -> tuple[str, int] | None:
    balance = get_balance(MODEL_NAME)
    if balance <= 0:
        logger.info("DeepSeek is eliminated.")
        return None

    prompt = build_prompt(MODEL_NAME, match)
    try:
        client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com/v1",
        )
        resp = client.chat.completions.create(
            model="deepseek-chat",
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.choices[0].message.content
        logger.info("DeepSeek raw: %s", raw)
        return parse_response(raw, balance)
    except Exception as e:
        logger.error("DeepSeek API error: %s", e)
        return None
