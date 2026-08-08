"""
engines/aggregators/crosstab.py

FACフォーマットのDataFrameを、任意の行軸・列軸でクロス集計する汎用エンジン。

【設計上の境界線】
集計ロジックの範囲は「新しい数値を生み出さないこと」。
ここで行うのは groupby / pivot_table による合計値の算出のみであり、
比率・差分・成長率などの派生計算は一切行わない
（それらは engines/metrics/ の責務であり、本モジュールには持ち込まない）。

【使い方の例】
  # 科目大分類 × 部門 のクロス集計（試算表）
  aggregate_fac(df, rows=["account_large"], cols=["dept_original"])

  # 科目大分類 × 月次推移
  aggregate_fac(df, rows=["account_large"], cols=["year_month"])

  # 科目大分類・科目中分類の2階層 × 部門（縦の階層はrowsに複数列を指定）
  aggregate_fac(df, rows=["account_large", "account_middle"], cols=["dept_original"])

  # 列展開せず、科目大分類だけで合計（縦持ちの単純集計）
  aggregate_fac(df, rows=["account_large"])
"""

import pandas as pd

# rows/colsに指定できる「日付由来の派生軸」。FACフォーマットのdate列から自動生成する。
_DERIVED_TIME_COLUMNS = {"year", "month", "year_month"}


def _add_derived_time_columns(df: pd.DataFrame, requested_columns) -> pd.DataFrame:
    """
    rows/colsに year, month, year_month が含まれる場合、date列から派生列を追加する。
    元のdfは変更せず、コピーを返す。
    """
    needed = _DERIVED_TIME_COLUMNS & set(requested_columns)
    if not needed:
        return df

    df = df.copy()
    dates = pd.to_datetime(df['date'])
    if 'year' in needed:
        df['year'] = dates.dt.year.astype(str)
    if 'month' in needed:
        df['month'] = dates.dt.month.astype(str).str.zfill(2)
    if 'year_month' in needed:
        df['year_month'] = dates.dt.strftime('%Y-%m')
    return df


def aggregate_fac(
    df: pd.DataFrame,
    rows,
    cols=None,
    value_col: str = "amount",
    include_total: bool = False,
) -> pd.DataFrame:
    """
    FACフォーマットのDataFrameを、指定した行軸・列軸でクロス集計する。

    Args:
        df: FACフォーマットのDataFrame（date列・amount列を含むこと）
        rows: 行として使う列名のリスト（例: ["account_large", "account_middle"]）。
              "year" / "month" / "year_month" を指定すると date列から自動的に派生させる。
        cols: 列として展開する列名のリスト（例: ["dept_original"]）。
              Noneの場合は展開せず、rowsでgroupbyしただけの縦持ちの表を返す。
        value_col: 集計対象の金額列。デフォルトは "amount"。
        include_total: True の場合、行・列それぞれに合計（「合計」列/行）を追加する。

    Returns:
        クロス集計されたDataFrame。
        - cols を指定した場合: pivot形式（列見出しがcolsの値になったワイド形式）
        - cols が None の場合: rowsでgroupbyしたsum値の縦持ちDataFrame
    """
    rows = list(rows)
    cols = list(cols) if cols else []

    if not rows:
        raise ValueError("rows には少なくとも1つの列名を指定してください。")

    df = _add_derived_time_columns(df, rows + cols)

    # pandasのgroupby/pivot_tableは、軸に使う列の値がNaNの行をデフォルトで
    # 黙って除外してしまう。FACフォーマットではdept_original等が未入力
    # （NaN）であることが正式に許容されているため、それらの行が集計結果から
    # 消えてしまわないよう、軸として使う列のNaNを明示的なプレースホルダーで埋める。
    axis_columns = rows + cols
    df = df.copy()
    for col in axis_columns:
        if df[col].isna().any():
            df[col] = df[col].fillna("(未設定)")

    if not cols:
        result = df.groupby(rows, dropna=False)[value_col].sum().reset_index()
        if include_total:
            total_row = {col: ("合計" if i == 0 else "") for i, col in enumerate(rows)}
            total_row[value_col] = result[value_col].sum()
            result = pd.concat([result, pd.DataFrame([total_row])], ignore_index=True)
        return result

    result = pd.pivot_table(
        df,
        index=rows,
        columns=cols,
        values=value_col,
        aggfunc="sum",
        fill_value=0,
        margins=include_total,
        margins_name="合計",
    )
    return result.reset_index()
