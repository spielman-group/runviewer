#####################################################################
#                                                                   #
# /runviewer/client.py                                              #
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
"""The client through which other programs reach runviewer's server."""
from labscript_utils.ls_zprocess import ZMQClient


class RunviewerClient(ZMQClient):
    """A ZMQClient for communication with runviewer."""

    server = 'runviewer'
    default_port = 42521

    def add_shot(self, filepath):
        """Queue a shot file to be opened in runviewer.

        Parameters
        ----------
        filepath : str
            The shot file, as a local path or as
            :func:`labscript_utils.shared_drive.path_to_agnostic` gives it.
        """
        self.request('add_shot', filepath)
