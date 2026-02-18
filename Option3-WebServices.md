# Option 3: Modular Services + Web UI — "meeting-hub"

## Overview

A modular architecture composed of three independent services (audio capture, transcription, LLM chat) communicating via WebSockets, with a React-based web UI opened in the browser. Each service is independently deployable and replaceable. The system starts with a single `docker-compose up` or a process manager script.

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        Browser (React UI)                         │
│  ┌────────────────────────────┐  ┌─────────────────────────────┐ │
│  │  📝 Live Transcript         │  │  💬 Chat                    │ │
│  │  ────────────────────────  │  │  ─────────────────────────  │ │
│  │  [14:01] We need to...     │  │  You: What action items?    │ │
│  │  [14:02] I think we...     │  │                             │ │
│  │  [14:03] Agreed, but...    │  │  AI: Based on discussion:   │ │
│  │                             │  │  1. Review Q3 budget...     │ │
│  │  🔍 Search transcript...   │  │  2. Schedule follow-up...   │ │
│  ├────────────────────────────┤  │                             │ │
│  │  ⏺ Recording 00:23:45     │  │  ┌──────────────┐ [Send]   │ │
│  │  Export: [MD] [TXT] [JSON] │  │  │ Ask...        │          │ │
│  └────────────────────────────┘  └─────────────────────────────┘ │
└────────┬────────────────────────────────────┬────────────────────┘
         │ WebSocket                           │ REST + WebSocket
         ▼                                     ▼
┌──────────────────┐  WebSocket  ┌──────────────────────────────┐
│  Transcription    │◄───────────│  API Gateway (FastAPI)        │
│  Service          │───────────►│  - /ws/transcript (push)      │
│  ──────────────  │  events     │  - /ws/chat (bidirectional)   │
│  faster-whisper   │            │  - /api/export                │
│  + cleaner LLM    │            │  - /api/settings              │
└────────┬─────────┘            └──────────────┬───────────────┘
         │ audio stream                         │
         │                                      │ prompt + context
┌────────┴─────────┐            ┌───────────────┴──────────────┐
│  Audio Capture    │            │  LLM Chat Service             │
│  Service          │            │  ──────────────────          │
│  ──────────────  │            │  Ollama / OpenAI / Anthropic  │
│  sounddevice      │            │  Context management           │
│  → WebSocket      │            │  Streaming responses          │
│  audio stream     │            └──────────────────────────────┘
└──────────────────┘
         │
         ▼
┌──────────────────┐
│  File Storage     │
│  transcripts/     │
│    2026-02-18.md  │
│    2026-02-18.json│
└──────────────────┘
```

## Technology Stack

| Component | Technology | Purpose |
|---|---|---|
| **Audio Capture Service** | Python + `sounddevice` + WebSocket | Mic capture, stream audio chunks |
| **Transcription Service** | Python + `faster-whisper` + `silero-vad` | Speech-to-text, VAD segmentation |
| **API Gateway** | Python + [FastAPI](https://fastapi.tiangolo.com/) | REST + WebSocket hub, serves frontend |
| **LLM Chat Service** | Python + `httpx` | Proxy to Ollama/OpenAI/Anthropic |
| **Frontend** | [React](https://react.dev/) + [Next.js](https://nextjs.org/) or Vite | Web-based UI |
| **Real-time Comms** | WebSockets (native) | Streaming transcript + chat |
| **LLM (local)** | [Ollama](https://ollama.ai/) | Local LLM inference |
| **LLM (cloud)** | OpenAI API / Anthropic API | Cloud LLM fallback |
| **Persistence** | Filesystem (Markdown + JSON) | Transcript storage |
| **Orchestration** | Docker Compose / `just` / `make` | Start all services |
| **Config** | `.env` + YAML | Service configuration |

## Project Structure

```
meeting-hub/
├── docker-compose.yml
├── Makefile                           # `make start`, `make stop`, etc.
├── .env.example
├── README.md
│
├── services/
│   ├── audio-capture/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── capture.py                 # Main: mic → WebSocket audio stream
│   │   ├── device_manager.py          # List/select audio devices
│   │   └── config.py                  # Audio settings (sample rate, chunk size)
│   │
│   ├── transcription/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── transcriber.py             # Main: receive audio → faster-whisper → emit events
│   │   ├── vad.py                     # Silero VAD chunking
│   │   ├── cleaner.py                 # LLM-based transcript cleanup
│   │   └── config.py                  # Model selection, language settings
│   │
│   └── api-gateway/
│       ├── Dockerfile
│       ├── requirements.txt
│       ├── main.py                    # FastAPI app
│       ├── routers/
│       │   ├── transcript_ws.py       # WebSocket: stream transcript to frontend
│       │   ├── chat_ws.py             # WebSocket: bidirectional chat
│       │   ├── export.py              # REST: export transcript as md/txt/json
│       │   └── settings.py            # REST: get/update settings
│       ├── services/
│       │   ├── llm_client.py          # Ollama/OpenAI/Anthropic client
│       │   ├── context_manager.py     # Build LLM prompts with transcript
│       │   ├── transcript_store.py    # Persist/retrieve transcripts
│       │   └── chat_history.py        # In-memory chat history
│       └── config.py                  # Gateway config (ports, LLM backend)
│
├── frontend/
│   ├── package.json
│   ├── vite.config.ts                 # or next.config.js
│   ├── src/
│   │   ├── App.tsx                    # Root component, layout
│   │   ├── main.tsx                   # Entry point
│   │   ├── components/
│   │   │   ├── TranscriptPanel.tsx    # Live transcript display
│   │   │   ├── ChatPanel.tsx          # Chat interface
│   │   │   ├── ControlBar.tsx         # Start/stop, export, settings
│   │   │   ├── SearchBar.tsx          # Search within transcript
│   │   │   ├── MessageBubble.tsx      # Chat message component
│   │   │   └── SettingsModal.tsx      # Settings dialog
│   │   ├── hooks/
│   │   │   ├── useTranscriptSocket.ts # WebSocket hook for transcript
│   │   │   ├── useChatSocket.ts       # WebSocket hook for chat
│   │   │   └── useRecording.ts        # Recording state management
│   │   ├── stores/
│   │   │   ├── transcriptStore.ts     # Zustand store for transcript state
│   │   │   └── chatStore.ts           # Zustand store for chat state
│   │   └── styles/
│   │       └── globals.css            # Tailwind CSS
│   └── public/
│       └── favicon.ico
│
├── shared/
│   ├── protocol.py                    # WebSocket message schemas (Python)
│   └── protocol.ts                    # WebSocket message types (TypeScript)
│
└── tests/
    ├── test_audio_capture.py
    ├── test_transcription.py
    ├── test_api_gateway.py
    ├── test_llm_client.py
    └── frontend/
        ├── TranscriptPanel.test.tsx
        └── ChatPanel.test.tsx
```

## WebSocket Protocol

### Audio Stream (Audio Capture → Transcription)

```json
{
  "type": "audio_chunk",
  "timestamp": "2026-02-18T14:01:23.456Z",
  "sample_rate": 16000,
  "channels": 1,
  "format": "float32",
  "data": "<base64-encoded PCM>"
}
```

### Transcript Events (Transcription → API Gateway → Frontend)

```json
{
  "type": "transcript_segment",
  "id": "seg_001",
  "timestamp": "2026-02-18T14:01:23Z",
  "raw_text": "uh we need to um discuss the Q3 budget",
  "clean_text": "We need to discuss the Q3 budget.",
  "confidence": 0.94,
  "is_final": true
}
```

```json
{
  "type": "transcript_partial",
  "text": "We need to discuss the Q3...",
  "is_final": false
}
```

### Chat Messages (Frontend ↔ API Gateway)

```json
// Client → Server
{
  "type": "chat_message",
  "content": "What action items were mentioned?"
}

// Server → Client (streamed token by token)
{
  "type": "chat_token",
  "content": "Based",
  "is_final": false
}

{
  "type": "chat_token",
  "content": "",
  "is_final": true
}
```

## Implementation Plan

### Phase 1: Project Scaffolding & Shared Protocol

- [ ] Initialize monorepo structure with `services/`, `frontend/`, `shared/`
- [ ] Define WebSocket message protocol in `shared/protocol.py` (Pydantic models) and `shared/protocol.ts` (TypeScript types)
- [ ] Create `docker-compose.yml` with service definitions (audio-capture, transcription, api-gateway, frontend)
- [ ] Create `Makefile` with targets: `start`, `stop`, `logs`, `dev` (for local development without Docker)
- [ ] Create `.env.example` with all configurable settings
- [ ] Set up each service with its `requirements.txt` and minimal `Dockerfile`

### Phase 2: Audio Capture Service

- [ ] Implement `capture.py`:
  - Initialize `sounddevice` input stream (16kHz, mono, float32)
  - On audio callback: buffer chunks (configurable size, default 2s)
  - Run WebSocket server on `ws://localhost:8001/audio`
  - Stream audio chunks as base64-encoded messages to connected clients
- [ ] Implement `device_manager.py` — REST endpoint to list available input devices, select device
- [ ] Add health check endpoint (`/health`)
- [ ] Test: start service, connect with a simple WebSocket client, verify audio data flows

### Phase 3: Transcription Service

- [ ] Implement `vad.py` — Silero VAD wrapper: receive audio chunks, detect speech boundaries, emit speech segments
- [ ] Implement `transcriber.py`:
  - Connect to Audio Capture service WebSocket as a client
  - Receive audio chunks → feed to VAD → on speech segment: run faster-whisper
  - Load configurable model size (tiny/base/small/medium)
  - Run WebSocket server on `ws://localhost:8002/transcript`
  - Emit `transcript_segment` events (raw text, timestamps) to connected clients
  - Also emit `transcript_partial` for real-time partial results
- [ ] Implement `cleaner.py`:
  - Batch raw transcript segments (e.g., every 30s of speech)
  - Send to LLM (via API Gateway's LLM service or direct Ollama call) for cleanup
  - Update segments with clean text, re-emit as updated events
- [ ] Add health check endpoint
- [ ] Test: pipe pre-recorded audio through capture → transcription, verify text output

### Phase 4: API Gateway

- [ ] Implement `main.py` — FastAPI app with CORS, static file serving for frontend
- [ ] Implement `routers/transcript_ws.py`:
  - Connect to Transcription Service as a WebSocket client
  - Maintain list of frontend WebSocket connections
  - Fan out transcript events to all connected frontends
  - Buffer transcript in memory for new connections (send history on connect)
- [ ] Implement `routers/chat_ws.py`:
  - Accept WebSocket connections from frontend
  - On message: build prompt (system prompt + transcript context + chat history), send to LLM client
  - Stream LLM response tokens back via WebSocket
- [ ] Implement `services/llm_client.py`:
  - Abstract interface for LLM backends
  - Ollama backend: HTTP client to `http://localhost:11434/api/generate` (streaming)
  - OpenAI backend: `openai` SDK with streaming
  - Anthropic backend: `anthropic` SDK with streaming
  - Config-driven backend selection
- [ ] Implement `services/context_manager.py`:
  - Maintain rolling transcript buffer
  - Build LLM prompts: system instruction + transcript context + chat history
  - Token budget management: truncate/summarize older transcript if exceeds limit
- [ ] Implement `services/transcript_store.py` — save transcript to `transcripts/` directory as `.md` and `.json`
- [ ] Implement `routers/export.py` — REST endpoints: `GET /api/export/md`, `GET /api/export/json`, `GET /api/export/txt`
- [ ] Implement `routers/settings.py` — REST endpoints to get/update runtime settings (LLM backend, model, etc.)
- [ ] Add health check endpoint

### Phase 5: Frontend — Core Layout

- [ ] Initialize React project with Vite + TypeScript + Tailwind CSS
- [ ] Implement `App.tsx` — responsive two-panel layout (transcript left, chat right), control bar top
- [ ] Implement `hooks/useTranscriptSocket.ts`:
  - Connect to `ws://localhost:8000/ws/transcript`
  - On message: parse transcript events, update store
  - Handle reconnection with exponential backoff
- [ ] Implement `hooks/useChatSocket.ts`:
  - Connect to `ws://localhost:8000/ws/chat`
  - Send messages, receive streaming tokens
  - Handle reconnection
- [ ] Implement `stores/transcriptStore.ts` — Zustand store: array of transcript segments, append/update operations
- [ ] Implement `stores/chatStore.ts` — Zustand store: array of chat messages, current streaming response

### Phase 6: Frontend — Components

- [ ] Implement `TranscriptPanel.tsx`:
  - Scrollable list of transcript segments with timestamps
  - Auto-scroll to bottom (disable when user scrolls up, "Jump to latest" button)
  - Highlight partial/in-progress segments with typing animation
  - Toggle between raw and clean transcript view
- [ ] Implement `ChatPanel.tsx`:
  - Message list with user/AI bubbles
  - Markdown rendering in AI responses (using `react-markdown`)
  - Text input with send button and `Enter` to send
  - Streaming response display (token-by-token append)
  - Quick action buttons: "Summarize", "Action Items", "Key Decisions"
- [ ] Implement `ControlBar.tsx`:
  - Start/Stop recording button (calls API Gateway)
  - Recording duration timer
  - Export dropdown (MD, TXT, JSON)
  - Settings gear icon
- [ ] Implement `SearchBar.tsx`:
  - Search input that filters/highlights transcript segments
  - Keyboard shortcut: `⌘K` or `Ctrl+K`
- [ ] Implement `SettingsModal.tsx`:
  - LLM backend selection (Ollama/OpenAI/Anthropic)
  - Model selection
  - Audio device selection
  - Transcription model size

### Phase 7: Integration & Docker

- [ ] Write `docker-compose.yml`:
  - `audio-capture`: Python service, needs host audio device access (`--device /dev/snd` or macOS equivalent)
  - `transcription`: Python service, may need GPU passthrough for faster-whisper
  - `api-gateway`: Python service, port 8000
  - `frontend`: Node build → nginx static serve, port 3000
  - `ollama` (optional): Ollama container for local LLM
  - Shared network for inter-service communication
- [ ] Note: On macOS, Docker audio access is limited. Provide alternative `Makefile` target for running services natively (`make dev`)
- [ ] End-to-end integration test: start all services, open browser, speak into mic, verify transcript appears, send chat message, verify response
- [ ] Load test: simulate 1-hour meeting volume of audio, verify stability

### Phase 8: Polish & Extensibility

- [ ] Add speaker diarization (via `pyannote-audio` or simple energy/voice fingerprint heuristics) as optional pipeline stage
- [ ] Add real-time summary: periodically (every 5 min) auto-generate and display a running summary
- [ ] Add WebSocket reconnection handling in all services
- [ ] Add logging (structured JSON logs) across all services
- [ ] Add error handling: service crash recovery, audio device loss, LLM timeout
- [ ] Frontend: dark/light theme toggle, responsive layout for narrow screens
- [ ] Frontend: keyboard shortcuts reference (`?` to show)
- [ ] Write comprehensive README: architecture overview, quickstart, configuration, troubleshooting

## Key Design Decisions

1. **Microservices over monolith:** Each service has a single responsibility. This means you can swap `faster-whisper` for Deepgram's API by replacing only the transcription service. Or swap Ollama for Claude by changing only the LLM client. The frontend doesn't care about the backend implementation.

2. **WebSockets for real-time:** HTTP polling would add latency and complexity. WebSockets give true real-time streaming — transcript segments appear as they're produced, chat tokens stream as they're generated. The protocol is simple JSON messages.

3. **API Gateway pattern:** The frontend connects only to the gateway (port 8000). The gateway fans out to internal services. This simplifies frontend code, enables CORS control, and provides a single point for authentication if needed later.

4. **Docker + native hybrid:** Docker Compose for production-like environments, but `make dev` for local development (since Docker on macOS can't easily access the microphone). Services communicate the same way regardless of deployment method.

5. **Filesystem persistence:** For a single-user tool, a database is overkill. Markdown files are human-readable, portable, and can be opened in any editor. JSON files provide structured access for programmatic use.

## Dependencies

### Python Services (each service)
```
# audio-capture
sounddevice==0.5.*
websockets==13.*
numpy==1.26.*

# transcription
faster-whisper==1.1.*
silero-vad==5.1.*
websockets==13.*
numpy==1.26.*

# api-gateway
fastapi==0.115.*
uvicorn==0.32.*
websockets==13.*
httpx==0.27.*
openai==1.50.*
anthropic==0.39.*
pydantic==2.10.*
```

### Frontend
```json
{
  "dependencies": {
    "react": "^19.0",
    "react-dom": "^19.0",
    "zustand": "^5.0",
    "react-markdown": "^9.0",
    "tailwindcss": "^4.0"
  }
}
```

## Estimated Complexity

| Phase | Effort |
|---|---|
| Phase 1: Scaffolding & Protocol | Small |
| Phase 2: Audio Capture Service | Small |
| Phase 3: Transcription Service | Medium |
| Phase 4: API Gateway | Medium–Large |
| Phase 5: Frontend Core | Medium |
| Phase 6: Frontend Components | Medium–Large |
| Phase 7: Docker Integration | Medium |
| Phase 8: Polish & Extensibility | Large |
