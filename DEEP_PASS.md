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

`Shot._load_device` has upstream's form: it loads a device's children only
through the lines its parser returns, each clocked by its line's trace. A
device with no runviewer parser raises in labscript-utils, and runviewer logs
"Failed to load device" and loads nothing below it, as upstream does.

## Upstream

`master` is upstream's `ba91d3e`. runviewer has all its changes, ported by
hand in upstream's form, each commit naming its upstream commit.

- The port-in-use exit (039a3ba) catches the error labscript-utils' `ZMQServer`
  raises, and the exit crash workaround (682a47b) is labscript-utils'
  `exec_qapplication`.

## Compatibility

The campaign and the upstream stage added no alias, shim, old name or
deprecation path. Channel configurations are read only from
`[runviewer_channels]`; the old `[runviewer_state]` table is not (Ian, C-RV2).
The `*.ini` filter in Load channel config, with the INI conversion in
labscript-utils' `load_appconfig`, is kept on Ian's word (C-RV1), so channel
configurations saved by upstream runviewer, which writes INI, still load.

## Deferred

- The `shots_to_process_queue` global, which `RunViewer._process_shots` reads,
  exists only under `if __name__ == '__main__'`. Passing it in, as
  `RunviewerServer` takes its queue, is a few lines.
- Qt enums are qualified but not scoped (`QtCore.Qt.Checked`). Scoping them all
  touches most of `__main__.py`.
- The tests use `os.path`, until those files change for another reason.
