# 第3回 解答

## 演習

- 第1回（素のLLM）とエージェントの回答の違い：（Codespaces で実行して記入）
- `--trace` で見えたツール呼び出し（ツール名と引数）：
  - 「lecNN-start タグとは？」→ `search_glossary({'query': 'lecNN-start タグ'})` を1回。用語集の定義どおり「各回の演習開始時点のコードに付けた Git タグ（例: lec03-start）」と答え、最後に「関連する回：第1回」を付けた
  - 「LoRAとQLoRAの違いは？」→ `search_glossary({'query': 'LoRA'})` と `search_glossary({'query': 'QLoRA'})` を同時に2回
  - 「第2回の内容から確認問題を1問出して」→ `make_quiz({'lecture': 2})`。問題（「LoRA」とは？）だけを出し、答えは見せなかった
- 1つの質問での LLM 呼び出し回数（`requests`）：どれも **2**（ツールを選ぶ1回＋結果を見て答える1回）。LoRA/QLoRA のようにツールを2回呼んでも、同じ応答の中で並列に呼ぶので `requests` は2のまま（`tool_calls` は2）
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
- 結果（Codespaces での実行）：

```
$ uv run python -m app.agent --trace "今日学んだLoRAとQLoRAの違いを学習記録に保存して"

[approval] save_learning_log を実行しようとしています
  content: ## 学んだ内容: LoRAとQLoRAの違い ...（モデルがまとめた本文）
  title: LoRAとQLoRAの違い
実行しますか？ [y/N] y
LoRAとQLoRAの違いについての学習記録を保存しました。...

--- trace ---
[tool call]   search_glossary({'query': 'LoRA'})
[tool call]   search_glossary({'query': 'QLoRA'})
[tool return] search_glossary -> ...
[tool return] search_glossary -> ...
[tool call]   save_learning_log({'content': '...', 'title': 'LoRAとQLoRAの違い'})
[tool return] save_learning_log -> 保存しました: learning_log/20261109-061421.md
[usage] RunUsage(input_tokens=3199, output_tokens=305, requests=3, tool_calls=3)
```

  - モデルは保存の前に用語集で LoRA と QLoRA を調べ、その定義をもとに本文を書いてから `save_learning_log` を呼んだ。保存の内容が用語集に沿ったものになる
  - 保存しようとした時点で実行が止まり、title と content を見てから `y` を押せた。`y` の後に続きが実行され、ファイルが作られた
  - `requests` は3（検索→保存の呼び出し→承認後に回答）。承認をはさんでも、`usage` を引き継いだので最初からの合計になっている
  - 拒否（`N`）の流れは TestModel のテストで確認した

### 基礎：INSTRUCTIONS / docstring を1か所だけ変えて比べる

- やったこと：`scripts/lec03_compare.py` で3条件を同じ質問で2回ずつ実行し、ツール呼び出しと `requests` を表にした（全結果は `lectures/03/basic_results.md`）
  - V0 基準：そのまま
  - V1：INSTRUCTIONS から「必ず search_glossary で用語集を確認する」の行を消す
  - V2：search_glossary の docstring の「用語を1つだけ入れる」を「まとめて入れてよい（例: "LoRA QLoRA"）」に変える
- 結果（model: gemini-3.5-flash-lite、各2回）：

| 条件 | 質問 | ツール呼び出し | requests | 入力トークン |
|---|---|---|---|---|
| V0 基準 | lecNN-start タグ | `search_glossary('lecNN-start タグ')` ×1（2回とも） | 2 | 1103 |
| V1 指示削除 | lecNN-start タグ | `search_glossary('lecNN-start タグ')` ×1（2回とも） | 2 | 1055 |
| V2 docstring | lecNN-start タグ | `search_glossary('lecNN-start タグ')` ×1（2回とも） | 2 | 1109 |
| V0 基準 | LoRAとQLoRA | `search_glossary('LoRA')` と `('QLoRA')` ×2（2回とも） | 2 | 1516 |
| V1 指示削除 | LoRAとQLoRA | `search_glossary('LoRA')` と `('QLoRA')` ×2（2回とも） | 2 | 1468 |
| V2 docstring | LoRAとQLoRA | `search_glossary('LoRA QLoRA')` ×1（2回とも） | 2 | 1215 |

  - **V1（「必ず search_glossary」を削除）**：予想に反して、2問×2回とも変化なし。指示がなくても検索してから答え、回答の内容も「関係する回」の表記も同じだった。docstring に「この講座（AIE2026）に固有の言葉について答える前に使うこと」と書いてあり、質問にも「AIE2026」が入っているので、INSTRUCTIONS の行がなくても docstring だけで検索する判断ができたと考えられる。入力トークンはこの1行の分だけ減った（−48）
  - **V2（docstring を「まとめて入れてよい」に変更）**：はっきり変わった。2回とも `search_glossary` を1回だけ、引数 `'LoRA QLoRA'` で呼んだ。用語集の検索は空白を除いた部分一致なので両方ヒットし、回答の質はV0と同じだった。V0 では `'LoRA'` の検索結果に QLoRA も部分一致で入り、`'QLoRA'` の検索と重複していたので、V2 の方が入力トークンが約20%少ない（1516→1215）
  - どの条件でも `requests` は2で、ツールの呼び出し回数が違っても LLM の呼び出し回数は変わらなかった
  - 全文は `lectures/03/basic_results.md`

### 気づき・疑問

- モデルがツールの「引数の作り方」を決めるときは docstring の例と書き方をそのまま真似る（V2 では例の `"LoRA QLoRA"` と同じ形で呼んだ）。一方、「使うかどうか」は INSTRUCTIONS と docstring のどちらか一方に書いてあれば十分なことがあった。指示を二重に書くと、片方を消しても効果が見えず、どちらが効いているのか分からなくなる
- `search_glossary` は空白を除いて部分一致するため、`"LoRA QLoRA"` や `"LoRAとQLoRA"` でも両方ヒットする。docstring では「1つだけ」と言っているのに、実装はまとめた検索にも対応している。docstring（モデルへの約束）と実装の挙動がずれていると、比較実験の結果の解釈も変わる
- 承認ツールを1つ足すと `output_type` が変わり、既存のテストや「出力は必ず str」という前提が崩れる。安全のための仕組みが、呼び出し側のコード全体に影響する
- 確認問題では、答えはツールの結果としてモデルに渡っているのに、INSTRUCTIONS どおり問題だけを出した。ただし CLI は1回ごとに会話がリセットされるので、「答えを教えて」と続けて聞いても前の問題を覚えていない。会話の履歴を持たせるかどうかもエージェントの設計の一部だと感じた
- 疑問：各条件2回だけでは、揺れがないのか、たまたま同じだったのか判断しにくい。どのくらいの回数で「変わらない」と言えるのか
- 実行中に一度 503（混雑）が出た。スクリプトで30秒待って再実行するようにしておいたので、止まらずに最後まで実行できた
