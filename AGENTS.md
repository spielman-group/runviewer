# Working in runviewer

`runviewer/__main__.py` builds the `Splash` and `QApplication` at module scope,
so importing it anywhere but a real start puts a banner on the screen that is
never hidden. No leaf module holds `RunViewer`'s methods, so a test that needs
one takes it from `tests/fixtures.py`, which stubs the splash first.

Workspace conventions are in `../AGENTS.md`.
