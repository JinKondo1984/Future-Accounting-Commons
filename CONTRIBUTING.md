# Contributing to Future Accounting Commons / コントリビュートガイド

Thank you for your interest in Future Accounting Commons. This project welcomes contributions from developers, accountants, and corporate finance/accounting professionals alike — you don't need to write code to help shape this project.

Future Accounting Commonsにご関心をお寄せいただきありがとうございます。本プロジェクトは、エンジニアだけでなく、会計士・税理士・コンサルタント・企業の経理担当者からの貢献も歓迎しています。コードを書けなくても、プロジェクトの方向性に関わることができます。

[![Discord](https://img.shields.io/discord/1532994257835528323?label=Discord&logo=discord&logoColor=white)](https://discord.gg/WvCYQgm83z)

---

## Four kinds of contributions / 4種類の貢献

**EN:** This project has four distinct kinds of contributions. Please identify which one applies to you before proceeding, as the process differs between them.

- **[1. Import engine contributions](#1-import-engine-contributions)** — code that decomposes double-entry data from a specific accounting system into FAC Format.
- **[2. FAC Format proposals](#2-fac-format-proposals)** — proposing changes to the standardized data specification itself (e.g. adding a column). A design discussion, not a code change.
- **[3. Analysis method / tool proposals](#3-analysis-method--tool-proposals)** — proposing a management-accounting metric or analysis approach that should be computable from FAC-formatted data. No code required — this is for anyone with domain expertise.
- **[4. Analytics tool development](#4-analytics-tool-development)** — building the code that computes management-accounting metrics from FAC-formatted data, including tools proposed under (3).

**JA:** 本プロジェクトへの貢献は性質の異なる4種類に分かれます。以下のどれに該当するかをまず確認してください。プロセスがそれぞれ異なります。

- **[1. インポートエンジンへの貢献](#1-import-engine-contributions)** — 特定の会計システムの複式データをFACフォーマットに分解するコード。
- **[2. FACフォーマットへの仕様提案](#2-fac-format-proposals)** — 標準データ仕様そのものへの変更提案(カラム追加など)。コード変更ではなく設計上の議論。
- **[3. 分析方法・分析ツールへの提案](#3-analysis-method--tool-proposals)** — FACフォーマットのデータから算出できるべき管理会計指標・分析アプローチの提案。コード不要。経営・会計・経理の専門知識を持つ方はぜひここから。
- **[4. 分析ツールの開発](#4-analytics-tool-development)** — FACフォーマットのデータから管理会計指標を算出するコードの開発。(3)で提案されたツールの実装を含む。

---

## 1. Import engine contributions / インポートエンジンへの貢献

**EN**
- Bug fixes for existing import engines (Money Forward, freee, Yayoi, etc.)
- New import engines for accounting software not yet supported
- Open an Issue first to discuss the target system's export format before implementing

**JA**
- 既存のインポートエンジン(マネーフォワード、freee、弥生会計など)のバグ修正
- 未対応の会計ソフト向けの新規インポートエンジン
- 実装前に、対象システムのエクスポート形式についてIssueで相談してください

### Development setup / 開発環境構築

```bash
git clone https://github.com/<org>/future-accounting-commons.git
cd future-accounting-commons
pip install -r requirements.txt
pytest
```

### Pull request guidelines / プルリクエストのガイドライン

**EN**
1. Open an Issue first for anything beyond a trivial fix.
2. Branch naming: `fix/<short-description>` or `feat/<short-description>`.
3. Keep PRs focused on a single change.
4. Include or update tests for any behavior change.
5. One maintainer review and approval is required before merging.

**JA**
1. 些細な修正以外は、まずIssueで相談してください。
2. ブランチ命名:`fix/<短い説明>`または`feat/<短い説明>`。
3. PRは1つの変更に絞ってください。
4. 挙動を変える変更には、テストの追加・更新を含めてください。
5. マージには、メンテナーによるレビューと承認が最低1件必要です。

---

## 2. FAC Format proposals / FACフォーマットへの仕様提案

**EN:** The FAC Format is the core standard this project maintains. Because it needs to remain stable and broadly usable across organizations, proposals go through a dedicated discussion process rather than a direct pull request.

**JA:** FACフォーマットは本プロジェクトが維持するコアの標準仕様です。安定性と組織横断での利用可能性を保つため、通常のプルリクエストとは別の、専用の議論プロセスを経て検討されます。

### Process / プロセス

**EN**
1. **Start a discussion** in [GitHub Discussions](../../discussions), under the "Ideas" category. Describe the use case and the problem you're trying to solve — not just the column you want to add.
2. If the idea gains traction, it will be **formalized as an Issue** labeled `format-proposal`, summarizing the discussion and the concrete proposed change.
3. The community and maintainers discuss the proposal on the Issue. Because backward compatibility is a core principle from v1.0.0 onward, proposals are evaluated primarily as **additive (MINOR) changes**.
4. Once consensus is reached, the change is merged into [`docs/fac_format.md`](docs/fac_format.md) and released under the next MINOR version.

**JA**
1. まず[GitHub Discussions](../../discussions)の「Ideas」カテゴリで議論を始めてください。追加したいカラムそのものではなく、解決したいユースケース・課題を説明してください。
2. 議論が深まったら、`format-proposal`ラベル付きの**Issueとして正式化**します。
3. Issue上でコミュニティとメンテナーが議論します。v1.0.0以降は後方互換性の維持が原則のため、提案は基本的に**追加的な変更(MINOR)**として評価されます。
4. 合意が形成されたら、[`docs/fac_format.md`](docs/fac_format.md)に反映し、次のMINORバージョンとしてリリースします。

**EN:** Note: proposals that would require a breaking (MAJOR) change are held to a much higher bar, given the project's stated goal of long-term stability.

**JA:** 注:破壊的変更(MAJOR)を伴う提案は、プロジェクトが掲げる長期的な安定性の目標から、より高いハードルで検討されます。

---

## 3. Analysis method / tool proposals / 分析方法・分析ツールへの提案

**EN:** This project actively encourages the community to propose and share management-accounting analysis methods that can be computed from FAC-formatted data — no coding required. Good analysis proposals become shared community assets once implemented.

**JA:** 本プロジェクトでは、FACフォーマットのデータから算出できる管理会計の分析手法を、コミュニティが提案・共有することを積極的に推奨しています。コードを書ける必要はありません。良い分析提案は、実装されればコミュニティ共有の資産になります。

### Process / プロセス

**EN**
1. Open a discussion in [GitHub Discussions](../../discussions), under the "Analysis Ideas" category. Describe the metric or method, why it's useful for management accounting, and which FAC Format columns it would use.
2. The community discusses feasibility and value. Proposals that gain interest are labeled `analysis-proposal` and tracked as Issues, ready for someone to pick up under Section 4.
3. If you can also implement it yourself, feel free to move directly to Section 4.

**JA**
1. [GitHub Discussions](../../discussions)の「Analysis Ideas」カテゴリで議論を始めてください。どんな指標・分析手法か、管理会計上なぜ有用か、FACフォーマットのどのカラムを使うかを説明してください。
2. コミュニティで実現可能性・有用性を議論します。関心が集まった提案には`analysis-proposal`ラベルを付けてIssue化し、セクション4での実装を待つ状態にします。
3. 自分で実装もできる場合は、そのままセクション4に進んでいただいて構いません。

---

## 4. Analytics tool development / 分析ツールの開発

**EN:** Building the engines and tools that compute management-accounting metrics from FAC-formatted data. This includes implementing proposals from Section 3, or contributing your own analysis tools directly.

**JA:** FACフォーマットのデータから管理会計指標を算出するエンジン・ツールの開発です。セクション3で提案された分析手法の実装、またはご自身で開発した分析ツールを直接コントリビュートすることも歓迎します。

**EN**
- Pick up an Issue labeled `analysis-proposal`, or propose your own tool directly via PR (a short discussion first is still encouraged for larger tools).
- Follow the same development setup and PR guidelines as Section 1.
- Where possible, keep analytics tools decoupled from any specific import engine — they should work against any valid FAC-formatted data, regardless of source.

**JA**
- `analysis-proposal`ラベルのIssueを選んで実装するか、直接PRとして分析ツールを提案してください(規模の大きいツールは事前の相談を推奨します)。
- 開発環境構築・PRガイドラインはセクション1と同様です。
- 可能な限り、分析ツールは特定のインポートエンジンに依存しない設計にしてください。出所を問わず、有効なFACフォーマットのデータであれば動作するのが理想です。

---

## Code of Conduct / 行動規範

Be respectful. Disagreements about design (especially FAC Format proposals) are expected and welcome — keep them focused on the idea, not the person.

敬意を持って接してください。特にFACフォーマットに関する設計上の意見の相違は当然起こり得るものであり、歓迎します。ただし、議論は「アイデア」に焦点を当て、「人」を対象にしないようにしてください。
