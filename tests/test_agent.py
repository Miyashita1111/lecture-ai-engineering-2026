"""エージェントの配線テスト。

TestModel は実際のLLMを呼ばない偽モデルで、登録されたツールを全部呼んでから
ダミーの回答を返す。APIキーも利用枠も使わずに、
「ツールが登録され、呼ばれ、結果がモデルに戻るか」を確かめられる。
"""

import pytest
from pydantic_ai import DeferredToolRequests
from pydantic_ai.messages import ToolCallPart, ToolReturnPart
from pydantic_ai.models.test import TestModel

from app import tools
from app.agent import agent, run_with_approval

BASE_TOOLS = {"search_glossary", "get_lecture_summary"}
APPROVAL_TOOLS = {"save_learning_log"}


def _parts(result, kind):
    return [p for m in result.all_messages() for p in m.parts if isinstance(p, kind)]


def test_base_tools_are_registered_and_called():
    model = TestModel()
    with agent.override(model=model):
        result = agent.run_sync("LoRAとは？")

    offered = {t.name for t in model.last_model_request_parameters.function_tools}
    assert BASE_TOOLS <= offered  # 演習でツールを足しても壊れないよう「含む」で判定

    called = {p.tool_name for p in _parts(result, ToolCallPart)}
    assert BASE_TOOLS <= called
    # 承認が必要なツール（第3回 宿題）は承認待ちで止まり、結果が返らないので数えない
    immediate_calls = [p for p in _parts(result, ToolCallPart) if p.tool_name not in APPROVAL_TOOLS]
    assert len(_parts(result, ToolReturnPart)) == len(immediate_calls)
    assert result.output


def test_glossary_result_reaches_the_model():
    model = TestModel(call_tools=["search_glossary"])
    with agent.override(model=model):
        result = agent.run_sync("RAGとは？")
    returns = _parts(result, ToolReturnPart)
    assert returns and returns[0].tool_name == "search_glossary"


# --- 第3回 演習: make_quiz ---


def test_make_quiz_is_offered_and_returns_question():
    model = TestModel(call_tools=["make_quiz"])
    with agent.override(model=model):
        result = agent.run_sync("第2回の確認問題を出して")
    returns = _parts(result, ToolReturnPart)
    assert returns and returns[0].tool_name == "make_quiz"


# --- 第3回 宿題（実装）: save_learning_log は保存の前に承認を挟む ---


@pytest.fixture
def log_dir(tmp_path, monkeypatch):
    """本物の learning_log/ を汚さないよう、保存先を一時フォルダに差し替える。"""
    monkeypatch.setattr(tools, "LOG_DIR", tmp_path / "learning_log")
    return tmp_path / "learning_log"


def _save_model():
    return TestModel(call_tools=["save_learning_log"])


def test_save_stops_for_approval_without_writing(log_dir):
    with agent.override(model=_save_model()):
        result = agent.run_sync("今日の学びを記録して")

    assert isinstance(result.output, DeferredToolRequests)
    assert [c.tool_name for c in result.output.approvals] == ["save_learning_log"]
    assert not log_dir.exists()  # 承認前にはファイルを書かない


def test_save_runs_after_approval(log_dir):
    asked = []

    def approve(tool_name, args):
        asked.append(tool_name)
        return True

    result = run_with_approval(agent, "今日の学びを記録して", _save_model(), approve=approve)

    assert asked == ["save_learning_log"]
    assert isinstance(result.output, str)
    files = list(log_dir.glob("*.md"))
    assert len(files) == 1
    returns = [p for p in _parts(result, ToolReturnPart) if p.tool_name == "save_learning_log"]
    assert "保存しました" in str(returns[0].content)


def test_save_is_skipped_when_denied(log_dir):
    result = run_with_approval(agent, "今日の学びを記録して", _save_model(), approve=lambda *_: False)

    assert isinstance(result.output, str)
    assert not log_dir.exists()
    returns = [p for p in _parts(result, ToolReturnPart) if p.tool_name == "save_learning_log"]
    assert "許可しませんでした" in str(returns[0].content)  # 拒否されたことがモデルに伝わる
