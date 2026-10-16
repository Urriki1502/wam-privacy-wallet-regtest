"""Opted-in multi-window acceptance lifetime; interactive shutdown is unchanged."""
from contextlib import contextmanager


@contextmanager
def acceptance_application():
    from .desktop import qt_application
    app=qt_application()
    prior=app.quitOnLastWindowClosed()
    # A probe intentionally closes windows before the next real-Core scenario.
    # Do not leave QApplication's deferred quit in the next nested event loop.
    app.setQuitOnLastWindowClosed(False)
    try:yield app
    finally:app.setQuitOnLastWindowClosed(prior)
