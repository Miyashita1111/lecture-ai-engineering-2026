"""第1回 宿題（発展）: 応答時間とトークン数を、複数のモデル・質問で計測する。

使い方:
    uv run python -m scripts.benchmark_ask
    uv run python -m scripts.benchmark_ask --models gemini-3.5-flash-lite gemini-3.5-flash --repeat 3
    uv run python -m scripts.benchmark_ask --interval 0   # 間隔を空けずに連続で呼び、レート制限を確かめる

結果は表（Markdown）で標準出力に、1回ごとの記録は CSV（--csv）に書き出す。
"""

import argparse
import csv
import time

from google import genai
from google.genai import errors

from app.config import DEFAULT_MODEL, get_api_key

QUESTIONS = {
    "一般(短)": "LoRAとは何ですか？一文で答えてください。",
    "一般(長)": "LoRAとは何ですか？",
    "講座固有": "AIE2026の講座の宿題にある「3レベル」とは何ですか？",
}


def measure(client: genai.Client, model: str, question: str) -> dict:
    """1回呼び出して、応答時間とトークン数を返す。エラーならステータスを記録する。"""
    start = time.perf_counter()
    try:
        response = client.models.generate_content(model=model, contents=question)
    except errors.APIError as e:
        return {"seconds": time.perf_counter() - start, "status": e.code}
    seconds = time.perf_counter() - start
    usage = response.usage_metadata
    return {
        "seconds": seconds,
        "status": 200,
        "input": usage.prompt_token_count or 0,
        "output": usage.candidates_token_count or 0,
        "thoughts": usage.thoughts_token_count or 0,
    }


def summarize(rows: list[dict]) -> None:
    """モデル×質問ごとに、成功した回の平均を Markdown の表で表示する。"""
    print("\n| モデル | 質問 | 成功/試行 | 平均時間[s] | 入力 | 出力 | 思考 | 出力tok/s |")
    print("|---|---|---|---|---|---|---|---|")
    keys = dict.fromkeys((r["model"], r["question"]) for r in rows)
    for model, question in keys:
        group = [r for r in rows if r["model"] == model and r["question"] == question]
        ok = [r for r in group if r["status"] == 200]
        if not ok:
            codes = ",".join(str(r["status"]) for r in group)
            print(f"| {model} | {question} | 0/{len(group)} | - | - | - | - | - ({codes}) |")
            continue

        def avg(k: str) -> float:
            return sum(r[k] for r in ok) / len(ok)

        speed = (avg("output") + avg("thoughts")) / avg("seconds")
        print(
            f"| {model} | {question} | {len(ok)}/{len(group)} | {avg('seconds'):.2f} "
            f"| {avg('input'):.0f} | {avg('output'):.0f} | {avg('thoughts'):.0f} | {speed:.0f} |"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="応答時間とトークン数を計測する")
    parser.add_argument("--models", nargs="+", default=[DEFAULT_MODEL, "gemini-3.5-flash"])
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--interval", type=float, default=5.0, help="呼び出しの間隔[秒]")
    parser.add_argument("--csv", default="lectures/01/benchmark.csv")
    args = parser.parse_args()

    client = genai.Client(api_key=get_api_key())
    rows = []
    for model in args.models:
        for label, question in QUESTIONS.items():
            for i in range(args.repeat):
                r = measure(client, model, question)
                r.update(model=model, question=label, trial=i + 1)
                rows.append(r)
                print(f"{model} / {label} #{i + 1}: status={r['status']} {r['seconds']:.2f}s")
                time.sleep(args.interval)

    fields = ["model", "question", "trial", "status", "seconds", "input", "output", "thoughts"]
    with open(args.csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    summarize(rows)


if __name__ == "__main__":
    main()
