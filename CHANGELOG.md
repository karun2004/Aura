# Changelog

## v0.1.0 (2026-06-22) — Project Foundation

### Completed
- **Goal 1:** Project skeleton — module structure, venv, git init
- **Goal 2 (in progress):** Custom "Hey AURA" wake word model training
  - openWakeWord training environment fully configured
  - Piper TTS sample generation working (30,000 samples generated)
  - AudioSet + MIT RIR augmentation data prepared
  - Full training pipeline proven end-to-end
  - Production-scale training run in progress (30k samples, 30k steps)

### Architecture
- 9-subsystem pipeline architecture defined
- Tiered intelligence model (Grammar → Local LLM → Cloud LLM)
- Safety-first action classification (Safe / Moderate / Destructive)
- Cross-platform accessibility bridge design (UIA / AX / AT-SPI)
