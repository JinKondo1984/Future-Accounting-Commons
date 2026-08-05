"""
engines/importers/yayoi.py

弥生会計の仕訳データ「標準フォーマット」（ヘッダー行なし・列位置固定のCSV）を
FACフォーマット（Future Accounting Commons標準フォーマット）に分解するインポーター。

インターフェース規約(engines/registry.py が要求するもの):
  - IMPORTER_META: dict (少なくとも "id", "display_name" を含む)
  - decompose_to_fac(source_path, mapping_path) -> pd.DataFrame

【MF/freee版との構造的な違い】
1. ヘッダー行が存在せず、列の意味は「A列=識別フラグ、B列=伝票No....」という
   位置(順序)だけで決まる。そのため本モジュールでは header=None で読み込み、
   固定の列名リスト(_YAYOI_COLUMNS)を position で割り当てる。
2. 税額は「税率」ではなく「借方税金額／貸方税金額」という実額で入っているため、
   金額から税金額を単純に差し引くだけで税抜金額が求まる。
   （MF/freeeのように税込経理／税抜経理を区別する必要がない）
3. 複数行にまたがる伝票データの場合、2行目以降は「取引日付」欄が空欄になり、
   1行目の日付を引き継ぐ仕様のため、読み込み後に取引日付列を前方補完(ffill)する。
4. 日付は西暦（20190701 / 2019/07/01 / 2019/7/1）と和暦（R01/07/01 / R01/7/1）の
   両方があり得るため、和暦を西暦に変換してから日付型に変換する。

【既知の制限（v1時点）】
複数行にまたがる伝票データ（識別フラグが 2110／2100／2101 の行、つまり借方・貸方が
別々の行に分かれているケース）は、キャッシュフロー(CF)側の「相手科目」を正しく
紐付けられない。CF抽出ロジックは同一行内の相手科目を参照する設計のため、
借方・貸方が別行にある場合、相手科目が空欄になり account_large/account_middle が
「未分類」として出力される。損益(PL)側の金額自体は行ごとに正しく計上されるため、
PLの集計値には影響しない。
複数行伝票をまたいだ相手科目の再構成（伝票No.でのグループ化）が必要な場合は、
将来のバージョンで対応する。それまでは、実行時に検出件数を警告表示する。
"""

import os
import re

import numpy as np
import pandas as pd

from engines.exceptions import (
    InvalidSourceFormatError,
    MappingFileNotFoundError,
    MissingColumnError,
    SourceFileNotFoundError,
)

# --------------------------------------------------
# インポーターの自己申告メタ情報
# --------------------------------------------------
IMPORTER_META = {
    "id": "yayoi",
    "display_name": "弥生会計（標準フォーマット）",
    # 弥生のCSVはShift-JIS(cp932)での出力が一般的という前提。異なる場合は要調整。
    "required_encoding": "cp932",
}

# 標準フォーマットの列定義（位置固定・ヘッダーなし）
# 「条件」「項目名」は仕様書(弥生インポート形式_仕様)のA列・B列に対応
_YAYOI_COLUMNS = [
    "識別フラグ",       # 1(A)
    "伝票No",           # 2(B)
    "決算",             # 3(C)
    "取引日付",          # 4(D)
    "借方勘定科目",       # 5(E)
    "借方補助科目",       # 6(F)
    "借方部門",          # 7(G)
    "借方税区分",         # 8(H)
    "借方金額",          # 9(I)
    "借方税金額",         # 10(J)
    "貸方勘定科目",       # 11(K)
    "貸方補助科目",       # 12(L)
    "貸方部門",          # 13(M)
    "貸方税区分",         # 14(N)
    "貸方金額",          # 15(O)
    "貸方税金額",         # 16(P)
    "摘要",              # 17(Q)
    "番号",              # 18(R)
    "期日",              # 19(S)
    "タイプ",             # 20(T)
    "生成元",            # 21(U)
    "仕訳メモ",           # 22(V)
    "付箋1",             # 23(W)
    "付箋2",             # 24(X)
    "調整",              # 25(Y)
]

# 本インポーターがFAC変換に実際に使用する列数（ここまであれば処理可能）
_MIN_REQUIRED_COLUMN_COUNT = 16  # 識別フラグ〜貸方税金額まで

_REQUIRED_PL_MAP_COLUMNS = ["会計ソフトの科目名"]
_REQUIRED_CF_MAP_COLUMNS = ["相手勘定の科目名"]

_REIWA_DATE_PATTERN = re.compile(r"^R(\d{1,2})[/\-]?(\d{1,2})[/\-](\d{1,2})$")
_COMPACT_DATE_PATTERN = re.compile(r"^(\d{4})(\d{2})(\d{2})$")
_SLASH_DATE_PATTERN = re.compile(r"^(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})$")


def _normalize_date(value) -> str:
    """
    弥生の取引日付欄（西暦8桁 / 西暦スラッシュ区切り / 令和表記）を
    "YYYY-MM-DD" 形式の文字列に正規化する。

    Args:
        value: 取引日付欄の値（例: "20190701", "2019/7/1", "R01/07/01"）

    Returns:
        "YYYY-MM-DD" 形式の文字列。変換できない場合は元の文字列をそのまま返す
        （後続の pd.to_datetime に判定を委ねる）。
    """
    s = str(value).strip()

    m = _REIWA_DATE_PATTERN.match(s)
    if m:
        reiwa_year, month, day = m.groups()
        # 令和元年(R01) = 2019年
        year = 2018 + int(reiwa_year)
        return f"{year}-{int(month):02d}-{int(day):02d}"

    m = _COMPACT_DATE_PATTERN.match(s)
    if m:
        year, month, day = m.groups()
        return f"{year}-{month}-{day}"

    m = _SLASH_DATE_PATTERN.match(s)
    if m:
        year, month, day = m.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"

    return s


def get_ex_tax_amount(amount_series, tax_amount_series):
    """
    金額列と税金額列から、税抜金額を返す（金額 - 税金額）。

    弥生の標準フォーマットでは「借方金額／貸方金額」は常に税込金額として入力され、
    実際の税額が「借方税金額／貸方税金額」に別途入っているため、
    MF/freeeのような税率からの割り戻し計算は不要で、単純な減算で済む。

    Args:
        amount_series: 借方金額 または 貸方金額（税込）
        tax_amount_series: 借方税金額 または 貸方税金額（空欄は0として扱う）

    Returns:
        税抜金額のSeries
    """
    amount = pd.to_numeric(amount_series, errors="coerce").fillna(0)
    tax_amount = pd.to_numeric(tax_amount_series, errors="coerce").fillna(0)
    return amount - tax_amount


def decompose_to_fac(source_path: str, mapping_path: str) -> pd.DataFrame:
    """
    弥生会計の仕訳データ（標準フォーマット、ヘッダーなし）を、FACフォーマットに分解する。

    Args:
        source_path: 弥生会計から出力した仕訳データCSV（標準フォーマット）のパス
        mapping_path: pl_cost_mapping / cf_mapping シートを含むマッピングマスタExcelのパス
                      （勘定科目名は弥生の科目体系に合わせたものを使用すること）

    Returns:
        FACフォーマットのDataFrame

    Raises:
        SourceFileNotFoundError: source_path が存在しない場合
        MappingFileNotFoundError: mapping_path が存在しない場合
        InvalidSourceFormatError: 列数が標準フォーマットとして不足している場合
        MissingColumnError: マッピングマスタ側の必須列が欠落している場合
    """
    print("=== FACフォーマット変換処理を開始します (弥生会計) ===")

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

    # 弥生標準フォーマットはヘッダー行を持たないため、header=Noneで読み込む
    df_ya = pd.read_csv(source_path, encoding="cp932", header=None, dtype=str)

    if df_ya.shape[1] < _MIN_REQUIRED_COLUMN_COUNT:
        raise InvalidSourceFormatError(
            f"列数が弥生標準フォーマットとして不足しています "
            f"(必要: {_MIN_REQUIRED_COLUMN_COUNT}列以上, 実際: {df_ya.shape[1]}列)。"
            "「弥生インポート形式（標準フォーマット）」でのエクスポートか確認してください。"
        )

    # 使用する列だけに列名を割り当てる（余分な列があっても無視する）
    df_ya = df_ya.iloc[:, :len(_YAYOI_COLUMNS)]
    df_ya.columns = _YAYOI_COLUMNS[:df_ya.shape[1]]

    # 既知の制限: 複数行伝票（借方・貸方が別行に分かれるケース）は、
    # CF側の相手科目を正しく紐付けられないため、検出件数を警告表示する。
    MULTI_LINE_FLAGS = ["2110", "2100", "2101"]
    multi_line_count = df_ya['識別フラグ'].astype(str).str.strip().isin(MULTI_LINE_FLAGS).sum()
    if multi_line_count > 0:
        print(
            f"\n【警告】複数行の伝票データが {multi_line_count} 行検出されました。"
            "現バージョンでは、これらの行のCF側相手科目を正しく紐付けられません"
            "（account_large/account_middle が「未分類」になります）。"
            "PL側の金額集計には影響しません。"
        )

    # マッピングマスタの読み込み
    xl_map = pd.ExcelFile(mapping_path)
    df_pl_map = xl_map.parse("pl_cost_mapping")
    df_cf_map = xl_map.parse("cf_mapping")

    def _validate_columns(df, required_columns, source_label):
        missing = [col for col in required_columns if col not in df.columns]
        if missing:
            raise MissingColumnError(missing[0], source=source_label)

    _validate_columns(df_pl_map, _REQUIRED_PL_MAP_COLUMNS, source_label="pl_cost_mapping シート")
    _validate_columns(df_cf_map, _REQUIRED_CF_MAP_COLUMNS, source_label="cf_mapping シート")

    # 常数列・定数の定義（MF版と同一）
    CASH_ACCOUNTS = ["現金", "普通預金", "当座預金", "定期預金"]
    SHOROKU_NAMES = ["諸口", "しょくち", "諸口勘定"]

    # 複数行の伝票データでは、2行目以降の「取引日付」が空欄で1行目の日付を引き継ぐ仕様のため、
    # 前方補完(ffill)して各行が自分の取引日付を持つようにする。
    df_ya['取引日付'] = df_ya['取引日付'].replace(r'^\s*$', np.nan, regex=True)
    df_ya['取引日付'] = df_ya['取引日付'].ffill()
    df_ya['取引日付'] = df_ya['取引日付'].apply(_normalize_date)

    # 金額・税額を数値化（空欄は0として扱う）
    for col in ['借方金額', '借方税金額', '貸方金額', '貸方税金額']:
        df_ya[col] = pd.to_numeric(df_ya[col], errors="coerce").fillna(0)

    # 税抜金額（借方・貸方それぞれ「金額 - 税金額」で算出。税率での割り戻しは不要）
    df_ya['debit_amount_ex'] = get_ex_tax_amount(df_ya['借方金額'], df_ya['借方税金額'])
    df_ya['credit_amount_ex'] = get_ex_tax_amount(df_ya['貸方金額'], df_ya['貸方税金額'])

    # 勘定科目・部門・補助科目の空欄をNaNではなく空文字に統一（isin判定・結合を安定させるため）
    for col in ['借方勘定科目', '借方補助科目', '借方部門', '貸方勘定科目', '貸方補助科目', '貸方部門']:
        df_ya[col] = df_ya[col].fillna("")

    # --------------------------------------------------
    # 2. 損益（PL・CVP）データの抽出と分解（税抜処理）
    # --------------------------------------------------
    # (2-1) 借方側からPL科目を抽出（費用はマイナス）
    df_pl_debit = df_ya[df_ya['借方勘定科目'].isin(df_pl_map['会計ソフトの科目名'])].copy()
    df_pl_debit['account'] = df_pl_debit['借方勘定科目']
    df_pl_debit['dept_original'] = df_pl_debit['借方部門']
    df_pl_debit['account_small'] = df_pl_debit['借方補助科目']
    df_pl_debit['amount'] = df_pl_debit['debit_amount_ex'] * -1

    # (2-2) 貸方側からPL科目を抽出（収益はプラス）
    df_pl_credit = df_ya[df_ya['貸方勘定科目'].isin(df_pl_map['会計ソフトの科目名'])].copy()
    df_pl_credit['account'] = df_pl_credit['貸方勘定科目']
    df_pl_credit['dept_original'] = df_pl_credit['貸方部門']
    df_pl_credit['account_small'] = df_pl_credit['貸方補助科目']
    df_pl_credit['amount'] = df_pl_credit['credit_amount_ex']

    df_pl_all = pd.concat([df_pl_debit, df_pl_credit], ignore_index=True)
    df_pl_all['date'] = df_pl_all['取引日付']
    df_pl_all['cf_type'] = "対象外"
    df_pl_all['status'] = "実績"

    df_pl_standard = pd.merge(df_pl_all, df_pl_map, left_on="account", right_on="会計ソフトの科目名", how="left")

    # --------------------------------------------------
    # 3. キャッシュフロー（直接法CF）データの抽出と分解（税込処理）
    # --------------------------------------------------
    # (3-1) 借方が現預金（＝入金：プラス）。金額は「借方金額」（税込）を採用。諸口は除外。
    df_cf_in = df_ya[df_ya['借方勘定科目'].isin(CASH_ACCOUNTS)].copy()
    df_cf_in = df_cf_in[~df_cf_in['貸方勘定科目'].isin(SHOROKU_NAMES)]
    df_cf_in['account'] = df_cf_in['貸方勘定科目']
    df_cf_in['dept_original'] = df_cf_in['貸方部門']
    df_cf_in['account_small'] = df_cf_in['貸方補助科目']
    df_cf_in['amount'] = df_cf_in['借方金額']

    # (3-2) 貸方が現預金（＝出金：マイナス）。金額は「貸方金額」（税込）を採用。諸口は除外。
    df_cf_out = df_ya[df_ya['貸方勘定科目'].isin(CASH_ACCOUNTS)].copy()
    df_cf_out = df_cf_out[~df_cf_out['借方勘定科目'].isin(SHOROKU_NAMES)]
    df_cf_out['account'] = df_cf_out['借方勘定科目']
    df_cf_out['dept_original'] = df_cf_out['借方部門']
    df_cf_out['account_small'] = df_cf_out['借方補助科目']
    df_cf_out['amount'] = df_cf_out['貸方金額'] * -1

    df_cf_all = pd.concat([df_cf_in, df_cf_out], ignore_index=True)
    df_cf_all['date'] = df_cf_all['取引日付']
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

    df_fac_output['account_large'] = df_fac_output['account_large'].fillna("未分類")
    df_fac_output['account_middle'] = df_fac_output['account_middle'].fillna("未分類")
    df_fac_output['cost_type'] = df_fac_output['cost_type'].fillna("未分類")
    df_fac_output['cf_type'] = df_fac_output['cf_type'].fillna("未分類")
    df_fac_output['account_small'] = df_fac_output['account_small'].fillna("")

    df_fac_output['date'] = pd.to_datetime(df_fac_output['date']).dt.strftime('%Y-%m-%d')

    print(f"処理完了: PLレコード数={len(df_pl_standard)}, CFレコード数={len(df_cf_standard)}")
    return df_fac_output


# ==========================================
# 実行テスト用スクリプト
# ==========================================
if __name__ == "__main__":
    input_csv = "yayoi_shiwake_raw.csv"
    input_excel = "mapping_master_yayoi.xlsx"
    output_csv = "fac_format_output_yayoi.csv"

    try:
        df_result = decompose_to_fac(input_csv, input_excel)
        df_result.to_csv(output_csv, index=False, encoding="utf-8-sig")
        print(f"成功: '{output_csv}' にFACフォーマットデータを書き出しました。")

        print("\n--- 【簡易検証】勘定大分類別の合計金額 ---")
        print(df_result.groupby('account_large')['amount'].sum())
        print(df_result.groupby('cf_type')['amount'].sum())

    except Exception as e:
        print(f"\nエラーが発生しました: {e}")
