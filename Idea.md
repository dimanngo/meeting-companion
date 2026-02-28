# Capabilities

## Listen to the meeting conversation

- Activate the microphone and listen to the conversation.
- Language support: English only.
- Continuously transcribe, stash, and persist the raw speech as a transcription.

## Speech analysis

- Continuously process the raw transcription to cleanse the data by removing errors and accurately recognizing the text.
- Continuously persist the clean transcription in Markdown format.

## Real-time interaction

Even while the meeting is ongoing, the solution should allow real-time interaction using the context generated from the conversation thus far. In other words, the primary goal of the solution is to serve as a real-time assistant **during the meeting**.

- **Example use case:** The user is attending a meeting. The system starts listening to the conversation (similar to the "Record Audio" function in Apple Notes). In the background, the system continuously processes the speech and adds it to the context. The user should be able to access the clean meeting transcription while simultaneously interacting with a separate chat interface based on that ongoing context.

## Technical considerations

- The user operates on a macOS laptop.
- The user is a power user who leverages various types of applications and interfaces, including Terminal-based User Interfaces (TUIs).

# Ask

Brainstorm ideas for such a solution and propose 3 different architectural or design options.