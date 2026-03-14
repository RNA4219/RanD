# RanD セットアップ

`RanD` 配下には、R&D Agent アーキテクチャを導入するための入口を置いています。

## 入口

- アーキテクチャ文書: [docs/architecture.md](/Users/ryo-n/Codex_dev/RanD/docs/architecture.md)
- 導入用リポジトリ: [r-and-d-agent-installer](/Users/ryo-n/Codex_dev/RanD/r-and-d-agent-installer)
- 一発実行バッチ: [install-r-and-d-agent.bat](/Users/ryo-n/Codex_dev/RanD/install-r-and-d-agent.bat)
- 調査ランタイム: [research-runtime](/Users/ryo-n/Codex_dev/RanD/research-runtime)
- 調査実行バッチ: [run-research-once.bat](/Users/ryo-n/Codex_dev/RanD/run-research-once.bat)
- 定期実行バッチ: [run-research-schedule.bat](/Users/ryo-n/Codex_dev/RanD/run-research-schedule.bat)

## 使い方

通常インストール:

```bat
install-r-and-d-agent.bat
```

必須コンポーネントだけ入れる:

```bat
install-r-and-d-agent.bat --skip-optional
```

既存導入を作り直す:

```bat
install-r-and-d-agent.bat --force
```

## バージョン固定

導入対象の各リポジトリは [components.json](/Users/ryo-n/Codex_dev/RanD/r-and-d-agent-installer/manifests/components.json) の `pinnedCommit` に固定されます。  
GitHub 側やローカル側に新しいコミットが出ても、再現される導入結果は変わりません。
