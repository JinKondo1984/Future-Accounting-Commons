"""
engines/allocators/dept_allocation.py

FACフォーマットのデータを、配賦ルールマスタ(Excel)に従って部門配賦するエンジン。

【設計方針:行分裂について】
FACフォーマットは基本的に「1行1トランザクション」だが、比率による配賦は
1つの金額を複数の配賦先部門に按分する行為であるため、配賦対象となった行は
配賦先部門の数だけ複数行に分裂する。これはFACフォーマットの基本思想である
「Excelフレンドリー」を、トランザクションとしての厳密性より優先した意図的な設計。

配賦ルールが適用されない行（dept_originalがどの配賦元(source_dept)にも
該当しない行、または該当するが対象科目(target_account_middle)の絞り込みに
合致しない行）は、1行のまま変更されない。

【マッピングマスタの仕様（シート名: allocation_rules）】
  - source_dept: 配賦元部門（FACデータのdept_originalと一致させる）
  - target_dept: 配賦先部門
  - rule_type: "固定比率" または "比率"
      - "固定比率": ratio列の値をそのまま按分比率として使う
      - "比率": FACデータ内の ratio_basis_account_large 列で指定した
                account_large の金額比率から、按分比率を動的に算出する
                （算出範囲は、同じsource_dept・同じ絞り込み条件のtarget_dept群のみ）
  - ratio: rule_type="固定比率"の場合のみ使用（例: 0.35）
  - ratio_basis_account_large: rule_type="比率"の場合のみ使用（例: "売上高"）
  - target_account_middle: 配賦対象をFACデータの特定のaccount_middleに
    絞り込みたい場合に指定。空欄の場合はsource_dept配下の全account_middleが対象。

同一source_dept内で、target_account_middleを指定した行（個別ルール）と
指定しない行（一般ルール）が両方存在する場合、個別ルールが優先される。

【既知の制限（v1時点）】
2段階配賦（ある配賦先部門の金額がさらに別ルールで再配賦される）はサポートしない。
必要な場合は、本エンジンを2回適用することで代替できる。
"""

import os

import pandas as pd

from engines.exceptions import MappingFileNotFoundError, MissingColumnError

_REQUIRED_RULE_COLUMNS = [
    "source_dept",
    "target_dept",
    "rule_type",
    "ratio",
    "ratio_basis_account_large",
    "target_account_middle",
]

# 固定比率の合計が1.0からこの範囲を超えて外れたら警告する
_RATIO_SUM_TOLERANCE = 0.01
# 配賦前後の合計金額の一致判定の許容誤差（浮動小数点誤差の吸収用）
_RECONCILIATION_TOLERANCE = 1e-6


def _validate_columns(df, required_columns, source_label):
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise MissingColumnError(missing[0], source=source_label)


def _load_allocation_rules(mapping_path: str) -> pd.DataFrame:
    if not os.path.exists(mapping_path):
        raise MappingFileNotFoundError(
            f"指定された配賦ルールマスタExcelが見つかりません: {mapping_path}"
        )
    xl = pd.ExcelFile(mapping_path)
    rules = xl.parse("allocation_rules")
    _validate_columns(rules, _REQUIRED_RULE_COLUMNS, source_label="allocation_rules シート")
    return rules


def _is_blank(value) -> bool:
    return pd.isna(value) or value == ""


def _select_rule_group(rules: pd.DataFrame, source_dept, account_middle) -> pd.DataFrame:
    """
    指定されたsource_dept・account_middleに適用すべきルール群を選ぶ。

    個別ルール（target_account_middleが account_middle と一致する行）があれば
    それを優先し、なければ一般ルール（target_account_middleが空欄の行）を使う。
    どちらもなければ、空のDataFrameを返す（＝配賦対象外）。
    """
    same_source = rules[rules["source_dept"] == source_dept]
    if same_source.empty:
        return same_source

    specific = same_source[same_source["target_account_middle"] == account_middle]
    if not specific.empty:
        return specific

    general = same_source[same_source["target_account_middle"].apply(_is_blank)]
    return general


def _compute_ratios(rule_group: pd.DataFrame, df: pd.DataFrame) -> dict:
    """
    ルール群から、target_dept ごとの按分比率を計算して返す。{target_dept: ratio, ...}
    """
    rule_types = rule_group["rule_type"].unique()
    if len(rule_types) > 1:
        raise ValueError(
            f"同一の配賦グループ内で rule_type が混在しています: {list(rule_types)} "
            f"(source_dept={rule_group['source_dept'].iloc[0]!r})。"
            "source_dept・target_account_middineの組ごとに rule_type は統一してください。"
        )
    rule_type = rule_types[0]

    if rule_type == "固定比率":
        ratios = dict(zip(rule_group["target_dept"], rule_group["ratio"]))
        total = sum(ratios.values())
        if abs(total - 1.0) > _RATIO_SUM_TOLERANCE:
            print(
                f"\n【警告】固定比率の合計が1.0になっていません "
                f"(source_dept={rule_group['source_dept'].iloc[0]!r}, 合計={total:.4f})。"
                "マッピングマスタのratio列を確認してください。"
            )
        return ratios

    if rule_type == "比率":
        basis_account = rule_group["ratio_basis_account_large"].iloc[0]
        target_depts = list(rule_group["target_dept"])
        basis_totals = (
            df[(df["account_large"] == basis_account) & (df["dept_original"].isin(target_depts))]
            .groupby("dept_original")["amount"]
            .sum()
        )
        grand_total = basis_totals.sum()
        if grand_total == 0:
            print(
                f"\n【警告】按分基礎(account_large={basis_account!r})の合計が0のため、"
                f"target_dept={target_depts} への配賦比率を算出できません。均等按分します。"
            )
            equal_ratio = 1.0 / len(target_depts)
            return {dept: equal_ratio for dept in target_depts}
        return {dept: basis_totals.get(dept, 0) / grand_total for dept in target_depts}

    raise ValueError(f"未知の rule_type です: {rule_type!r}")


def allocate_fac(df: pd.DataFrame, mapping_path: str) -> pd.DataFrame:
    """
    FACフォーマットのDataFrameを、配賦ルールマスタ(Excel)に従って部門配賦する。

    配賦対象となった行は、配賦先部門の数だけ複数行に分裂する
    （FACフォーマットの「1行1トランザクション」という原則よりも、
    「Excelフレンドリー」という基本思想を優先した意図的な設計）。

    Args:
        df: FACフォーマットのDataFrame
        mapping_path: allocation_rules シートを含む配賦ルールマスタExcelのパス

    Returns:
        dept_allocatedが配賦後の値に更新されたFACフォーマットのDataFrame
        （配賦対象行は複数行に分裂しているため、入力より行数が増える場合がある）

    Raises:
        MappingFileNotFoundError: mapping_path が存在しない場合
        MissingColumnError: 配賦ルールマスタの必須列が欠落している場合
        ValueError: 同一配賦グループ内でrule_typeが混在している、
                    または未知のrule_typeが指定されている場合
    """
    print("=== 部門配賦処理を開始します ===")

    rules = _load_allocation_rules(mapping_path)

    output_rows = []

    for _, row in df.iterrows():
        source_dept = row["dept_original"]
        account_middle = row["account_middle"]

        rule_group = _select_rule_group(rules, source_dept, account_middle)

        if rule_group.empty:
            output_rows.append(row.to_dict())
            continue

        ratios = _compute_ratios(rule_group, df)

        original_amount = row["amount"]
        for target_dept, ratio in ratios.items():
            new_row = row.to_dict()
            new_row["dept_allocated"] = target_dept
            new_row["amount"] = original_amount * ratio
            output_rows.append(new_row)

    df_result = pd.DataFrame(output_rows, columns=df.columns)

    # 検算: 配賦前後で合計金額が変わっていないことを確認する
    # （accounting.pyでreindexによる本部比率の取りこぼしが発生した反省を踏まえた組み込み）
    before_total = df["amount"].sum()
    after_total = df_result["amount"].sum()
    if abs(before_total - after_total) > _RECONCILIATION_TOLERANCE:
        print(
            f"\n【警告】配賦前後で合計金額が一致しません "
            f"(配賦前={before_total:,.2f}, 配賦後={after_total:,.2f}, "
            f"差={after_total - before_total:,.2f})。配賦ロジックを確認してください。"
        )
    else:
        print(f"\n検算OK: 配賦前後の合計金額が一致しています(合計={before_total:,.2f})。")

    print(f"処理完了: 入力{len(df)}行 → 出力{len(df_result)}行")
    return df_result
