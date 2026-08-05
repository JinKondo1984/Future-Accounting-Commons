"""
engines/importers/freee.py

freee会計の仕訳帳CSV（汎用形式、UTF-8 BOMなし）を
FACフォーマット（Future Accounting Commons標準フォーマット）に分解するインポーター。

インターフェース規約(engines/registry.py が要求するもの):
  - IMPORTER_META: dict (少なくとも "id", "display_name" を含む)
  - decompose_to_fac(source_path, mapping_path) -> pd.DataFrame

【税抜化ロジックについて】
freeeでは、事業所の消費税経理処理方法（税込経理／税抜経理）によって、
仕訳帳CSVの金額列(借方金額・貸方金額)が税込か税抜かが変わる。
  - 税抜経理の場合: 仕訳金額は既に税抜きで計上されているため、割り戻し不要（除数1.0）
  - 税込経理の場合: 借方税率／貸方税率列（例: 10% なら "10" という数値）を用いて
    1 + 税率/100 を除数として割り戻す
本インポーターは「消費税経理処理方法」列の値に "抜" が含まれるかどうかで判定する。
"""

import os

import numpy as np
import pandas as pd

from engines.exceptions import (
    MappingFileNotFoundError,
    MissingColumnError,
    SourceFileNotFoundError,
)

# --------------------------------------------------
# インポーターの自己申告メタ情報
# --------------------------------------------------
IMPORTER_META = {
    "id": "freee",
    "display_name": "freee会計（汎用形式）",
    "required_encoding": "utf-8",
}

# 仕訳データ側で必須となる列（freee汎用形式の「項目名」に準拠）
_REQUIRED_FREEE_COLUMNS = [
    "取引日",
    "借方勘定科目",
    "借方金額",
    "借方税区分",
    "借方税率",
    "借方部門",
    "貸方勘定科目",
    "貸方金額",
    "貸方税区分",
    "貸方税率",
    "貸方部門",
    "消費税経理処理方法",
]

# マッピングマスタ側で必須となる列（MF版と同一契約）
_REQUIRED_PL_MAP_COLUMNS = ["会計ソフトの科目名"]
_REQUIRED_CF_MAP_COLUMNS = ["相手勘定の科目名"]


def get_tax_divisor(tax_rate_series, tax_method_series):
    """
    税率列と消費税経理処理方法列から、税抜化のための除数を返す。

    Args:
        tax_rate_series: 借方税率 または 貸方税率 列（数値、例: 10, 8。空欄は対象外）
        tax_method_series: 消費税経理処理方法 列（例: "税込経理", "税抜経理"）

    Returns:
        除数のnumpy配列（1.0 / 1.1 / 1.08 等）
    """
    rate = pd.to_numeric(tax_rate_series, errors="coerce").fillna(0)
    is_tax_excluded = tax_method_series.fillna("").astype(str).str.contains("抜")

    # 税込経理を前提に、税率から除数を計算（税率0＝対象外は1.0のまま）
    divisor_if_included = np.where(rate == 0, 1.0, 1 + rate / 100)
    # 税抜経理の場合は、税率の有無に関わらず割り戻し不要（常に1.0）
    divisor = np.where(is_tax_excluded, 1.0, divisor_if_included)
    return divisor


def _validate_columns(df, required_columns, source_label):
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise MissingColumnError(missing[0], source=source_label)


def decompose_to_fac(source_path: str, mapping_path: str) -> pd.DataFrame:
    """
    freee会計の仕訳帳CSV（汎用形式）を、FACフォーマットに分解する。

    Args:
        source_path: freeeから出力した仕訳帳CSV（汎用形式、UTF-8 BOMなし）のパス
        mapping_path: pl_cost_mapping / cf_mapping シートを含むマッピングマスタExcelのパス
                      （勘定科目名はfreeeの科目体系に合わせたものを使用すること）

    Returns:
        FACフォーマットのDataFrame

    Raises:
        SourceFileNotFoundError: source_path が存在しない場合
        MappingFileNotFoundError: mapping_path が存在しない場合
        MissingColumnError: 必須列が欠落している場合
    """
    print("=== FACフォーマット変換処理を開始します (freee会計) ===")

    # --------------------------------------------------
    # 1. データの読み込みと前処理
    # --------------------------------------------------
    if not os.path.exists(source_path):
        raise SourceFileNotFoundError(
            f"指定された仕訳データCSVが見つかりません: {source_path}"
        )
    if not os.path.exists(mapping_path):
        raise MappingFileNotFoundError(
            f"指定されたマッピングマスタExcelが見つかりません: {mapping_path}"
        )

    # freee汎用形式はUTF-8（BOMなし）。"utf-8-sig"はBOM有無どちらでも読めるため安全に採用。
    df_fr = pd.read_csv(source_path, encoding="utf-8-sig")

    _validate_columns(df_fr, _REQUIRED_FREEE_COLUMNS, source_label="仕訳データCSV")

    # マッピングマスタの読み込み
    xl_map = pd.ExcelFile(mapping_path)
    df_pl_map = xl_map.parse("pl_cost_mapping")
    df_cf_map = xl_map.parse("cf_mapping")

    _validate_columns(df_pl_map, _REQUIRED_PL_MAP_COLUMNS, source_label="pl_cost_mapping シート")
    _validate_columns(df_cf_map, _REQUIRED_CF_MAP_COLUMNS, source_label="cf_mapping シート")

    # 常数列・定数の定義（MF版と同一）
    CASH_ACCOUNTS = ["現金", "普通預金", "当座預金", "定期預金"]
    SHOROKU_NAMES = ["諸口", "しょくち", "諸口勘定"]

    # 消費税の自動割り戻し（借方は借方税率、貸方は貸方税率をそれぞれ税抜化）
    df_fr['debit_tax_divisor'] = get_tax_divisor(df_fr['借方税率'], df_fr['消費税経理処理方法'])
    df_fr['credit_tax_divisor'] = get_tax_divisor(df_fr['貸方税率'], df_fr['消費税経理処理方法'])
    df_fr['debit_amount_ex'] = df_fr['借方金額'] / df_fr['debit_tax_divisor']
    df_fr['credit_amount_ex'] = df_fr['貸方金額'] / df_fr['credit_tax_divisor']

    # freeeには「補助科目」に相当する列がないため、account_smallは空文字で統一する
    df_fr['借方補助科目'] = ""
    df_fr['貸方補助科目'] = ""

    # --------------------------------------------------
    # 2. 損益（PL・CVP）データの抽出と分解（税抜処理）
    # --------------------------------------------------
    # (2-1) 借方側からPL科目を抽出（費用はマイナス）
    df_pl_debit = df_fr[df_fr['借方勘定科目'].isin(df_pl_map['会計ソフトの科目名'])].copy()
    df_pl_debit['account'] = df_pl_debit['借方勘定科目']
    df_pl_debit['dept_original'] = df_pl_debit['借方部門']
    df_pl_debit['account_small'] = df_pl_debit['借方補助科目']
    df_pl_debit['amount'] = df_pl_debit['debit_amount_ex'] * -1

    # (2-2) 貸方側からPL科目を抽出（収益はプラス）
    df_pl_credit = df_fr[df_fr['貸方勘定科目'].isin(df_pl_map['会計ソフトの科目名'])].copy()
    df_pl_credit['account'] = df_pl_credit['貸方勘定科目']
    df_pl_credit['dept_original'] = df_pl_credit['貸方部門']
    df_pl_credit['account_small'] = df_pl_credit['貸方補助科目']
    df_pl_credit['amount'] = df_pl_credit['credit_amount_ex']

    # 縦に結合してマッピングをぶつける
    df_pl_all = pd.concat([df_pl_debit, df_pl_credit], ignore_index=True)
    df_pl_all['date'] = df_pl_all['取引日']
    df_pl_all['cf_type'] = "対象外"
    df_pl_all['status'] = "実績"

    df_pl_standard = pd.merge(df_pl_all, df_pl_map, left_on="account", right_on="会計ソフトの科目名", how="left")

    # --------------------------------------------------
    # 3. キャッシュフロー（直接法CF）データの抽出と分解（税込処理）
    # --------------------------------------------------
    # (3-1) 借方が現預金（＝入金：プラス）。金額は「借方金額」（税込）を採用。諸口は除外。
    df_cf_in = df_fr[df_fr['借方勘定科目'].isin(CASH_ACCOUNTS)].copy()
    df_cf_in = df_cf_in[~df_cf_in['貸方勘定科目'].isin(SHOROKU_NAMES)]
    df_cf_in['account'] = df_cf_in['貸方勘定科目']
    df_cf_in['dept_original'] = df_cf_in['貸方部門']
    df_cf_in['account_small'] = df_cf_in['貸方補助科目']
    df_cf_in['amount'] = df_cf_in['借方金額']

    # (3-2) 貸方が現預金（＝出金：マイナス）。金額は「貸方金額」（税込）を採用。諸口は除外。
    df_cf_out = df_fr[df_fr['貸方勘定科目'].isin(CASH_ACCOUNTS)].copy()
    df_cf_out = df_cf_out[~df_cf_out['借方勘定科目'].isin(SHOROKU_NAMES)]
    df_cf_out['account'] = df_cf_out['借方勘定科目']
    df_cf_out['dept_original'] = df_cf_out['借方部門']
    df_cf_out['account_small'] = df_cf_out['借方補助科目']
    df_cf_out['amount'] = df_cf_out['貸方金額'] * -1

    # 縦に結合してマッピングをぶつける
    df_cf_all = pd.concat([df_cf_in, df_cf_out], ignore_index=True)
    df_cf_all['date'] = df_cf_all['取引日']
    df_cf_all['cost_type'] = "対象外"
    df_cf_all['status'] = "実績"

    df_cf_standard = pd.merge(df_cf_all, df_cf_map, left_on="account", right_on="相手勘定の科目名", how="left")

    print("\n--- 【診断】cf_typeが対象外・未分類の内訳 ---")
    print(df_cf_standard[df_cf_standard['cf_type'].isin(['対象外']) | df_cf_standard['cf_type'].isna()][['account', 'amount']].groupby('account').sum())

    # --------------------------------------------------
    # 4. FACフォーマットへの統合と出力
    # --------------------------------------------------
    df_pl_standard['dept_allocated'] = df_pl_standard['dept_original']
    df_cf_standard['dept_allocated'] = df_cf_standard['dept_original']

    target_columns = [
        'date', 'account_large', 'account_middle', 'account_small', 'amount',
        'cost_type', 'cf_type', 'dept_original', 'dept_allocated', 'status'
    ]

    df_fac_output = pd.concat([
        df_pl_standard[target_columns],
        df_cf_standard[target_columns]
    ], ignore_index=True)

    # 欠損値（マッピング漏れ等）の簡易補正
    df_fac_output['account_large'] = df_fac_output['account_large'].fillna("未分類")
    df_fac_output['account_middle'] = df_fac_output['account_middle'].fillna("未分類")
    df_fac_output['cost_type'] = df_fac_output['cost_type'].fillna("未分類")
    df_fac_output['cf_type'] = df_fac_output['cf_type'].fillna("未分類")
    df_fac_output['account_small'] = df_fac_output['account_small'].fillna("")

    # 日付型の一元化
    df_fac_output['date'] = pd.to_datetime(df_fac_output['date']).dt.strftime('%Y-%m-%d')

    print(f"処理完了: PLレコード数={len(df_pl_standard)}, CFレコード数={len(df_cf_standard)}")
    return df_fac_output


# ==========================================
# 実行テスト用スクリプト
# ==========================================
if __name__ == "__main__":
    input_csv = "freee_shiwake_raw.csv"
    input_excel = "mapping_master_freee.xlsx"
    output_csv = "fac_format_output_freee.csv"

    try:
        df_result = decompose_to_fac(input_csv, input_excel)
        df_result.to_csv(output_csv, index=False, encoding="utf-8-sig")
        print(f"成功: '{output_csv}' にFACフォーマットデータを書き出しました。")

        print("\n--- 【簡易検証】勘定大分類別の合計金額 ---")
        print(df_result.groupby('account_large')['amount'].sum())
        print(df_result.groupby('cf_type')['amount'].sum())

    except Exception as e:
        print(f"\nエラーが発生しました: {e}")
