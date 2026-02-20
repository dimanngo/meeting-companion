# Meeting TUI - Deep Code Review & Analysis

**Date:** 2026-02-18
**Project:** meeting-tui (v0.1.0)
**Reviewer:** Gemini CLI

## 1. Executive Summary

The `meeting-tui` project is a well-structured terminal application leveraging modern Python tooling (`uv`, `hatch`) and libraries (`textual`, `faster-whisper`). The core architecture—separating audio capture, VAD, transcription, and UI—is sound and modular.

However, several critical performance bottlenecks and architectural limitations exist that will degrade user experience during long meetings or extensive chat sessions. Specifically, the JSON persistence mechanism and chat history management require immediate refactoring to ensure scalability.

## 2. Codebase Structure & Quality

### Strengths
-   **Modular Design:** Clear separation of concerns in `src/meeting_tui/` (audio, chat, llm, persistence, transcription, widgets).
-   **Configuration:** Robust layered configuration (CLI > Env > Config File) in `config.py`.
-   **Type Hinting:** Consistent use of Python type hints and dataclasses.
-   **Testing:** Comprehensive test suite covering all major components (`tests/`).
-   **Dependency Management:** Modern `pyproject.toml` setup with optional dependencies.

### Weaknesses
-   **Chat Context Handling:** The `ChatManager` flattens structured chat history into a single string prompt. This confuses LLM backends about speaker roles and degrades response quality.
-   **Persistence Strategy:** The `JSONWriter` performs a full file rewrite for every new transcript segment, leading to $O(N^2)$ I/O complexity.
-   **UI Rendering:** The `ChatPane` widget clears and re-renders the entire message history for every single token generated during streaming, which is highly inefficient.

## 3. Detailed Findings

### 3.1. Critical Issues (High Severity)

#### 1. Chat Prompt Construction (Architectural Flaw)
*   **Location:** `src/meeting_tui/chat/manager.py`
*   **Issue:** The `_build_chat_prompt` method concatenates the entire chat history into a single string (e.g., `User: ...
Assistant: ...`) before sending it to the LLM backend.
*   **Impact:**
    -   Most modern LLM APIs (OpenAI, Anthropic, Gemini, Ollama) are optimized for structured *lists of messages* (`[{"role": "user", ...}, {"role": "assistant", ...}]`).
    -   Passing a flattened string forces the model to interpret the conversation structure from text, which is prone to errors and role confusion.
    -   It prevents the use of advanced features like function calling or separate system instructions (beyond the initial context).
*   **Recommendation:** Refactor `ChatManager` and `LLMBackend` to support passing a list of `ChatMessage` objects directly to the API.

#### 2. JSON Persistence Performance (Performance Bottleneck)
*   **Location:** `src/meeting_tui/persistence/json_writer.py`
*   **Issue:** The `_save()` method calls `json.dump` on the entire accumulated list of segments every time a new segment is added.
*   **Impact:**
    -   **Quadratic Complexity:** Writing $N$ segments requires $O(N^2)$ disk I/O operations over the course of a meeting.
    -   **High Latency:** For a 1-hour meeting with ~500 segments, this will cause noticeable freezes and high disk usage towards the end.
*   **Recommendation:** Switch to an append-only format like **JSON Lines (`.jsonl`)**, where each segment is written as a single line to the file. This reduces complexity to $O(N)$.

### 3.2. Medium Issues (Performance & UX)

#### 3. Chat Pane Rendering Efficiency
*   **Location:** `src/meeting_tui/widgets/chat_pane.py`
*   **Issue:** `_rewrite_all()` clears the `RichLog` and re-writes every message in history for *every token* received during streaming.
*   **Impact:**
    -   High CPU usage during generation.
    -   Potential UI flickering or lag, especially with long chat histories.
*   **Recommendation:** Modify `ChatPane` to append tokens to the log in-place, or batch UI updates (e.g., every 50ms or 10 tokens).

#### 4. Blocking Model Loading
*   **Location:** `src/meeting_tui/app.py` (`_load_off_loop`)
*   **Issue:** The app relies on a synchronous model loading process that, while technically offloaded to a worker, might still impact responsiveness or simple block if not handled perfectly. The comment notes a specific CTranslate2 race condition.
*   **Recommendation:** Ensure `run_in_executor` is used where safe, or keep the current workaround but add a more robust loading screen that doesn't rely on the main loop being free.

#### 5. Context Truncation
*   **Location:** `src/meeting_tui/chat/manager.py`
*   **Issue:** Context is truncated by simply dropping the oldest text when the limit is reached.
*   **Impact:** Critical context from the start of the meeting (introductions, agenda) is lost once the transcript grows long.
*   **Recommendation:** Implement a smarter context window (e.g., keeping the first N segments + sliding window of recent segments) or use a summarization step.

## 4. Prioritized Recommendations

| Priority | Task | Effort | Value |
| :--- | :--- | :--- | :--- |
| **P0** | **Refactor JSON Persistence**<br>Switch `JSONWriter` to use `jsonlines` (append-only) to fix $O(N^2)$ performance bottleneck. | Low | High |
| **P0** | **Fix Chat Message Structure**<br>Update `ChatManager` and `LLMBackend` to pass structured message lists instead of flattened strings. | Medium | High |
| **P1** | **Optimize Chat Rendering**<br>Update `ChatPane` to append tokens efficiently instead of rewriting full history. | Medium | Medium |
| **P2** | **Smart Context Management**<br>Keep meeting start/agenda in context; summarize middle sections instead of dropping them. | High | Medium |
| **P3** | **Automatic Diarization**<br>Integrate pyannote.audio or similar for automatic speaker detection (vs. manual `Ctrl+S`). | High | Low (MVP) |

## 5. Conclusion

The `meeting-tui` app is a solid MVP with a clean codebase. Addressing the **JSON persistence** and **Chat prompting** issues is critical for stability and response quality. Once these are fixed, the app will be robust enough for daily use. Future work should focus on automatic speaker diarization to reduce user workload.
