# 第3回 解答

## 演習

- 第1回（素のLLM）とエージェントの回答の違い：（Codespaces で実行して記入）
- `--trace` で見えたツール呼び出し（ツール名と引数）：（Codespaces で実行して記入）
- 1つの質問での LLM 呼び出し回数（`requests`）：（Codespaces で実行して記入）
- 追加したツールと、docstring に書いた説明：
  - `make_quiz(lecture: int)`：指定した回の用語集から1語をランダムに選び、「〇〇とはどのような意味ですか？」という問題と答え（用語集の定義）を JSON で返す
  - docstring：「『第2回の確認問題を出して』『復習のクイズがほしい』のように、理解度を確かめる問題を求められたときに使う。用語の意味を説明するだけなら search_glossary を使う」。似た用途の `search_glossary` と使い分けられるよう、「使わない場面」も書いた
  - `INSTRUCTIONS` に「答えはすぐに見せず、まず問題だけを出す」を追加した

## 宿題

- 取り組んだレベル：実装（＋基礎）

### 実装：保存の前に確認を挟む `save_learning_log`

- やったこと：
  - `app/tools.py` に `save_learning_log(title, content)` を追加。`learning_log/YYYYMMDD-HHMMSS.md` に Markdown で保存する
    - ファイル名に `title` を使わない（`../../etc/passwd` のような title でもフォルダの外に書かれない）
    - 同じ秒に2回保存しても上書きしない（`-2` などを付ける）
    - `learning_log/` は個人の記録なので `.gitignore` 済み
  - `app/agent.py` で `requires_approval=True` を付けて登録し、`output_type=[str, DeferredToolRequests]` にした
  - CLI に `run_with_approval()` を追加。`DeferredToolRequests` が返ったらツール名と引数を表示して `[y/N]` で聞き、`DeferredToolResults` に `True` か `ToolDenied(...)` を入れて `message_history` と一緒に再実行する。承認待ちが続く限りループする
  - 再実行時に `usage=result.usage` を渡し、`[usage] requests` が最初の質問からの合計になるようにした
  - `INSTRUCTIONS` に「頼まれていないのに保存しない」を追加
- テスト（TestModel、APIキー不要）：`uv run pytest -q` → **19 passed**
  - 承認前は `DeferredToolRequests` で止まり、ファイルが作られない
  - 承認すると1ファイル保存され、ツールの結果がモデルに戻る
  - 拒否するとファイルは作られず、「許可しませんでした」がモデルに伝わる
  - `approve` 関数を引数で差し替えられるようにして、`input()` を使わずに承認・拒否の両方を試せるようにした
  - 既存テスト `test_base_tools_are_registered_and_called` は、TestModel が全ツールを呼ぶため承認待ちのツールの結果が返らず失敗した。承認が必要なツールを数から除くよう直した
- 結果（Codespaces での実行）：（記入）

```
uv run python -m app.agent --trace "今日学んだLoRAとQLoRAの違いを学習記録に保存して"
```

### 基礎：INSTRUCTIONS / docstring を1か所だけ変えて比べる

- やったこと：`scripts/lec03_compare.py` で3条件を同じ質問で2回ずつ実行し、ツール呼び出しと `requests` を表にした（全結果は `lectures/03/basic_results.md`）
  - V0 基準：そのまま
  - V1：INSTRUCTIONS から「必ず search_glossary で用語集を確認する」の行を消す
  - V2：search_glossary の docstring の「用語を1つだけ入れる」を「まとめて入れてよい（例: "LoRA QLoRA"）」に変える
- 結果：（`basic_results.md` の表から記入）
  - V1 で `lecNN-start タグ` の質問：
  - V2 で `LoRAとQLoRAの違いは？` の `search_glossary` の回数と引数：

### 気づき・疑問

- `search_glossary` は空白を除いて部分一致するため、`"LoRA QLoRA"` や `"LoRAとQLoRA"` でも両方ヒットする。docstring では「1つだけ」と言っているのに、実装はまとめた検索にも対応している。docstring（モデルへの約束）と実装の挙動がずれていると、比較実験の結果の解釈も変わる
- 承認ツールを1つ足すと `output_type` が変わり、既存のテストや「出力は必ず str」という前提が崩れる。安全のための仕組みが、呼び出し側のコード全体に影響する
- （実行結果を見て追記）
