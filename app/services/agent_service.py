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

# Appended to the system prompt only for the public demo portfolio (see
# analyze_portfolio() below). Its holdings use fictional placeholder-company tickers
# (Contoso, Fabrikam, Northwind, AdventureWorks) with synthetic price history, since real
# tickers' price history is shared across every user and can't be fabricated without
# corrupting real charts. Without this, the model might recognize these as well-known
# placeholder names and comment on that instead of analyzing the data, or worse, invent
# real-sounding "facts" about a company that doesn't exist.
DEMO_SYSTEM_PROMPT_ADDENDUM = """

Note: this specific portfolio is a demonstration example. Its holdings (Contoso, \
Fabrikam, Northwind, AdventureWorks) are fictional placeholder company names, not real, \
tradeable companies -- do not describe real-world business operations, sector news, or \
"facts" about them, and do not claim they are real. Instead, base your analysis entirely \
on the concrete patterns in the data your tools return: price trends, volatility, cost \
basis performance, and trade timing, exactly as you would for a real portfolio -- just \
without the general-knowledge company color you'd normally add."""

FORCE_FINAL_ANSWER_MESSAGE = (
    "You've reached the tool-call limit for this analysis. Based on what you've already "
    "learned, give your final analysis now -- no more tool calls."
)


def analyze_portfolio(db: Session, portfolio_id: int, question: str | None = None) -> str:
    """Runs the tool-use loop for one portfolio analysis and returns the final text report.
    portfolio_id is bound here, server-side -- it is never exposed to the model as a tool
    parameter, so the model can only ever see data for the portfolio this call was made for."""
    client = Anthropic(api_key=settings.anthropic_api_key, base_url=settings.anthropic_base_url)
    system_prompt = SYSTEM_PROMPT
    if portfolio_id == settings.demo_portfolio_id:
        system_prompt += DEMO_SYSTEM_PROMPT_ADDENDUM

    messages: list[dict] = [
        {"role": "user", "content": question or "Analyze this portfolio's performance and notable patterns."}
    ]

    for _ in range(MAX_TOOL_ROUNDS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
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
        system=system_prompt,
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
