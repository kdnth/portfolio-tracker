"""Sprint 3 checkpoint: proves the configured Anthropic-contract endpoint actually supports
tool calling before anything in the real agent loop gets built on top of that assumption.
Currently targets the real Anthropic API (Claude Haiku 4.5, no extended thinking) -- see
the product spec's decisions log for why, and for the planned DeepSeek pivot later.

This test makes a real network call (no mocking) -- that's deliberate. The whole point is
to verify the live contract, not our assumptions about it.
"""
from anthropic import Anthropic

from app.core.config import settings

ADD_TOOL = {
    "name": "add",
    "description": "Add two numbers together and return the sum.",
    "input_schema": {
        "type": "object",
        "properties": {
            "a": {"type": "number", "description": "The first number"},
            "b": {"type": "number", "description": "The second number"},
        },
        "required": ["a", "b"],
    },
}


def test_anthropic_endpoint_returns_a_tool_use_block():
    client = Anthropic(api_key=settings.anthropic_api_key, base_url=settings.anthropic_base_url)

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        tools=[ADD_TOOL],
        messages=[
            {"role": "user", "content": "What is 7 plus 5? Use the add tool to compute it, don't do it yourself."}
        ],
    )

    tool_use_blocks = [block for block in response.content if block.type == "tool_use"]

    assert len(tool_use_blocks) == 1, f"expected exactly one tool_use block, got: {response.content}"
    tool_use = tool_use_blocks[0]
    assert tool_use.name == "add"
    assert float(tool_use.input["a"]) == 7
    assert float(tool_use.input["b"]) == 5
