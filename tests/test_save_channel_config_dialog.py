"""The save panel behind *Save channel config*.

A save panel decides the extension of the file it returns. Given a name that
already has one it keeps that one, and typing replaces only the stem. Given a
bare folder it has no extension to preserve and supplies one of its own, taken
from the host's type database rather than from the name filter the dialog asked
for -- so the file that comes back need not be a ``.toml`` file at all, and
nothing between the panel and ``save_appconfig`` would notice.

What is pinned here is that the handler hands the panel a filename carrying the
extension a channel configuration is meant to have, in the folder those
configurations live in, and that the name offered is not the runviewer state
file -- which sits in that same folder, holds something else entirely, and is
the one file an operator must not be invited to overwrite from this dialog.

Pinned alongside it is what becomes of the name the panel returns, whatever the
panel or the operator made of it: the file written is a ``.toml`` file, and a
name already ending in an app config extension has that extension replaced
rather than added to. Those two rules are ``appconfig_path_with_suffix``, and
they are pinned here because the extension a dialog offers and the extension its
file ends up with are one contract, not two.

The panel belongs to the operating system and cannot be driven from a test, so
the seam under test is the call into it: ``QFileDialog`` is replaced in
``file_dialogs``, which makes the call, and the arguments it was given are read
back. What the file is called is read from the directory afterwards, the name
being the whole of what is under test.
"""
import os
import shutil
import tempfile
import unittest

import labscript_utils.qtwidgets.file_dialogs as file_dialogs

# fixtures stubs the splash and does the guarded import of the application,
# once, for every test module. Importing runviewer.__main__ here instead would
# show the startup banner.
from fixtures import RunViewer, main_module


class FakeChannelModel(object):
    """The rows ``on_save_channel_config`` reads to build the channel list.

    A ``QStandardItemModel`` would need a ``QApplication``, and the handler
    asks it for four things.
    """

    class Item(object):
        def __init__(self, name, checked):
            self.name = name
            self.checked = checked

        def text(self):
            return self.name

        def checkState(self):
            return main_module.Qt.Checked if self.checked else main_module.Qt.Unchecked

    def __init__(self, channels):
        self.items = [self.Item(name, checked) for name, checked in channels]

    def rowCount(self):
        return len(self.items)

    def item(self, row):
        return self.items[row]


class FakeRunViewer(object):
    """Enough of a RunViewer for ``on_save_channel_config`` to run.

    ``RunViewer.__init__`` builds the whole application, which this one handler
    has no use for.
    """

    on_save_channel_config = RunViewer.on_save_channel_config

    def __init__(self, folder):
        # The dialog's parent widget. Never reached, because the call into the
        # panel is intercepted.
        self.ui = None
        self.default_config_path = folder
        self.channel_model = FakeChannelModel(
            [('ni_card/ao0', True), ('ni_card/ao1', False)]
        )

    def get_default_config_file(self, ensure_directory=False):
        """The runviewer state file, as ``LabscriptApplication`` returns it.

        The handler does not call this. It is here so that the test which says
        the offered name is not this file can fail when it is: a stand-in
        without the method would raise instead, and an error raised reaching
        the assertion is not the assertion doing its work.
        """
        return os.path.join(self.default_config_path, RunViewer.default_config_filename)


class FakeFileDialog(object):
    """Stands in for ``QFileDialog`` in ``file_dialogs``.

    The dialog helpers look ``QFileDialog`` up in their own module, so rebinding
    the name there is enough to intercept the call. Doing it this way leaves the
    real Qt class untouched for everything else in the process.
    """

    def __init__(self):
        # Directories the panel was opened at, one per call, and the name it is
        # to hand back. A falsy name is a cancelled dialog.
        self.calls = []
        self.answer = ''

    def getSaveFileName(self, parent, caption, directory, filter=None):
        self.calls.append(directory)
        return (self.answer, filter)


class SaveChannelConfigDialogTests(unittest.TestCase):
    """What the handler asks the panel for."""

    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder, ignore_errors=True)

        self.file_dialog = FakeFileDialog()
        self.saved_file_dialog = file_dialogs.QFileDialog
        file_dialogs.QFileDialog = self.file_dialog
        self.addCleanup(self.restore)

        self.app = FakeRunViewer(self.folder)

    def restore(self):
        file_dialogs.QFileDialog = self.saved_file_dialog

    def suggested_path(self):
        """The name the panel was offered, the dialog having been cancelled."""
        self.file_dialog.answer = ''
        self.app.on_save_channel_config()
        self.assertEqual(len(self.file_dialog.calls), 1, 'the panel is opened once')
        return self.file_dialog.calls[0]

    def test_the_offered_filename_carries_the_toml_extension(self):
        suggested = self.suggested_path()

        self.assertTrue(
            suggested.lower().endswith('.toml'),
            'the panel keeps the extension it is given and replaces only the '
            'stem, so the name offered has to end in .toml; got %r' % suggested,
        )

    def test_the_offered_filename_sits_in_the_default_config_folder(self):
        suggested = self.suggested_path()

        self.assertEqual(
            os.path.dirname(suggested),
            self.folder,
            'the panel still opens where saved configurations are kept',
        )

    def test_the_offered_filename_is_not_the_runviewer_state_file(self):
        # The state file lives in this same folder, and *Save runviewer state*
        # writes window geometry to it. A channel configuration written over it
        # would take that geometry with it, so the panel must not offer its
        # name as the one to accept.
        suggested = self.suggested_path()

        self.assertNotEqual(
            os.path.basename(suggested).lower(),
            RunViewer.default_config_filename.lower(),
            'the name offered is one to type over, not a file that exists',
        )


class SaveChannelConfigExtensionTests(unittest.TestCase):
    """What the file is called, for every name the panel can hand back.

    An operator can clear the extension the panel offers, and a panel asked for
    a type the host resolves elsewhere can return one nobody asked for, so the
    name that arrives here is not necessarily the name that was offered.
    """

    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder, ignore_errors=True)

        self.file_dialog = FakeFileDialog()
        self.saved_file_dialog = file_dialogs.QFileDialog
        file_dialogs.QFileDialog = self.file_dialog
        self.addCleanup(self.restore)

        self.app = FakeRunViewer(self.folder)

    def restore(self):
        file_dialogs.QFileDialog = self.saved_file_dialog

    def written(self, returned_name):
        """Save with the panel returning ``returned_name``, and list the folder."""
        self.file_dialog.answer = os.path.join(self.folder, returned_name)
        self.app.on_save_channel_config()
        return sorted(os.listdir(self.folder))

    def test_a_name_returned_without_an_extension_is_given_one(self):
        self.assertEqual(
            self.written('test'),
            ['test.toml'],
            'a bare stem becomes a .toml file',
        )

    def test_a_name_returned_with_the_extension_keeps_it_as_it_is(self):
        self.assertEqual(
            self.written('test.toml'),
            ['test.toml'],
            'the extension is not doubled',
        )

    def test_a_name_returned_with_a_foreign_extension_keeps_it_and_gains_toml(self):
        # What a native panel hands back when it resolves the name filter
        # through the host's type database instead of preserving a name.
        self.assertEqual(
            self.written('test.cfg'),
            ['test.cfg.toml'],
            'an extension that is not an app config extension is part of the '
            'name, so the .toml goes after it rather than over it',
        )

    def test_a_legacy_ini_name_has_its_extension_replaced(self):
        # .ini is the app config extension runviewer still reads. A name
        # carrying it is the same configuration, so the TOML file takes its
        # place rather than sitting beside it as test.ini.toml.
        self.assertEqual(
            self.written('test.ini'),
            ['test.toml'],
            'a legacy extension is replaced, not appended to',
        )

    def test_a_name_whose_stem_contains_dots_keeps_all_of_them(self):
        # Channel configurations are named after apparatus and shots, which
        # carry dots; replacing after the last one would address another file.
        self.assertEqual(
            self.written('rb.87.imaging'),
            ['rb.87.imaging.toml'],
            'only an app config extension is replaced',
        )

    def test_the_channels_reach_the_file_that_was_written(self):
        # The extension rules are about naming; this is the one test that says
        # the named file holds what the dialog was opened to save.
        self.written('test')

        config = main_module.load_appconfig(os.path.join(self.folder, 'test.toml'))

        self.assertEqual(
            config['runviewer_state']['channels'],
            [['ni_card/ao0', True], ['ni_card/ao1', False]],
            'each channel is stored with its checked state',
        )


if __name__ == '__main__':
    unittest.main()
