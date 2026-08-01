# Future Accounting Commons/未来会計コモンズ

> A Python engine that decomposes double-entry bookkeeping data into single-entry format for management accounting
> 複式簿記データを、管理会計に適した単式データ(FACフォーマット)に分解するPythonエンジン
> 
> **Good numbers. Better decisions.** / 正しい数字は、より良い意思決定をもたらす。


---

## Why can't management accounting be automated? / なぜ企業の管理会計は自動化できないのか?

**EN:** Because the data coming out of accounting software is still shaped like double-entry bookkeeping.

Future Accounting Commons is a community-driven engine, built in Python, that decomposes double-entry data into a standardized single-entry format — ready for management accounting, in one step.

**JA:** それは、会計ソフトから出力されるデータが「複式簿記の形」のままだからです。

Future Accounting Commonsは、Pythonで開発されたコミュニティ主導のエンジンです。複式簿記データを、管理会計にすぐ使える標準化された単式データへと一発で分解します。

---

## What it does / できること

**Before: Double-entry journal (as exported from accounting software) / 複式仕訳(会計ソフトからの出力)**

| Date       | Debit Account       | Credit Account | Amount   |
|------------|----------------------|------------------|---------:|
| 2026-04-01 | Advertising Expense  | Cash             | ¥50,000  |

**After: Single-entry data — FAC Format / 単式データ(FACフォーマット)**

| date       | account_large | account_middle       | amount   | cost_type   | cf_type    | dept_original | dept_allocated | status |
|------------|----------------|------------------------|---------:|-------------|------------|----------------|------------------|--------|
| 2026-04-01 | 経費 (Expense) | 広告宣伝費 (Advertising) | -50,000  | 変動費 (Variable) | 営業CF (Operating) | Marketing      | Marketing        | 実績 (Actual) |

> **EN:** Revenue and cash inflows are recorded as positive values; expenses and cash outflows are recorded as negative values. This sign convention makes it possible to sum `amount` directly across any dimension (department, account, cost type) without worrying about debit/credit direction.
>
> **JA:** 収益・キャッシュインはプラス、費用・キャッシュアウトはマイナスで記録されます。この符号規則により、借方/貸方の方向を意識せず、部門・科目・固変区分など任意の軸で`amount`を直接合計できます。

**EN:** Future Accounting Commons converts the left into the right — automatically classifying cost type, cash-flow type, and department allocation in a single decomposition step.
**JA:** 左のデータを右へ、固変区分・CF区分・部門配賦までを含めて一度の分解ステップで自動変換します。

### Allocation example / 配賦の例:`dept_original` vs `dept_allocated`

**EN:** Head-office costs are often booked to a single department in the source system, but need to be allocated across the departments that actually benefited from them for management accounting purposes.

**JA:** 本社費は会計システム上では単一の部門に計上されがちですが、管理会計上は実際に恩恵を受けた各部門へ配賦する必要があります。

**Before allocation / 配賦前**

| date       | account_middle | amount    | dept_original | dept_allocated |
|------------|------------------|----------:|----------------|------------------|
| 2026-04-01 | 地代家賃 (Rent)  | -300,000  | Head Office    | Head Office      |

**After running the allocation engine (split across 3 departments by headcount) / 配賦エンジン実行後(人員数比で3部門に按分)**

| date       | account_middle | amount    | dept_original | dept_allocated |
|------------|------------------|----------:|----------------|------------------|
| 2026-04-01 | 地代家賃 (Rent)  | -150,000  | Head Office    | Sales            |
| 2026-04-01 | 地代家賃 (Rent)  | -90,000   | Head Office    | Engineering      |
| 2026-04-01 | 地代家賃 (Rent)  | -60,000   | Head Office    | Marketing        |

**EN:** `dept_original` always preserves where the cost was originally booked, while `dept_allocated` reflects the result of the allocation logic — so you can trace every allocated row back to its source.

**JA:** `dept_original`は常に元の計上部門を保持し、`dept_allocated`は配賦ロジックの結果を反映します。これにより、配賦後のどの行も元データまで遡ってトレースできます。

---

## The FAC Format / FACフォーマットについて

**EN:** FAC (Future Accounting Commons) Format is the standardized single-entry data specification at the core of this project. It follows Semantic Versioning, and from v1.0.0 onward, backward compatibility is maintained as a principle — since the fundamental metrics of management accounting have remained largely unchanged for nearly a century, version changes are expected to be additive (new columns), not breaking.

Full specification: [`fac_format.md`](fac_format.md)

**JA:** FAC(Future Accounting Commons)フォーマットは、本プロジェクトの根幹となる標準化された単式データ仕様です。セマンティックバージョニングに従い、v1.0.0以降は原則として後方互換性を維持します。管理会計の基本指標はこの100年近く大きく変わっていないため、バージョン変更は主にカラムの追加(非破壊的変更)を想定しています。

詳細な仕様:[`fac_format.md`](fac_format.md)

---

## Two-engine architecture / 2エンジン構成

**EN:** This project develops two kinds of engines, connected by the FAC Format as a common intermediate representation:

1. **Import engines** — decompose double-entry journal data exported from accounting systems (Money Forward, freee, Yayoi, and others) into FAC Format.
2. **Analytics engines** — compute management-accounting metrics from FAC-formatted data.

**JA:** 本プロジェクトでは、FACフォーマットを共通の中間表現として、以下2種類のエンジンを開発しています。

1. **インポートエンジン** — マネーフォワード・freee・弥生会計など各種会計システムから出力された複式仕訳データを、FACフォーマットに分解します。
2. **分析エンジン** — FACフォーマットのデータをもとに、各種管理会計指標を算出します。

---

## Status / 開発状況

**EN:** Currently in beta. FAC Format is in pre-release design discussion (targeting v1.0.0 at public launch).

**JA:** 現在ベータ版です。FACフォーマットは公開前の設計検討段階(公開時点でv1.0.0を予定)です。

---

## Contributing / コントリビュート

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for how to propose changes, report issues, or open a pull request.

変更提案・Issue報告・プルリクエストの方法は[`CONTRIBUTING.md`](CONTRIBUTING.md)をご覧ください。

---

## License / ライセンス

Apache License 2.0
