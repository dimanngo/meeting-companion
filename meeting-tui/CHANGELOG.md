# Changelog

## [0.1.1](https://github.com/dimanngo/meeting-companion/compare/meeting-tui-v0.1.0...meeting-tui-v0.1.1) (2026-03-01)


### Features

* include timestamp in transcript filenames ([0c6d4d0](https://github.com/dimanngo/meeting-companion/commit/0c6d4d087793b6da67d9d5e1b3edf0aea7f29a8a))
* Refactor JSON persistence to append-only JSONL ([a5e01cb](https://github.com/dimanngo/meeting-companion/commit/a5e01cb11f46ca6cc1966c82a2c398344db23147))


### Bug Fixes

* Added a default no-op close() method to LLMBackend in base.py and simplified the caller in app.py to call it directly without hasattr duck-typing. ([f9d4773](https://github.com/dimanngo/meeting-companion/commit/f9d4773fd466040a5000cd4dd9372e07732ce741))
* Fix transcription confidence bug ([9af9a43](https://github.com/dimanngo/meeting-companion/commit/9af9a43f72f3d09598446abf6cc26bd519d66c2c))
* Guard signal handler for cross-platform safety ([35c95b8](https://github.com/dimanngo/meeting-companion/commit/35c95b8054d11922991a8bb8cb6689a94d70bf71))
* pre-load ML models before Textual event loop to avoid fds_to_keep bug ([a7dcc4f](https://github.com/dimanngo/meeting-companion/commit/a7dcc4f0b3956009984b04e4b9214c0caf3f3478))
* resolve mypy type errors across source files ([d36b0ab](https://github.com/dimanngo/meeting-companion/commit/d36b0abd4227bebf037b3b23960c1d0b2ddcacd8))
* rewrite ChatPane streaming to avoid RichLog.write(end=) error ([555ac02](https://github.com/dimanngo/meeting-companion/commit/555ac02ae0a0b844745c4b76dd30029b36c13fb9))
* Silero VAD frame size mismatch causing silent transcription failure ([a86e156](https://github.com/dimanngo/meeting-companion/commit/a86e1565741d93758a5851eb88696f656f195f68))
* status bar visibility, model loading fd race, and bell noise ([0a97541](https://github.com/dimanngo/meeting-companion/commit/0a9754109306c614c16c14762d317c71d0e79f89))
* use correct avg_logprob attribute for faster-whisper &gt;= 1.1 ([b01c864](https://github.com/dimanngo/meeting-companion/commit/b01c8649390ae47634af35f0607e35a210bbcc89))


### Documentation

* add detailed technical design specification ([b943050](https://github.com/dimanngo/meeting-companion/commit/b9430509424ea36d6b86be7f753507da15e14283))
* add review reports (performance. codebase structure, critical issues) ([e9d18ab](https://github.com/dimanngo/meeting-companion/commit/e9d18ab937b643c2a26eeb36bdd53f35c1b2b1d5))
* implementaion plan based on review reports ([0cda2ec](https://github.com/dimanngo/meeting-companion/commit/0cda2ecfdc4b9f09a3186fe3cf3b314e82c6d394))
* remove 'uv run' prefix for user-facing commands ([474cab6](https://github.com/dimanngo/meeting-companion/commit/474cab608ea5167edcb7c4c881fe09467d44856b))
* use selected ASCII logo across all READMEs ([9f933bc](https://github.com/dimanngo/meeting-companion/commit/9f933bc2c2966c73434b7c912c23c6ba9cdf5e6c))
