# Meeting Companion — Options Comparison

## Option Summary

| | **Option 1: TUI** | **Option 2: Native macOS** | **Option 3: Web + Services** |
|---|---|---|---|
| **Codename** | `meeting-tui` | `MeetingCompanion.app` | `meeting-hub` |
| **Interface** | Terminal split-pane (Textual) | Menu bar + floating overlay | Browser tab (React) |
| **Language** | Python | Swift + Python (MLX bridge) | Python + TypeScript |
| **Architecture** | Single process | Single native app | 3 microservices + frontend |

---

## Feature Comparison

| Feature | **TUI** | **Native macOS** | **Web + Services** |
|---|---|---|---|
| Live transcript | ✅ | ✅ | ✅ |
| Chat with context | ✅ | ✅ | ✅ |
| Mic audio capture | ✅ | ✅ | ✅ |
| System audio capture (Zoom/Teams) | ❌ | ✅ (via BlackHole) | ❌ |
| Fully offline capable | ✅ (Ollama + faster-whisper) | ✅ (MLX + Whisper.cpp/Apple Speech) | ⚠️ (with Ollama; cloud optional) |
| Transcript export (Markdown) | ✅ | ✅ | ✅ |
| Transcript search | ❌ basic only | ✅ (⌘F) | ✅ (rich search) |
| Speaker diarization | ❌ (manual labels) | ❌ (could add) | ⚠️ (extensible) |
| Markdown rendering in chat | ⚠️ (Rich library) | ✅ (native markdown) | ✅ (react-markdown) |
| Streaming chat responses | ✅ | ✅ | ✅ |
| Global hotkey | ❌ (terminal only) | ✅ (⌘⇧M) | ❌ |
| Works alongside other apps | ⚠️ (terminal must be visible) | ✅ (floating overlay) | ⚠️ (browser tab) |
| Multi-user / remote access | ❌ | ❌ | ✅ |

---

## Technical Comparison

| Aspect | **TUI** | **Native macOS** | **Web + Services** |
|---|---|---|---|
| **Setup complexity** | Low — `pip install` | High — Xcode, Python env, optional BlackHole | Medium — Docker or `make dev` |
| **Development effort** | Small–Medium | Large | Medium–Large |
| **Maintenance burden** | Low (single codebase) | Medium (Swift + Python) | Medium (multiple services) |
| **Deployment** | `pip install meeting-tui` | DMG / App Store | `docker-compose up` |
| **Resource usage (RAM)** | ~500MB (model dependent) | ~1–2GB (models on-device) | ~1–2GB (multiple processes) |
| **Resource usage (CPU)** | Moderate (whisper inference) | Low (Apple Silicon optimized) | Moderate (whisper + gateway) |
| **Extensibility** | Medium — add to single app | Low — native app changes harder | High — swap/add services |
| **Testability** | Good (Python unit tests) | Medium (XCTest + UI tests) | Good (each service isolated) |
| **Platform lock-in** | None (cross-platform) | macOS only | Minimal (audio capture needs host) |

---

## LLM Backend Comparison

| Aspect | **TUI** | **Native macOS** | **Web + Services** |
|---|---|---|---|
| **Primary LLM** | Ollama (local) | MLX (Apple Silicon) | Ollama (local) |
| **Cloud fallback** | OpenAI API | OpenAI API | OpenAI / Anthropic |
| **Inference speed** | ~20-30 tok/s (Ollama) | ~30-60 tok/s (MLX, Apple Silicon) | ~20-30 tok/s (Ollama) |
| **Model flexibility** | Any Ollama model | MLX-compatible models | Any Ollama/cloud model |
| **Context window** | Depends on model | Depends on model | Depends on model |

---

## Transcription Comparison

| Aspect | **TUI** | **Native macOS** | **Web + Services** |
|---|---|---|---|
| **Engine** | faster-whisper | Apple Speech or whisper.cpp | faster-whisper |
| **Latency** | ~2-5s per segment | <1s (Apple Speech, streaming) | ~2-5s per segment |
| **Accuracy** | High (Whisper) | Medium (Apple) / High (Whisper) | High (Whisper) |
| **Cost** | Free (local) | Free (on-device) | Free (local) |
| **Languages** | English (configurable) | English (configurable) | English (configurable) |

---

## UX / Workflow Fit

### Option 1: TUI — Best for terminal-centric workflow

- ✅ Never leave the terminal
- ✅ Integrates with tmux/screen sessions
- ✅ Keyboard-driven, minimal mouse usage
- ✅ Low resource overhead
- ❌ Must keep terminal window visible/accessible
- ❌ Limited formatting capabilities
- ❌ Can't capture system audio

### Option 2: Native macOS — Best for seamless desktop integration

- ✅ Always accessible via menu bar / global hotkey
- ✅ Floats above other apps, doesn't steal focus
- ✅ Captures both mic AND system audio (remote participants)
- ✅ Best performance on Apple Silicon
- ✅ Most polished user experience
- ❌ macOS only, no portability
- ❌ Highest development effort (Swift + Python)
- ❌ Harder to iterate/extend

### Option 3: Web + Services — Best for flexibility and extensibility

- ✅ Richest UI capabilities (browser)
- ✅ Easy to add features (new service, new UI component)
- ✅ Swappable backends (change LLM, change transcription engine)
- ✅ Could serve multiple users or be accessed remotely
- ✅ Each component is independently testable and deployable
- ❌ Most moving parts to manage
- ❌ Requires browser tab (context switching)
- ❌ Docker + audio device access is tricky on macOS

---

## Decision Matrix

Rate each criterion 1–5 (5 = best):

| Criterion | Weight | **TUI** | **Native macOS** | **Web + Services** |
|---|---|---|---|---|
| Ease of initial development | 20% | ⭐⭐⭐⭐⭐ (5) | ⭐⭐ (2) | ⭐⭐⭐ (3) |
| User experience quality | 20% | ⭐⭐⭐ (3) | ⭐⭐⭐⭐⭐ (5) | ⭐⭐⭐⭐ (4) |
| Power-user workflow fit | 15% | ⭐⭐⭐⭐⭐ (5) | ⭐⭐⭐⭐ (4) | ⭐⭐⭐ (3) |
| Offline capability | 10% | ⭐⭐⭐⭐ (4) | ⭐⭐⭐⭐⭐ (5) | ⭐⭐⭐ (3) |
| System audio capture | 10% | ⭐ (1) | ⭐⭐⭐⭐⭐ (5) | ⭐ (1) |
| Extensibility | 10% | ⭐⭐⭐ (3) | ⭐⭐ (2) | ⭐⭐⭐⭐⭐ (5) |
| Maintenance effort | 10% | ⭐⭐⭐⭐⭐ (5) | ⭐⭐⭐ (3) | ⭐⭐⭐ (3) |
| Portability | 5% | ⭐⭐⭐⭐⭐ (5) | ⭐ (1) | ⭐⭐⭐⭐ (4) |
| **Weighted Score** | | **4.00** | **3.70** | **3.25** |

---

## Recommendation

### 🏆 Start with Option 1 (TUI) → Evolve to Option 3 (Web) if needed

**Rationale:**

1. **Option 1 (TUI)** has the fastest path to a working prototype. A power user comfortable with the terminal gets maximum value with minimum development effort. The entire application is a single Python package — easy to develop, test, and iterate.

2. **If richer UI or extensibility is needed later**, the core components (audio capture, transcription, LLM integration) can be extracted into services and reused in **Option 3 (Web)**. The Python code is directly portable.

3. **Option 2 (Native macOS)** is the most polished end-state but has the highest development cost and is locked to one platform. Consider this only if system audio capture (hearing remote meeting participants) is a hard requirement — this is the only option that supports it natively.

### Hybrid Path

A pragmatic approach: build Option 1, then wrap the same Python backend with a FastAPI server (Option 3's gateway) while keeping the TUI as an alternative frontend. This gives both terminal and browser access with shared backend code.
