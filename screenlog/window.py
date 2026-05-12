"""アクティブウィンドウ取得モジュール - PyObjC版"""

import gc
from typing import Any, Optional


EXCLUDED_WORKING_APPS = {
    "dock",
    "loginwindow",
    "notification center",
    "screencaptureui",
    "systemuiserver",
    "tldv",
    "window server",
}


def _normalized_app_name(name: str | None) -> str:
    """比較用にアプリ名を正規化する。"""
    return (name or "").strip().casefold()


def _window_title(window: dict[str, Any]) -> str:
    return str(window.get("window_title") or window.get("name") or "")


def _window_owner(window: dict[str, Any]) -> str:
    return str(window.get("owner_name") or "")


def _window_id(window: dict[str, Any]) -> int | None:
    value = window.get("window_id")
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _window_area(window: dict[str, Any]) -> int:
    bounds = window.get("bounds") or {}
    try:
        return int(bounds.get("Width", 0)) * int(bounds.get("Height", 0))
    except (TypeError, ValueError):
        return 0


def is_excluded_working_app(app_name: str | None) -> bool:
    """作業アプリとして扱わない補助的なプロセスか判定する。"""
    return _normalized_app_name(app_name) in EXCLUDED_WORKING_APPS


def is_visible_normal_window(window: dict[str, Any]) -> bool:
    """作業候補にできる通常ウィンドウか判定する。"""
    try:
        layer = int(window.get("layer", -1))
        alpha = float(window.get("alpha", 0))
    except (TypeError, ValueError):
        return False

    return layer == 0 and alpha > 0 and _window_area(window) > 0


def _with_selection_reason(window: dict[str, Any], reason: str) -> dict[str, Any]:
    selected = dict(window)
    selected["selection_reason"] = reason
    return selected


def select_working_window(
    windows: list[dict[str, Any]],
    *,
    focused_app: str | None,
    focused_title: str | None = None,
) -> dict[str, Any] | None:
    """
    CGWindowListの候補から、実作業ウィンドウを1つ選ぶ。

    tldvのような補助ウィンドウが前面扱いになっても、通常ウィンドウ一覧から
    作業に使っていそうな非除外アプリを選ぶ。
    """
    visible = [window for window in windows if is_visible_normal_window(window)]
    focused_key = _normalized_app_name(focused_app)

    if focused_key and not is_excluded_working_app(focused_app):
        for window in visible:
            if _normalized_app_name(_window_owner(window)) == focused_key:
                return _with_selection_reason(window, "focused_app_visible_window")

    non_excluded = [
        window
        for window in visible
        if not is_excluded_working_app(_window_owner(window))
    ]
    if non_excluded:
        return _with_selection_reason(
            non_excluded[0],
            "first_non_excluded_visible_window",
        )

    return None


def _compact_window(window: dict[str, Any]) -> dict[str, Any]:
    """ログに残すため、ウィンドウ候補を小さな辞書へ圧縮する。"""
    compact: dict[str, Any] = {
        "owner_name": _window_owner(window),
        "window_title": _window_title(window),
        "layer": window.get("layer"),
        "alpha": window.get("alpha"),
    }
    window_id = _window_id(window)
    if window_id is not None:
        compact["window_id"] = window_id
    bounds = window.get("bounds")
    if bounds:
        compact["bounds"] = bounds
    return compact


def diagnostic_windows(windows: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    """doctorやログに残す候補ウィンドウを、通常ウィンドウ優先で返す。"""
    visible_normal = [window for window in windows if is_visible_normal_window(window)]
    ordered = visible_normal + [
        window for window in windows if not is_visible_normal_window(window)
    ]

    seen_ids: set[int] = set()
    result: list[dict[str, Any]] = []
    for window in ordered:
        window_id = _window_id(window)
        if window_id is not None:
            if window_id in seen_ids:
                continue
            seen_ids.add(window_id)
        result.append(_compact_window(window))
        if len(result) >= limit:
            break
    return result


def get_active_app() -> str:
    """
    アクティブなアプリケーション名を取得（NSWorkspace使用、権限不要）

    Returns:
        str: アプリケーション名。取得失敗時は"Unknown"
    """
    try:
        from AppKit import NSWorkspace

        workspace = NSWorkspace.sharedWorkspace()
        active_app = workspace.frontmostApplication()

        if active_app:
            return active_app.localizedName() or "Unknown"
        return "Unknown"

    except ImportError:
        print("AppKit not available")
        return "Unknown"
    except Exception as e:
        print(f"Get active app error: {e}")
        return "Unknown"


def get_focused_app_context() -> dict[str, Any]:
    """NSWorkspaceからフォーカス中アプリの基本情報を取得する。"""
    try:
        from AppKit import NSWorkspace

        workspace = NSWorkspace.sharedWorkspace()
        active_app = workspace.frontmostApplication()
        if not active_app:
            return {
                "focused_app": "Unknown",
                "focused_bundle_id": None,
                "focused_pid": None,
            }

        return {
            "focused_app": active_app.localizedName() or "Unknown",
            "focused_bundle_id": active_app.bundleIdentifier(),
            "focused_pid": int(active_app.processIdentifier()),
        }
    except Exception as e:
        print(f"Get focused app context error: {e}")
        return {
            "focused_app": "Unknown",
            "focused_bundle_id": None,
            "focused_pid": None,
        }


def get_window_title() -> str:
    """
    アクティブウィンドウのタイトルを取得（AXUIElement使用）

    Returns:
        str: ウィンドウタイトル。取得失敗時は"Unknown"
    """
    try:
        from AppKit import NSWorkspace
        import ApplicationServices

        # アクティブアプリのPIDを取得
        workspace = NSWorkspace.sharedWorkspace()
        active_app = workspace.frontmostApplication()

        if not active_app:
            return "Unknown"

        pid = active_app.processIdentifier()
        create_application = getattr(
            ApplicationServices,
            "AXUIElementCreateApplication",
            None,
        )
        copy_attribute = getattr(
            ApplicationServices,
            "AXUIElementCopyAttributeValue",
            None,
        )
        focused_window_attribute = getattr(
            ApplicationServices,
            "kAXFocusedWindowAttribute",
            None,
        )
        title_attribute = getattr(ApplicationServices, "kAXTitleAttribute", None)

        if not all(
            [
                create_application,
                copy_attribute,
                focused_window_attribute,
                title_attribute,
            ]
        ):
            return "Unknown"

        # AXUIElementを作成
        app_element = create_application(pid)
        if not app_element:
            return "Unknown"

        try:
            # フォーカスされているウィンドウを取得
            error, focused_window = copy_attribute(
                app_element, focused_window_attribute, None
            )

            if error or not focused_window:
                return "Unknown"

            try:
                # ウィンドウタイトルを取得
                error, title = copy_attribute(
                    focused_window, title_attribute, None
                )

                if error or not title:
                    return "Unknown"

                return str(title)

            finally:
                # focused_windowの参照をクリア
                del focused_window

        finally:
            # app_elementの参照をクリア
            del app_element

    except ImportError:
        return "Unknown"
    except Exception as e:
        # アクセシビリティ権限がない場合もここに来る
        # エラーメッセージは出さない（頻繁に呼ばれるため）
        return "Unknown"


def get_active_window_info() -> tuple[str, str]:
    """
    アクティブウィンドウの情報を取得

    Returns:
        tuple[str, str]: (アプリケーション名, ウィンドウタイトル)
    """
    context = get_window_context()
    return context["working_app"], context["working_title"]


def collect_window_candidates() -> list[dict[str, Any]]:
    """画面上の通常ウィンドウ候補をCGWindowListから取得する。"""
    window_list = None

    try:
        import objc
        import Quartz

        with objc.autorelease_pool():
            window_list = Quartz.CGWindowListCopyWindowInfo(
                Quartz.kCGWindowListOptionOnScreenOnly,
                Quartz.kCGNullWindowID,
            )
            if not window_list:
                return []

            candidates: list[dict[str, Any]] = []
            for window in window_list:
                window_id = window.get(Quartz.kCGWindowNumber)
                owner_name = window.get(Quartz.kCGWindowOwnerName, "")
                window_title = window.get(Quartz.kCGWindowName, "")
                layer = window.get(Quartz.kCGWindowLayer, -1)
                alpha = window.get(Quartz.kCGWindowAlpha, 0)
                bounds = window.get(Quartz.kCGWindowBounds, {}) or {}

                candidates.append(
                    {
                        "window_id": int(window_id) if window_id is not None else None,
                        "owner_name": str(owner_name or ""),
                        "window_title": str(window_title or ""),
                        "layer": int(layer) if layer is not None else -1,
                        "alpha": float(alpha) if alpha is not None else 0,
                        "bounds": dict(bounds),
                    }
                )
            return candidates

    except ImportError:
        print("Quartz framework not available")
        return []
    except Exception as e:
        print(f"Failed to collect window candidates: {e}")
        return []
    finally:
        window_list = None
        gc.collect()


def get_window_context() -> dict[str, Any]:
    """
    記録用の作業ウィンドウ文脈を取得する。

    focused_* はOSが前面とみなすアプリ、working_* はScreenLogが作業実体と
    判断したアプリ。tldv等の補助アプリ誤判定を避けるため両方を残す。
    """
    focused = get_focused_app_context()
    focused_title = get_window_title()
    windows = collect_window_candidates()
    selected = select_working_window(
        windows,
        focused_app=str(focused.get("focused_app") or ""),
        focused_title=focused_title,
    )

    if selected is None:
        return {
            **focused,
            "focused_title": focused_title,
            "working_app": str(focused.get("focused_app") or "Unknown"),
            "working_title": focused_title,
            "working_bundle_id": focused.get("focused_bundle_id"),
            "window_id": None,
            "capture_mode": "full_screen",
            "selection_reason": "no_visible_working_window",
            "top_windows": diagnostic_windows(windows),
        }

    return {
        **focused,
        "focused_title": focused_title,
        "working_app": _window_owner(selected) or str(focused.get("focused_app") or "Unknown"),
        "working_title": _window_title(selected) or focused_title or "Unknown",
        "working_bundle_id": None,
        "window_id": _window_id(selected),
        "capture_mode": "working_window",
        "selection_reason": str(selected.get("selection_reason") or "selected_window"),
        "top_windows": diagnostic_windows(windows),
    }


def get_active_window_id() -> Optional[int]:
    """
    アクティブウィンドウのウィンドウIDを取得（screencaptureコマンド用）

    Returns:
        Optional[int]: ウィンドウID。取得失敗時はNone
    """
    return get_window_context().get("window_id")
