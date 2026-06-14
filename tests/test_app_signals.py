"""Tests for :mod:`heroforge.signals` (signal-driven graceful Qt shutdown)."""

from __future__ import annotations

import signal
from unittest.mock import patch

import pytest

from heroforge.signals import install_signal_quit


@pytest.mark.skipif(
    not hasattr(signal, "raise_signal"),
    reason="signal.raise_signal requires Python 3.8+",
)
def test_sigterm_triggers_app_quit(qapp: object) -> None:
    """A delivered SIGTERM should wake the event loop and call ``app.quit``."""
    from PyQt6.QtCore import QEventLoop, QTimer

    guard = install_signal_quit(qapp, signals=(signal.SIGTERM,))
    try:
        quit_called: list[bool] = []
        loop = QEventLoop()

        def _fake_quit() -> None:
            quit_called.append(True)
            loop.quit()

        with patch.object(qapp, "quit", side_effect=_fake_quit):
            # Fallback so the test can never hang if the notifier fails to fire.
            QTimer.singleShot(2000, loop.quit)
            signal.raise_signal(signal.SIGTERM)
            loop.exec()

        assert quit_called, "SIGTERM did not trigger app.quit() via the notifier"
    finally:
        guard.uninstall()


def test_uninstall_restores_previous_handler(qapp: object) -> None:
    """``uninstall`` should restore the signal handler that was in place before."""
    sentinel = signal.getsignal(signal.SIGTERM)

    guard = install_signal_quit(qapp, signals=(signal.SIGTERM,))
    # While installed, our no-op handler is in place (not the original).
    assert signal.getsignal(signal.SIGTERM) is not sentinel

    guard.uninstall()
    assert signal.getsignal(signal.SIGTERM) is sentinel
