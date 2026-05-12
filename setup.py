"""
py2app setup script for ScreenLog
Build with: python setup.py py2app
"""
from setuptools import setup

APP = ['run_screenlog.py']
DATA_FILES = []
OPTIONS = {
    'argv_emulation': False,
    'iconfile': 'assets/ScreenLog.icns',
    'plist': {
        'CFBundleName': 'ScreenLog',
        'CFBundleDisplayName': 'ScreenLog',
        'CFBundleIdentifier': 'com.screenlog.app',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'LSUIElement': True,  # Dockに表示しない（メニューバーアプリ）
        'NSHighResolutionCapable': True,
        # 権限の説明（権限ダイアログに表示される）
        'NSScreenCaptureUsageDescription': 'ScreenLog needs screen recording permission to capture screenshots for activity logging.',
        'NSAppleEventsUsageDescription': 'ScreenLog needs accessibility permission to get active window information.',
    },
    'packages': [
        'screenlog',
        'rumps',
        'objc',
        'Quartz',
        'Vision',
        'Foundation',
        'AppKit',
        'CoreFoundation',
        'ApplicationServices',
    ],
    'includes': [
        'Quartz',
        'Quartz.CoreGraphics',
        'AppKit',
        'Vision',
        'objc',
        'Foundation',
        'rumps',
        'ApplicationServices',
    ],
}

setup(
    name='ScreenLog',
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
