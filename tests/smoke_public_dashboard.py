"""Exercise the public entry point against the published GitHub data release."""

import unittest

from streamlit.testing.v1 import AppTest


class PublicDashboardSmokeTest(unittest.TestCase):
    def test_published_data_loads(self):
        app = AppTest.from_file("app/public_app.py", default_timeout=75).run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error, [error.value for error in app.error])
        self.assertFalse(app.warning)
        charts = app.get("arrow_vega_lite_chart")
        self.assertTrue(any("Nigeria map of monthly values by LGA" in chart.proto.spec for chart in charts))

        case_count = next(metric for metric in app.metric if metric.label == "Reported confirmed cases")
        self.assertTrue(case_count.value.replace(",", "").isdigit())
        self.assertIn("**Nationwide backtest errors**", [item.value for item in app.markdown])

        delay = next(radio for radio in app.radio if radio.label == "Assumed input delay (months)")
        delay.set_value(2).run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error, [error.value for error in app.error])
        self.assertIn("**Nationwide backtest errors**", [item.value for item in app.markdown])
