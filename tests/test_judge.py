"""第4回: 採点（app/judge.py）の配線テスト。API キーは使わない。

--model test と同じ偽モデル（規則で判定する FunctionModel）で、評価セット 10 件の
「採点 → 人のラベルとの比較 → 要確認・不一致の集計」が通ることを確かめる。
"""

from app import judge
from app.judge import (
    ALL_CRITERIA,
    DEFAULT_CASES,
    DEFAULT_RUBRIC,
    build_judge,
    build_test_model,
    check_lecture_mark,
    judge_cases,
    load_labels,
    overall,
    read_jsonl,
    summarize,
)

INSTRUCTOR_LABELS = judge.ROOT / "lectures" / "04" / "reference" / "labels_instructor.jsonl"


def test_lecture_mark_is_checked_by_code():
    assert check_lecture_mark("LoRA は…\n\n関係する回：第2回") == "pass"
    assert check_lecture_mark("第2回で扱う LoRA は…\n\n以上です。") == "fail"  # 末尾に無ければ fail
    assert check_lecture_mark("") == "fail"


def test_overall_requires_all_required_criteria():
    base = {"grounding": "pass", "scope": "pass", "hint": "pass", "lecture_mark": "pass", "clarity": "fail"}
    assert overall(base) == "pass"  # 分かりやすさは総合に入れない
    assert overall({**base, "hint": "fail"}) == "fail"
    assert overall({**base, "grounding": "unsure"}) == "unsure"


def test_cases_and_rubric_are_consistent():
    cases = read_jsonl(DEFAULT_CASES)
    assert len(cases) == 10
    assert len({c["id"] for c in cases}) == 10
    for c in cases:
        assert c["question"] and c["answer"] and c["reference"]["expected"]
    rubric = DEFAULT_RUBRIC.read_text(encoding="utf-8")
    for key, name in ALL_CRITERIA[:-1]:  # 回の表示はコードで判定するので rubric には書かない
        assert f"{name}（{key}）" in rubric
    labels = load_labels(INSTRUCTOR_LABELS)
    assert set(labels) == {c["id"] for c in cases}


def test_judge_pipeline_with_fake_model():
    cases = read_jsonl(DEFAULT_CASES)
    labels = load_labels(INSTRUCTOR_LABELS)
    agent = build_judge(build_test_model(), DEFAULT_RUBRIC.read_text(encoding="utf-8"))

    verdicts = judge_cases(agent, cases)
    assert set(verdicts) == {c["id"] for c in cases}
    for v in verdicts.values():
        for key, _ in ALL_CRITERIA:
            assert v[key]["verdict"] in ("pass", "fail", "unsure")
            assert v[key]["reason"]

    summary = summarize(cases, verdicts, labels)
    assert summary["n"] == 10
    # unsure にした項目は一致率の分母から外れ、要確認に入る
    excluded = sum(p["total"] - p["compared"] for p in summary["per_criterion"].values())
    assert excluded == len(summary["review"])
    assert summary["coverage"]["covered"] + len({r["id"] for r in summary["review"]}) == 10
    for m in summary["mismatches"]:
        assert m["kind"] in ("見逃し", "過検出")


# --- 第4回 宿題（基礎）: 判定の順序を入れ替える ---


def test_verdict_first_swaps_field_order_in_schema():
    reason_first = list(judge.CriterionVerdict.model_json_schema()["properties"])
    verdict_first = list(judge.CriterionVerdictFirst.model_json_schema()["properties"])
    assert reason_first == ["reason", "verdict"]
    assert verdict_first == ["verdict", "reason"]


def test_verdict_first_pipeline_with_fake_model():
    cases = read_jsonl(DEFAULT_CASES)
    rubric = DEFAULT_RUBRIC.read_text(encoding="utf-8")
    normal = judge_cases(build_judge(build_test_model(), rubric), cases)
    swapped = judge_cases(build_judge(build_test_model(), rubric, verdict_first=True), cases)
    assert swapped == normal  # 偽モデルは順序に関係なく同じ規則で判定するので、集計の配線だけを確かめる


def test_verdict_first_rewrites_order_in_rubric():
    rubric = DEFAULT_RUBRIC.read_text(encoding="utf-8")
    assert "先に理由を書いてから判定を決める" in rubric
    text = judge.judge_instructions(rubric, verdict_first=True)
    assert "先に理由を書いてから判定を決める" not in text
    assert "先に判定を決めてから理由を書く" in text
    assert "先に理由を書いてから判定を決める" in judge.judge_instructions(rubric)  # 既定は変えない
