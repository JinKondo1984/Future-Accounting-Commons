# Future Accounting Commons

> A Python engine that decomposes double-entry bookkeeping data into single-entry format for management accounting

## Why can't management accounting be automated?

Because the data coming out of accounting software is still shaped like double-entry bookkeeping.

Future Accounting Commons is a community-driven engine, built in Python, that decomposes double-entry data into a standardized single-entry format — ready for management accounting, in one step.

## What it does

**Before: Double-entry journal (as exported from accounting software)**

| Date       | Debit Account       | Credit Account | Amount   |
|------------|----------------------|------------------|---------:|
| 2026-04-01 | Advertising Expense  | Cash             | ¥50,000  |

**After: Single-entry data (Future Accounting Commons standard format)**

| date       | account_large | account_middle       | amount   | cost_type   | cf_type    | dept_original | dept_allocated | status |
|------------|----------------|------------------------|---------:|-------------|------------|----------------|------------------|--------|
| 2026-04-01 | 経費 (Expense) | 広告宣伝費 (Advertising) | -50,000  | 変動費 (Variable) | 営業CF (Operating) | Marketing      | Marketing        | 実績 (Actual) |

> **Note:** Revenue and cash inflows are recorded as positive values; expenses and cash outflows are recorded as negative values. This sign convention makes it possible to sum `amount` directly across any dimension (department, account, cost type) without worrying about debit/credit direction.

Future Accounting Commons converts the left into the right — automatically classifying cost type, cash-flow type, and department allocation in a single decomposition step.

### Allocation example: `dept_original` vs `dept_allocated`

Head-office costs are often booked to a single department in the source system, but need to be allocated across the departments that actually benefited from them for management accounting purposes.

**Before allocation**

| date       | account_middle | amount    | dept_original | dept_allocated |
|------------|------------------|----------:|----------------|------------------|
| 2026-04-01 | 地代家賃 (Rent)  | -300,000  | Head Office    | Head Office      |

**After running the allocation engine** (split across 3 departments by headcount)

| date       | account_middle | amount    | dept_original | dept_allocated |
|------------|------------------|----------:|----------------|------------------|
| 2026-04-01 | 地代家賃 (Rent)  | -150,000  | Head Office    | Sales            |
| 2026-04-01 | 地代家賃 (Rent)  | -90,000   | Head Office    | Engineering      |
| 2026-04-01 | 地代家賃 (Rent)  | -60,000   | Head Office    | Marketing        |

`dept_original` always preserves where the cost was originally booked, while `dept_allocated` reflects the result of the allocation logic — so you can trace every allocated row back to its source.


## 💡 プロジェクトの理念（Japanese）
「なぜ、企業の管理会計は自動化できないのか？」

それは、会計ソフトから出力されるデータがすべて**「複式簿記（2次元）」**の形をしているからです。経営判断（CVP分析や資金繰り予測）を行うためには、この貸借データを、1次元の時系列データへ「分解・翻訳」する必要があります。

Future-Accounting-Commonsは、日本中の会計事務所担当者や経理実務者が集まり、管理会計をスマートに自動化するための**「共通データフォーマット」と「変換エンジン」を共創するコミュニティ**です。

---

## 🚀 提供する価値
- **複式簿記の1次元分解：** マネーフォワード等の仕訳CSVから、損益（PL）と直接法キャッシュフロー（CF）を自動抽出。
- **簡易税抜化ロジック：** 複雑な消費税区分を「1.1」「1.08」「1.0」の3パターンに抽象化し、管理会計に最適な数値を自動算出。
- **固変分解・部門配賦の基盤：** 経営シミュレーション（CVP分析）にそのまま流せる標準フォーマットの生成。

---
