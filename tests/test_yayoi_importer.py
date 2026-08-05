"""
tests/test_yayoi_importer.py

engines/importers/yayoi.py の単体テスト。
freeeインポーターのテスト方針に揃え、tmp_pathでダミーCSV/Excelを都度生成する。

【既知の制限に関する注記】
複数行伝票（借方・貸方が別行に分かれるケース）はCF側の相手科目を正しく
紐付けられない仕様上の制限がある(yayoi.py のdocstring参照)。
test_multi_line_voucher_cf_counterpart_is_unclassified は、この制限が
"意図した挙動どおり"であることを固定するための回帰テストであり、
将来この制限を解消した際にはこのテストの期待値も更新すること。
"""

import pandas as pd
import pytest

from engines.exceptions import (
    InvalidSourceFormatError,
    MappingFileNotFoundError,
    MissingColumnError,
    SourceFileNotFoundError,
)
from engines.importers.yayoi import decompose_to_fac, get_ex_tax_amount, _normalize_date


# --------------------------------------------------
# _normalize_date 単体テスト
# --------------------------------------------------

def test_normalize_date_compact():
    assert _normalize_date("20260401") == "2026-04-01"


def test_normalize_date_slash():
    assert _normalize_date("2026/4/1") == "2026-04-01"


def test_normalize_date_reiwa():
    """令和8年 = 2026年"""
    assert _normalize_date("R08/4/2") == "2026-04-02"


def test_normalize_date_reiwa_gannen():
    """令和元年(R01) = 2019年"""
    assert _normalize_date("R1/7/1") == "2019-07-01"


def test_normalize_date_unrecognized_passthrough():
    """想定外の形式はそのまま返す（後続のpd.to_datetimeに判定を委ねる）"""
    assert _normalize_date("2026-04-01") == "2026-04-01"


# --------------------------------------------------
# get_ex_tax_amount 単体テスト
# --------------------------------------------------

def test_get_ex_tax_amount_subtracts_tax():
    result = get_ex_tax_amount(pd.Series([1100]), pd.Series([100]))
    assert result.iloc[0] == 1000


def test_get_ex_tax_amount_blank_tax_is_zero():
    """税金額が空欄（対象外など）の場合、金額はそのまま返る"""
    result = get_ex_tax_amount(pd.Series([1100]), pd.Series([None]))
    assert result.iloc[0] == 1100


# --------------------------------------------------
# decompose_to_fac 用フィクスチャ
# --------------------------------------------------

def _row(識別フラグ="2000", 伝票No="", 決算="", 取引日付="", 借方勘定科目="", 借方補助科目="", 借方部門="",
         借方税区分="対象外", 借方金額=0, 借方税金額=0, 貸方勘定科目="", 貸方補助科目="", 貸方部門="",
         貸方税区分="対象外", 貸方金額=0, 貸方税金額=0):
    base = [識別フラグ, 伝票No, 決算, 取引日付, 借方勘定科目, 借方補助科目, 借方部門, 借方税区分,
            借方金額, 借方税金額, 貸方勘定科目, 貸方補助科目, 貸方部門, 貸方税区分, 貸方金額, 貸方税金額]
    base += ["摘要"] + [""] * 8  # 残り(番号〜調整)は空でパディング、合計25列
    return base


@pytest.fixture
def sample_rows():
    return [
        # 単一行仕訳: 課税10%の経費
        _row(識別フラグ="2000", 取引日付="2026/4/1", 借方勘定科目="旅費交通費", 借方部門="営業部",
             借方税区分="課税仕入10%", 借方金額=1100, 借方税金額=100,
             貸方勘定科目="現金", 貸方税区分="対象外", 貸方金額=1100, 貸方税金額=0),
        # 単一行仕訳: 令和日付・入金(普通預金が借方)
        _row(識別フラグ="2000", 取引日付="R08/4/2", 借方勘定科目="普通預金", 借方金額=55000,
             貸方勘定科目="売上高", 貸方部門="営業部", 貸方税区分="課税売上10%",
             貸方金額=55000, 貸方税金額=5000),
        # 諸口を相手科目とする仕訳(CFから除外されることを確認するため)
        _row(識別フラグ="2000", 取引日付="2026/4/4", 借方勘定科目="現金", 借方金額=5000,
             貸方勘定科目="諸口", 貸方税区分="対象外", 貸方金額=5000, 貸方税金額=0),
    ]


@pytest.fixture
def multi_line_rows():
    return [
        # 複数行伝票 1行目: 借方のみ(消耗品費)、日付あり
        _row(識別フラグ="2110", 取引日付="20260403", 借方勘定科目="消耗品費", 借方部門="管理部",
             借方税区分="課税仕入10%", 借方金額=3300, 借方税金額=300,
             貸方勘定科目="", 貸方金額=0),
        # 複数行伝票 2行目: 貸方のみ(現金)、日付は空欄=1行目を継承
        _row(識別フラグ="2101", 取引日付="", 借方勘定科目="", 借方金額=0,
             貸方勘定科目="現金", 貸方税区分="対象外", 貸方金額=3300, 貸方税金額=0),
    ]


def _write_yayoi_csv(path, rows):
    df = pd.DataFrame(rows)
    df.to_csv(path, index=False, header=False, encoding="cp932")
    return path


def _write_mapping_excel(path):
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame({
            "会計ソフトの科目名": ["旅費交通費", "売上高", "消耗品費"],
            "account_large": ["変動費", "売上", "固定費"],
            "account_middle": ["旅費交通費", "売上高", "消耗品費"],
            "cost_type": ["変動費", "対象外", "固定費"],
        }).to_excel(writer, sheet_name="pl_cost_mapping", index=False)
        pd.DataFrame({
            "相手勘定の科目名": ["旅費交通費", "売上高", "消耗品費"],
            "account_large": ["変動費", "売上", "固定費"],
            "account_middle": ["旅費交通費", "売上高", "消耗品費"],
            "cf_type": ["営業CF", "営業CF", "営業CF"],
        }).to_excel(writer, sheet_name="cf_mapping", index=False)
    return path


@pytest.fixture
def yayoi_csv_path(tmp_path, sample_rows):
    return _write_yayoi_csv(tmp_path / "yayoi_shiwake.csv", sample_rows)


@pytest.fixture
def yayoi_csv_path_multi_line(tmp_path, multi_line_rows):
    return _write_yayoi_csv(tmp_path / "yayoi_shiwake_multi.csv", multi_line_rows)


@pytest.fixture
def mapping_excel_path(tmp_path):
    return _write_mapping_excel(tmp_path / "mapping_master_yayoi.xlsx")


# --------------------------------------------------
# decompose_to_fac 統合テスト
# --------------------------------------------------

def test_decompose_returns_fac_columns(yayoi_csv_path, mapping_excel_path):
    result = decompose_to_fac(str(yayoi_csv_path), str(mapping_excel_path))
    expected_columns = [
        'date', 'account_large', 'account_middle', 'account_small', 'amount',
        'cost_type', 'cf_type', 'dept_original', 'dept_allocated', 'status'
    ]
    assert list(result.columns) == expected_columns


def test_decompose_pl_amount_subtracts_tax(yayoi_csv_path, mapping_excel_path):
    """PL側の金額は「金額-税金額」で税抜化される(1,100円・税額100円 -> -1,000円)"""
    result = decompose_to_fac(str(yayoi_csv_path), str(mapping_excel_path))
    pl_travel = result[(result['cf_type'] == "対象外") & (result['account_middle'] == "旅費交通費")]
    assert pl_travel['amount'].iloc[0] == pytest.approx(-1000.0)


def test_decompose_cf_amount_uses_tax_included_value(yayoi_csv_path, mapping_excel_path):
    """CF側の金額は常に税込(借方金額・貸方金額そのまま)で計上される"""
    result = decompose_to_fac(str(yayoi_csv_path), str(mapping_excel_path))
    cf_travel = result[(result['cf_type'] == "営業CF") & (result['account_middle'] == "旅費交通費")]
    assert cf_travel['amount'].iloc[0] == pytest.approx(-1100.0)


def test_decompose_reiwa_date_is_converted(yayoi_csv_path, mapping_excel_path):
    """令和表記の日付が正しく西暦に変換される(R08/4/2 -> 2026-04-02)"""
    result = decompose_to_fac(str(yayoi_csv_path), str(mapping_excel_path))
    sales_row = result[result['account_middle'] == "売上高"]
    assert (sales_row['date'] == "2026-04-02").all()


def test_decompose_dept_allocated_defaults_to_dept_original(yayoi_csv_path, mapping_excel_path):
    result = decompose_to_fac(str(yayoi_csv_path), str(mapping_excel_path))
    assert (result['dept_allocated'] == result['dept_original']).all()


def test_decompose_excludes_shoroku_from_cf(yayoi_csv_path, mapping_excel_path):
    result = decompose_to_fac(str(yayoi_csv_path), str(mapping_excel_path))
    assert "諸口" not in result['account_middle'].values
    assert "諸口" not in result['account_large'].values


def test_multi_line_voucher_cf_counterpart_is_unclassified(yayoi_csv_path_multi_line, mapping_excel_path):
    """
    既知の制限の回帰テスト: 複数行伝票では、CF側の相手科目を同一行内から
    参照できないため、相手科目が空欄となり account_large が「未分類」になる。
    この制限を将来解消した場合は、本テストの期待値を更新すること。
    """
    result = decompose_to_fac(str(yayoi_csv_path_multi_line), str(mapping_excel_path))
    # 相手科目が空欄のため、cf_mappingにもマッチせず account_large・cf_type ともに「未分類」になる
    unmatched_rows = result[result['account_large'] == "未分類"]
    assert len(unmatched_rows) > 0
    assert (unmatched_rows['cf_type'] == "未分類").all()

    # 一方でPL側(消耗品費)の金額自体は正しく計上されていることを確認
    pl_row = result[(result['cf_type'] == "対象外") & (result['account_middle'] == "消耗品費")]
    assert pl_row['amount'].iloc[0] == pytest.approx(-3000.0)


# --------------------------------------------------
# 異常系テスト
# --------------------------------------------------

def test_missing_input_file_raises(tmp_path, mapping_excel_path):
    with pytest.raises(SourceFileNotFoundError):
        decompose_to_fac(
            str(tmp_path / "does_not_exist.csv"),
            str(mapping_excel_path),
        )


def test_missing_mapping_file_raises(yayoi_csv_path, tmp_path):
    with pytest.raises(MappingFileNotFoundError):
        decompose_to_fac(
            str(yayoi_csv_path),
            str(tmp_path / "does_not_exist.xlsx"),
        )


def test_insufficient_columns_raises(tmp_path, mapping_excel_path):
    """列数が標準フォーマットとして不足している(16列未満)場合はInvalidSourceFormatError"""
    csv_path = tmp_path / "yayoi_shiwake_broken.csv"
    # 借方金額(9列目)までしかない、明らかに列不足のデータ
    broken_row = ["2000", "", "", "2026/4/1", "旅費交通費", "", "営業部", "課税仕入10%", 1100]
    pd.DataFrame([broken_row]).to_csv(csv_path, index=False, header=False, encoding="cp932")

    with pytest.raises(InvalidSourceFormatError):
        decompose_to_fac(str(csv_path), str(mapping_excel_path))


def test_missing_mapping_column_raises(yayoi_csv_path, tmp_path):
    """マッピングマスタ側の必須列(会計ソフトの科目名)が欠落している場合"""
    broken_mapping_path = tmp_path / "broken_mapping.xlsx"
    with pd.ExcelWriter(broken_mapping_path) as writer:
        pd.DataFrame({"account_large": ["変動費"]}).to_excel(writer, sheet_name="pl_cost_mapping", index=False)
        pd.DataFrame({"相手勘定の科目名": ["旅費交通費"]}).to_excel(writer, sheet_name="cf_mapping", index=False)

    with pytest.raises(MissingColumnError):
        decompose_to_fac(str(yayoi_csv_path), str(broken_mapping_path))
