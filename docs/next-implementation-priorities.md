# RanD 実装優先順位メモ（3層）

## 方針

現状の `RanD` は、ルートリポジトリとして導入層と実行層を束ね、`research-runtime` が source preset に従って収集・正規化・評価・state 保存を行い、成果物を `research-runtime/runs/<run_id>/` に残す構成になっている。導入対象 OSS としては `open_deep_research`、`llm-guard`、`kestra`、`pulse-kestra`、`agent-taskstate`、`experiment-gate`、`insight-agent`、`memx-resolver`、`tracker-bridge-materials`、`Roadmap-Design-Skill` などが列挙されており、R&D エージェントの主要部品そのものはすでに揃っている。つまり、いま不足しているのは主に「部品」ではなく「本番配線」である。 ([GitHub][1])

優先順位は、賢さを増すことより先に、**常時運転できること、壊れても戻ること、外界へ返せること**を重視する。特に `pulse-kestra` は Phase 1 の bridge 実装完了として、Misskey webhook 受信から Kestra flow 起動までの基盤は動作可能とされる一方、Phase 2 以降の未実装として durable dedupe、heartbeat flow 本体、manual replay と未通知再送、stuck task 回復を含む retry 制御、複数 worker chaining が明記されている。したがって最優先はここを太くすることになる。 ([GitHub][2])

---

## 第1層: 制御面を完成させる

### 優先度

**最優先**

### 主対象 OSS

* `pulse-kestra`
* `kestra`
* `agent-taskstate`
* `llm-guard`

### 実装すること

`pulse-kestra` を「Misskey webhook を受ける薄い HTTP サーバ」から、**本番常用できる制御ハブ**に引き上げる。README 上では想定コンポーネントとして `bridge`、`kestra flows`、`taskstate gateway`、`worker adapters`、`reply notifier` が置かれているため、この構成を前提に、入口統一・状態管理・再送・復旧を一体化させる。 ([GitHub][2])

実装対象は以下のとおり。

1. **heartbeat flow 本体の実装**
   mention 起点だけではなく、定期巡回・自律調査・自律投稿の駆動源を作る。これにより RanD 全体が「聞かれたときだけ動く系」から「自発的に回る系」に変わる。 ([GitHub][2])

2. **manual replay と未通知再送導線の実装**
   投稿失敗、途中停止、通知漏れが起きた場合に再送できる導線を作る。これがないと Misskey や tracker への反映が偶然性に依存する。 ([GitHub][2])

3. **stuck task 回復を含む retry 制御の実装**
   長時間系 R&D ワークフローでは、API 失敗・途中停止・worker 固着を前提にすべきであり、失敗時の再試行と再開点復元を標準動作にする。 ([GitHub][2])

4. **durable dedupe の実装**
   同一入力や同一話題で二重起票・二重投稿が起きないよう、イベントレベルの永続的重複排除を入れる。RanD 側には URL または title ベースの重複除去があるが、入口でも抑える必要がある。 ([GitHub][2])

5. **複数 worker chaining の実装**
   単発 worker 呼び出しではなく、Kestra 上で `research -> insight -> gate -> sync -> notify` の連鎖を正規ルートとして固定する。これにより「ワークフローを束ねる母艦」としての RanD が完成に近づく。 ([GitHub][2])

6. **`agent-taskstate` を正本にした run / state / decision 管理の徹底**
   `agent-taskstate` は long-running work 向けの structured Task/State/Decision/Question/Run/ContextBundle 管理を掲げているため、会話履歴や一時 JSON を正本にせず、再開点と通知状態を含めて state backend へ集約する。 ([GitHub][3])

7. **`llm-guard` の入口適用だけでなく出口適用**
   README 上では RanD の導入対象として「外部入力や出力候補に対するガード層」とされているため、Misskey 投稿前・tracker 同期前にも必ずガードを挟む。 ([GitHub][1])

### この層の狙い

この層の目的は、RanD を「研究用の寄せ集め」から **常時運転するエージェント基盤**へ上げることにある。ここができていない状態で第2層・第3層を足しても、賢くはなるが運用できない。 ([GitHub][2])

---

## 第2層: 研究・判断面を多段化する

### 優先度

**第2優先**

### 主対象 OSS

* `open_deep_research`
* `memx-resolver`
* `insight-agent`
* `experiment-gate`
* `strategy-guided-policy-prompt`

### 実装すること

この層では、現在の直列パイプラインを **多段の研究ループ**へ引き上げる。`insight-agent` は公開入口 `run()` を持ち、外部入力を `InsightRequest` に正規化し、既定出力を `output_schema_v2` に揃えているため、調査結果の構造化抽出器として十分に安定している。`experiment-gate` も 8評価軸のスコアリング、go/hold/no_go の三値判定、次アクション推奨を備えており、仮説評価エージェントとして役割が明確である。つまり不足は性能ではなく、往復運動である。 ([GitHub][4])

実装対象は以下のとおり。

1. **探索 worker の強化**
   `open_deep_research` を広域探索の中核にし、論文・AIニュース・技術記事・OSS 更新を preset 単位で巡回させる。これは RanD の README でも「調査と探索の中核」と明記されている。 ([GitHub][1])

2. **文脈解決 worker の追加**
   `memx-resolver` を、単なる journal 補助ではなく、既読判定・関連履歴参照・過去結論との衝突確認・近縁テーマ接続の層として使う。これにより毎回ゼロから考えない。RanD では `memx-resolver` を参照知識、読了記録、補助コンテキストの層と位置づけている。 ([GitHub][1])

3. **洞察 worker の本格接続**
   `insight-agent` に対して収集済み bundle を渡し、`claims / assumptions / limitations / insights / open_questions` を抽出する。特に `open_questions` を次段の再探索クエリへ戻すことで、要約で終わらない「追跡検索」を成立させる。 `insight-agent` は文書やソースから insight を抽出する層として RanD に組み込まれている。 ([GitHub][1])

4. **反証 worker の追加**
   洞察結果をそのまま gate に送るのではなく、反例・不足根拠・依存リスクを集める専用段を挟む。これは `experiment-gate` が dependency_risk や operational_risk を評価軸に含み、skeptical reviewer を持つ設計と整合する。 ([GitHub][5])

5. **gate worker の昇格**
   `experiment-gate` を終端評価器ではなく、**研究ループの関門**として扱う。8評価軸、閾値、persona を活かし、go/hold/no_go だけでなく `run_minimal_probe / gather_evidence / defer / reject` の次アクションをワークフロー分岐に直結させる。 ([GitHub][5])

6. **planning worker の接続**
   gate の結果を `Roadmap-Design-Skill` と `ai-product-requirement-document` に流し、Go 判定のものだけを計画や PRD に昇格させる。RanD ではこれらが「計画へ落とす層」「実装ハンドオフ用の PRD 出口」として明示されている。 ([GitHub][1])

### この層の狙い

この層の目的は、RanD を「検索して要約する機械」ではなく、**検索し、洞察し、反証し、評価し、次アクションまで切る機械**へ変えることにある。研究の質を決めるのはモデル単体ではなく、この往復構造である。 ([GitHub][4])

---

## 第3層: 外界反映面を完成させる

### 優先度

**第3優先**

### 主対象 OSS

* `pulse-kestra`
* Misskey
* `tracker-bridge-materials`
* `Roadmap-Design-Skill`
* `ai-product-requirement-document`

### 実装すること

この層では、RanD の成果物を **実際の外部アクション**へ変換する。RanD の README では `research-runtime/runs/<run_id>/` に成果物が保存されること、`tracker-bridge-materials` が GitHub Issues / Jira / Linear / Backlog などへの外部同期層であること、`Roadmap-Design-Skill` と PRD 出口が存在することが示されている。つまり、出口候補はすでに揃っている。足りないのは常用経路としての接続である。 ([GitHub][1])

実装対象は以下のとおり。

1. **Misskey mention 返信の完全閉路化**
   `pulse-kestra` の `reply notifier` を RanD の `report.json` / `gate.json` / 要約出力とつなぎ、mention を受けたら必ず返す経路を完成させる。 `pulse-kestra` は Misskey 返信と通知を想定コンポーネントとして持つ。 ([GitHub][2])

2. **Misskey heartbeat 自律投稿の実装**
   Phase 2 以降の未実装とされる heartbeat flow 本体を使い、AIニュース要約、論文監視、Go 判定トピック通知、中間進捗、エラー通知などを自律投稿させる。これにより「対話相手」だけでなく「能動的広報面」を持てる。 ([GitHub][2])

3. **tracker 同期の本実装**
   `tracker-bridge-materials` を payload 保存止まりにせず、GitHub Issues / Jira / Linear / Backlog へ実送信する。Go 判定は実験タスクへ、Hold 判定は evidence gap 付きの保留タスクへ送る。RanD はこれを外部同期層として導入対象に含めている。 ([GitHub][1])

4. **Roadmap / PRD 自動昇格**
   スコア閾値を超えたテーマは自動的に `Roadmap-Design-Skill` と PRD 出口へ流し、設計・実装ハンドオフまでつなげる。これで「考えた」で終わらず「次の仕事」に変換される。 ([GitHub][1])

5. **運用ダッシュボードの追加**
   日次 run 数、未通知数、go/hold/no_go 比率、再送件数、失敗箇所、投稿成功率、トラッカー起票数を可視化する。README ではここはまだ表に出ていないが、本番運用では必須の観測点になる。これは README からの設計上の自然な拡張である。 ([GitHub][1])

### この層の狙い

この層の目的は、RanD を **研究成果を外へ出し、仕事へ変える装置**にすることにある。研究・判定だけでは自己完結だが、Misskey、tracker、roadmap、PRD まで出ると、初めて実務系エージェントになる。 ([GitHub][1])

---

## 優先順位まとめ

### 1. 制御面

`pulse-kestra + kestra + agent-taskstate + llm-guard` を本番運転可能にする。
最初にここをやる。理由は、常時運転、再送、復旧、重複排除がないと他層を足しても運用不能だからである。 ([GitHub][2])

### 2. 研究・判断面

`open_deep_research + memx-resolver + insight-agent + experiment-gate` を多段研究ループ化する。
次にここをやる。理由は、R&D の質は単発推論ではなく、探索・洞察・反証・判定の往復で決まるからである。 ([GitHub][1])

### 3. 外界反映面

`Misskey + tracker-bridge-materials + Roadmap-Design-Skill + PRD` で成果を自動的に仕事へ変える。
最後にここをやる。理由は、外界反映は価値を出す最終段だが、その前に制御面と研究面が固まっていないと不安定なまま広がってしまうからである。 ([GitHub][1])

---

## 結論

RanD はすでに「頭脳の部品」はかなり揃っている。
次に優先して実装すべきなのは、**制御面、研究・判断面、外界反映面**の順であり、順番を崩さないほうが全体最適になる。特に最優先は `pulse-kestra` を中心とした制御面の完成であり、ここを埋めると Misskey・Kestra・state・worker 群がようやく一本の実運転経路になる。 ([GitHub][1])

[1]: https://github.com/RNA4219/RanD "GitHub - RNA4219/RanD: A multi-layer orchestration foundation for R&D agents, connecting research, insight extraction, experiment gating, roadmap design, state management, and external sync into a single execution loop. - 探索・洞察・評価・計画・状態管理をつなぐ、R&Dエージェント向けオーケストレーション基盤。 · GitHub"
[2]: https://github.com/RNA4219/pulse-kestra "GitHub - RNA4219/pulse-kestra: 「Misskey webhook を受ける薄い HTTP サーバ」「LLM Guard の入口判定」「Kestra 起動用の最小コード」だけ · GitHub"
[3]: https://github.com/RNA4219/agent-taskstate "GitHub - RNA4219/agent-taskstate: Agent-first task state backend for long-running work: structured Task/State/Decision/Question/Run/ContextBundle management, SQLite-first, CLI-first, chat-history-free. · GitHub"
[4]: https://github.com/RNA4219/insight-agent "GitHub - RNA4219/insight-agent: A structured insight extraction engine that turns papers and technical documents into claims, assumptions, limitations, problem candidates, insights, and open questions. - 論文・技術資料から課題候補と気づきを構造化抽出する Insight Agent コア · GitHub"
[5]: https://github.com/RNA4219/experiment-gate "GitHub - RNA4219/experiment-gate: A gate agent for evaluating whether a PoC hypothesis is worth trying now. · GitHub"
