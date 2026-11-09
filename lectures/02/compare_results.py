"""宿題（基礎）：2 つの result.json を並べて Markdown の比較表を出す。

使い方:
    python lectures/02/compare_results.py result_ep20.json result_ep5.json

Colab のセクション 7 の後に次のセルを足して実行しておくと、
最終 loss と学習時間も result.json に入る（元の result.json には入っていないため）。

    hist = trainer.state.log_history
    result["train"] = {
        "final_loss": [h["loss"] for h in hist if "loss" in h][-1],
        "train_seconds": round(hist[-1].get("train_runtime", float("nan")), 1),
        "global_step": trainer.state.global_step,
    }
    (WORK / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(result["train"])
"""

import json
import sys
from pathlib import Path


def load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def fmt(x) -> str:
    if x is None:
        return "—"
    if isinstance(x, float):
        return f"{x:.3g}" if abs(x) < 1e-2 else f"{x:.3f}"
    return str(x)


def main(paths: list[str]) -> None:
    results = [load(p) for p in paths]
    names = [Path(p).stem for p in paths]

    rows = [
        ("num_train_epochs", lambda r: r["config"]["num_train_epochs"]),
        ("lr", lambda r: r["config"]["lr"]),
        ("lora_r", lambda r: r["config"]["lora_r"]),
        ("ステップ数", lambda r: r.get("train", {}).get("global_step")),
        ("学習前 format_rate", lambda r: r["before"]["format_rate"]),
        ("学習前 content_rate", lambda r: r["before"]["content_rate"]),
        ("学習後 format_rate", lambda r: r["after"]["format_rate"]),
        ("学習後 content_rate", lambda r: r["after"]["content_rate"]),
        ("学習後 both_rate", lambda r: r["after"].get("both_rate")),
        ("最終 loss", lambda r: r.get("train", {}).get("final_loss")),
        ("学習時間 [秒]", lambda r: r.get("train", {}).get("train_seconds")),
        ("退行した質問数", lambda r: len(r.get("regressed", []))),
    ]

    print("| 項目 | " + " | ".join(names) + " |")
    print("|---|" + "---|" * len(names))
    for label, get in rows:
        cells = []
        for r in results:
            try:
                cells.append(fmt(get(r)))
            except (KeyError, TypeError):
                cells.append("—")
        print(f"| {label} | " + " | ".join(cells) + " |")

    print("\n### 知識を問う質問（学習後の分類）")
    for name, r in zip(names, results):
        print(f"- {name}: " + ", ".join(f"{k['質問']}（{k['学習前の分類']} → {k['学習後の分類']}）"
                                        for k in r.get("knowledge", [])))
    for name, r in zip(names, results):
        if r.get("regressed"):
            print(f"\n退行（{name}）: {r['regressed']}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(sys.argv[1:])
