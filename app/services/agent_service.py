import json
import logging

from anthropic import Anthropic
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.agent_tools import AGENT_TOOLS, TOOL_FUNCTIONS

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5-20251001"
TEMPERATURE = 0.2
MAX_TOOL_ROUNDS = 6
MAX_TOKENS = 1500

SYSTEM_PROMPT = """You are a portfolio analysis assistant. You have tools to look up a \
user's actual holdings, price history, and trade history for the portfolio they're asking \
about -- use them to ground your analysis in real data before answering.

You may also draw on your own general knowledge (e.g. what a company does, sector context, \
typical volatility characteristics) to add color, but stay analytical: describe what \
happened and why it might have happened. Do not give prescriptive advice like "you should \
buy/sell X" or tell the user what to do with their money. You are not a financial advisor.

Always end your analysis with a brief disclaimer that this is not financial advice."""

FORCE_FINAL_ANSWER_MESSAGE = (
    "You've reached the tool-call limit for this analysis. Based on what you've already "
    "learned, give your final analysis now -- no more tool calls."
)


def analyze_portfolio(db: Session, portfolio_id: int, question: str | None = None) -> str:
    """Runs the tool-use loop for one portfolio analysis and returns the final text report.
    portfolio_id is bound here, server-side -- it is never exposed to the model as a tool
    parameter, so the model can only ever see data for the portfolio this call was made for."""
    client = Anthropic(api_key=settings.anthropic_api_key, base_url=settings.anthropic_base_url)

    messages: list[dict] = [
        {"role": "user", "content": question or "Analyze this portfolio's performance and notable patterns."}
    ]

    for _ in range(MAX_TOOL_ROUNDS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=AGENT_TOOLS,
            messages=messages,
            extra_body={"temperature": TEMPERATURE},
        )

        if response.stop_reason != "tool_use":
            return _extract_text(response)

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": _run_tool_calls(db, portfolio_id, response.content)})

    logger.warning(
        "Agent hit the %d-round tool-call cap for portfolio %d; forcing a final answer",
        MAX_TOOL_ROUNDS,
        portfolio_id,
    )
    messages.append({"role": "user", "content": FORCE_FINAL_ANSWER_MESSAGE})
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=messages,
        extra_body={"temperature": TEMPERATURE},
    )
    return _extract_text(response)


def _run_tool_calls(db: Session, portfolio_id: int, content_blocks: list) -> list[dict]:
    tool_results = []
    for block in content_blocks:
        if block.type != "tool_use":
            continue
        logger.info("Agent tool call: %s(%s)", block.name, block.input)
        result = _call_tool(db, portfolio_id, block.name, block.input)
        tool_results.append(
            {"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result)}
        )
    return tool_results


def _call_tool(db: Session, portfolio_id: int, name: str, tool_input: dict) -> dict | list:
    function = TOOL_FUNCTIONS.get(name)
    if function is None:
        return {"error": f"Unknown tool '{name}'"}
    try:
        return function(db=db, portfolio_id=portfolio_id, **tool_input)
    except Exception:
        logger.exception("Tool call failed: %s(%s)", name, tool_input)
        return {"error": f"Tool '{name}' failed unexpectedly."}


def _extract_text(response) -> str:
    return "".join(block.text for block in response.content if block.type == "text")
