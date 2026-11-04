"""Exercise the hosted entry point with the pinned dashboard dependencies."""

import unittest

from streamlit.testing.v1 import AppTest


class DemoDashboardSmokeTest(unittest.TestCase):
    def test_demo_loads_and_answers_for_selected_month(self):
        app = AppTest.from_file("app/demo_app.py", default_timeout=30).run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        self.assertIn("Synthetic demo", app.warning[0].value)
        self.assertEqual([tab.label for tab in app.tabs], [
            "Overview", "Case and rainfall trends", "LGA comparison", "Demo map", "Forecast backtest",
        ])
        self.assertIn("Fictional shapes", " ".join(caption.value for caption in app.caption))
        comparison = next(box for box in app.selectbox if box.label == "Second LGA")
        comparison.set_value("demo-lga-3").run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.get("arrow_vega_lite_chart")), 5)

        next(button for button in app.button if button.label == "Tell me about this LGA").click().run()
        self.assertFalse(app.exception)
        self.assertIn("December 2025", app.chat_message[0].markdown[0].value)
        month = next(box for box in app.selectbox if box.label == "Question month")
        month.set_value("2024-05").run()
        self.assertFalse(app.exception)
        reply = app.chat_message[0].markdown[0].value
        self.assertIn("May 2024", reply)
        self.assertIn("**145**", reply)

        delay = next(radio for radio in app.radio if radio.label == "Assumed input delay (months)")
        delay.set_value(2).run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        self.assertIn("**Backtest errors across demo LGAs**", [item.value for item in app.markdown])
