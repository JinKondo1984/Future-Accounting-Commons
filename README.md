# Future Accounting Commons

> A Python engine that decomposes double-entry bookkeeping data into single-entry format for management accounting

[日本語版はこちら](README.ja.md)

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
