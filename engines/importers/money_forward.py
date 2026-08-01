import pandas as pd
import numpy as np
import os

def get_tax_divisor(tax_series):
    """
    消費税区分に応じて除数を返す（1.1 / 1.08 / 1.0）
    管理会計用に複雑な税区分を3パターンに抽象化
    """
    divisors = np.ones(len(tax_series))
    tax_str = tax_series.fillna("").astype(str)
    
    # 10%対象の判定
    divisors[tax_str.str.contains("10%")] = 1.1
    # 8%対象（軽減税率含む）の判定
    divisors[tax_str.str.contains("8%|軽")] = 1.08
    
    return divisors

def decompose_mf_to_fac(mf_csv_path, mapping_excel_path):
    """
    マネーフォワードの仕訳データを、FACフォーマット（Future Accounting Commons標準フォーマット）に分解する。
    """
    print("=== FACフォーマット変換処理を開始します ===")
    
    # --------------------------------------------------
    # 1. データの読み込みと前処理
    # --------------------------------------------------
    if not os.path.exists(mf_csv_path) or not os.path.exists(mapping_excel_path):
        raise FileNotFoundError("指定されたCSVまたはExcelファイルが見つかりません。")
        
    # MF仕訳帳は通常Shift-JIS(cp932)
    df_mf = pd.read_csv(mf_csv_path, encoding="cp932")
    
    # カッコ付きの金額列名を扱いやすくリネーム（表記のブレを吸収）
    df_mf = df_mf.rename(columns={
        '借方金額(円)': '借方金額',
        '貸方金額(円)': '貸方金額'
    })
    
    # マッピングマスタの読み込み
    xl_map = pd.ExcelFile(mapping_excel_path)
    df_pl_map = xl_map.parse("pl_cost_mapping")
    df_cf_map = xl_map.parse("cf_mapping")
    
    # 常数列・定数の定義
    CASH_ACCOUNTS = ["現金", "普通預金", "当座預金", "定期預金"]
    SHOROKU_NAMES = ["諸口", "しょくち", "諸口勘定"]
    
    # 消費税の自動割り戻し（借方は借方金額、貸方は貸方金額をそれぞれ税抜化）
    df_mf['debit_tax_divisor'] = get_tax_divisor(df_mf['借方税区分'])
    df_mf['credit_tax_divisor'] = get_tax_divisor(df_mf['貸方税区分'])
    df_mf['debit_amount_ex'] = df_mf['借方金額'] / df_mf['debit_tax_divisor']
    df_mf['credit_amount_ex'] = df_mf['貸方金額'] / df_mf['credit_tax_divisor']
    
    # 補助科目列の有無を吸収（マネーフォワードの出力仕様変更に備え、無ければ空文字で扱う）
    for col in ['借方補助科目', '貸方補助科目']:
        if col not in df_mf.columns:
            df_mf[col] = ""
    
    # --------------------------------------------------
    # 2. 損益（PL・CVP）データの抽出と分解（税抜処理）
    # --------------------------------------------------
    # (2-1) 借方側からPL科目を抽出（費用はマイナス）
    df_pl_debit = df_mf[df_mf['借方勘定科目'].isin(df_pl_map['会計ソフトの科目名'])].copy()
    df_pl_debit['account'] = df_pl_debit['借方勘定科目']
    df_pl_debit['dept_original'] = df_pl_debit['借方部門']
    df_pl_debit['account_small'] = df_pl_debit['借方補助科目']
    df_pl_debit['amount'] = df_pl_debit['debit_amount_ex'] * -1 
    
    # (2-2) 貸方側からPL科目を抽出（収益はプラス）
    df_pl_credit = df_mf[df_mf['貸方勘定科目'].isin(df_pl_map['会計ソフトの科目名'])].copy()
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
    # (3-1) 借方が現預金（＝入金：プラス）。金額は「借方金額」を採用。諸口は除外。
    # account/dept_original/account_small はすべて「相手科目側（貸方）」で揃える
    df_cf_in = df_mf[df_mf['借方勘定科目'].isin(CASH_ACCOUNTS)].copy()
    df_cf_in = df_cf_in[~df_cf_in['貸方勘定科目'].isin(SHOROKU_NAMES)]
    df_cf_in['account'] = df_cf_in['貸方勘定科目']
    df_cf_in['dept_original'] = df_cf_in['貸方部門']       # 修正: 借方部門 → 貸方部門（相手科目側に統一）
    df_cf_in['account_small'] = df_cf_in['貸方補助科目']    # 追加: 相手科目側の補助科目
    df_cf_in['amount'] = df_cf_in['借方金額']
    
    # (3-2) 貸方が現預金（＝出金：マイナス）。金額は「貸方金額」を採用。諸口は除外。
    # account/dept_original/account_small はすべて「相手科目側（借方）」で揃える
    df_cf_out = df_mf[df_mf['貸方勘定科目'].isin(CASH_ACCOUNTS)].copy()
    df_cf_out = df_cf_out[~df_cf_out['借方勘定科目'].isin(SHOROKU_NAMES)]
    df_cf_out['account'] = df_cf_out['借方勘定科目']
    df_cf_out['dept_original'] = df_cf_out['借方部門']      # 修正: 貸方部門 → 借方部門（相手科目側に統一）
    df_cf_out['account_small'] = df_cf_out['借方補助科目']   # 追加: 相手科目側の補助科目
    df_cf_out['amount'] = df_cf_out['貸方金額'] * -1
    
    # 縦に結合してマッピングをぶつける
    df_cf_all = pd.concat([df_cf_in, df_cf_out], ignore_index=True)
    df_cf_all['date'] = df_cf_all['取引日']
    df_cf_all['cost_type'] = "対象外"
    df_cf_all['status'] = "実績"
    
    df_cf_standard = pd.merge(df_cf_all, df_cf_map, left_on="account", right_on="相手勘定の科目名", how="left")
    
    # ↓ここに挿入
    print("\n--- 【診断】cf_typeが対象外・未分類の内訳 ---")
    print(df_cf_standard[df_cf_standard['cf_type'].isin(['対象外']) | df_cf_standard['cf_type'].isna()][['account', 'amount']].groupby('account').sum())
    
    # --------------------------------------------------
    # 4. FACフォーマットへの統合と出力
    # --------------------------------------------------
    # dept_allocated は配賦エンジン実行前の暫定値として dept_original をそのままコピーする
    # （配賦ロジックを別途実行した場合、この列が上書きされる想定）
    df_pl_standard['dept_allocated'] = df_pl_standard['dept_original']
    df_cf_standard['dept_allocated'] = df_cf_standard['dept_original']
    
    target_columns = [
        'date', 'account_large', 'account_middle', 'account_small', 'amount', 
        'cost_type', 'cf_type', 'dept_original', 'dept_allocated', 'status'
    ]
    
    # 必要な列だけに絞ってPLとCFを統合
    df_fac_output = pd.concat([
        df_pl_standard[target_columns],
        df_cf_standard[target_columns]
    ], ignore_index=True)
    
    # 欠損値（マッピング漏れ等）の簡易補正
    df_fac_output['account_large'] = df_fac_output['account_large'].fillna("未分類")
    df_fac_output['account_middle'] = df_fac_output['account_middle'].fillna("未分類")
    df_fac_output['cost_type'] = df_fac_output['cost_type'].fillna("未分類")
    df_fac_output['cf_type'] = df_fac_output['cf_type'].fillna("未分類")
    
    # account_small は補助科目を使っていない場合、空文字のままでよい（任意カラム）
    df_fac_output['account_small'] = df_fac_output['account_small'].fillna("")
    
    # 日付型の一元化
    df_fac_output['date'] = pd.to_datetime(df_fac_output['date']).dt.strftime('%Y-%m-%d')
    
    print(f"処理完了: PLレコード数={len(df_pl_standard)}, CFレコード数={len(df_cf_standard)}")
    return df_fac_output

# ==========================================
# 実行テスト用スクリプト
# ==========================================
if __name__ == "__main__":
    # ファイル名は実際の環境に合わせて書き換えてください
    input_csv = "mf_shiwake_raw.csv" 
    input_excel = "mapping_master.xlsx"
    output_csv = "fac_format_output.csv"
    
    try:
        df_result = decompose_mf_to_fac(input_csv, input_excel)
        # Excelで開いたときに文字化けしないよう utf-8-sig で出力
        df_result.to_csv(output_csv, index=False, encoding="utf-8-sig")
        print(f"成功: '{output_csv}' にFACフォーマットデータを書き出しました。")
        
        # 簡易チェック用の集計表示
        print("\n--- 【簡易検証】勘定大分類別の合計金額 ---")
        print(df_result.groupby('account_large')['amount'].sum())
        print(df_result.groupby('cf_type')['amount'].sum())
       
        
        
    except Exception as e:
        print(f"\nエラーが発生しました: {e}")