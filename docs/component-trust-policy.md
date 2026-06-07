# コンポーネント信頼ポリシー

## 目的

RanD が統合するコンポーネントを信頼レベルで分類し、その出力をどの判断に利用できるかを明確にする。固定コミットは再現性を高めるが、それだけでコンポーネントや出力の安全性、正確性、信頼性を保証するものではない。

## 信頼レベル

| レベル | 分類と例 | 許可される利用 | 必要な証拠 |
| --- | --- | --- | --- |
| Level 0 | 契約の正本: local schema、state contract、decision record、taskstate-compatible record | 検証、状態遷移、判断条件の authoritative contract | schema version、変更履歴、所有者 |
| Level 1 | 決定論的ローカルコア: deterministic fallback、fixture-based evaluation、local contract validation | 入力と規則を記録した場合の判断支援証拠 | input refs、規則、実行結果、再現手順 |
| Level 2 | 内部 peer repository: manifest に存在する `agent-taskstate`、`workflow-cookbook`、`experiment-gate`、`insight-agent`、`memx-resolver` など | 明示的な artifact contract を介した内部連携 | pinned version、契約検証、sample artifact 比較 |
| Level 3 | 外部 OSS: manifest に存在する `open_deep_research`、`llm-guard`、`kestra`、`pulse-kestra` など | 正規化後の信号、実行補助、判断支援 | source、timestamp、version または pinned commit、confidence、fallback path |
| Level 4 | live 外部依存: live web fetch、外部 LLM API、notification API、tracker sync API | 探索、収集、同期候補、判断支援 | source、timestamp、API/component version、confidence、fallback path |

Level 0 は契約の正本であり、個別の調査結果や判断内容が自動的に正しいことを意味しない。Level 2 も、内部管理されていることだけを理由に無条件では信頼しない。

## 利用ルール

- Level 3 と Level 4 の出力は、`go`、`pass`、`approve` または同等の最終結果を直接決定してはならない。
- Level 3 と Level 4 の出力は、downstream で利用する前に inspectable artifact へ正規化する。artifact には最低限 `source_refs`、`created_at`、`producer_version` または `pinned_commit`、`confidence`、fallback path を記録する。
- live 外部出力と LLM 出力は、それ単独では authoritative evidence として扱わない。
- 劣化実行経路の判断結果は、`needs_review`、`conditional_go`、`hold` または同等の非最終状態へ写像する。レビューなしに最終判断へ昇格してはならない。
- コンポーネントの version または pinned commit を変更するときは、契約検証と代表 sample artifact の比較を実施する。
- inspectable artifact を生成できず、判断根拠を監査できないコンポーネントは、利用範囲を制限するか、削除または置換できる。
- downstream での許可用途は [Artifact Contract Policy](artifact-contract-policy.md) に従って artifact ごとに明示する。
- 障害時と fallback 時の扱いは [Fallback Policy](fallback-policy.md) に従う。

## コンポーネント追加・更新チェックリスト

- [ ] trust level と所有者を記録した
- [ ] version または pinned commit を記録した
- [ ] 固定コミットだけを信頼根拠にしていない
- [ ] 入出力 artifact contract と schema version を定義した
- [ ] Level 3 / 4 出力の正規化経路を定義した
- [ ] 許可される downstream 利用と禁止される最終判断を定義した
- [ ] primary path、fallback path、失われる capability を定義した
- [ ] contract validation と sample artifact 比較を実施した
- [ ] failure、degraded、stale、欠損 field の挙動を確認した
- [ ] コンポーネントを無効化または置換できることを確認した
