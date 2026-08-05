"""
engines/registry.py

各インポーターモジュール(engines/importers/*.py)を集約するレジストリ。

新しい会計ソフト対応を追加する際にアプリ本体(GUI)を改修せずに済むよう、
「インポーター側が自己申告した IMPORTER_META を、ここで一箇所に集める」
という構造にしている。

新しいインポーターを追加する手順:
  1. engines/importers/<ソフト名>.py を作成する
  2. モジュールに IMPORTER_META (dict) と decompose_to_fac(source_path, mapping_path) を実装する
  3. 本ファイルの import 文と _IMPORTER_MODULES に1行追加する
  (GUI側のコードは変更不要)
"""

from engines.importers import freee, money_forward

# 対応済みインポーターのモジュール一覧。
# 新しいソフトに対応したら、ここに追記するだけでよい。
_IMPORTER_MODULES = [
    money_forward,
    freee,
]


def _build_registry() -> dict:
    registry = {}
    for module in _IMPORTER_MODULES:
        meta = getattr(module, "IMPORTER_META", None)
        if meta is None:
            raise AttributeError(
                f"{module.__name__} に IMPORTER_META が定義されていません。"
            )
        importer_id = meta["id"]
        if importer_id in registry:
            raise ValueError(f"インポーターID '{importer_id}' が重複しています。")
        registry[importer_id] = module
    return registry


# id -> モジュール のマッピング。GUIはこれを走査してプルダウン等を構築する。
IMPORTERS = _build_registry()


def get_importer(importer_id: str):
    """importer_id に対応するインポーターモジュールを返す。

    Args:
        importer_id: IMPORTER_META["id"] の値(例: "money_forward")

    Returns:
        該当インポーターモジュール。decompose_to_fac(source_path, mapping_path) を持つ。

    Raises:
        KeyError: 該当する importer_id が登録されていない場合。
    """
    if importer_id not in IMPORTERS:
        available = ", ".join(IMPORTERS.keys())
        raise KeyError(
            f"インポーター '{importer_id}' は登録されていません。"
            f"(利用可能: {available})"
        )
    return IMPORTERS[importer_id]


def list_importers() -> list:
    """GUIのプルダウン等に使う一覧を返す。

    Returns:
        [{"id": ..., "display_name": ...}, ...] のリスト
    """
    return [
        {"id": meta["id"], "display_name": meta["display_name"]}
        for meta in (module.IMPORTER_META for module in _IMPORTER_MODULES)
    ]
