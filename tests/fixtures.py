#####################################################################
#                                                                   #
# /tests/fixtures.py                                                #
#                                                                   #
# Copyright 2026, JQI                                               #
# Author: Ian Spielman                                              #
#                                                                   #
# This file is part of runviewer, in the labscript suite            #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
"""Stand-ins shared by runviewer's tests.

Importing ``runviewer.__main__`` builds a splash and a ``QApplication``, so this
module stubs ``labscript_utils.splash`` first and imports the application once.
Tests take its names from here, never from ``runviewer.__main__``.
"""
import sys
import types


class Splash:
    """A ``labscript_utils.splash.Splash`` that builds no window."""

    def __init__(self, *args, **kwargs):
        pass

    def show(self):
        pass

    def hide(self):
        pass

    def update_text(self, text):
        pass


def _stub_splash_module():
    # Not undone: the application keeps the stub for the life of the process.
    module = types.ModuleType('labscript_utils.splash')
    module.Splash = Splash
    sys.modules['labscript_utils.splash'] = module


_stub_splash_module()

from runviewer.__main__ import RunViewer, RunviewerServer  # noqa: E402

__all__ = ['RunViewer', 'RunviewerServer']
