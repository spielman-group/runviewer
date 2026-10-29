# Known issues

- An NI_DAQmx card on a line whose parser returns no trace logs "Failed to load device" and is not drawn, because its parser needs a clock (`Shot._load_device`, `runviewer/__main__.py`).
