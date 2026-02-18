# Option 2: Native macOS Menu Bar App — "MeetingCompanion.app"

## Overview

A native macOS application that lives in the menu bar. When activated, it captures audio (microphone and/or system audio via BlackHole), transcribes using on-device models (Apple Speech framework or Whisper.cpp), cleans and processes transcription with a local LLM (MLX), and presents a floating overlay window with live transcript and chat interface.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    macOS Menu Bar                             │
│    ┌──┐                                                      │
│    │🎙│ ← Menu bar icon (click to toggle overlay)            │
│    └──┘                                                      │
└────┬────────────────────────────────────────────────────────┘
     │  ⌘⇧M global hotkey
     ▼
┌─────────────────────────────────────────────────────────────┐
│              Floating Overlay Window (SwiftUI)               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  📝 Live Transcript                          [⏸ ● ⏹]  │  │
│  │  ─────────────────────────────────────────────────── │  │
│  │  [14:01] We need to discuss the Q3 budget...         │  │
│  │  [14:02] I think we should allocate more to R&D...   │  │
│  │  [14:03] Agreed, but let's review last quarter...    │  │
│  │                                                       │  │
│  ├───────────────────────────────────────────────────────┤  │
│  │  💬 Chat                                              │  │
│  │  ─────────────────────────────────────────────────── │  │
│  │  You: Summarize the budget discussion so far          │  │
│  │  AI: The team is considering increasing R&D...        │  │
│  │  ┌─────────────────────────────────────────┐ [Send]  │  │
│  │  │ Ask about the meeting...                 │         │  │
│  │  └─────────────────────────────────────────┘         │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────────┐ ┌─────────────────┐ ┌──────────────────┐
│  Audio Engine    │ │  Transcription   │ │  LLM Engine      │
│  AVAudioEngine   │ │  SFSpeechRecog.  │ │  MLX Framework   │
│  + BlackHole     │ │  or whisper.cpp  │ │  (Mistral/Llama) │
│  (system audio)  │ │  (on-device)     │ │  (Apple Silicon) │
└─────────────────┘ └─────────────────┘ └──────────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │ transcript.md │
                    │ (Documents/) │
                    └──────────────┘
```

## Technology Stack

| Component | Technology | Purpose |
|---|---|---|
| UI Framework | SwiftUI + AppKit | Native macOS overlay, menu bar |
| Audio Capture (mic) | `AVAudioEngine` | Low-latency microphone capture |
| Audio Capture (system) | [BlackHole](https://github.com/ExistentialAudio/BlackHole) | Virtual audio driver for system/app audio |
| Transcription (primary) | `SFSpeechRecognizer` (Speech framework) | Apple's on-device speech recognition, zero latency |
| Transcription (alt) | [whisper.cpp](https://github.com/ggerganov/whisper.cpp) | Higher-accuracy alternative, runs on Apple Silicon |
| LLM Inference | [MLX](https://github.com/ml-explore/mlx) + [mlx-lm](https://github.com/ml-explore/mlx-examples) | Apple Silicon-optimized local LLM inference |
| LLM Models | Mistral-7B-Instruct, Llama-3-8B | Local models quantized for MLX (4-bit) |
| Persistence | `FileManager` + plain text | Markdown transcript files |
| Settings | `UserDefaults` / Settings pane | Audio device, model, hotkey preferences |
| Distribution | Xcode Archive / DMG | Standard macOS app distribution |

## Project Structure

```
MeetingCompanion/
├── MeetingCompanion.xcodeproj
├── README.md
├── MeetingCompanion/
│   ├── App/
│   │   ├── MeetingCompanionApp.swift      # @main, menu bar setup
│   │   ├── AppDelegate.swift              # Global hotkey registration, lifecycle
│   │   └── AppState.swift                 # Observable app state (recording, transcript)
│   ├── Audio/
│   │   ├── AudioCaptureManager.swift      # AVAudioEngine mic capture
│   │   ├── SystemAudioCapture.swift       # BlackHole/aggregate device management
│   │   ├── AudioChunker.swift             # Buffer management, VAD-like chunking
│   │   └── AudioDeviceManager.swift       # Enumerate/select audio devices
│   ├── Transcription/
│   │   ├── TranscriptionProtocol.swift    # Protocol for transcription engines
│   │   ├── AppleSpeechEngine.swift        # SFSpeechRecognizer wrapper
│   │   ├── WhisperEngine.swift            # whisper.cpp wrapper via C bridge
│   │   └── TranscriptCleaner.swift        # LLM-based cleanup pass
│   ├── LLM/
│   │   ├── LLMProtocol.swift             # Protocol for LLM backends
│   │   ├── MLXEngine.swift               # MLX local inference engine
│   │   ├── ModelManager.swift            # Download/manage/select local models
│   │   └── ContextBuilder.swift          # Build prompts with transcript context
│   ├── Chat/
│   │   ├── ChatManager.swift             # Conversation state, history
│   │   └── ChatMessage.swift             # Message model
│   ├── Persistence/
│   │   ├── TranscriptStore.swift         # Read/write transcript files
│   │   └── ExportManager.swift           # Export to .md, .txt, .pdf
│   ├── Views/
│   │   ├── MenuBarView.swift             # Menu bar icon + dropdown
│   │   ├── OverlayWindow.swift           # Floating panel (NSPanel)
│   │   ├── TranscriptView.swift          # Live transcript display
│   │   ├── ChatView.swift                # Chat input + messages
│   │   ├── SettingsView.swift            # Preferences window
│   │   └── StatusIndicator.swift         # Recording indicator, audio levels
│   └── Utilities/
│       ├── HotKeyManager.swift           # Global keyboard shortcut (⌘⇧M)
│       ├── PermissionsManager.swift      # Mic/speech recognition permissions
│       └── Logger.swift                  # Structured logging
├── WhisperBridge/                         # C/Obj-C bridge to whisper.cpp
│   ├── whisper_bridge.h
│   ├── whisper_bridge.m
│   └── module.modulemap
├── MLXBridge/                             # Python/Swift bridge for MLX
│   ├── mlx_runner.py                     # Python script for MLX inference
│   └── MLXProcessBridge.swift            # Swift ↔ Python subprocess comms
└── Tests/
    ├── AudioCaptureTests.swift
    ├── TranscriptionTests.swift
    ├── ChatManagerTests.swift
    └── ContextBuilderTests.swift
```

## Implementation Plan

### Phase 1: App Shell & Menu Bar

- [ ] Create Xcode project (macOS App, SwiftUI lifecycle)
- [ ] Configure as menu bar app (LSUIElement, `MenuBarExtra`)
- [ ] Implement `MeetingCompanionApp.swift` — menu bar icon with dropdown (Start/Stop Recording, Open Overlay, Settings, Quit)
- [ ] Implement `OverlayWindow.swift` — floating `NSPanel` (`.floating` level, non-activating, resizable) with placeholder transcript + chat views
- [ ] Implement `HotKeyManager.swift` — register global hotkey `⌘⇧M` using `CGEvent` tap or `MASShortcut` to toggle overlay
- [ ] Implement `PermissionsManager.swift` — request microphone and speech recognition permissions, handle denials gracefully
- [ ] Implement `AppState.swift` — `@Observable` class holding recording state, transcript data, chat messages

### Phase 2: Audio Capture

- [ ] Implement `AudioCaptureManager.swift` — `AVAudioEngine` setup: install a tap on the input node, convert to 16kHz mono Float32 PCM, buffer into chunks (e.g., 5-second segments with 0.5s overlap)
- [ ] Implement `AudioDeviceManager.swift` — enumerate `AVAudioSession` input devices, allow user selection in settings
- [ ] Implement `SystemAudioCapture.swift` — detect if BlackHole is installed, create aggregate audio device (mic + BlackHole) via `AudioObjectSetPropertyData`, enabling capture of both mic and system audio simultaneously
- [ ] Implement `AudioChunker.swift` — simple energy-based VAD: accumulate audio until silence gap > 1s, then emit segment; avoids cutting mid-sentence
- [ ] Test: record 30s of speech, verify chunks are correctly segmented

### Phase 3: On-Device Transcription

- [ ] Implement `TranscriptionProtocol.swift` — `protocol TranscriptionEngine { func transcribe(audioBuffer:) async -> TranscriptSegment }`
- [ ] Implement `AppleSpeechEngine.swift`:
  - Use `SFSpeechRecognizer` with `SFSpeechAudioBufferRecognitionRequest`
  - Feed audio chunks from capture pipeline
  - Handle real-time partial results for live display
  - Map to `TranscriptSegment` (timestamp, text, confidence)
- [ ] Implement `WhisperEngine.swift`:
  - Integrate whisper.cpp via C bridge (`WhisperBridge/`)
  - Load model from app bundle or downloaded location
  - Process audio segments, return timestamped text
  - Run inference on background thread (DispatchQueue)
- [ ] Config toggle: user selects Apple Speech (faster, lower accuracy) vs Whisper (slower, higher accuracy)
- [ ] Test: feed pre-recorded audio, compare outputs from both engines

### Phase 4: Transcript Cleanup & Persistence

- [ ] Implement `TranscriptCleaner.swift` — takes raw transcript segments, batches them (e.g., every 30s of speech), sends to LLM with cleanup prompt, returns polished text
- [ ] Implement `TranscriptStore.swift`:
  - Auto-create meeting file: `~/Documents/MeetingCompanion/2026-02-18_Meeting.md`
  - Append-only writes with timestamps
  - Store both raw and clean versions (raw in comments or separate file)
  - File locking for concurrent access safety
- [ ] Implement `ExportManager.swift` — export current transcript as `.md`, `.txt`, or `.pdf` (using `NSAttributedString` → PDF)

### Phase 5: Local LLM via MLX

- [ ] Implement `MLXProcessBridge.swift` — spawn Python subprocess running `mlx_runner.py`, communicate via stdin/stdout JSON-RPC protocol
- [ ] Implement `mlx_runner.py`:
  - Load quantized model (e.g., `mlx-community/Mistral-7B-Instruct-v0.3-4bit`)
  - Accept prompt via stdin, stream tokens via stdout
  - Handle context window management
- [ ] Implement `ModelManager.swift`:
  - Download models from Hugging Face on first launch
  - Store in `~/Library/Application Support/MeetingCompanion/Models/`
  - Show download progress in settings
  - Allow model switching
- [ ] Implement `ContextBuilder.swift` — assemble system prompt + transcript context + chat history, manage token budget
- [ ] Alternative: support OpenAI API as cloud fallback (simple `URLSession` HTTP client)

### Phase 6: Chat Interface

- [ ] Implement `ChatManager.swift` — manages conversation history, sends messages to LLM engine, handles streaming responses
- [ ] Implement `ChatView.swift`:
  - Message bubbles (user vs AI) with markdown rendering
  - Text input field with Send button
  - Streaming response display (token-by-token)
  - Scroll to bottom on new messages
- [ ] Implement quick actions: pre-built prompts ("Summarize so far", "List action items", "What was decided about...?")
- [ ] Wire chat to use accumulated transcript as context

### Phase 7: Live Transcript UI

- [ ] Implement `TranscriptView.swift`:
  - Real-time updating text view with timestamps
  - Auto-scroll with "scroll to bottom" button when user scrolls up
  - Highlight currently-being-transcribed segment
  - Search/filter within transcript (`⌘F`)
- [ ] Implement `StatusIndicator.swift`:
  - Recording pulse animation on menu bar icon
  - Audio level meter in overlay
  - Duration counter
  - Model/engine indicator

### Phase 8: Settings & Polish

- [ ] Implement `SettingsView.swift`:
  - Audio input device selection (dropdown)
  - System audio capture toggle (requires BlackHole)
  - Transcription engine selection (Apple Speech / Whisper)
  - Whisper model size selection (tiny/base/small/medium)
  - LLM model selection + download management
  - Global hotkey customization
  - Output directory selection
  - Launch at login toggle
- [ ] Handle edge cases:
  - Mic disconnection → graceful pause + notification
  - Model loading failure → fallback to Apple Speech
  - Long meetings → context window management (summarize older segments)
- [ ] Add notifications: "Recording started", "Transcript saved"
- [ ] App icon and menu bar icon design
- [ ] Code signing and notarization for distribution
- [ ] Write README with installation guide, BlackHole setup instructions, usage

## Key Design Decisions

1. **Menu bar app with floating panel:** Stays out of the way during meetings. The overlay floats above other apps but doesn't steal focus — you can type in Zoom while the transcript scrolls. `NSPanel` with `.nonactivatingPanel` style mask achieves this.

2. **Dual transcription engines:** Apple Speech is instant (streaming partial results) and free, making it great for real-time display. Whisper.cpp is more accurate, better for the final clean transcript. Could even use both: Apple Speech for live display, Whisper for post-processing.

3. **MLX for local LLM:** Apple's MLX framework is specifically designed for Apple Silicon. A 4-bit quantized 7B model runs at ~30 tokens/sec on M1, ~60 tokens/sec on M2/M3. This is fast enough for streaming chat responses. No cloud dependency.

4. **System audio via BlackHole:** This is the key differentiator. By creating an aggregate device (mic + BlackHole), the app captures both the user's voice AND remote participants from Zoom/Teams/Meet. Setup requires a one-time BlackHole install.

5. **Python bridge for MLX:** While MLX has Swift bindings, the Python ecosystem (`mlx-lm`, model loading from Hugging Face) is more mature. A subprocess bridge is the pragmatic choice; it adds ~100ms latency which is acceptable for chat.

## Dependencies & Requirements

- **macOS 14.0+ (Sonoma)** — for `MenuBarExtra`, latest Speech APIs
- **Xcode 15+** — Swift 5.9+, SwiftUI
- **Python 3.11+** — for MLX inference subprocess
- **BlackHole** (optional) — for system audio capture
- **~4GB disk** — for Whisper model (medium) + LLM model (7B-4bit)
- **Apple Silicon** (M1+) — required for MLX, strongly recommended for whisper.cpp performance

## Estimated Complexity

| Phase | Effort |
|---|---|
| Phase 1: App Shell & Menu Bar | Small |
| Phase 2: Audio Capture | Medium |
| Phase 3: Transcription | Medium–Large |
| Phase 4: Cleanup & Persistence | Small–Medium |
| Phase 5: Local LLM (MLX) | Large |
| Phase 6: Chat Interface | Medium |
| Phase 7: Live Transcript UI | Medium |
| Phase 8: Settings & Polish | Medium–Large |
