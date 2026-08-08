"""
scripts/export_aggregation.py

FACフォーマットのCSVを読み込み、engines/aggregators/crosstab.py の
aggregate_fac() でクロス集計し、結果をCSVに出力するCLIラッパー。

ブラウザやStreamlitを開かず、コマンド一行で「集計→CSV保存」を完結させるための
薄いスクリプト。aggregate_fac自体には一切手を加えず、
引数の受け取り・ファイルの読み書きだけを担う。

使い方:
    python scripts/export_aggregation.py <入力CSV> <出力CSV> --rows <行軸...> [--cols <列軸...>] [--total]

例:
    # 科目大分類 × 部門
    python scripts/export_aggregation.py fac_output.csv trial_balance.csv --rows account_large --cols dept_original --total

    # 科目大分類 × 月次推移
    python scripts/export_aggregation.py fac_output.csv monthly.csv --rows account_large --cols year_month

    # 科目大分類・中分類の2階層で縦持ち集計（cols省略）
    python scripts/export_aggregation.py fac_output.csv summary.csv --rows account_large account_middle
"""

import argparse
import os
import sys

import pandas as pd

# scripts/ から見て一つ上（リポジトリルート）を import パスに追加する。
# これにより、リポジトリルート以外のカレントディレクトリから実行しても
# `from engines...` の import が解決できるようにする。
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from engines.aggregators.crosstab import aggregate_fac  # noqa: E402


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="FACフォーマットのCSVをクロス集計し、結果をCSVに出力する。"
    )
    parser.add_argument("input_csv", help="FACフォーマットのCSVファイルパス")
    parser.add_argument("output_csv", help="集計結果の出力先CSVファイルパス")
    parser.add_argument(
        "--rows",
        nargs="+",
        required=True,
        metavar="COLUMN",
        help="行軸に使う列名（複数指定可）。例: --rows account_large account_middle "
             "'year'/'month'/'year_month' も指定可能（date列から自動生成）。",
    )
    parser.add_argument(
        "--cols",
        nargs="+",
        default=None,
        metavar="COLUMN",
        help="列展開に使う列名（複数指定可）。省略時はrowsでのgroupbyのみ（縦持ち）。",
    )
    parser.add_argument(
        "--value-col",
        default="amount",
        metavar="COLUMN",
        help="集計対象の金額列。デフォルトは 'amount'。",
    )
    parser.add_argument(
        "--total",
        action="store_true",
        help="合計行・合計列を追加する。",
    )
    parser.add_argument(
        "--encoding",
        default="utf-8-sig",
        help="出力CSVの文字コード。デフォルトは 'utf-8-sig'（Excelで文字化けしない）。",
    )
    return parser


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    if not os.path.exists(args.input_csv):
        print(f"エラー: 入力CSVが見つかりません: {args.input_csv}", file=sys.stderr)
        sys.exit(1)

    df = pd.read_csv(args.input_csv)

    try:
        result = aggregate_fac(
            df,
            rows=args.rows,
            cols=args.cols,
            value_col=args.value_col,
            include_total=args.total,
        )
    except (ValueError, KeyError) as e:
        print(f"エラー: 集計に失敗しました: {e}", file=sys.stderr)
        sys.exit(1)

    result.to_csv(args.output_csv, index=False, encoding=args.encoding)
    print(f"集計結果を '{args.output_csv}' に出力しました。（{len(result)}行）")


if __name__ == "__main__":
    main()
