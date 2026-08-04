"""
Tests for the Money Forward -> FAC Format import engine.

これらのテストは実際の会計データを使わず、最小限の合成データを都度生成する。
- get_tax_divisor: 消費税区分の除数変換ロジック
- decompose_to_fac: PL/CF分解、部門の左右整合性、dept_allocatedの暫定値、
  account_smallの抽出、を検証する
"""
import numpy as np
import pandas as pd
import pytest
from engines.exceptions import SourceFileNotFoundError

# 実際の配置場所に合わせてこのimportを調整してください
# 例: engines/importers/money_forward.py に配置した場合
from engines.importers.money_forward import get_tax_divisor, decompose_to_fac


# --------------------------------------------------
# get_tax_divisor のテスト
# --------------------------------------------------

def test_get_tax_divisor_10_percent():
    series = pd.Series(["課税売上10%"])
    result = get_tax_divisor(series)
    assert result[0] == pytest.approx(1.1)


def test_get_tax_divisor_8_percent_reduced():
    series = pd.Series(["課税仕入8%(軽減)"])
    result = get_tax_divisor(series)
    assert result[0] == pytest.approx(1.08)


def test_get_tax_divisor_non_taxable_defaults_to_one():
    series = pd.Series(["非課税", "対象外", None])
    result = get_tax_divisor(series)
    assert list(result) == [1.0, 1.0, 1.0]


# --------------------------------------------------
# decompose_to_fac のテスト用フィクスチャ
# --------------------------------------------------

@pytest.fixture
def mf_csv_and_mapping(tmp_path):
    """
    最小限の合成MF仕訳データと、対応するマッピングマスタを一時ファイルとして生成する。
    シナリオ:
    - 広告宣伝費(経費・変動費・営業CF対象外)を、マーケティング部門で1件計上
    - 売上高(収益)を、営業部門で1件計上
    - 売上の入金(現金への入金)を1件計上
    """
    mf_rows = pd.DataFrame([
        {
            "取引日": "2026-04-01",
            "借方勘定科目": "広告宣伝費",
            "借方部門": "マーケティング",
            "借方補助科目": "Web広告",
            "借方金額(円)": 55000,
            "借方税区分": "課税仕入10%",
            "貸方勘定科目": "現金",
            "貸方部門": "経理",
            "貸方補助科目": "",
            "貸方金額(円)": 55000,
            "貸方税区分": "対象外",
        },
        {
            "取引日": "2026-04-02",
            "借方勘定科目": "現金",
            "借方部門": "経理",
            "借方補助科目": "",
            "借方金額(円)": 110000,
            "借方税区分": "対象外",
            "貸方勘定科目": "売上高",
            "貸方部門": "営業",
            "貸方補助科目": "A社向け",
            "貸方金額(円)": 110000,
            "貸方税区分": "課税売上10%",
        },
    ])
    mf_csv_path = tmp_path / "mf_shiwake_raw.csv"
    mf_rows.to_csv(mf_csv_path, index=False, encoding="cp932")

    pl_map = pd.DataFrame([
        {"会計ソフトの科目名": "広告宣伝費", "account_large": "経費", "account_middle": "広告宣伝費", "cost_type": "変動費"},
        {"会計ソフトの科目名": "売上高", "account_large": "売上", "account_middle": "売上高", "cost_type": "対象外"},
    ])
    cf_map = pd.DataFrame([
        {"相手勘定の科目名": "売上高", "account_large": "売上", "account_middle": "売上高", "cf_type": "営業CF"},
    ])

    mapping_excel_path = tmp_path / "mapping_master.xlsx"
    with pd.ExcelWriter(mapping_excel_path) as writer:
        pl_map.to_excel(writer, sheet_name="pl_cost_mapping", index=False)
        cf_map.to_excel(writer, sheet_name="cf_mapping", index=False)

    return str(mf_csv_path), str(mapping_excel_path)


# --------------------------------------------------
# decompose_to_fac のテスト本体
# --------------------------------------------------

def test_decompose_produces_required_fac_columns(mf_csv_and_mapping):
    csv_path, excel_path = mf_csv_and_mapping
    df = decompose_to_fac(csv_path, excel_path)

    required_columns = [
        "date", "account_large", "account_middle", "account_small", "amount",
        "cost_type", "cf_type", "dept_original", "dept_allocated", "status",
    ]
    for col in required_columns:
        assert col in df.columns, f"FACフォーマット必須カラム '{col}' が出力に含まれていません"


def test_pl_expense_is_negative_and_tax_excluded(mf_csv_and_mapping):
    csv_path, excel_path = mf_csv_and_mapping
    df = decompose_to_fac(csv_path, excel_path)

    ad_row = df[(df["account_middle"] == "広告宣伝費") & (df["cf_type"] == "対象外")]
    assert len(ad_row) == 1
    # 55,000円(税込10%) → 税抜50,000円、費用なのでマイナス
    assert ad_row.iloc[0]["amount"] == pytest.approx(-50000.0)
    assert ad_row.iloc[0]["dept_original"] == "マーケティング"
    assert ad_row.iloc[0]["account_small"] == "Web広告"


def test_cf_department_matches_counter_account_side(mf_csv_and_mapping):
    """
    部門バグ修正の回帰テスト:
    CF側のdept_originalは、現金側ではなく相手科目側(この場合は売上高＝営業部門)の
    部門と一致していなければならない。
    """
    csv_path, excel_path = mf_csv_and_mapping
    df = decompose_to_fac(csv_path, excel_path)

    cf_row = df[(df["account_middle"] == "売上高") & (df["cf_type"] == "営業CF")]
    assert len(cf_row) == 1
    # 現金勘定側の部門(経理)ではなく、相手科目(売上高)側の部門(営業)であること
    assert cf_row.iloc[0]["dept_original"] == "営業"
    assert cf_row.iloc[0]["account_small"] == "A社向け"
    # 入金なのでプラス、税込金額のまま(CFは税込処理)
    assert cf_row.iloc[0]["amount"] == pytest.approx(110000.0)


def test_dept_allocated_defaults_to_dept_original(mf_csv_and_mapping):
    """
    配賦エンジンが未実行の段階では、dept_allocatedはdept_originalと同値であること。
    """
    csv_path, excel_path = mf_csv_and_mapping
    df = decompose_to_fac(csv_path, excel_path)

    assert (df["dept_allocated"] == df["dept_original"]).all()


def test_missing_input_file_raises(tmp_path):
    with pytest.raises(SourceFileNotFoundError):
        decompose_to_fac(
            str(tmp_path / "does_not_exist.csv"),
            str(tmp_path / "does_not_exist.xlsx"),
        )