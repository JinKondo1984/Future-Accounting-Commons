# FAC Format Specification / FACフォーマット仕様書

**Version: 1.0.0 (planned at public release)**

---

## 1. Overview / 概要

**EN:** The FAC (Future Accounting Commons) Format is a standardized single-entry data format designed for management accounting. It is produced by decomposing double-entry bookkeeping data exported from accounting software (e.g. Money Forward, freee, Yayoi) into a structure optimized for analysis rather than compliance.

**JA:** FAC(Future Accounting Commons)フォーマットは、管理会計向けに設計された標準化された単式データフォーマットです。マネーフォワード・freee・弥生会計などの会計ソフトから出力された複式簿記データを分解することで生成され、税務コンプライアンスではなく分析を目的とした構造になっています。

**EN:** FAC Format follows Semantic Versioning. From v1.0.0 onward, backward compatibility is maintained as a principle — version changes are expected to be additive (new columns), not breaking, since the fundamental metrics of management accounting have remained largely unchanged for nearly a century.

**JA:** FACフォーマットはセマンティックバージョニングに従います。v1.0.0以降は原則として後方互換性を維持します。管理会計の基本指標はこの100年近く大きく変わっていないため、バージョン変更は主にカラムの追加(非破壊的変更)を想定しています。

---

## 2. Columns / カラム構成

| # | Column (physical name) | Type / データ型 | Required / 必須 | Description (EN) | 説明(JA) |
|---|---|---|---|---|---|
| 1 | `date` | `YYYY-MM-DD` | Required | Actual transaction date, or target month for budget/forecast data. | 実績日、または予算・予測の対象月。 |
| 2 | `account_large` | string | Required | Top-level account category, e.g. Revenue / COGS / Personnel / Expenses / Non-operating / Assets / Liabilities. | 科目大分類。売上 / 原価 / 人件費 / 経費 / 営業外 / 資産 / 負債 など。 |
| 3 | `account_middle` | string | Required | Mid-level account category, e.g. Advertising Expense / Travel Expense / Accounts Payable / Loans Payable. | 科目中分類。広告宣伝費 / 旅費交通費 / 未払金 / 借入金 など。 |
| 4 | `account_small` | string | Optional | Sub-account as defined in the source accounting system's chart of accounts (補助科目). Values are constrained by the company's own account master data, so no spelling variation occurs within a single organization. Omit this column if the source system has no sub-account layer. | 補助科目に相当するカラム。会計システム内であらかじめ決められた科目構成であり、自由記述ではない(企業内で表記ゆれが起きない)。補助科目を使っていない場合は本カラムを省略してよい。 |
| 5 | `amount` | numeric | Required | Revenue and cash inflows are positive; expenses and cash outflows are negative. This convention allows direct summation across any dimension without tracking debit/credit direction. | 金額。収益・キャッシュインはプラス、費用・キャッシュアウトはマイナス。この符号規則により、借方/貸方を意識せず任意の軸で合計できる。 |
| 6 | `cost_type` | string | Required | Fixed/variable cost classification: Variable / Fixed / Not applicable (e.g. revenue, assets). | 固変区分。変動費 / 固定費 / 対象外(売上や資産などは対象外)。 |
| 7 | `cf_type` | string | Required | Cash-flow classification: Operating / Investing / Financing / Not applicable (non-cash entries). | CF区分。営業CF / 投資CF / 財務CF / 対象外(現金不随の仕訳は対象外)。 |
| 8 | `dept_original` | string | Required | Department as originally recorded at export time from the accounting system. Always preserved, even after allocation. | 元部門。会計ソフトから出力された時点の初期部門。配賦後も常に元の値を保持する。 |
| 9 | `dept_allocated` | string | Required | Department after running the allocation engine's logic. Traces every allocated row back to its source via `dept_original`. | 配賦後部門。Pythonの配賦ロジックを実行した後に書き込まれる列。`dept_original`との対応により、配賦後もトレーサビリティを保つ。 |
| 10 | `status` | string | Required | Data status: Actual / Budget / Forecast. | データ状態。実績 / 予算 / 予測。 |

---

## 3. Design principles / 設計原則

**EN**
- **Simplicity over completeness**: FAC Format intentionally excludes free-text fields (tags, memos). Structured, closed-vocabulary columns preserve both cross-organization comparability and privacy — analysis is possible without exposing individual transaction details (counterparties, project names, invoice numbers, etc.).
- **Traceability**: Allocation logic never overwrites the original department; `dept_original` and `dept_allocated` are always kept as separate columns.
- **Two-engine architecture**: FAC Format is the intermediate format between (1) import engines that decompose double-entry data from various accounting systems, and (2) analytics engines that compute management-accounting metrics from FAC-formatted data.

**JA**
- **完全性よりもシンプルさを優先**:FACフォーマットは意図的に自由記述欄(タグ・摘要)を採用していません。構造化された閉じた語彙のカラムにすることで、組織間の比較可能性とプライバシー保護を両立します。取引先名・案件名・請求書番号などの個別詳細を露出せずに分析が可能です。
- **トレーサビリティ**:配賦ロジックは元の部門情報を上書きしません。`dept_original`と`dept_allocated`を常に別カラムとして保持します。
- **2エンジン構成**:FACフォーマットは、(1)各種会計ソフトの複式データを分解するインポートエンジンと、(2)FACフォーマットのデータから管理会計指標を算出する分析エンジン、の中間フォーマットとして機能します。

---

## 4. Versioning policy / バージョニング方針

**EN**
- Semantic Versioning (`MAJOR.MINOR.PATCH`)
- **MINOR**: Additive changes (new columns, new enumerated values) — existing data remains valid.
- **PATCH**: Documentation fixes, validation rule clarifications with no structural impact.
- **MAJOR**: Reserved for changes that break backward compatibility. Expected to be rare, given that core management-accounting concepts are stable.
- Specification changes are proposed via GitHub Discussions, formalized as an Issue, and merged following community review.

**JA**
- セマンティックバージョニング(`MAJOR.MINOR.PATCH`)を採用
- **MINOR**:カラムの追加、列挙値の追加など非破壊的な変更。既存データはそのまま有効。
- **PATCH**:ドキュメント修正、構造に影響しないバリデーションルールの明確化など。
- **MAJOR**:後方互換性を破る変更のために予約。管理会計の基本概念は安定しているため、発生頻度は低いと想定。
- 仕様変更はGitHub Discussionsでの議論→Issue化→コミュニティレビューを経てマージ、というプロセスで進める。
