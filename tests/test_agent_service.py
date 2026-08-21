import json
from datetime import datetime, timezone

from app.core.config import settings
from app.models import Holding, Portfolio, User
from app.services import agent_service, agent_tools


def _make_user_and_portfolio(db_session, username="alice"):
    user = User(username=username, email=f"{username}@test.com", password_hash="hashed")
    db_session.add(user)
    db_session.flush()
    portfolio = Portfolio(user_id=user.id, name=f"{username}'s portfolio")
    db_session.add(portfolio)
    db_session.flush()
    return user, portfolio


def _make_holding(db_session, portfolio_id, ticker, shares, avg_cost_basis_cents=15000, current_price_cents=16000):
    holding = Holding(
        portfolio_id=portfolio_id,
        ticker=ticker,
        shares=shares,
        avg_cost_basis_cents=avg_cost_basis_cents,
        current_price_cents=current_price_cents,
        last_priced_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    db_session.add(holding)
    db_session.flush()
    return holding


class FakeBlock:
    def __init__(self, type, **kwargs):
        self.type = type
        for key, value in kwargs.items():
            setattr(self, key, value)


class FakeResponse:
    def __init__(self, stop_reason, content):
        self.stop_reason = stop_reason
        self.content = content


class FakeMessagesResource:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


class FakeAnthropicClient:
    def __init__(self, responses):
        self.messages = FakeMessagesResource(responses)


def _install_fake_anthropic(monkeypatch, responses):
    fake_client = FakeAnthropicClient(responses)
    monkeypatch.setattr(agent_service, "Anthropic", lambda **kwargs: fake_client)
    return fake_client


def test_analyze_portfolio_dispatches_tool_call_and_returns_final_text(db_session, monkeypatch):
    _, portfolio = _make_user_and_portfolio(db_session)
    _make_holding(db_session, portfolio.id, "AAPL", shares=10)

    responses = [
        FakeResponse("tool_use", [FakeBlock("tool_use", id="t1", name="get_holdings", input={})]),
        FakeResponse("end_turn", [FakeBlock("text", text="Here is your analysis.")]),
    ]
    fake_client = _install_fake_anthropic(monkeypatch, responses)

    result = agent_service.analyze_portfolio(db_session, portfolio.id)

    assert result == "Here is your analysis."
    assert len(fake_client.messages.calls) == 2

    # the second call must carry back a real tool_result for the tool_use_id the model sent
    second_call_messages = fake_client.messages.calls[1]["messages"]
    tool_result_message = second_call_messages[-1]
    assert tool_result_message["role"] == "user"
    tool_result_block = tool_result_message["content"][0]
    assert tool_result_block["type"] == "tool_result"
    assert tool_result_block["tool_use_id"] == "t1"
    payload = json.loads(tool_result_block["content"])
    assert payload[0]["ticker"] == "AAPL"


def test_analyze_portfolio_adds_demo_addendum_only_for_the_demo_portfolio(db_session, monkeypatch):
    _, real_portfolio = _make_user_and_portfolio(db_session, username="alice")
    _, demo_portfolio = _make_user_and_portfolio(db_session, username="demo_portfolio_owner")
    monkeypatch.setattr(settings, "demo_portfolio_id", demo_portfolio.id)

    responses = [FakeResponse("end_turn", [FakeBlock("text", text="Analysis.")])]
    fake_client = _install_fake_anthropic(monkeypatch, responses)
    agent_service.analyze_portfolio(db_session, real_portfolio.id)
    assert "fictional" not in fake_client.messages.calls[0]["system"]

    responses = [FakeResponse("end_turn", [FakeBlock("text", text="Analysis.")])]
    fake_client = _install_fake_anthropic(monkeypatch, responses)
    agent_service.analyze_portfolio(db_session, demo_portfolio.id)
    assert "fictional" in fake_client.messages.calls[0]["system"]


def test_analyze_portfolio_handles_unknown_tool_gracefully(db_session, monkeypatch):
    _, portfolio = _make_user_and_portfolio(db_session)

    responses = [
        FakeResponse("tool_use", [FakeBlock("tool_use", id="t1", name="not_a_real_tool", input={})]),
        FakeResponse("end_turn", [FakeBlock("text", text="Done.")]),
    ]
    fake_client = _install_fake_anthropic(monkeypatch, responses)

    result = agent_service.analyze_portfolio(db_session, portfolio.id)

    assert result == "Done."
    tool_result_block = fake_client.messages.calls[1]["messages"][-1]["content"][0]
    payload = json.loads(tool_result_block["content"])
    assert "Unknown tool" in payload["error"]


def test_analyze_portfolio_stops_at_loop_cap_and_forces_final_answer(db_session, monkeypatch):
    _, portfolio = _make_user_and_portfolio(db_session)
    _make_holding(db_session, portfolio.id, "AAPL", shares=10)

    # The model never stops calling tools on its own -- every response requests another tool call.
    looping_response = FakeResponse(
        "tool_use", [FakeBlock("tool_use", id="loop", name="get_holdings", input={})]
    )
    responses = [looping_response] * agent_service.MAX_TOOL_ROUNDS
    responses.append(FakeResponse("end_turn", [FakeBlock("text", text="Forced final answer.")]))
    fake_client = _install_fake_anthropic(monkeypatch, responses)

    result = agent_service.analyze_portfolio(db_session, portfolio.id)

    assert result == "Forced final answer."
    assert len(fake_client.messages.calls) == agent_service.MAX_TOOL_ROUNDS + 1

    final_call = fake_client.messages.calls[-1]
    assert "tools" not in final_call  # tool access is dropped on the forced final call
    assert final_call["messages"][-1]["content"] == agent_service.FORCE_FINAL_ANSWER_MESSAGE


def test_analyze_portfolio_real_integration(db_session, caplog):
    """Real network call against the configured Anthropic endpoint -- no mocking. Same
    trade-off as the Sprint 3.1 smoke test: this is the thing that actually proves the loop
    works, not just that our mocked control flow is internally consistent. Costs real
    credits per run."""
    _, portfolio = _make_user_and_portfolio(db_session, "integration_user")
    _make_holding(db_session, portfolio.id, "AAPL", shares=10, avg_cost_basis_cents=15000, current_price_cents=18000)

    with caplog.at_level("INFO", logger="app.services.agent_service"):
        result = agent_service.analyze_portfolio(db_session, portfolio.id)

    assert isinstance(result, str)
    assert len(result) > 100
    assert any("Agent tool call:" in message for message in caplog.messages)


def test_call_tool_catches_exceptions_instead_of_propagating(db_session, monkeypatch):
    def raise_error(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setitem(agent_tools.TOOL_FUNCTIONS, "get_holdings", raise_error)

    result = agent_service._call_tool(db_session, portfolio_id=1, name="get_holdings", tool_input={})

    assert "error" in result
    assert "failed unexpectedly" in result["error"]
