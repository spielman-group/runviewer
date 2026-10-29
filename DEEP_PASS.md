# runviewer deep pass

The code-health campaign's pass over runviewer (`issues/code_health_campaign.md`
in the meta repo), on `CodeHealth`. It records the decisions that still hold and
the work deferred, and is deleted when the pass is merged.

## Tests

Each test protects one behaviour a user relies on, and fails when it breaks:

- `tests/test_client.py`: a shot sent through `RunviewerClient.add_shot`
  reaches runviewer's queue as its local path.
- `tests/test_save_channel_config_dialog.py`: *Save channel config* offers the
  save panel a `.toml` name in the default config folder, never the runviewer
  state file, and writes each channel with its checked state.

No test covers `LabscriptGuiApplication.offer_to_save_changes`, which
labscript-utils holds.

## Loading a shot's devices

`Shot._load_device` walks the connection table once and calls each device's
parser once. It carries down the traces the parsers above have returned, and
gives each device the one returned under its parent's name, or None, drawn as
if triggered at 0. A parser that raises stops only its own subtree. It asserts
that a parser returns a dict, and never its own name.

- It needs labscript-utils' default parser, which draws nothing for a clock
  line, trigger, output or parser-less device, and warns only for a device
  module with no parser.
- No connection-table walk exists elsewhere in the suite to reuse (librarian),
  so the recursion stays in runviewer.

## Upstream

`master` is upstream's `ba91d3e`. runviewer has its changes, ported by hand in
upstream's form, each commit naming its upstream commit: everything but
c25afc2 and e8d1817.

- c25afc2 (`labscript_utils.excepthook.install()`): labscript-utils' excepthook
  installs at import and has no `install()`; it follows labscript-utils.
- e8d1817 (`setup_application`): waits for labscript-utils.
- The port-in-use exit (039a3ba) catches the error labscript-utils' `ZMQServer`
  raises, and the exit crash workaround (682a47b) is labscript-utils'
  `exec_qapplication`.

## Decisions that hold

- Legacy INI app configs: runviewer keeps its `*.ini` filters and the "LEGACY
  INI COMPATIBILITY. DEPRECATED CODE, WILL BE REMOVED." markers until
  labscript-utils drops INI support suite-wide; the markers are the suite's way
  of finding that code.

## Deferred

- The `shots_to_process_queue` global, which `RunViewer._process_shots` reads,
  exists only under `if __name__ == '__main__'`. Passing it in, as
  `RunviewerServer` takes its queue, is a few lines.
- Qt enums are qualified but not scoped (`QtCore.Qt.Checked`). Scoping them all
  touches most of `__main__.py`.
- The tests use `os.path`, until those files change for another reason.
