"""
tests/test_freee_importer.py

engines/importers/freee.py の単体テスト。
money_forwardインポーターのテスト方針(tmp_pathでダミーCSV/Excelを都度生成し、
ファイル未存在・列欠落・税処理・CF判定などを検証する)に揃えている。
"""

import pandas as pd
import pytest

from engines.exceptions import (
    MappingFileNotFoundError,
    MissingColumnError,
    SourceFileNotFoundError,
)
from engines.importers.freee import decompose_to_fac, get_tax_divisor


# --------------------------------------------------
# get_tax_divisor 単体テスト
# --------------------------------------------------

def test_get_tax_divisor_10percent_zeikomi():
    """税込経理・税率10%の場合、除数は1.1になる"""
    rate = pd.Series([10])
    method = pd.Series(["税込経理"])
    result = get_tax_divisor(rate, method)
    assert result[0] == pytest.approx(1.1)


def test_get_tax_divisor_8percent_zeikomi():
    """税込経理・税率8%（軽減税率含む）の場合、除数は1.08になる"""
    rate = pd.Series([8])
    method = pd.Series(["税込経理"])
    result = get_tax_divisor(rate, method)
    assert result[0] == pytest.approx(1.08)


def test_get_tax_divisor_no_rate_is_untouched():
    """税率が空欄（対象外など）の場合、税込経理でも除数は1.0になる"""
    rate = pd.Series([None])
    method = pd.Series(["税込経理"])
    result = get_tax_divisor(rate, method)
    assert result[0] == pytest.approx(1.0)


def test_get_tax_divisor_zeinuki_ignores_rate():
    """税抜経理の場合、税率が入っていても割り戻しは行わず除数は1.0になる"""
    rate = pd.Series([10])
    method = pd.Series(["税抜経理"])
    result = get_tax_divisor(rate, method)
    assert result[0] == pytest.approx(1.0)


def test_get_tax_divisor_mixed_rows():
    """複数行が混在していても行ごとに正しく判定できる"""
    rate = pd.Series([10, 8, None, 10])
    method = pd.Series(["税込経理", "税込経理", "税込経理", "税抜経理"])
    result = get_tax_divisor(rate, method)
    assert result[0] == pytest.approx(1.1)
    assert result[1] == pytest.approx(1.08)
    assert result[2] == pytest.approx(1.0)
    assert result[3] == pytest.approx(1.0)


# --------------------------------------------------
# decompose_to_fac 用フィクスチャ
# --------------------------------------------------

def _write_freee_csv(path, rows, tax_method="税込経理"):
    df = pd.DataFrame(rows)
    df["消費税経理処理方法"] = tax_method
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def _write_mapping_excel(path):
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame({
            "会計ソフトの科目名": ["旅費交通費", "売上高", "受取手数料"],
            "account_large": ["変動費", "売上", "営業外収益"],
            "account_middle": ["旅費交通費", "売上高", "受取手数料"],
            "cost_type": ["変動費", "対象外", "対象外"],
        }).to_excel(writer, sheet_name="pl_cost_mapping", index=False)
        pd.DataFrame({
            "相手勘定の科目名": ["旅費交通費", "売上高", "受取手数料"],
            "account_large": ["変動費", "売上", "営業外収益"],
            "account_middle": ["旅費交通費", "売上高", "受取手数料"],
            "cf_type": ["営業CF", "営業CF", "営業CF"],
        }).to_excel(writer, sheet_name="cf_mapping", index=False)
    return path


@pytest.fixture
def sample_rows():
    return [
        {
            "取引日": "2026/04/01",
            "借方勘定科目": "旅費交通費",
            "借方金額": 1080,
            "借方税区分": "課対仕入8%",
            "借方税率": 8,
            "借方部門": "営業部",
            "貸方勘定科目": "現金",
            "貸方金額": 1080,
            "貸方税区分": "対象外",
            "貸方税率": None,
            "貸方部門": "",
        },
        {
            "取引日": "2026/04/02",
            "借方勘定科目": "普通預金",
            "借方金額": 55000,
            "借方税区分": "対象外",
            "借方税率": None,
            "借方部門": "",
            "貸方勘定科目": "売上高",
            "貸方金額": 55000,
            "貸方税区分": "課税売上10%",
            "貸方税率": 10,
            "貸方部門": "営業部",
        },
        {
            "取引日": "2026/04/03",
            "借方勘定科目": "普通預金",
            "借方金額": 33000,
            "借方税区分": "対象外",
            "借方税率": None,
            "借方部門": "",
            "貸方勘定科目": "受取手数料",
            "貸方金額": 33000,
            "貸方税区分": "課税売上10%",
            "貸方税率": 10,
            "貸方部門": "管理部",
        },
        {
            # 諸口経由の取引はCFから除外されることを確認するための行
            "取引日": "2026/04/04",
            "借方勘定科目": "現金",
            "借方金額": 5000,
            "借方税区分": "対象外",
            "借方税率": None,
            "借方部門": "",
            "貸方勘定科目": "諸口",
            "貸方金額": 5000,
            "貸方税区分": "対象外",
            "貸方税率": None,
            "貸方部門": "",
        },
    ]


@pytest.fixture
def freee_csv_path(tmp_path, sample_rows):
    return _write_freee_csv(tmp_path / "freee_shiwake.csv", sample_rows, tax_method="税込経理")


@pytest.fixture
def freee_csv_path_zeinuki(tmp_path, sample_rows):
    return _write_freee_csv(tmp_path / "freee_shiwake_zeinuki.csv", sample_rows, tax_method="税抜経理")


@pytest.fixture
def mapping_excel_path(tmp_path):
    return _write_mapping_excel(tmp_path / "mapping_master_freee.xlsx")


# --------------------------------------------------
# decompose_to_fac 統合テスト
# --------------------------------------------------

def test_decompose_returns_fac_columns(freee_csv_path, mapping_excel_path):
    """戻り値がFACフォーマットの列構成を満たしている"""
    result = decompose_to_fac(str(freee_csv_path), str(mapping_excel_path))
    expected_columns = [
        'date', 'account_large', 'account_middle', 'account_small', 'amount',
        'cost_type', 'cf_type', 'dept_original', 'dept_allocated', 'status'
    ]
    assert list(result.columns) == expected_columns


def test_decompose_pl_amount_is_tax_excluded_under_zeikomi(freee_csv_path, mapping_excel_path):
    """税込経理の場合、PL側の金額は税抜化されている（1,080円・税率8% -> -1,000円）"""
    result = decompose_to_fac(str(freee_csv_path), str(mapping_excel_path))
    pl_travel = result[(result['cf_type'] == "対象外") & (result['account_middle'] == "旅費交通費")]
    assert pl_travel['amount'].iloc[0] == pytest.approx(-1000.0)


def test_decompose_pl_amount_is_untouched_under_zeinuki(freee_csv_path_zeinuki, mapping_excel_path):
    """税抜経理の場合、PL側の金額は割り戻されず、そのまま（-1,080円）になる"""
    result = decompose_to_fac(str(freee_csv_path_zeinuki), str(mapping_excel_path))
    pl_travel = result[(result['cf_type'] == "対象外") & (result['account_middle'] == "旅費交通費")]
    assert pl_travel['amount'].iloc[0] == pytest.approx(-1080.0)


def test_decompose_cf_amount_uses_tax_included_value(freee_csv_path, mapping_excel_path):
    """CF側の金額は常に税込（借方金額・貸方金額そのまま）で計上される"""
    result = decompose_to_fac(str(freee_csv_path), str(mapping_excel_path))
    cf_travel = result[(result['cf_type'] == "営業CF") & (result['account_middle'] == "旅費交通費")]
    assert cf_travel['amount'].iloc[0] == pytest.approx(-1080.0)


def test_decompose_cf_cash_in_is_positive(freee_csv_path, mapping_excel_path):
    """現預金が借方（入金）の場合、CF金額はプラスになる"""
    result = decompose_to_fac(str(freee_csv_path), str(mapping_excel_path))
    cf_sales = result[(result['cf_type'] == "営業CF") & (result['account_middle'] == "売上高")]
    assert cf_sales['amount'].iloc[0] == pytest.approx(55000.0)


def test_decompose_dept_allocated_defaults_to_dept_original(freee_csv_path, mapping_excel_path):
    """配賦エンジン未実行時、dept_allocatedはdept_originalと同じ値になる"""
    result = decompose_to_fac(str(freee_csv_path), str(mapping_excel_path))
    assert (result['dept_allocated'] == result['dept_original']).all()


def test_decompose_excludes_shoroku_from_cf(freee_csv_path, mapping_excel_path):
    """諸口を相手科目とする仕訳は、CF側の抽出から除外される"""
    result = decompose_to_fac(str(freee_csv_path), str(mapping_excel_path))
    assert "諸口" not in result['account_middle'].values
    assert "諸口" not in result['account_large'].values


# --------------------------------------------------
# 異常系テスト
# --------------------------------------------------

def test_missing_input_file_raises(tmp_path, mapping_excel_path):
    with pytest.raises(SourceFileNotFoundError):
        decompose_to_fac(
            str(tmp_path / "does_not_exist.csv"),
            str(mapping_excel_path),
        )


def test_missing_mapping_file_raises(freee_csv_path, tmp_path):
    with pytest.raises(MappingFileNotFoundError):
        decompose_to_fac(
            str(freee_csv_path),
            str(tmp_path / "does_not_exist.xlsx"),
        )


def test_missing_required_column_raises(tmp_path, mapping_excel_path, sample_rows):
    # 「借方税率」列を欠落させたCSVを用意する
    broken_rows = [{k: v for k, v in row.items() if k != "借方税率"} for row in sample_rows]
    csv_path = tmp_path / "freee_shiwake_broken.csv"
    df = pd.DataFrame(broken_rows)
    df["消費税経理処理方法"] = "税込経理"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    with pytest.raises(MissingColumnError):
        decompose_to_fac(str(csv_path), str(mapping_excel_path))