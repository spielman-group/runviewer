# runviewer deep pass

A planning document for the code-health campaign (`issues/code_health_campaign.md`
in the meta repo). It lists candidates for Ian's review and is deleted when the
pass is done. Nothing is changed until Ian has reviewed each entry.

## Step 1: contract

What each existing test protects. Marks: **keep**, **rename**, **fix** (the
behaviour is real but the test is not where it should be, or carries dead
parts), **cut** (protects nothing worth keeping).

All 10 tests were written by the fork; upstream had none. Each fix and cut
below was checked by breaking a scratch copy of the code (`git archive` of
`CodeHealth`, run with `PYTHONPATH` pointing at it).

### Totals

- Test files: 2, plus `conftest.py` and `fixtures.py`. Tests: 10.
- Marks: keep 5, fix 5, cut 0.

### tests/test_client.py

- `test_a_shot_reaches_the_queue_as_its_local_path`: a shot sent through
  `RunviewerClient.add_shot` reaches runviewer's queue as its local path.
  **keep**. Fails when `handle_add_shot` raises.

### tests/test_save_channel_config_dialog.py

`SaveChannelConfigDialogTests`, what *Save channel config* offers the save
panel. All **keep**; each fails alone when its rule is broken.
- `test_the_offered_filename_carries_the_toml_extension`: the panel is offered
  a name ending `.toml`, so the macOS panel keeps it. Fails when the offer is
  `untitled`.
- `test_the_offered_filename_sits_in_the_default_config_folder`: fails when the
  offer is in another folder.
- `test_the_offered_filename_is_not_the_runviewer_state_file`: fails when the
  offer is `runviewer.toml`.

`SaveChannelConfigExtensionTests`, what the saved file is called.
- `test_a_name_returned_without_an_extension_is_given_one`,
  `test_a_name_returned_with_the_extension_keeps_it_as_it_is`,
  `test_a_name_returned_with_a_foreign_extension_keeps_it_and_gains_toml`,
  `test_a_legacy_ini_name_has_its_extension_replaced`,
  `test_a_name_whose_stem_contains_dots_keeps_all_of_them`: **fix, move to
  labscript-utils**. Deleting runviewer's own suffix line
  (`__main__.py:717`) leaves all five passing, because `save_appconfig` applies
  `appconfig_path_with_suffix` itself. They test labscript-utils' naming rule,
  which has no test of its own there. Line 717 is a step 2 candidate.
- `test_the_channels_reach_the_file_that_was_written`: each channel is saved
  with its checked state. **keep**. Fails when the checked state is dropped.

### Fixtures

- `FakeRunViewer.get_default_config_file` is never called: the handler does not
  use it, and the state-file test compares with `RunViewer.default_config_filename`.
  Its docstring's reason is stale. Delete it with the move above.

## Shared GUI features runviewer does not use

Ian's study for this pass: what runmanager and lyse take from the shared parents
(`LabscriptApplication`, `LabscriptGuiApplication`, `themed_window`,
`file_dialogs`, `LinkIndicator`) that runviewer does not, or have that could
move into a parent. Already shared by runviewer: `LabscriptApplication`
(`save_configuration`, the elided config-path title), `file_dialogs`,
`exec_qapplication`. Sizes are rough line counts in runviewer.

| # | Feature | runviewer today | Gives a user | Change | Fits |
| --- | --- | --- | --- | --- | --- |
| A | `LabscriptGuiApplication` Load / Save as handlers | own `on_load_runviewer_state`, `on_save_runviewer_state` | offer to save unsaved changes before a load; same captions as the other apps | subclass `LabscriptGuiApplication`, connect the two existing actions, delete both methods (about −22) | yes |
| B | Save (to current file) and Revert actions | absent | save the layout without a dialog; undo layout changes | two actions in `main.ui`, two `connect` lines; needs A | yes, small value |
| C | `error_dialog` / `question_dialog` | hand-built `QMessageBox` at 768 (open-shot warning) and 784 (remove shots) | none visible; the same dialog code everywhere | two call sites (about −8); needs A | yes |
| D | `ThemedWindow` main window | plain `QMainWindow` from `main.ui` | trees, menus and buttons follow a live OS light/dark switch; plots (pyqtgraph) do not | a three-line `RunviewerMainWindow(ThemedWindow, QMainWindow)` registered with `UiLoader` | yes |
| E | Autoload of the config at startup | none; the title names the default config file although nothing was loaded | window size and splitters come back at start | load `get_default_config_file()` (or `runviewer/autoload_config_file`, as runmanager and lyse read theirs) after the window shows; about +8. A user-visible change, so Ian's choice | yes |
| F | Save on quit | none | the layout is kept between runs | runmanager and lyse each write the same Yes/No/Cancel prompt in `on_close_event`; it could move into `LabscriptGuiApplication`. runviewer's state is only geometry, which lyse saves without asking, so runviewer would save silently. Needs D's window class for `closeEvent`; touches three repos | only with E |
| G | `FirstPaintWindow` | not used | nothing on its own; runmanager and lyse use it only to defer their autoload | only if E defers its load | with E |
| H | `LinkIndicator` | not used | nothing: runviewer calls no other app | none | no |

The false title in E is listed in `KNOWN_ISSUES.md`.
