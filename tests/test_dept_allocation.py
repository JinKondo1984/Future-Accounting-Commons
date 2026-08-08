"""
tests/test_dept_allocation.py

engines/allocators/dept_allocation.py の単体テスト。
"""

import pandas as pd
import pytest

from engines.allocators.dept_allocation import allocate_fac
from engines.exceptions import MappingFileNotFoundError, MissingColumnError


def _write_rules(path, rows):
    df = pd.DataFrame(rows)
    with pd.ExcelWriter(path) as writer:
        df.to_excel(writer, sheet_name="allocation_rules", index=False)
    return path


@pytest.fixture
def fac_df():
    return pd.DataFrame([
        {'date': '2026-04-01', 'account_large': '固定費', 'account_middle': '家賃', 'account_small': '',
         'amount': -100000, 'cost_type': '固定費', 'cf_type': '対象外',
         'dept_original': '本部', 'dept_allocated': '本部', 'status': '実績'},
        {'date': '2026-04-02', 'account_large': '人件費', 'account_middle': '給与手当', 'account_small': '',
         'amount': -90000, 'cost_type': '固定費', 'cf_type': '対象外',
         'dept_original': '本部', 'dept_allocated': '本部', 'status': '実績'},
        {'date': '2026-04-03', 'account_large': '売上高', 'account_middle': '売上高', 'account_small': '',
         'amount': 300000, 'cost_type': '対象外', 'cf_type': '対象外',
         'dept_original': '名セン', 'dept_allocated': '名セン', 'status': '実績'},
        {'date': '2026-04-04', 'account_large': '売上高', 'account_middle': '売上高', 'account_small': '',
         'amount': 100000, 'cost_type': '対象外', 'cf_type': '対象外',
         'dept_original': '和セン', 'dept_allocated': '和セン', 'status': '実績'},
        {'date': '2026-04-05', 'account_large': '変動費', 'account_middle': '旅費交通費', 'account_small': '',
         'amount': -5000, 'cost_type': '変動費', 'cf_type': '対象外',
         'dept_original': '名セン', 'dept_allocated': '名セン', 'status': '実績'},
    ])


@pytest.fixture
def rules_path(tmp_path):
    rows = [
        # 固定比率(家賃のみに限定)
        {'source_dept': '本部', 'target_dept': '名セン', 'rule_type': '固定比率', 'ratio': 0.6,
         'ratio_basis_account_large': '', 'target_account_middle': '家賃'},
        {'source_dept': '本部', 'target_dept': '和セン', 'rule_type': '固定比率', 'ratio': 0.4,
         'ratio_basis_account_large': '', 'target_account_middle': '家賃'},
        # 比率(一般ルール。給与手当はこちらにマッチ)
        {'source_dept': '本部', 'target_dept': '名セン', 'rule_type': '比率', 'ratio': None,
         'ratio_basis_account_large': '売上高', 'target_account_middle': ''},
        {'source_dept': '本部', 'target_dept': '和セン', 'rule_type': '比率', 'ratio': None,
         'ratio_basis_account_large': '売上高', 'target_account_middle': ''},
    ]
    return _write_rules(tmp_path / "rules.xlsx", rows)


def test_fixed_ratio_splits_row_correctly(fac_df, rules_path):
    """固定比率ルールにより、対象行が比率通りに分裂する(家賃 0.6/0.4)"""
    result = allocate_fac(fac_df, str(rules_path))
    rent_rows = result[result['account_middle'] == '家賃']
    assert len(rent_rows) == 2
    name_sen = rent_rows[rent_rows['dept_allocated'] == '名セン']['amount'].iloc[0]
    wa_sen = rent_rows[rent_rows['dept_allocated'] == '和セン']['amount'].iloc[0]
    assert name_sen == pytest.approx(-60000)
    assert wa_sen == pytest.approx(-40000)


def test_dynamic_ratio_uses_basis_account_large(fac_df, rules_path):
    """比率ルールにより、売上高比率(300,000:100,000=0.75:0.25)で按分される"""
    result = allocate_fac(fac_df, str(rules_path))
    salary_rows = result[result['account_middle'] == '給与手当']
    name_sen = salary_rows[salary_rows['dept_allocated'] == '名セン']['amount'].iloc[0]
    wa_sen = salary_rows[salary_rows['dept_allocated'] == '和セン']['amount'].iloc[0]
    assert name_sen == pytest.approx(-67500)
    assert wa_sen == pytest.approx(-22500)


def test_unmatched_dept_passes_through_unchanged(fac_df, rules_path):
    """配賦ルールが定義されていないdept_originalの行は、1行のまま変更されない"""
    result = allocate_fac(fac_df, str(rules_path))
    travel_rows = result[result['account_middle'] == '旅費交通費']
    assert len(travel_rows) == 1
    assert travel_rows['dept_allocated'].iloc[0] == '名セン'
    assert travel_rows['amount'].iloc[0] == -5000


def test_specific_rule_takes_precedence_over_general_rule(fac_df, rules_path):
    """target_account_middleを指定した個別ルールが、一般ルールより優先される"""
    result = allocate_fac(fac_df, str(rules_path))
    # 家賃は個別ルール(固定比率0.6/0.4)が適用され、一般ルール(比率)は使われない
    rent_rows = result[result['account_middle'] == '家賃']
    name_sen = rent_rows[rent_rows['dept_allocated'] == '名セン']['amount'].iloc[0]
    assert name_sen == pytest.approx(-60000)  # 比率ルール(0.75)ではなく固定比率(0.6)


def test_reconciliation_amount_unchanged_before_after(fac_df, rules_path):
    """配賦前後で合計金額が変わらないこと(検算ロジックの前提を直接確認)"""
    before_total = fac_df['amount'].sum()
    result = allocate_fac(fac_df, str(rules_path))
    after_total = result['amount'].sum()
    assert after_total == pytest.approx(before_total)


def test_row_count_increases_by_split(fac_df, rules_path):
    """配賦対象2行(家賃・給与手当)が、それぞれ2行に分裂 -> 全体で+2行になる"""
    result = allocate_fac(fac_df, str(rules_path))
    assert len(result) == len(fac_df) + 2


def test_fixed_ratio_sum_warning(tmp_path, capsys):
    """固定比率の合計が1.0からずれている場合、警告が表示される(処理自体は継続する)"""
    df = pd.DataFrame([
        {'date': '2026-04-01', 'account_large': '固定費', 'account_middle': '家賃', 'account_small': '',
         'amount': -100000, 'cost_type': '固定費', 'cf_type': '対象外',
         'dept_original': '本部', 'dept_allocated': '本部', 'status': '実績'},
    ])
    rules = _write_rules(tmp_path / "bad_rules.xlsx", [
        {'source_dept': '本部', 'target_dept': '名セン', 'rule_type': '固定比率', 'ratio': 0.5,
         'ratio_basis_account_large': '', 'target_account_middle': ''},
        {'source_dept': '本部', 'target_dept': '和セン', 'rule_type': '固定比率', 'ratio': 0.3,
         'ratio_basis_account_large': '', 'target_account_middle': ''},
    ])
    allocate_fac(df, str(rules))
    captured = capsys.readouterr()
    assert "警告" in captured.out
    assert "合計が1.0になっていません" in captured.out


def test_zero_basis_total_falls_back_to_equal_split(tmp_path):
    """按分基礎の合計が0の場合、均等按分にフォールバックする"""
    df = pd.DataFrame([
        {'date': '2026-04-01', 'account_large': '人件費', 'account_middle': '給与手当', 'account_small': '',
         'amount': -90000, 'cost_type': '固定費', 'cf_type': '対象外',
         'dept_original': '本部', 'dept_allocated': '本部', 'status': '実績'},
        # 売上高データが存在しない(按分基礎の合計が0になる)
    ])
    rules = _write_rules(tmp_path / "zero_basis_rules.xlsx", [
        {'source_dept': '本部', 'target_dept': '名セン', 'rule_type': '比率', 'ratio': None,
         'ratio_basis_account_large': '売上高', 'target_account_middle': ''},
        {'source_dept': '本部', 'target_dept': '和セン', 'rule_type': '比率', 'ratio': None,
         'ratio_basis_account_large': '売上高', 'target_account_middle': ''},
    ])
    result = allocate_fac(df, str(rules))
    name_sen = result[result['dept_allocated'] == '名セン']['amount'].iloc[0]
    wa_sen = result[result['dept_allocated'] == '和セン']['amount'].iloc[0]
    assert name_sen == pytest.approx(-45000)
    assert wa_sen == pytest.approx(-45000)


def test_mixed_rule_type_raises_value_error(tmp_path):
    """同一配賦グループ内でrule_typeが混在している場合はValueError"""
    df = pd.DataFrame([
        {'date': '2026-04-01', 'account_large': '固定費', 'account_middle': '家賃', 'account_small': '',
         'amount': -100000, 'cost_type': '固定費', 'cf_type': '対象外',
         'dept_original': '本部', 'dept_allocated': '本部', 'status': '実績'},
    ])
    rules = _write_rules(tmp_path / "mixed_rules.xlsx", [
        {'source_dept': '本部', 'target_dept': '名セン', 'rule_type': '固定比率', 'ratio': 0.5,
         'ratio_basis_account_large': '', 'target_account_middle': ''},
        {'source_dept': '本部', 'target_dept': '和セン', 'rule_type': '比率', 'ratio': None,
         'ratio_basis_account_large': '売上高', 'target_account_middle': ''},
    ])
    with pytest.raises(ValueError):
        allocate_fac(df, str(rules))


def test_missing_mapping_file_raises(fac_df, tmp_path):
    with pytest.raises(MappingFileNotFoundError):
        allocate_fac(fac_df, str(tmp_path / "does_not_exist.xlsx"))


def test_missing_rule_column_raises(fac_df, tmp_path):
    broken_path = tmp_path / "broken_rules.xlsx"
    with pd.ExcelWriter(broken_path) as writer:
        pd.DataFrame({"source_dept": ["本部"]}).to_excel(writer, sheet_name="allocation_rules", index=False)

    with pytest.raises(MissingColumnError):
        allocate_fac(fac_df, str(broken_path))
