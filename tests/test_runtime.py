import unittest

from screenlog.config import validate_retention_days
from screenlog.runtime import load_runtime_settings


class RuntimeSettingsTests(unittest.TestCase):
    def test_load_runtime_settings_defaults_to_one_minute_capture(self):
        settings = load_runtime_settings({})

        self.assertEqual(settings.interval, 60)
        self.assertEqual(settings.flush_interval, 300)

    def test_load_runtime_settings_reads_config_values(self):
        settings = load_runtime_settings(
            {
                "interval": 120,
                "retention_days": 14,
                "flush_interval": 240,
            }
        )

        self.assertEqual(settings.interval, 120)
        self.assertEqual(settings.retention_days, 14)
        self.assertEqual(settings.flush_interval, 240)

    def test_load_runtime_settings_defaults_flush_interval(self):
        settings = load_runtime_settings({"interval": 60, "retention_days": 30})

        self.assertEqual(settings.flush_interval, 300)

    def test_load_runtime_settings_rejects_zero_retention(self):
        with self.assertRaises(ValueError):
            load_runtime_settings({"interval": 60, "retention_days": 0})

    def test_validate_retention_days_requires_positive_value(self):
        self.assertEqual(validate_retention_days(1), 1)
        with self.assertRaises(ValueError):
            validate_retention_days(-1)


if __name__ == "__main__":
    unittest.main()
