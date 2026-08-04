"""
engines/exceptions.py

各インポーター(engines/importers/*.py)が共通で送出する例外クラス群。
アプリ側(GUI)は FacImportError を一つ捕まえておけば、
どのインポーターが失敗してもユーザーに分かりやすいエラー表示ができる。

各インポーターを実装する際は、ここで定義された例外を投げること
(標準の FileNotFoundError や KeyError をそのまま外に漏らさない)。
"""


class FacImportError(Exception):
    """FAC変換処理中に発生するエラー全般の基底クラス。

    アプリ側はこの型を try/except することで、
    インポーターごとの実装差異を意識せずにエラーハンドリングできる。
    """


class SourceFileNotFoundError(FacImportError):
    """会計ソフトから出力された仕訳データファイルが見つからない場合。"""


class MappingFileNotFoundError(FacImportError):
    """マッピングマスタ(Excel)ファイルが見つからない場合。"""


class MissingColumnError(FacImportError):
    """仕訳データまたはマッピングマスタに、処理に必要な列が存在しない場合。

    Attributes:
        column_name: 見つからなかった列名
        source: どのファイル・シートで発生したか(任意)
    """

    def __init__(self, column_name: str, source: str = ""):
        self.column_name = column_name
        self.source = source
        message = f"必須列 '{column_name}' が見つかりません。"
        if source:
            message += f" (対象: {source})"
        super().__init__(message)


class MappingNotFoundError(FacImportError):
    """マッピングマスタに対応する行が見つからない場合(未分類が多すぎる等)。"""


class InvalidSourceFormatError(FacImportError):
    """仕訳データの形式が想定外(エンコーディング不正・列構成の破損等)の場合。"""
