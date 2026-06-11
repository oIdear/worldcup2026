import logging
import anthropic
from config import ANTHROPIC_API_KEY
from agents.base_agent import build_prompt, parse_response
from database import get_balance

logger = logging.getLogger(__name__)

MODEL_NAME = "Claude"


def decide(match: dict) -> tuple[str, int] | None:
    balance = get_balance(MODEL_NAME)
    if balance <= 0:
        logger.info("Claude is eliminated.")
        return None

    prompt = build_prompt(MODEL_NAME, match)
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text
        logger.info("Claude raw: %s", raw)
        return parse_response(raw, balance)
    except Exception as e:
        logger.error("Claude API error: %s", e)
        return None
