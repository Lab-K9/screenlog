"""ScreenLog - 設定管理"""

import json
from pathlib import Path

# デフォルト設定
DEFAULT_INTERVAL = 60  # 1分
DEFAULT_RETENTION_DAYS = 30
DEFAULT_FLUSH_INTERVAL = 300  # 5分
MIN_INTERVAL = 10  # 最小間隔（秒）

CONFIG_DIR = Path.home() / "Library" / "Application Support" / "ScreenLog"
CONFIG_FILE = CONFIG_DIR / "config.json"


def get_config() -> dict:
    """
    設定ファイルを読み込む。存在しない場合はデフォルト値を返す。

    Returns:
        dict: 設定辞書
    """
    defaults = {
        "interval": DEFAULT_INTERVAL,
        "retention_days": DEFAULT_RETENTION_DAYS,
        "flush_interval": DEFAULT_FLUSH_INTERVAL,
    }

    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                user_config = json.load(f)
            defaults.update(user_config)
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: Could not read config file {CONFIG_FILE}: {e}")

    return defaults


def save_config(config: dict) -> bool:
    """
    設定をファイルに保存する。

    Args:
        config: 保存する設定辞書

    Returns:
        bool: 保存成功ならTrue
    """
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except OSError as e:
        print(f"Warning: Could not save config file {CONFIG_FILE}: {e}")
        return False


def validate_interval(interval: int) -> int:
    """
    間隔値をバリデーションする。

    Args:
        interval: キャプチャ間隔（秒）

    Returns:
        int: バリデーション済みの間隔値

    Raises:
        ValueError: 間隔が不正な場合
    """
    if interval < MIN_INTERVAL:
        raise ValueError(
            f"キャプチャ間隔は{MIN_INTERVAL}秒以上を指定してください（指定値: {interval}秒）"
        )
    return interval
