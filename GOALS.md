# AURA — Sequenced Build Goals

This is the complete, ordered list of build goals for AURA. Each goal is a single, concrete, buildable step. They are sequenced so that every goal only depends on goals that come before it — building them in order, one at a time, and completing all 43 results in the full project.

**How to use:** pick the lowest-numbered goal you haven't completed yet, build and test just that one thing, confirm it works on its own, then move to the next number. The "Depends On" column tells you exactly which earlier goals need to already be working.

| # | Goal | Why We Need It | Depends On | Libraries |
|---|------|---------------|------------|-----------|
| 1 | Set up dev environment & project skeleton | Every later goal needs a working codebase with separated modules | None | Python 3.11+, git, venv |
| 2 | Integrate wake word detector | AURA must listen continuously; the wake word triggers a real command | Goal 1 | openWakeWord |
| 3 | Integrate local speech-to-text (ASR) | Converts spoken command to text after wake word fires | Goal 2 | faster-whisper with CUDA |
| 4 | Integrate local text-to-speech (TTS) | Only output channel for a blind user | Goal 1 | Piper TTS |
| 5 | Build audio state cue system | Blind user can't see spinners; sounds communicate system state | Goals 2, 3, 4 | simpleaudio or sounddevice |
| 6 | Wire up wake→ASR→TTS demo loop | Phase 0 exit test: full hear→understand→speak loop on real hardware | Goals 2, 3, 4, 5 | Integration of 2–5 |
| 7 | Build OS accessibility API wrapper | How AURA "sees" the screen | Goal 1 | pywinauto/comtypes (Win), PyObjC (Mac), pyatspi (Linux) |
| 8 | Read active window title & control tree | Simplest screen-reading capability | Goal 7 | Same as Goal 7 |
| 9 | Build browser extension skeleton + local IPC | Browser dashboards are top priority use case | Goal 1 | JavaScript (WebExtensions API), websockets |
| 10 | Read browser tab list, titles, focused tab | Answers "what tab am I on" and "what tabs do I have open" | Goal 9 | WebExtensions tabs API |
| 11 | Read DOM/ARIA structure of a page | Lets AURA read headings, text, labels on any website | Goal 9 | JavaScript DOM APIs, ARIA |
| 12 | Add MutationObserver dynamic-content tracking | Dashboards update via JS without reloading; without this, AURA reads stale data | Goal 11 | JavaScript MutationObserver API |
| 13 | Integrate local LLM runtime with CUDA | Needed for flexible language understanding beyond pattern matching | Goal 1 | Ollama or llama.cpp with CUDA |
| 14 | Benchmark & select local model size | Validates best-fit model on real GPU hardware with CPU fallback | Goal 13 | Same as Goal 13 |
| 15 | Build Tier 1 deterministic intent grammar | Most commands are structural and don't need an LLM | Goal 3 | spaCy or regex/rule engine |
| 16 | Build Tier 2 LLM-based intent fallback | Catches flexible phrasing Tier 1 can't classify | Goals 14, 15 | Local LLM from Goal 13/14 |
| 17 | Build turn-level dialogue memory | Resolves "it," "that file," "go back" within conversation | Goals 15, 16 | In-memory Python structures |
| 18 | Build session state tracking | Tracks what's open, recent navigation, enables "go back" | Goal 17 | In-memory/SQLite |
| 19 | Build persistent user profile storage | Stores preferences, aliases, habits across sessions | Goal 18 | SQLite or local JSON |
| 20 | Implement barge-in / interruption | Blind user can't skim ahead visually; must be able to interrupt mid-sentence | Goals 2, 4 | Audio playback control |
| 21 | Build application registry | Maps spoken app names to real executables | Goal 1 | psutil, OS app discovery |
| 22 | Implement open/foreground app + verification | Launches apps, brings to foreground, confirms success | Goals 7, 15, 21 | psutil, subprocess |
| 23 | Implement in-page/in-app navigation | Move to heading, field, or button by voice | Goals 7, 8, 11 | Accessibility libs + browser extension |
| 24 | Implement literal full-read mode | Most basic "read this page to me" — exactly what's there, in order | Goals 8, 11, 12 | Uses structured data from 8/11/12 |
| 25 | Implement structured table/form extraction | Dashboards present data in tables; enables questions about the data | Goals 11, 12 | DOM/accessibility tree parsing |
| 26 | Implement AI summary mode | "Metrics" read-back: structured page data → natural spoken summary | Goals 16, 24, 25 | Local LLM from Goal 13/14 |
| 27 | Integrate native OS file search | Powers "find the file called X" | Goal 1 | Windows Search API / Spotlight / local index |
| 28 | Implement file open & save actions | "Open it," "save this as X in folder Y" | Goals 22, 27 | OS file APIs + Goal 7 |
| 29 | Implement create-folder action | "Create a new folder called X" | Goal 27 | Python os/pathlib |
| 30 | Implement delete / destructive action handling | File deletion — highest-risk file operation | Goals 27, 28 | os/pathlib, send2trash |
| 31 | Build action risk classifier | Tags every action Safe/Moderate/Destructive | Goals 22–30 | Rules/config-driven classifier |
| 32 | Build double-confirmation dialogue flow | Destructive actions must never execute on a single utterance | Goals 17, 31 | Built on dialogue memory |
| 33 | Build global stop/cancel hot-path | Halts anything AURA is doing, top priority over all processing | Goals 2, 3, 20 | Priority interrupt on ASR/audio |
| 34 | Build low-confidence clarification | When confidence is low, ask rather than guess | Goals 15, 16, 31 | Confidence thresholds |
| 35 | Build alias-learning system | Teaches AURA that "IEP" maps to a specific dashboard page | Goals 11, 19 | Stored via Goal 19's profile |
| 36 | Build setup/onboarding flow | One-time guided setup by sighted helper | Goals 7, 9, 21, 35 | OS permission-prompt APIs |
| 37 | Build startup health check | Proactively tells user if something isn't working | Goals 2, 3, 4, 7, 9 | Status checks on components |
| 38 | Build crash detection & auto-restart | Recovers from crashes, tells user it restarted | Goal 1 | Watchdog/supervisord |
| 39 | Integrate optional cloud LLM tier | Stronger summarization when internet available and user opts in | Goals 16, 26 | requests/httpx |
| 40 | Build screenshot + vision-model fallback | Covers poorly-built apps with no accessibility data | Goals 7, 8 | Vision model + mss/Pillow |
| 41 | Expand to remaining OS platforms | Cross-platform after core loop proven on one OS | Goal 7 | OS-specific equivalents |
| 42 | Build self-service alias-teaching | New users teach their own aliases without developer involvement | Goals 35, 36 | Guided conversational flow |
| 43 | Build regression test suite | Protects against regressions as new apps/sites added | Goals 15, 16, 22–30 | pytest + recorded fixtures |
