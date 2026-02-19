# Quick Start After Bug Fixes

## What Was Wrong Before

1. **Python cache issue** - Old bytecode was being used
2. **Virtual environment cache** - uv's .venv had stale package installation

## How to Run Now

### Step 1: Environment was already refreshed
✅ Deleted `.venv` directory  
✅ Reinstalled all packages with `uv sync --extra dev`  
✅ Package is now using the fixed source code

### Step 2: Run the application

```bash
cd /Users/dima/_git/AI/meeting-companion/meeting-tui
uv run meeting-tui
```

## What You Should See Now

### ✅ On Startup
- **Status bar visible** at the bottom (just above keybinding footer)
- Status bar shows: `⏸️  Ready 00:00:00 │ Words: 0 │ Segments: 0 │ Model: <model-name>`
- Notification: "Ready to record. Press Ctrl+R to start."

### ✅ When You Press Ctrl+R
1. Immediate notification: "Loading models, please wait..." (5 seconds)
2. Status bar changes to: `⏳ Loading VAD model (first run may download)...`
3. Then: `⏳ Loading Whisper 'base' model...`
4. Success notification: "Models loaded successfully!" (2 seconds)
5. Status bar changes to: `🔴 Recording 00:00:01 │ Words: 0 │ Segments: 0 │ Model: <model-name>`

### ✅ No More Beeps
- Moving mouse over terminal = silent
- All notifications are visual only
- No system bell sounds

### ✅ No More Crashes
- No "fds_to_keep" error
- Models load successfully
- Recording works properly

## If You Still See Old Behavior

If the old behavior persists, the Python interpreter might be caching imports. Try:

```bash
# Kill the app completely (Ctrl+C)
cd /Users/dima/_git/AI/meeting-companion/meeting-tui

# Clear Python cache again
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null

# Run fresh
uv run meeting-tui
```

## Troubleshooting

### Status bar still not visible?
- Resize your terminal window to be taller (at least 20 lines)
- Check that you're running with `uv run meeting-tui`, not another Python

### Still getting fds_to_keep error?
- Check that you're running the code from the fixed source
- Verify with: `grep "asyncio.to_thread" src/meeting_tui/app.py` should return nothing
- Should see: `self._vad._load_model()` and `self._engine._load_model()` (direct calls)

### Still hearing beeps?
- Check your terminal emulator settings (some override Python's bell control)
- Verify with: `grep "def bell" src/meeting_tui/app.py` should show the override method

## Configuration

You can configure audio device, model, etc. via:

### List audio devices
```bash
uv run meeting-tui --list-devices
```

### Run with specific model
```bash
uv run meeting-tui --model tiny    # Fastest, less accurate
uv run meeting-tui --model base    # Default balance
uv run meeting-tui --model small   # Better accuracy, slower
```

### Run with specific device
```bash
uv run meeting-tui --device 2      # Device index from --list-devices
```

## What the Fixes Changed

### 1. Status Bar CSS
- **Before:** `dock: bottom` in StatusBar component conflicted with Footer
- **After:** `dock: bottom` moved to main app CSS, proper Z-order

### 2. Model Loading
- **Before:** Used `asyncio.to_thread()` which caused subprocess conflicts
- **After:** Direct synchronous calls with `await asyncio.sleep(0)` to yield control

### 3. Bell Sounds
- **Before:** Default Textual bell behavior triggered on events
- **After:** Overridden `bell()` method + environment variable + disabled command palette

### 4. User Feedback
- **Before:** No feedback when starting, user confused
- **After:** Clear notifications at every step with appropriate timeouts

## Success Indicators

You'll know everything works when:
- ✅ You see the status bar immediately on startup
- ✅ Ctrl+R shows loading progress
- ✅ No error messages about "fds_to_keep"
- ✅ No beeping sounds when moving mouse
- ✅ Recording starts after models load
- ✅ Status shows live timer and word count

Enjoy your fixed meeting-tui! 🎉
