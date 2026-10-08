"""Settings that have to be in place before the modules that read them.

A test run should not depend on anyone remembering an environment variable, and
a conftest is the right place for both of these: pytest imports it and nothing
else does, so a real runviewer run is unaffected.

``QT_QPA_PLATFORM`` -- running the tests is not supposed to put anything on the
screen of whoever runs them. Most of that is dealt with where it arises:
``fixtures.py`` stands in for the splash module, so importing runviewer builds
no ``QApplication`` at all rather than a hidden one. A test that genuinely
renders is the exception -- Qt does not lay out a widget that was never shown,
so its geometry assertions read zero unless the window really is shown, and
rendering offscreen is what lets such a test go on showing a real window
without one appearing.

``LABSCRIPT_NO_ERROR_DIALOG`` -- stops ``labscript_utils.excepthook`` spawning a
tkinter window for every unhandled exception, which during a test run means one
window per failure. Exceptions are still logged and still reach stderr, so
nothing is hidden from the person running the tests.

Both use ``setdefault``, so a value already in the environment wins.

That is also why this is a conftest rather than a fixture. Both variables have
to be set before the module that reads them is imported -- ``QT_QPA_PLATFORM``
before qtutils imports Qt, ``LABSCRIPT_NO_ERROR_DIALOG`` before excepthook --
and pytest imports conftest before the test modules that pull either in.
"""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('LABSCRIPT_NO_ERROR_DIALOG', '1')
