"""
tests/test_aggregate_fac.py

engines/aggregators/crosstab.py の単体テスト。
"""

import pandas as pd
import pytest

from engines.aggregators.crosstab import aggregate_fac


@pytest.fixture
def fac_df():
    return pd.DataFrame([
        {'date': '2026-04-01', 'account_large': '変動費', 'account_middle': '旅費交通費', 'amount': -1000, 'dept_original': '営業部'},
        {'date': '2026-04-02', 'account_large': '売上', 'account_middle': '売上高', 'amount': 50000, 'dept_original': '営業部'},
        {'date': '2026-05-01', 'account_large': '変動費', 'account_middle': '旅費交通費', 'amount': -2000, 'dept_original': '営業部'},
        {'date': '2026-05-03', 'account_large': '売上', 'account_middle': '売上高', 'amount': 60000, 'dept_original': '管理部'},
        {'date': '2026-05-05', 'account_large': '固定費', 'account_middle': '地代家賃', 'amount': -30000, 'dept_original': '管理部'},
    ])


def test_rows_only_returns_long_format(fac_df):
    """colsを指定しない場合、rowsでgroupbyした縦持ちのDataFrameを返す"""
    result = aggregate_fac(fac_df, rows=["account_large"])
    assert list(result.columns) == ["account_large", "amount"]
    sales = result[result["account_large"] == "売上"]["amount"].iloc[0]
    assert sales == 110000


def test_rows_and_cols_returns_pivot(fac_df):
    """rows・cols両方を指定した場合、colsの値が列見出しになるpivot形式を返す"""
    result = aggregate_fac(fac_df, rows=["account_large"], cols=["dept_original"])
    assert "営業部" in result.columns
    assert "管理部" in result.columns
    sales_row = result[result["account_large"] == "売上"]
    assert sales_row["営業部"].iloc[0] == 50000
    assert sales_row["管理部"].iloc[0] == 60000


def test_year_month_derived_column(fac_df):
    """'year_month'をcolsに指定すると、date列から月次列が自動生成される"""
    result = aggregate_fac(fac_df, rows=["account_large"], cols=["year_month"])
    assert "2026-04" in result.columns
    assert "2026-05" in result.columns
    travel_row = result[result["account_large"] == "変動費"]
    assert travel_row["2026-04"].iloc[0] == -1000
    assert travel_row["2026-05"].iloc[0] == -2000


def test_year_derived_column(fac_df):
    """'year'をrowsに指定すると、date列から年次列が自動生成される"""
    result = aggregate_fac(fac_df, rows=["year"])
    assert list(result["year"]) == ["2026"]
    assert result["amount"].iloc[0] == 77000


def test_multi_level_rows_without_cols(fac_df):
    """rowsに複数列を指定すると、その階層でgroupbyされる"""
    result = aggregate_fac(fac_df, rows=["account_large", "account_middle"])
    assert list(result.columns) == ["account_large", "account_middle", "amount"]
    assert len(result) == 3  # 変動費/旅費交通費, 売上/売上高, 固定費/地代家賃


def test_include_total_adds_total_row_for_long_format(fac_df):
    result = aggregate_fac(fac_df, rows=["account_large"], include_total=True)
    total_row = result[result["account_large"] == "合計"]
    assert len(total_row) == 1
    assert total_row["amount"].iloc[0] == 77000


def test_include_total_adds_total_row_and_column_for_pivot(fac_df):
    result = aggregate_fac(fac_df, rows=["account_large"], cols=["dept_original"], include_total=True)
    assert "合計" in result.columns
    total_row = result[result["account_large"] == "合計"]
    assert len(total_row) == 1
    assert total_row["合計"].iloc[0] == 77000


def test_custom_value_col():
    """value_colを指定すれば、amount以外の列も集計できる"""
    df = pd.DataFrame([
        {'date': '2026-04-01', 'account_large': '変動費', 'budget_amount': -1200},
        {'date': '2026-04-02', 'account_large': '変動費', 'budget_amount': -800},
    ])
    result = aggregate_fac(df, rows=["account_large"], value_col="budget_amount")
    assert result["budget_amount"].iloc[0] == -2000


def test_empty_rows_raises_value_error(fac_df):
    with pytest.raises(ValueError):
        aggregate_fac(fac_df, rows=[])


def test_all_nan_axis_column_is_not_silently_dropped():
    """
    dept_originalが未入力(全てNaN)のFACデータでも、pivot_tableがNaN軸の行を
    黙って除外してしまわないよう、プレースホルダーで埋められて結果に残ること。
    """
    df = pd.DataFrame([
        {'date': '2026-04-01', 'account_large': '経費', 'amount': -1000, 'dept_original': None},
        {'date': '2026-04-02', 'account_large': '売上', 'amount': 5000, 'dept_original': None},
    ])
    result = aggregate_fac(df, rows=["account_large"], cols=["dept_original"])
    assert len(result) == 2
    assert "(未設定)" in result.columns


def test_partial_nan_axis_column_groups_nan_separately():
    """rows/colsの一部がNaNの場合も、そのNaN分がプレースホルダーとして独立集計される"""
    df = pd.DataFrame([
        {'date': '2026-04-01', 'account_large': '経費', 'amount': -1000, 'dept_original': '営業部'},
        {'date': '2026-04-02', 'account_large': '経費', 'amount': -500, 'dept_original': None},
    ])
    result = aggregate_fac(df, rows=["account_large"], cols=["dept_original"])
    assert result["営業部"].iloc[0] == -1000
    assert result["(未設定)"].iloc[0] == -500
