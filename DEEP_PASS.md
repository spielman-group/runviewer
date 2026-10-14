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

## Done

Ian approved the contract and A-F. Commits on `CodeHealth`:

- Contract: the five naming tests are one test in labscript-utils
  (`tests/test_labconfig.py`, 0f41853), and runviewer drops them and the unused
  stand-in method (e51e735). Line 717 waits for step 2.
- A, B: 862e2bd. C: f1ece9a. D: 1d59ba2. E: 8709a04.
- F: labscript-utils `LabscriptGuiApplication.offer_to_save_changes` and
  `geometry_keys` (ab74f34); runviewer 000c645; runmanager 3dcdfea; lyse
  8f4eb9a.
- From the review: Load configuration refuses a channel configuration, which
  quitting would otherwise overwrite with the layout, and a bad state file no
  longer stops runviewer starting.
- Not done: runmanager's on-screen quit check, which would rewrite Ian's saved
  `runmanager.toml`; its owner offers it to Ian. No test covers
  `offer_to_save_changes`; the contract adds none.

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

## Step 2.1: behaviour no one asked for

The source is `git diff master CodeHealth`, leaving out the approved contract
and shared-GUI round (193d554..66bd6df). Every behaviour the fork added traces
to a request or a suite-wide decision, so there are **no candidates**.

| Behaviour | Commits | Where it was asked for |
| --- | --- | --- |
| TOML config files; legacy INI read and converted | 9d26a24, fbf846e, a6a5502, cda43b2 | `toml` and `RunmanagerTOML` in `CODEX.md`: TOML as the suite's config format. The INI path is for step 4 |
| Window geometry saved in the config | a6a5502 | `RunmanagerTOML` in `CODEX.md`; upstream already had the two state actions in `main.ui`, unwired. Superseded by the approved A, E and F |
| Config path in the window title | 01b5931 | `UpdatedTitleBars` in `CODEX.md`; approved again as E |
| macOS display name | 2da35fe, 6e3fe1d | `MacOS` in `CODEX.md`; its `desktop-app` part went upstream |
| Channel-config save panel offers `untitled.toml` | 1897e32, c23c527 | The macOS panel bug recorded in shared memory (`macos-save-panel-invents-extensions.md`) |
| Request protocol for the server, `RunviewerClient` | 4377c47, 1ba24c9, 22c8808 | `issues/server_interfaces_2026_09_25.md`, step 3 |
| Shared version, dialogs, event loop, docs, setuptools_scm scheme | a5ef546, 4db574e, 0ec3be3, b39a93e, fa6b8d5 | The campaign's step 2 and 5 rounds in labscript-utils, approved by Ian |

Searched: `CODEX.md`, the meta repo's `issues/`, shared memory, and each
commit's message and branch. Users reached: the operator through the menus and
the window, and runmanager through `RunviewerClient`.

A note for step 6, not behaviour: the fork's TOML branch reverted upstream's
`from qtutils.qt import QtCore, QtGui, QtWidgets` to star imports from
`qtutils.qt.QtCore`, `QtGui` and `QtWidgets`, against labscript-style.

## Step 2.2: duplication

Searched: the librarian's map (`labscript-library/capabilities.md`,
`notes/runviewer.txt`), and `git grep` over labscript-utils, lyse, runmanager,
blacs and labscript-devices for each runviewer routine below. Positive control:
the same searches found lyse's four move handlers.

| # | What | Copies | Origin | Proposal |
| --- | --- | --- | --- | --- |
| D1 | `.toml` suffix applied before `save_appconfig` | `__main__.py` `on_save_channel_config` (the `appconfig_path_with_suffix` line and its comment), and `save_appconfig` itself | fork, c23c527 | Delete runviewer's line and comment: with it gone, the file is still named the same (checked by mutation in step 1). About −9 lines |
| D2 | Move the selected rows up, down, to top, to bottom | runviewer `_move_up`, `_move_down`, `_move_top`, `_move_bottom` (about 80 lines, four near-copies); lyse `routines.py` `on_move_*_clicked` (four more, computing a new row order) | upstream, both | (a) runviewer only: one method with a direction argument, about −50 lines. (b) Suite: one function in `labscript_utils.qtwidgets` that returns the new row order for a selection and a direction, used by runviewer and lyse; two repos, about −100 lines in all |
| D3 | Python resampling, `__resample3` and `__resample4` | the C extension `labscript_c_extensions.runviewer.resample`, which is what runs | upstream | Dead (nothing calls them; see the mapping list), so it belongs to step 4, not here |

Considered and not proposed: `RunviewerClient.add_shot` beside `LyseClient.add_shot`
(the ServerInterfaces spec gives each tool its own client); reading
`time_markers` in runviewer and BLACS's progress bar (one line each, different
uses).

Done (Ian approved D1, D2 (b), and D3 for step 4): D1 runviewer ebd803e. D2
labscript-utils 1d25c47 (`qtwidgets.row_order.moved_row_order`, its test, and
docs "Possible improvements"), runviewer b71a338, lyse aafd7e5. runmanager's
axis list (`on_axis_*_clicked`) is a third copy, found by the librarian, not yet
approved.

## Step 2.3: root causes

Each guard the fork added (`git diff master CodeHealth`), traced to its cause.

| # | Guard | Commit | Cause | Proposal |
| --- | --- | --- | --- | --- |
| R1 | Load configuration refuses a file holding `channels` | d7b6087 | Channel configurations and the runviewer state file share the `[runviewer_state]` table, the folder and the `*.toml` filter, so either can be loaded as the other. The test that the channel-config panel does not offer `runviewer.toml` guards the same confusion | Save channel configurations under their own table, `[runviewer_channels]`, and read the old table too when loading one. The refusal can then test for that table, or go. About +3 −3 lines |
| R2 | `tests/fixtures.py` stubs the splash and imports `runviewer.__main__`; `test_client.py` patches the module global `shots_to_process_queue` with `create=True` | 4377c47 and earlier | `RunviewerServer.handle_add_shot` reads `shots_to_process_queue`, a global that exists only under `if __name__ == '__main__'`, so the server cannot be built or tested from anything but the running app (also item 19 of the mapping list) | `RunviewerServer(port, shots_queue)` keeps the queue it is given; `__main__` passes it. `test_client.py` then needs no global, and runmanager's `tests/test_send_to_runviewer.py`, which patches the same global, passes a queue instead. Two repos, about 10 lines |

Not proposed:
- The `try`/`except` around the start-up load (d7b6087): the file is the user's and can be malformed, and labscript-style rule 5 contains such errors at the boundary with `logger.exception`.
- `if not selected_files: return` in `on_add_shot` (4db574e): a cancelled dialog returns None by `file_dialogs`' contract.
- The splash stub itself: every suite app builds its `Splash` at module scope so the splash shows before the slow imports; this is the suite's settled pattern.

Done (Ian approved R1 and R2):
- R1, runviewer 7266381: channel configurations are saved under
  `[runviewer_channels]`, and the old `[runviewer_state]` channels are still
  read. The load refusal stays, now matching either table: saving the layout
  rewrites the whole file, so a channel configuration loaded as the state file
  would still lose its channels on quitting, whichever table holds them.
- R2: runviewer c1df4df (`RunviewerServer(port, shots_queue)`; its test passes a
  queue), runmanager dcf10bb (`test_send_to_runviewer.py` passes a queue, and no
  longer leaves runviewer's module global rebound).

## Row moving in the shared views (Ian's question)

Should moving rows be a method of the shared views
(`labscript_utils.qtwidgets.leftclick`), so that every app's buttons call it?

| List | View | Model | Work after a move |
| --- | --- | --- | --- |
| runviewer channels | plain `QTreeView` (`main.ui`) | `QStandardItemModel` | `update_plot_positions()`; keeps the selection |
| lyse routines | labscript-utils `TreeView` | `UneditableModel(QStandardItemModel)` | `reorder(order)`: sets a sort-index role and sorts the view, and reorders `self.routines`. The sort role is used only by `reorder`, and the view has no header sorting |
| runmanager axes | labscript-utils `TreeView` | `QStandardItemModel` | `update_axes_indentation()`; keeps the selection (four near-copies of runviewer's old methods, about 85 lines) |

All three models are `QStandardItemModel`s, so one take-and-insert move serves
them all, and the extra work after it fits a signal that carries the order.

Proposal: the view method.
- labscript-utils: `TreeView` and `TableView` gain
  `move_selected_rows(direction)`. It reads the selection, takes the new order
  from `moved_row_order`, moves the rows, keeps them selected, and emits
  `rowsMoved(order)`. A later drag and drop would emit the same signal, so the
  apps would not change again. About +25 lines, in a small mixin beside
  `LeftClickMixin`, which is about clicks.
- runviewer: `channel_treeview` becomes the shared `TreeView` (a `.ui` class
  change; it only adds the click signals). The buttons call the method, and
  `rowsMoved` connects to `update_plot_positions`. `_move_channels` goes.
- lyse: the buttons call the method; `rowsMoved` reorders `self.routines`. The
  sort role and `sortByColumn` in `reorder` go.
- runmanager: the four `on_axis_*_clicked` go; `rowsMoved` connects to
  `update_axes_indentation`. About −80 lines.
- `moved_row_order` stays, as the method's helper.
