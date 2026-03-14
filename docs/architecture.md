# R&D Agent Architecture

## 目的

本アーキテクチャは、複数のOSSを組み合わせて **Research / Insight / Decision / Plan / Execution Hand-off** を一貫して扱う R&D エージェントを構成するための全体像を示す。

このエージェントは単なる検索・要約器ではない。  
外部刺激や定期実行を入口として、情報収集、洞察抽出、仮説評価、計画化、状態保存、外部トラッカー同期までを一つの流れとして扱う。

---

## 設計方針

- **入口は複数でも、内部の実行線は細く保つ**
- **各OSSの責務を分離し、重複責務を減らす**
- **状態・知識・実行・方針を別レイヤに分ける**
- **PoC段階でも、将来の差し替えを前提に境界を明確にする**
- **研究で終わらず、実装やタスク化まで接続する**

---

## 使用するOSS
https://github.com/langchain-ai/open_deep_research
https://github.com/protectai/llm-guard
https://github.com/kestra-io/kestra
https://github.com/RNA4219/pulse-kestra
https://github.com/RNA4219/agent-taskstate
https://github.com/RNA4219/experiment-gate
https://github.com/RNA4219/ai-product-requirement-document
https://github.com/RNA4219/Roadmap-Design-Skill
https://github.com/RNA4219/strategy-guided-policy-prompt
https://github.com/RNA4219/insight-agent
https://github.com/RNA4219/memx-resolver
https://github.com/RNA4219/tracker-bridge-materials
https://github.com/RNA4219/workflow-cookbook

## 全体像

```mermaid
flowchart TD

    A[External Trigger\n- Misskey mention / webhook\n- Cron / heartbeat\n- Manual run] --> B[Pulse / Entry Adapter\npulse-kestra]
    B --> C[Workflow Orchestrator\nKestra]

    C --> D[Input Guard / Safety Layer\nllm-guard]
    D --> E[Research Layer\nopen_deep_research]
    E --> F[Insight Extraction Layer\ninsight-agent]
    F --> G[Experiment Evaluation Layer\nexperiment-gate]
    G --> H[Planning / Structuring Layer\nRoadmap-Design-Skill]

    H --> I[State Store\nagent-taskstate]
    F --> J[Knowledge Access\nmemx-resolver]
    G --> I
    E --> J
    H --> K[External Tracker Sync\ntracker-bridge-materials]

    H --> L[Implementation Handoff\nai-product-requirement-document\nfuture replacement]
    H --> M[Workflow / Execution Recipes\nworkflow-cookbook\nfuture replacement]

    N[Policy / Strategy Layer\nstrategy-guided-policy-prompt] -.guides.-> E
    N -.guides.-> F
    N -.guides.-> G
    N -.guides.-> H

    I --> C
    J --> F
    K --> O[GitHub Issues / Jira / Linear / Backlog]
````

---

## レイヤ構成

### 1. Trigger / Entry Layer

**役割**
外部からの刺激を受け取り、実行要求へ変換する。

**構成**

* `pulse-kestra`
* `Kestra` の schedule / webhook / flow 起動

**入口の例**

* Misskey の mention
* Webhook
* cron / heartbeat
* CLI / 手動実行

**責務**

* 外部イベントの受信
* 実行コンテキストの初期化
* ワークフロー起動

**責務外**

* LLM判断そのもの
* 長期知識の保持
* 仮説の妥当性判定

---

### 2. Guard Layer

**役割**
入力・中間生成物・出力候補に対する安全性と防御の付与。

**構成**

* `llm-guard`

**責務**

* prompt injection 耐性の補助
* 有害入力や漏えいリスクの低減
* 下流に渡す前のガード

**備考**

* ここは「完全防御」ではなく「事故率低減層」
* 特に外部入力起点の自動実行で重要

---

### 3. Research Layer

**役割**
対象領域の探索、検索、ソース収集、候補情報の獲得。

**構成**

* `open_deep_research`

**責務**

* クエリベースの探索
* 候補情報の収集
* 深掘り対象の抽出

**出力**

* 収集ソース
* 調査メモ
* 深掘り候補

**責務外**

* 洞察の最終確定
* Go / Hold / No-Go 判定
* ロードマップ策定

---

### 4. Insight Layer

**役割**
収集した資料や論文、技術文書から、洞察・論点・課題候補・仮説の芽を抽出する。

**構成**

* `insight-agent`
* `memx-resolver`（必要に応じた知識参照）

**責務**

* 文書からの構造化洞察抽出
* 論点整理
* 仮説候補の生成
* 追加で読むべき情報の示唆

**出力**

* insight
* issue candidate
* hypothesis seed
* follow-up question

---

### 5. Experiment Gate Layer

**役割**
抽出された仮説やPoC案に対して、**今試す価値があるか**を判定する。

**構成**

* `experiment-gate`

**責務**

* Go / Hold / No-Go 判定
* 仮説の実行優先度付け
* 「今やる意味」の評価
* 根拠の不足箇所の明示

**出力**

* gate decision
* confidence
* blocking points
* missing evidence

---

### 6. Planning Layer

**役割**
採択した仮説や研究テーマを、実行可能な計画へ落とす。

**構成**

* `Roadmap-Design-Skill`

**責務**

* ロードマップ化
* タスク分解
* マイルストン化
* 検証順序の整理

**出力**

* roadmap
* milestone
* execution plan
* next actions

---

### 7. State Layer

**役割**
実行中・継続中の作業状態を保持する。
「今何をやっていて、何が未解決で、次に何をやるか」を管理する。

**構成**

* `agent-taskstate`

**責務**

* task / state / decision / question / run の保持
* コンテキスト束ね
* 長時間タスクの継続管理
* 再開ポイントの保持

**正本として扱うもの**

* 実行状態
* 意思決定ログ
* 未解決点
* run 履歴

---

### 8. Knowledge Layer

**役割**
長期知識・資料参照・読了記録・ stale 判定などを担う。

**構成**

* `memx-resolver`

**責務**

* 文書解決
* chunk 取得
* 既読/未読管理
* stale 判定
* insight 時の補助参照

**正本として扱うもの**

* 参照知識の取得経路
* 読んだもの / 読んでいないもの
* 参照時の補助コンテキスト

---

### 9. External Sync Layer

**役割**
内部状態や計画を外部トラッカーへ接続する。

**構成**

* `tracker-bridge-materials`

**接続先候補**

* GitHub Issues
* Jira
* Linear
* Backlog

**責務**

* 内部状態の外部反映
* 外部タスクとの対応付け
* 運用系ワークフローとの橋渡し

---

### 10. Policy Layer

**役割**
各エージェントや各レイヤの振る舞いに対して、上位の行動規範・判断方針を与える。

**構成**

* `strategy-guided-policy-prompt`

**責務**

* 調査方針
* 優先順位の癖づけ
* 判断の一貫性補助
* 無駄な探索や暴走の抑制

**特徴**

* 実行器ではなく、全体の行動制約・行動指針
* 各レイヤへ横断的に作用する

---

### 11. Implementation Handoff Layer

**役割**
研究成果や採択済み仮説を、実装や仕様策定へ接続する。

**現行構成**

* `ai-product-requirement-document`
* `workflow-cookbook`

**注意**

* これらは将来的に更新・置換予定
* 現時点では「出口の仮置き」として扱う

**責務**

* PRD化
* 実装タスク分解
* 実行レシピ整備
* 開発/検証フローへの接続

---

## 正本の整理

責務の重なりを減らすため、正本は以下のように置く。

| 領域       | 正本                              |
| -------- | ------------------------------- |
| 実行状態     | `agent-taskstate`               |
| 参照知識アクセス | `memx-resolver`                 |
| 外部イベント起動 | `pulse-kestra`                  |
| ワークフロー制御 | `Kestra`                        |
| 探索       | `open_deep_research`            |
| 洞察抽出     | `insight-agent`                 |
| 仮説採否判定   | `experiment-gate`               |
| 計画化      | `Roadmap-Design-Skill`          |
| 振る舞い方針   | `strategy-guided-policy-prompt` |
| 外部同期     | `tracker-bridge-materials`      |

---

## 基本データフロー

```mermaid
sequenceDiagram
    participant U as User / External Event
    participant P as pulse-kestra
    participant K as Kestra
    participant G as llm-guard
    participant R as open_deep_research
    participant I as insight-agent
    participant M as memx-resolver
    participant E as experiment-gate
    participant D as Roadmap-Design-Skill
    participant S as agent-taskstate
    participant T as tracker-bridge-materials

    U->>P: mention / webhook / cron
    P->>K: start flow
    K->>G: validate input
    G->>R: research request
    R->>M: optional knowledge lookup
    R->>I: gathered materials
    I->>M: retrieve supporting context
    I->>E: hypothesis / issues / insights
    E->>D: approved or deferred candidates
    D->>S: save roadmap / state / next actions
    D->>T: sync tasks / tickets
    S-->>K: resumable state
```

---

## 最小E2Eフロー

最初に通すべき最小構成は以下。

1. `pulse-kestra` が mention または cron を受ける
2. `Kestra` が flow を起動する
3. `llm-guard` で入力をガードする
4. `open_deep_research` で対象テーマを探索する
5. `insight-agent` で洞察・仮説候補を抽出する
6. `experiment-gate` で Go / Hold / No-Go を判定する
7. `Roadmap-Design-Skill` で next actions に落とす
8. `agent-taskstate` に保存する
9. 必要に応じて `tracker-bridge-materials` で外部タスク化する

この1本が通れば、単体OSS群ではなく「R&Dエージェント」として成立する。

---

## 典型ユースケース

### 1. 論文起点のPoC検討

* 論文URLまたは論文テーマを入力
* Research で周辺情報を収集
* Insight で粗・仮説・実装観点を抽出
* Gate で試す価値を判定
* Roadmap で最小PoC計画へ落とす

### 2. 新技術ウォッチ

* cron / heartbeat で定期実行
* 新着候補を探索
* 既知知識との差分を抽出
* 試す価値の高いものだけ gate 通過
* 状態保存して後続作業へ

### 3. メンション起点の即応

* Misskey mention からテーマ受信
* Guard を通し research 実施
* Insight を構造化
* 必要なら task 化して backlog へ送る

---

## 境界の注意点

### Research と Insight を混ぜすぎない

`open_deep_research` は探索に寄せ、
`insight-agent` は抽出と構造化に寄せる。
両者を一体化しすぎると責務が崩れる。

### Gate と Planning を混ぜすぎない

`experiment-gate` は「やる価値があるか」の層。
`Roadmap-Design-Skill` は「どう進めるか」の層。
採否判断と計画作成を分けることで、見直ししやすくなる。

### State と Knowledge を混ぜない

`agent-taskstate` は進行中の作業状態。
`memx-resolver` は参照知識アクセス。
ここを分離しておくと、長期運用時の破綻が減る。

---

## 将来の差し替え前提

以下は将来的に置換または再設計される前提で扱う。

* `ai-product-requirement-document`
* `workflow-cookbook`

したがって、全体設計ではこれらを中核正本にせず、
**implementation handoff の交換可能な出口層**として扱う。

---

## 推奨ディレクトリ配置例

```text
r-and-d-agent/
├─ docs/
│  ├─ ARCHITECTURE.md
│  ├─ FLOWS.md
│  ├─ DECISIONS.md
│  └─ INTERFACES.md
├─ flows/
│  ├─ mention-research.yaml
│  ├─ cron-watch.yaml
│  └─ poc-evaluation.yaml
├─ policies/
│  └─ strategy-guided-policy.md
├─ adapters/
│  └─ pulse-kestra/
├─ integrations/
│  └─ tracker-bridge/
└─ examples/
   ├─ research-inputs/
   └─ output-snapshots/
```

---

## MVP定義

R&Dエージェントとして最低限成立したとみなす条件は以下。

* 外部トリガーで起動できる
* research -> insight -> gate -> roadmap の1本が通る
* `agent-taskstate` に状態保存できる
* 次回再開時に状態を引き継げる
* 任意で外部トラッカーに同期できる

---

## この構成の本質

この構成は「万能エージェント」ではなく、
**研究から実行判断までの知的パイプライン**である。

中心にあるのは以下の流れ。

* 調べる
* 気づく
* 試す価値を決める
* 計画に落とす
* 状態を保持する
* 外部実装系へ橋渡しする

つまり、検索エージェントでもなく、単なる要約器でもなく、
**R&Dの推進系として設計されたエージェント群**である。

---

## 一文まとめ

> このR&Dエージェントは、外部刺激を受けて調査・洞察・仮説評価・計画化・状態保持・外部同期までを流し込む、レイヤ分離型の研究推進アーキテクチャである。