# Future Accounting Commons

> A Python engine that decomposes double-entry bookkeeping data into single-entry format for management accounting


[日本語の案内は後半にあります / Japanese description follows below]


## Why can't management accounting be automated?

Because the data coming out of accounting software is still shaped like double-entry bookkeeping.

Future Accounting Commons is a community-driven engine, built in Python, that decomposes double-entry data into a standardized single-entry format — ready for management accounting, in one step.

---

## 📊 FAC Format Specifications (Ver.0.9.1)
FAC (Future Accounting Commons) format deconstructs 2D double-entry bookkeeping data into a unified, 1D transactional database optimized for data analytics. 
*Positive values indicate revenue/cash-in, while negative values indicate expenses/cash-out.*

| # | Column Name | Data Type | Description / Sample Values |
| :--- | :--- | :--- | :--- |
| 1 | `date` | String | `YYYY-MM-DD` (Transaction or forecast date) |
| 2 | `account_large` | String | Large Category: `Revenue` / `Cost` / `HR_Expense` / `Operating_Expense` / `Non_Operating` / `Asset` / `Liability` |
| 3 | `account_middle` | String | Middle Category: `Sales` / `Rent` / `Accounts_Receivable` / etc. |
| 4 | `account_small` | String | Small Category: `Supplementary subject` /  etc. |
| 5 | `amount` | Float | **Tax-excluded for PL**, **Tax-included for CF**. (Positive = Inflow, Negative = Outflow) |
| 6 | `cost_type` | String | CVP breakdown: `Fixed_Cost` / `Variable_Cost` / `N/A` |
| 7 | `cf_type` | String | Cash Flow breakdown: `Operating_CF` / `Investing_CF` / `Financial_CF` / `N/A` |
| 8 | `dept_original` | String | The original department name from the raw accounting software. |
| 9 | `status` | String | Data state: `Actual` / `Budget` / `Forecast` |

### 📌 Version Control Policy
- **Semantic Versioning (e.g., Ver. 1.0.0):** Major changes to columns or definitions will trigger a major version bump. Minor additions (e.g., adding subcategories or tags) will bump the minor version.
- All versions and specifications will be managed via GitHub Releases and the main branch documentation.

---

## 💡 プロジェクトの理念（Japanese）
「なぜ、企業の管理会計は自動化できないのか？」

それは、会計ソフトから出力されるデータがすべて「複式簿記（2次元）」の形をしているからです。経営判断（CVP分析や資金繰り予測）を行うためには、この貸借データを、1次元の時系列データへ「分解・翻訳」する必要があります。

Future-Accounting-Commonsは、日本中の会計事務所担当者や経理実務者が集まり、管理会計をスマートに自動化するための「共通データフォーマット（FACフォーマット）」と「変換エンジン」、そして「分析ツール」を共創するコミュニティ**です。

---
---

## 📊 FACフォーマット仕様 (Ver.0.9.1)
FAC（Future Accounting Commons）フォーマットは、2次元の複式簿記データを、データ分析に最適化された1次元の時系列データへ分解・統合した共通データモデルです。
*収益・入金はプラス（正）、費用・出金はマイナス（負）のベクトルとして一元管理されます。*

| # | カラム名 | データ型 | 格納する値のイメージ・役割 |
| :--- | :--- | :--- | :--- |
| 1 | `date` | 文字列 | `YYYY-MM-DD`（実績発生日、または予算・予測の対象月） |
| 2 | `account_large` | 文字列 | 科目大分類：売上 / 原価 / 人件費 / 経費 / 営業外 / 資産 / 負債 など |
| 3 | `account_middle` | 文字列 | 科目中分類：売上高 / 地代家賃 / 売掛金 / 買入金 など |
| 4 | `account_small` | 文字列 | 科目小分類：補助科目など |
| 5 | `amount` | 数値 | **PLは管理会計用税抜、CFは税込金額**（正＝入金・収益、負＝出金・費用） |
| 6 | `cost_type` | 文字列 | 固変区分（CVP分析用）：固定費 / 変動費 / 対象外 |
| 7 | `cf_type` | 文字列 | CF区分（資金繰り用）：営業CF / 投資CF / 財務CF / 対象外 |
| 8 | `dept_original` | 文字列 | 会計ソフトから出力された時点の初期部門名。 |
| 9 | `status` | 文字列 | データ状態：実績 / 予算 / 予測 |

### 📌 バージョン管理方針
- **セマンティックバージョニングの採用（例: Ver.1.0.0）**: カラムの追加・削除や定義の根本的な変更など、互換性を破る場合はメジャーバージョンを上げます。タグの追加など軽微な拡張はマイナーバージョンで対応します。
- 過去の仕様や変更履歴はすべてGitHubのReleases機能、およびコミット履歴に資産として蓄積します。
---

