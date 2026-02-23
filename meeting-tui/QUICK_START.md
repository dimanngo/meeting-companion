# Quick Start

## How to Run

```bash
cd meeting-tui
uv run meeting-tui
```

## What You Should See

### ✅ On Startup (Terminal, Before TUI)

Models are pre-loaded before the TUI appears — you'll see progress in the terminal:

```
Loading VAD model...                       ← ~2 seconds
Loading Whisper 'base' model...            ← ~6 seconds (first run downloads ~142 MB)
Models loaded. Starting app...
```

### ✅ TUI Appears
- **Status bar visible** at the bottom (just above keybinding footer)
- Status bar shows: `⏸️  Ready 00:00:00 │ Words: 0 │ Segments: 0 │ Model: <model-name>`
- No audio level meter shown yet (appears only while recording)
- Notification: "Ready to record. Press Ctrl+R to start."

### ✅ When You Press Ctrl+R
- Recording starts **immediately** (models are already loaded)
- Status bar changes to: `🔴 Recording 00:00:01 │ 🎤 ████░░░░ │ Words: 0 │ Segments: 0 │ Model: <model-name>`
- The `🎤 ████░░░░` bar shows the live audio level — it moves when you speak
- No UI freeze, no loading delay

### ⚠️ No-Speech Warnings
- If the app records for **15 seconds** with zero transcript segments, a warning appears:
  - **No audio signal:** "Check microphone permissions and input device" — the mic may be muted or wrong device selected
  - **Audio present but no speech:** "Try speaking louder or adjust VAD threshold" — audio is arriving but VAD doesn't detect speech

### ✅ No Beeps
- Moving mouse over terminal = silent
- All notifications are visual only
- No system bell sounds

## If You See Stale Behavior

If old behavior persists, clear the Python cache:

```bash
cd meeting-tui
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
uv run meeting-tui
```

## Troubleshooting

### Status bar not visible?
- Resize your terminal window to be taller (at least 20 lines)
- Check that you're running with `uv run meeting-tui`, not another Python

### Still hearing beeps?
- Check your terminal emulator settings (some override Python's bell control)
- Verify with: `grep "def bell" src/meeting_tui/app.py` should show the override method

## Configuration

### List audio devices
```bash
uv run meeting-tui --list-devices
```

### Run with specific model
```bash
uv run meeting-tui --model tiny    # Fastest (~39 MB), less accurate
uv run meeting-tui --model base    # Default (~142 MB), good balance
uv run meeting-tui --model small   # Better accuracy (~466 MB), slower
```

### Run with specific device
```bash
uv run meeting-tui --device 2      # Device index from --list-devices
```

## Architecture Notes

### Model Loading
Models (Silero VAD + faster-whisper) are loaded **synchronously before the Textual event loop starts**.
This avoids the Python 3.13+ `fds_to_keep` race condition in CTranslate2 that occurs when
model loading runs in any thread inside an asyncio event loop (`asyncio.to_thread` or `run_in_executor`).

The pre-loaded models are passed to `MeetingApp` via constructor, so pressing Ctrl+R starts
recording instantly without any model-loading delay or UI freeze.

## Success Indicators

You'll know everything works when:
- ✅ Models load in the terminal before the TUI appears (~8 seconds)
- ✅ TUI appears with status bar immediately visible
- ✅ Ctrl+R starts recording instantly — no freeze or delay
- ✅ Audio level meter (`🎤 ████░░░░`) moves when you speak
- ✅ No beeping sounds when moving mouse
- ✅ Status shows live timer and word count
- ✅ No "⚠️ No speech" warning after 15 seconds of talking
