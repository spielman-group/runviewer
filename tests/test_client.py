#####################################################################
#                                                                   #
# /tests/test_client.py                                             #
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
"""RunviewerClient.add_shot queues a shot in a real runviewer server."""
import os
import unittest
from queue import Queue
from unittest import mock

from labscript_utils import shared_drive

from fixtures import RunviewerServer, main_module
from runviewer.client import RunviewerClient


class AddShotTests(unittest.TestCase):

    def test_a_shot_reaches_the_queue_as_its_local_path(self):
        queue = Queue()
        self.enterContext(
            mock.patch.object(main_module, 'shots_to_process_queue', queue, create=True)
        )
        server = RunviewerServer(bind_address='tcp://127.0.0.1')
        self.addCleanup(server.shutdown)
        path = os.path.join(shared_drive.prefix, 'shot.h5')
        RunviewerClient('127.0.0.1', server.port, 5).add_shot(
            shared_drive.path_to_agnostic(path)
        )
        self.assertEqual(queue.get(timeout=5), path)


if __name__ == '__main__':
    unittest.main()
