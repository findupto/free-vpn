"""Runtime adapter for the premium UI.

The legacy engine owns the event queue and calls ``_pump`` from its constructor.
This adapter routes that callback to the premium UI event renderer so the old
admin-dashboard renderer cannot consume premium UI events first.
"""
from gui_premium import App as PremiumBase


class App(PremiumBase):
    def _pump(self):
        self._premium_pump()
