"""ScreenLogのアイドル（無操作）時間検知モジュール"""


def get_idle_seconds() -> float | None:
    """直近の入力イベントからの経過秒数を取得する。

    macOSのQuartzイベントソースAPI（HIDシステム全体の入力ソース）を使い、
    キーボード・マウスいずれの入力からも経過した秒数を返す。Quartzの
    importや呼び出しに失敗した場合は判定不能としてNoneを返す
    （Noneの場合はrecorder側で通常キャプチャを継続する＝fail openにする）。

    Returns:
        float | None: 直近の入力イベントからの経過秒数。取得できない場合はNone
    """
    try:
        import Quartz

        return Quartz.CGEventSourceSecondsSinceLastEventType(
            Quartz.kCGEventSourceStateHIDSystemState,
            Quartz.kCGAnyInputEventType,
        )
    except Exception:
        return None
