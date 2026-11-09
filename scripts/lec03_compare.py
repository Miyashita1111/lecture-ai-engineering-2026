"""第3回 宿題（基礎）: INSTRUCTIONS や docstring を1か所だけ変え、ツールの呼ばれ方を比べる。

使い方（Codespaces など GEMINI_API_KEY がある環境で）:
    uv run python -m scripts.lec03_compare                 # 各条件を2回ずつ実行
    uv run python -m scripts.lec03_compare --repeat 3

結果は画面に出し、同じ内容を lectures/03/basic_results.md に書き出す。
変えるのは1条件につき1か所だけ:
    V0 基準     : app/agent.py の INSTRUCTIONS と app/tools.py の docstring そのまま
    V1 指示削除 : INSTRUCTIONS から「必ず search_glossary で用語集を確認する」の行を消す
    V2 docstring: search_glossary の「用語を1つだけ入れる」を「まとめて入れてよい」に変える
"""

import argparse
import time
from pathlib import Path

from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import ToolCallPart

from app import tools
from app.agent import INSTRUCTIONS, build_model
from app.config import MODEL

OUT = Path(__file__).resolve().parent.parent / "lectures" / "03" / "basic_results.md"

QUESTIONS = [
    "AIE2026の講座で使う「lecNN-start タグ」とは何ですか？",
    "LoRAとQLoRAの違いは？",
]

SEARCH_LINE = "- 用語や講座に固有のことを答える前に、必ず search_glossary で用語集を確認する。\n"
assert SEARCH_LINE in INSTRUCTIONS, "INSTRUCTIONS が変わっています。SEARCH_LINE を合わせてください"

SEARCH_DOC_MANY = """講座の用語集から用語を検索し、定義と、どの回で扱うかを返す。

AIエンジニアリングの用語や、この講座（AIE2026）に固有の言葉について
答える前に使うこと。query には調べたい用語をまとめて入れてよい（例: "LoRA QLoRA"）。
"""


def build_agent(instructions: str, search_description: str | None = None) -> Agent:
    """演習のエージェントと同じツールで組み立てる（保存ツールは承認が要るので外す）。"""
    agent = Agent(instructions=instructions)
    agent.tool_plain(tools.search_glossary, description=search_description)
    agent.tool_plain(tools.get_lecture_summary)
    agent.tool_plain(tools.make_quiz)
    return agent


VARIANTS = {
    "V0 基準": build_agent(INSTRUCTIONS),
    "V1 指示削除": build_agent(INSTRUCTIONS.replace(SEARCH_LINE, "")),
    "V2 docstring": build_agent(INSTRUCTIONS, SEARCH_DOC_MANY),
}


def run_once(agent: Agent, question: str, model, retries: int = 3):
    for attempt in range(retries):
        try:
            return agent.run_sync(question, model=model)
        except ModelHTTPError as e:
            if e.status_code not in (429, 503) or attempt == retries - 1:
                raise
            print(f"  ({e.status_code} のため 30 秒待って再実行)")
            time.sleep(30)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repeat", type=int, default=2, help="各条件の実行回数（回答は揺れるので2回以上）")
    parser.add_argument("--wait", type=float, default=5.0, help="実行の間隔（秒）。レート制限よけ")
    args = parser.parse_args()

    model = build_model()
    lines = [f"# 第3回 宿題（基礎）比較結果\n\nmodel: `{MODEL}` / 各条件 {args.repeat} 回\n"]
    rows = ["| 条件 | 質問 | 回 | ツール呼び出し（引数） | requests |", "|---|---|---|---|---|"]
    details = []

    for question in QUESTIONS:
        for name, agent in VARIANTS.items():
            for i in range(1, args.repeat + 1):
                print(f"\n=== {name} / {question} / {i} 回目 ===")
                result = run_once(agent, question, model)
                calls = [
                    f"{p.tool_name}({p.args})"
                    for m in result.all_messages() for p in m.parts if isinstance(p, ToolCallPart)
                ]
                usage = result.usage
                print("[tool call] " + ("; ".join(calls) or "なし"))
                print(f"[usage] {usage}")
                print(result.output)
                rows.append(
                    f"| {name} | {question} | {i} | {'<br>'.join(calls) or 'なし'} | {usage.requests} |"
                )
                details.append(f"### {name} / {question} / {i} 回目\n\n{result.output}\n")
                time.sleep(args.wait)

    lines += ["## ツールの呼ばれ方\n", "\n".join(rows), "\n## 回答の全文\n", "\n".join(details)]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n書き出しました: {OUT.relative_to(OUT.parents[2])}")


if __name__ == "__main__":
    main()
