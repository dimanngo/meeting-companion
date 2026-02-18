# Option 1 (TUI) — Technology Stack Analysis

> Report date: 2026-02-18

This report provides a detailed comparison of alternative technologies for each component of the **meeting-tui** solution. For each category, candidates are evaluated and a recommendation is provided.

---

## Table of Contents

1. [UI Framework](#1-ui-framework)
2. [Audio Capture](#2-audio-capture)
3. [Voice Activity Detection (VAD)](#3-voice-activity-detection-vad)
4. [Speech-to-Text / Transcription](#4-speech-to-text--transcription)
5. [Transcript Cleanup LLM](#5-transcript-cleanup-llm)
6. [Chat LLM Backend](#6-chat-llm-backend)
7. [Persistence & Export](#7-persistence--export)
8. [Configuration Management](#8-configuration-management)
9. [Package & Dependency Management](#9-package--dependency-management)
10. [Summary of Recommendations](#10-summary-of-recommendations)

---

## 1. UI Framework

The TUI framework renders the split-pane interface (transcript + chat + status bar) in the terminal.

| Candidate | Version | Description | Pros | Cons |
|---|---|---|---|---|
| **[Textual](https://textual.textualize.io/)** | 3.x | Modern Python TUI framework by Textualize. Built on Rich. CSS-like styling, widget system, async-native. | Rich widget library (DataTable, Input, TextArea, ListView). CSS-based layout and theming. First-class async support (workers, timers). Active development, large community. Built-in dev tools (console, inspector). | Heavier than alternatives (~30MB with dependencies). Opinionated widget model — custom layouts require subclassing. Relatively young API, occasional breaking changes between major versions. |
| **[Rich](https://rich.readthedocs.io/)** | 13.x | Python library for rich terminal output. Tables, markdown, syntax highlighting, progress bars. | Lightweight. Excellent text formatting and markdown rendering. Can be used standalone for simpler UIs (Live display). | Not a TUI framework — no interactive widgets, no input handling, no layout system. Would need to build event loop and input handling manually. |
| **[urwid](https://urwid.org/)** | 2.x | Mature Python TUI library. Widget-based, signal-driven. | Battle-tested (15+ years). Low-level control. Lightweight. | Dated API, callback-heavy. No async support (requires adapter). Poor documentation. Steep learning curve. No modern styling. |
| **[prompt_toolkit](https://python-prompt-toolkit.readthedocs.io/)** | 3.x | Python library for building interactive CLI applications. Powers `ipython`, `pgcli`. | Excellent input handling and autocompletion. Async-ready. Good for chat-style input. | Primarily designed for line-oriented input, not full-screen TUI. Layout system is limited compared to Textual. Complex split-pane layouts are awkward. |
| **[blessed](https://blessed.readthedocs.io/)** | 1.x | Python wrapper around `curses` with a friendlier API. | Simple, Pythonic API. Direct terminal control. Lightweight. | Low-level — no widget system, must build everything manually. No async support. Limited community/maintenance. |

### Recommendation: **Textual**

Textual is the clear winner for this use case. The split-pane layout, auto-scrolling transcript, chat input, and status bar map directly to Textual's widget model. Async workers integrate naturally with the audio pipeline. The CSS-based theming allows easy customization. Rich is used internally by Textual for rendering, so markdown and syntax highlighting come free.

---

## 2. Audio Capture

Captures microphone input and delivers raw PCM audio data to the processing pipeline.

| Candidate | Version | Description | Pros | Cons |
|---|---|---|---|---|
| **[sounddevice](https://python-sounddevice.readthedocs.io/)** | 0.5.x | Python bindings for PortAudio. Provides blocking and callback-based audio I/O. | Simple API. Supports input/output/duplex streams. Callback mode integrates well with async (bridge via queue). Cross-platform (macOS, Linux, Windows). Device enumeration. Numpy integration for audio buffers. | Depends on PortAudio system library (usually bundled). Callback runs in a separate C thread — must be careful with Python GIL. No built-in resampling. |
| **[PyAudio](https://people.csail.mit.edu/hubert/pyaudio/)** | 0.2.x | Another PortAudio binding. Older, more established. | Widely used, many tutorials. Blocking and callback modes. | Maintenance has been sporadic. More verbose API. Installation issues on macOS (portaudio headers). No numpy integration — returns raw bytes. Last significant update was 2023. |
| **[pyaudiowpatch](https://github.com/s0d3s/PyAudioWPatch)** | 0.2.x | Fork of PyAudio with WASAPI loopback support (Windows). | System audio capture on Windows. | Windows-only feature. macOS not relevant. Same API issues as PyAudio. |
| **[miniaudio](https://github.com/irmen/pyminiaudio)** | 1.x | Python bindings for the miniaudio C library. Single-header, no dependencies. | No external dependencies (no PortAudio). Simple API. Built-in format conversion and resampling. Supports playback and capture. | Smaller community. Fewer examples for real-time streaming. Callback API is less flexible than sounddevice. |
| **[av (PyAV)](https://pyav.org/)** | 12.x | Python bindings for FFmpeg. Full multimedia processing. | Extremely powerful. Can capture from any FFmpeg-supported source. Built-in resampling, format conversion. | Massive dependency (FFmpeg). Overkill for simple mic capture. Complex API for real-time streaming. High learning curve. |
| **Native `AVFoundation` via `pyobjc`** | — | Direct macOS API access via Python-ObjC bridge. | Native macOS audio. Could capture system audio (with entitlements). No C library dependency. | macOS-only. Complex API. pyobjc is heavy (~100MB). Not well-documented for audio use cases. Fragile bridge. |

### Recommendation: **sounddevice**

sounddevice provides the best balance of simplicity, reliability, and cross-platform support. The callback-based API is well-suited for feeding an async pipeline via `asyncio.Queue`. Device enumeration is built-in (important for `--device` CLI flag). The numpy integration simplifies audio buffer manipulation. miniaudio is a viable alternative if PortAudio dependency is a concern.

---

## 3. Voice Activity Detection (VAD)

Detects speech vs. silence in the audio stream to produce natural speech segments for transcription (instead of fixed-time chunks).

| Candidate | Version | Description | Pros | Cons |
|---|---|---|---|---|
| **[Silero VAD](https://github.com/snakers4/silero-vad)** | 5.x | Pre-trained ONNX/PyTorch model for voice activity detection. | High accuracy. Very fast (~1ms per frame on CPU). Language-agnostic. Well-maintained, regular updates. Small model size (~2MB). Works with 16kHz audio. Python API via PyTorch or ONNX Runtime. | Requires PyTorch or ONNX Runtime as dependency (adds ~200MB for PyTorch, ~30MB for ONNX). Slight complexity in frame-level to segment-level conversion. |
| **[webrtcvad](https://github.com/wiseman/py-webrtcvad)** | 2.x | Python wrapper around Google WebRTC's VAD module. | Extremely lightweight (C extension, no ML framework). Very fast. Three aggressiveness modes. Battle-tested (used in WebRTC). | Lower accuracy than Silero (rule-based, not ML). Requires specific frame sizes (10/20/30ms) and sample rates (8/16/32/48kHz). Unmaintained since 2020. Python 3.12+ compatibility issues reported. |
| **Energy-based (custom)** | — | Simple amplitude/RMS thresholding with hysteresis. | Zero dependencies. Trivially simple. No model to load. | Poor accuracy in noisy environments. No adaptation to different speakers/volumes. Requires manual threshold tuning. |
| **[pyannote-audio](https://github.com/pyannote/pyannote-audio)** | 3.x | Full speaker diarization and segmentation pipeline. Includes VAD. | State-of-the-art accuracy. Also provides speaker diarization. | Very heavy dependency (PyTorch + transformers + pyannote). Requires Hugging Face token for model access. Overkill for just VAD. Higher latency. ~1GB+ model downloads. |
| **[ONNX Runtime](https://onnxruntime.ai/) + Silero ONNX** | 1.x | Run Silero VAD model via ONNX Runtime instead of PyTorch. | Smaller dependency than full PyTorch (~30MB). Fast inference. Cross-platform. | Slightly more setup than PyTorch path. Must manage ONNX model file separately. |

### Recommendation: **Silero VAD (via ONNX Runtime)**

Silero VAD offers the best accuracy-to-weight ratio. Using the ONNX Runtime backend (instead of full PyTorch) keeps the dependency footprint small (~30MB vs ~200MB+). The model is only ~2MB and runs in ~1ms per frame. This is significantly better than webrtcvad for real-world noisy environments (typing, background noise during meetings). The frame-level predictions can be smoothed into speech segments with a simple state machine (speech start when confidence > 0.5 for N consecutive frames, speech end after M frames of silence).

---

## 4. Speech-to-Text / Transcription

Converts audio segments into text. This is the most critical component for quality.

| Candidate | Version | Type | Description | Pros | Cons |
|---|---|---|---|---|---|
| **[faster-whisper](https://github.com/SYSTRAN/faster-whisper)** | 1.1.x | Local | CTranslate2-based reimplementation of OpenAI Whisper. | 4x faster than original Whisper. Low memory usage. CPU and GPU support (CUDA, CoreML). Multiple model sizes (tiny→large-v3). Word-level timestamps. Language detection. Active maintenance. | Requires CTranslate2 (C++ library). CoreML support is experimental. No native streaming — processes segments batch-style. |
| **[whisper.cpp](https://github.com/ggerganov/whisper.cpp)** (via [pywhispercpp](https://github.com/abdeladim-s/pywhispercpp)) | — | Local | C/C++ port of Whisper. Optimized for CPU, especially Apple Silicon. | Fastest CPU inference (Metal/NEON optimized). Minimal dependencies. Apple Silicon acceleration via Metal. Small binary. | Python bindings are third-party and less mature. API is lower-level. Fewer convenience features than faster-whisper. |
| **[OpenAI Whisper](https://github.com/openai/whisper)** | — | Local | Original Whisper model implementation in PyTorch. | Reference implementation. Full feature set. Well-documented. | Slow inference (no CTranslate2 optimization). Heavy PyTorch dependency. High memory usage. Not recommended for real-time. |
| **[whisper-streaming](https://github.com/ufal/whisper_streaming)** | — | Local | Streaming wrapper around faster-whisper/whisper.cpp for real-time transcription. | True streaming (partial results while speaking). Built on faster-whisper. Local-first approach. | Experimental. Less stable than batch processing. Accuracy can be lower for partial results. Smaller community. |
| **[Whisper API (OpenAI)](https://platform.openai.com/docs/guides/speech-to-text)** | — | Cloud | OpenAI's hosted Whisper service. | Zero local compute. High accuracy. Simple API. | Requires internet. Costs $0.006/min. Latency (~2-5s roundtrip). Privacy concern (audio sent to cloud). Rate limits. |
| **[Deepgram](https://deepgram.com/)** | — | Cloud | Cloud speech-to-text API with real-time streaming. | True real-time streaming WebSocket API. Very low latency (<300ms). Speaker diarization built-in. Punctuation and formatting. | Cloud-only. Costs ~$0.0043/min (pay-as-you-go). Requires internet. Privacy concern. |
| **[AssemblyAI](https://www.assemblyai.com/)** | — | Cloud | Cloud speech-to-text with real-time streaming. | Real-time streaming. Speaker diarization. Sentiment analysis. Good accuracy. | Cloud-only. Costs ~$0.01/min. Requires internet. |
| **Apple `SFSpeechRecognizer`** (via `pyobjc`) | — | Local/Hybrid | macOS native speech recognition. | Zero dependencies on macOS. On-device mode available (macOS 13+). Free. Streaming partial results. | macOS-only. Accuracy lower than Whisper for non-US English. Limited language support. pyobjc bridge is complex. On-device mode has limited vocabulary. |
| **[NVIDIA Parakeet](https://huggingface.co/collections/nvidia/parakeet-702d25c20068e3140bb9f0a0)** (via [NeMo](https://github.com/NVIDIA/NeMo) or [Hugging Face](https://huggingface.co/nvidia)) | 1.1B / 0.6B | Local | NVIDIA's family of ASR models (CTC, RNNT, TDT variants) trained on 64K+ hours of English speech. Released as open-weight models on Hugging Face. | State-of-the-art English accuracy — tops Open ASR Leaderboard (WER ~5-6% on LibriSpeech test-clean). Punctuation and capitalization built-in (TDT variant). Multiple architectures: CTC (fastest), RNNT (streaming-capable), TDT (best accuracy + punctuation). Available on Hugging Face with `nemo_toolkit` or standalone ONNX export. Strong on long-form audio. | English-only (no multilingual support). Requires NVIDIA NeMo toolkit (~heavy dependency, pulls PyTorch + many extras) or manual ONNX export. Primarily optimized for NVIDIA GPUs (CUDA); CPU inference is significantly slower. No native Apple Silicon / Metal acceleration. Models are large (0.6B–1.1B params, ~600MB–2.2GB). Less community tooling and fewer tutorials compared to Whisper ecosystem. No built-in word-level timestamps in all variants. |

### Recommendation: **faster-whisper**

faster-whisper provides the best balance of speed, accuracy, and developer experience for a local-first TUI. The `base` or `small` model offers good real-time performance on modern hardware (~2-3s to transcribe a 10s segment on CPU). For Apple Silicon, the `small` model runs faster than real-time. The library is well-maintained with a clean Python API.

**NVIDIA Parakeet consideration:** Parakeet models (especially `parakeet-tdt-1.1b`) achieve the best English transcription accuracy available in open-weight models as of early 2026, surpassing Whisper large-v3 on most benchmarks. However, for this project Parakeet has significant drawbacks: (1) the NeMo toolkit dependency is heavy and complex, (2) inference is optimized for NVIDIA CUDA GPUs — on a macOS Apple Silicon laptop (no CUDA), performance would be poor compared to faster-whisper which leverages CPU efficiently, and (3) Whisper's ecosystem (tooling, streaming wrappers, community) is far more mature. **If the user later runs this on a Linux machine with an NVIDIA GPU, Parakeet becomes the top accuracy choice.** For macOS, faster-whisper remains the recommendation.

**Model size guidance (faster-whisper / Whisper):**

| Model | Size | Relative Speed | Quality | Use Case |
|---|---|---|---|---|
| `tiny` | 75MB | Fastest (~10x real-time) | Acceptable | Quick testing, low-resource machines |
| `base` | 142MB | Fast (~7x real-time) | Good | Default for real-time use |
| `small` | 466MB | Moderate (~4x real-time) | Very Good | Recommended balance |
| `medium` | 1.5GB | Slow (~2x real-time) | Excellent | When accuracy is priority |
| `large-v3` | 3.1GB | Slowest (~1x real-time) | Best | Post-meeting reprocessing |

**Model size guidance (NVIDIA Parakeet):**

| Model | Params | Size | Architecture | Quality | Notes |
|---|---|---|---|---|---|
| `parakeet-ctc-0.6b` | 0.6B | ~600MB | CTC | Very Good | Fastest inference, no streaming |
| `parakeet-rnnt-0.6b` | 0.6B | ~600MB | RNNT | Very Good | Streaming-capable (partial results) |
| `parakeet-tdt-1.1b` | 1.1B | ~2.2GB | TDT | Best-in-class | Built-in punctuation & capitalization |
| `parakeet-ctc-1.1b` | 1.1B | ~2.2GB | CTC | Excellent | Non-streaming, highest CTC accuracy |

**Consider whisper-streaming** as an add-on for partial results during active speech (improves perceived latency). Can fall back to batch faster-whisper for final results.

---

## 5. Transcript Cleanup LLM

Takes raw transcription (with errors, filler words, grammar issues) and produces clean, readable text.

| Candidate | Type | Description | Pros | Cons |
|---|---|---|---|---|
| **[Ollama](https://ollama.ai/) (local)** | Local | Local LLM runner. Supports Llama, Mistral, Gemma, Phi, etc. | Easy setup (`ollama pull mistral`). HTTP API. Streaming. Runs on CPU and GPU. Model management built-in. Active development. | Requires separate process (Ollama server). ~4-8GB RAM per model. Slower than cloud on CPU-only machines. |
| **[llama.cpp](https://github.com/ggerganov/llama.cpp)** (via [llama-cpp-python](https://github.com/abramson/llama-cpp-python)) | Local | C++ LLM inference engine with Python bindings. | In-process (no server needed). Metal acceleration on macOS. More control over inference parameters. Can be embedded directly. | More complex setup. Must manage model files manually. Less convenient than Ollama for model management. |
| **[MLX](https://github.com/ml-explore/mlx)** (via [mlx-lm](https://github.com/ml-explore/mlx-examples)) | Local | Apple's ML framework optimized for Apple Silicon. | Fastest inference on Apple Silicon. Unified memory advantage. Growing model ecosystem. | Apple Silicon only. Python-only. Smaller community than llama.cpp. Fewer model formats. |
| **[OpenAI API](https://platform.openai.com/) (`gpt-4o-mini`)** | Cloud | OpenAI's hosted LLM API. | Highest quality cleanup. Fast. No local resources. | Requires internet. Costs ~$0.15/1M input tokens. Privacy concern (transcript sent to cloud). Rate limits. |
| **[Anthropic API](https://www.anthropic.com/) (`claude-3.5-haiku`)** | Cloud | Anthropic's hosted LLM API. | High quality. Fast (Haiku). Good at structured tasks. | Requires internet. Costs ~$0.25/1M input tokens. Privacy concern. |
| **Rule-based (regex + NLP)** | Local | Custom pipeline: remove filler words, fix punctuation, sentence segmentation. | Zero dependencies. Instant. No model needed. Deterministic. | Limited quality. Can't fix semantic errors. No context understanding. Brittle rules. |

### Recommendation: **Ollama (primary) + OpenAI API (optional fallback)**

For transcript cleanup, Ollama with a small, fast model like `mistral` or `phi-3` is ideal. Cleanup is a simpler task than general chat — it doesn't need the largest models. A 7B model can effectively remove filler words, fix grammar, and add punctuation.

**Recommended models for cleanup (via Ollama):**

| Model | Size | Speed | Quality for Cleanup |
|---|---|---|---|
| `phi-3:mini` | 2.3GB | Very fast | Good — efficient for simple tasks |
| `mistral` (7B) | 4.1GB | Fast | Very good — strong instruction following |
| `llama3.1:8b` | 4.7GB | Fast | Very good — latest Llama quality |
| `gemma2:9b` | 5.4GB | Moderate | Excellent — strong at text editing |

The same Ollama instance serves both cleanup and chat (Section 6), avoiding duplicate infrastructure.

---

## 6. Chat LLM Backend

Powers the interactive chat where users query the meeting context.

| Candidate | Type | Description | Pros | Cons |
|---|---|---|---|---|
| **[Ollama](https://ollama.ai/)** | Local | Same as above. | Shared with cleanup — single server. Good model variety. Streaming support. Privacy-preserving. | Quality ceiling lower than cloud models. Context window limited (most models: 4K-32K tokens). Long meetings may exceed context. |
| **[OpenAI API](https://platform.openai.com/) (`gpt-4o`, `gpt-4o-mini`)** | Cloud | OpenAI's hosted models. | Highest quality reasoning. Large context windows (128K tokens). Fast. | Cost: $2.50-$10/1M input tokens. Requires internet. Privacy. |
| **[Anthropic API](https://www.anthropic.com/) (`claude-3.5-sonnet`)** | Cloud | Anthropic's Claude models. | Excellent at analysis and summarization. 200K context window. Strong instruction following. | Cost: $3/1M input tokens. Requires internet. Privacy. |
| **[Google Gemini API](https://ai.google.dev/)** | Cloud | Google's Gemini models. | 1M+ context window (Gemini 1.5 Pro). Good for very long meetings. Competitive pricing. | Requires internet. Privacy. Less consistent than OpenAI/Anthropic for some tasks. |
| **[llama-cpp-python](https://github.com/abramson/llama-cpp-python)** with OpenAI-compatible server | Local | llama.cpp with built-in OpenAI-compatible API server. | Drop-in replacement for OpenAI API. In-process or server mode. | Same local model limitations as Ollama. More setup than Ollama. |

### Recommendation: **Ollama (default) + configurable cloud backends**

Use Ollama as the default for privacy and offline capability. Provide configuration to switch to OpenAI or Anthropic for users who want higher quality or larger context windows. The LLM abstraction layer in the code should make backends interchangeable.

**Context window strategy for long meetings:**

| Meeting Length | ~Words | ~Tokens | Strategy |
|---|---|---|---|
| 15 min | ~2,500 | ~3,500 | Full transcript fits in any model |
| 30 min | ~5,000 | ~7,000 | Full transcript fits in 8K+ models |
| 1 hour | ~10,000 | ~14,000 | Fits in 16K+ models; truncate for 8K |
| 2 hours | ~20,000 | ~28,000 | Requires 32K model or rolling summary |
| 4 hours | ~40,000 | ~56,000 | Requires cloud (128K+) or aggressive summarization |

For local models with limited context, implement a **rolling summary strategy**: summarize older transcript sections and keep recent sections verbatim.

---

## 7. Persistence & Export

How transcript and chat data are stored and exported.

| Candidate | Description | Pros | Cons |
|---|---|---|---|
| **Plain Markdown files** | Append to `.md` files in a configured output directory. | Human-readable. Portable. Version-controllable (git). Opens in any editor. Zero dependencies. | No structured queries. No metadata indexing. Concurrent write safety requires file locking. |
| **Markdown + JSON sidecar** | `.md` for human reading, `.json` for structured data (timestamps, confidence, raw/clean pairs). | Best of both worlds. JSON enables programmatic access and future UI features (search, filter). | Two files to manage per meeting. Slight complexity increase. |
| **SQLite** | Local database file. | Structured queries. Full-text search. Concurrent access safe. Single file. | Not human-readable without tooling. Overkill for append-only transcription. Adds dependency. |
| **Plain text files** | Simple `.txt` files. | Simplest possible. | No formatting. No metadata. Less useful than Markdown. |

### Recommendation: **Markdown + JSON sidecar**

Store `{date}_{title}.md` for the clean, human-readable transcript and `{date}_{title}.json` for structured data (timestamps, confidence scores, raw text, segment IDs). The Markdown file is the primary output the user cares about. The JSON file enables future features (search, re-processing, analytics) without complicating the Markdown.

**File structure example:**
```
~/meeting-transcripts/
├── 2026-02-18_standup.md          # Clean transcript
├── 2026-02-18_standup.json        # Structured data
├── 2026-02-18_standup_chat.md     # Chat history (optional)
└── 2026-02-19_planning.md
```

---

## 8. Configuration Management

How the application is configured (audio device, model selection, LLM backend, output directory, etc.).

| Candidate | Description | Pros | Cons |
|---|---|---|---|
| **TOML file (`config.toml`)** | TOML configuration file in `~/.config/meeting-tui/config.toml`. | Python 3.11+ has `tomllib` in stdlib. Human-readable. Supports nested sections. Standard for Python tools (`pyproject.toml`). | Write support requires `tomli-w` (not in stdlib). |
| **`.env` file + environment variables** | `.env` file parsed by `python-dotenv`. | Simple key-value. 12-factor app compatible. Easy to override in CI/scripts. | Flat structure — no nesting. No type validation. Less readable for complex configs. |
| **YAML (`config.yaml`)** | YAML configuration file. | Human-readable. Supports complex nesting. Widely known. | Requires `pyyaml` dependency. YAML parsing pitfalls (e.g., `yes`/`no` as booleans). |
| **CLI arguments only** | All config via `argparse` / `click` flags. | No config file to manage. Self-documenting (`--help`). | Verbose for many options. No persistence — must re-specify every run. |
| **Combined: TOML + CLI overrides + env vars** | TOML for defaults, CLI flags for overrides, env vars for secrets. | Flexible. Persistent defaults with per-run overrides. Secrets stay out of files. | Slightly more implementation effort (merge 3 sources). |

### Recommendation: **TOML + CLI overrides + env vars**

Use `~/.config/meeting-tui/config.toml` for persistent settings, CLI flags (via `click` or `argparse`) for per-run overrides, and environment variables for secrets (API keys). This follows Python ecosystem conventions and provides maximum flexibility.

**Precedence order:** CLI flags > environment variables > config file > defaults.

---

## 9. Package & Dependency Management

How the project is structured, dependencies installed, and distributed.

| Candidate | Description | Pros | Cons |
|---|---|---|---|
| **[uv](https://github.com/astral-sh/uv)** | Fast Python package manager and project manager by Astral (creators of Ruff). | 10-100x faster than pip. Built-in venv management. Lockfile support. Replaces pip, pip-tools, venv, pyenv. `uv run` for scripts. Growing rapidly. | Relatively new (2024). Not yet universal in all CI environments. Some edge cases with complex packages (C extensions). |
| **[pip](https://pip.pypa.io/) + venv** | Standard Python package installer + virtual environments. | Universal. Pre-installed with Python. Every tutorial uses it. Maximum compatibility. | Slow resolution. No lockfile (needs pip-tools). Manual venv management. |
| **[Poetry](https://python-poetry.org/)** | Python dependency management and packaging tool. | Lockfile. Dependency resolution. Publish to PyPI. Nice CLI. | Slower than uv. Opinionated (own `pyproject.toml` format). Can conflict with standard tooling. Heavy. |
| **[PDM](https://pdm-project.org/)** | PEP 582/621 compliant Python package manager. | Standards-compliant. Fast. Lockfile. PEP 621 `pyproject.toml`. | Smaller community than Poetry/uv. Less documentation. |
| **[Hatch](https://hatch.pypa.io/)** | Modern Python project manager. | Standards-compliant. Multi-environment support. Built-in build system. | Less popular for application development (more for libraries). |

### Recommendation: **uv**

uv is the modern choice for 2026. It's dramatically faster than alternatives, handles virtual environments automatically, and supports standard `pyproject.toml`. The project should use `pyproject.toml` with PEP 621 metadata. `uv run` provides a convenient way to run the app without manual venv activation. For users without uv, standard `pip install .` will still work since we use standard `pyproject.toml`.

---

## 10. Summary of Recommendations

| Component | Recommended | Runner-up | Rationale |
|---|---|---|---|
| **UI Framework** | Textual 3.x | — | Only real option for rich async TUI in Python |
| **Audio Capture** | sounddevice 0.5.x | miniaudio | Best API, numpy integration, cross-platform |
| **VAD** | Silero VAD (ONNX Runtime) | webrtcvad | Best accuracy, small footprint with ONNX |
| **Transcription** | faster-whisper 1.1.x | whisper.cpp (pywhispercpp) | Best speed/accuracy/API balance; `small` model recommended |
| **Cleanup LLM** | Ollama (mistral/phi-3) | OpenAI gpt-4o-mini | Local, private, shared with chat backend |
| **Chat LLM** | Ollama (default) + cloud option | Anthropic Claude 3.5 | Offline-first with configurable cloud fallback |
| **Persistence** | Markdown + JSON sidecar | SQLite | Human-readable + structured, zero dependencies |
| **Configuration** | TOML + CLI + env vars | .env only | Flexible, follows Python conventions |
| **Package Management** | uv | pip + venv | Fast, modern, standard-compliant |

### Final Dependency Stack

```
Core:
  textual >= 3.0          # TUI framework
  sounddevice >= 0.5      # Audio capture
  numpy >= 1.26           # Audio buffer manipulation

ML / Transcription:
  faster-whisper >= 1.1   # Speech-to-text (bundles CTranslate2)
  onnxruntime >= 1.17     # Silero VAD inference (lightweight)
  silero-vad >= 5.1       # VAD model + utilities

LLM Integration:
  httpx >= 0.27           # HTTP client for Ollama + cloud APIs
  openai >= 1.50          # OpenAI SDK (optional, for cloud backend)

Utilities:
  rich >= 13.0            # Markdown rendering (bundled with Textual)
  click >= 8.1            # CLI argument parsing
  python-dotenv >= 1.0    # Environment variable loading
```

**Estimated total dependency footprint:** ~100MB (without ML models)
**With models:** +150MB (Whisper `base`) to +1.5GB (Whisper `medium`) + ~4GB (Ollama `mistral` 7B)
