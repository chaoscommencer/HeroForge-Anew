"""Wire POSIX termination signals into the Qt event loop for clean shutdown.

When the containerised QA stack is stopped (``docker compose stop`` / ``down``)
the engine sends ``SIGTERM`` to the Qt process; an interactive Ctrl-C sends
``SIGINT``. Without a handler the OS default disposition terminates the process,
which surfaces as a non-zero ``143`` (``128 + SIGTERM``) exit status and an
abrupt teardown. We instead translate those signals into a graceful
:meth:`QApplication.quit`, so the event loop unwinds normally and the process
exits ``0``.

The tricky part is *latency*: while Qt is blocked inside ``app.exec()`` (a C++
event loop) a delivered signal only sets a flag in CPython — Python-level signal
handlers run on the next bytecode boundary, which may not come for a while if the
loop is idle. Rather than poll (a periodic no-op ``QTimer`` that merely hands
control back to the interpreter), this module uses the standard
:func:`signal.set_wakeup_fd` "self-pipe" trick: CPython writes the signal number
to a socket the moment a signal arrives — even from within C code — and a
:class:`~PyQt6.QtCore.QSocketNotifier` watching the other end wakes the event
loop immediately, with no polling and no added latency.

A socket pair (rather than :func:`os.pipe`) is used because
:func:`signal.set_wakeup_fd` requires a socket on Windows, keeping the helper
correct for a desktop app that may run there too.
"""

from __future__ import annotations

import signal
import socket
from collections.abc import Iterable
from dataclasses import dataclass, field

from PyQt6.QtCore import QSocketNotifier
from PyQt6.QtWidgets import QApplication

# Signals that should trigger a graceful application quit.
_DEFAULT_SIGNALS: tuple[signal.Signals, ...] = (signal.SIGINT, signal.SIGTERM)


@dataclass
class SignalQuitGuard:
    """Keep the signal-to-quit plumbing alive for the application's lifetime.

    :func:`signal.set_wakeup_fd` and :class:`QSocketNotifier` only work while the
    underlying sockets and the notifier remain referenced; if this guard were
    garbage-collected the wakeup pipe would close and the notifier would stop
    firing. Callers must therefore retain the returned instance (e.g. as a local
    in :func:`heroforge.app.main`) until the process exits.
    """

    read_socket: socket.socket
    write_socket: socket.socket
    notifier: QSocketNotifier
    signals: tuple[signal.Signals, ...]
    _previous_handlers: dict[signal.Signals, signal.Handlers | object] = field(
        default_factory=dict
    )
    _previous_wakeup_fd: int = -1

    def uninstall(self) -> None:
        """Restore the previous signal handlers and wakeup fd, then close sockets.

        Primarily useful in tests, where leaving process-global signal state
        mutated would leak into later tests. Safe to call more than once.
        """
        self.notifier.setEnabled(False)
        for signum, handler in self._previous_handlers.items():
            try:
                signal.signal(signum, handler)  # type: ignore[arg-type]
            except (OSError, ValueError, TypeError):
                pass
        self._previous_handlers.clear()
        try:
            signal.set_wakeup_fd(self._previous_wakeup_fd)
        except (OSError, ValueError):
            pass
        self.read_socket.close()
        self.write_socket.close()


def install_signal_quit(
    app: QApplication,
    *,
    signals: Iterable[signal.Signals] = _DEFAULT_SIGNALS,
) -> SignalQuitGuard:
    """Make *app* quit gracefully when any of *signals* is delivered.

    Sets up a :func:`signal.set_wakeup_fd` socket pair whose readable end is
    watched by a :class:`QSocketNotifier`; when a signal fires, CPython writes to
    the socket, the notifier wakes the Qt event loop, and :meth:`QApplication.quit`
    is invoked so ``app.exec()`` returns and the process exits cleanly (status 0).

    Must be called from the main thread (only there can :func:`signal.signal` and
    :func:`signal.set_wakeup_fd` be installed). Returns a :class:`SignalQuitGuard`
    that the caller **must** keep referenced for the lifetime of the application;
    dropping it tears the mechanism down.
    """
    signal_tuple = tuple(signals)

    read_socket, write_socket = socket.socketpair()
    read_socket.setblocking(False)
    write_socket.setblocking(False)

    previous_wakeup_fd = signal.set_wakeup_fd(
        write_socket.fileno(), warn_on_full_buffer=False
    )

    # A non-default handler is still required: set_wakeup_fd only delivers the
    # wakeup byte, it does not change the signal's disposition. Without this the
    # OS would still apply the default terminate action (exit 143). The handler
    # body is intentionally empty — the actual quit is driven by the notifier.
    previous_handlers: dict[signal.Signals, signal.Handlers | object] = {}
    for signum in signal_tuple:
        previous_handlers[signum] = signal.getsignal(signum)
        signal.signal(signum, lambda *_: None)

    notifier = QSocketNotifier(read_socket.fileno(), QSocketNotifier.Type.Read)

    def _on_signal() -> None:
        # Drain whatever the wakeup writes deposited so the socket does not stay
        # readable (which would busy-loop the notifier), then quit.
        try:
            read_socket.recv(4096)
        except (BlockingIOError, InterruptedError, OSError):
            pass
        app.quit()

    notifier.activated.connect(lambda _socket: _on_signal())

    return SignalQuitGuard(
        read_socket=read_socket,
        write_socket=write_socket,
        notifier=notifier,
        signals=signal_tuple,
        _previous_handlers=previous_handlers,
        _previous_wakeup_fd=previous_wakeup_fd,
    )
