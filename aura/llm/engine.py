"""
LLM integration — local Ollama and optional cloud API.
"""

import json
import logging
import subprocess
import time
from typing import Optional

logger = logging.getLogger(__name__)


class LocalLLM:
    """GPU-accelerated local LLM via Ollama."""

    def __init__(self, model: str = "llama3.2:1b"):
        self.model = model
        self._available = None

    def is_available(self) -> bool:
        """Check if Ollama is running and the model exists."""
        if self._available is not None:
            return self._available
        try:
            result = subprocess.run(
                ["ollama", "list"], capture_output=True, timeout=5, text=True
            )
            self._available = result.returncode == 0 and self.model.split(":")[0] in result.stdout
            if not self._available:
                logger.warning(f"Ollama model '{self.model}' not found. Run: ollama pull {self.model}")
            return self._available
        except (FileNotFoundError, subprocess.TimeoutExpired):
            logger.warning("Ollama not installed or not running")
            self._available = False
            return False

    def generate(self, prompt: str, max_tokens: int = 256, system: str = "") -> str:
        """Generate a response from the local LLM via Ollama API."""
        if not self.is_available():
            raise RuntimeError("Local LLM not available")

        start = time.time()
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": max_tokens},
            }
            if system:
                payload["system"] = system

            # Use Ollama's REST API
            import urllib.request
            req = urllib.request.Request(
                "http://localhost:11434/api/generate",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
                text = data.get("response", "").strip()
                elapsed = time.time() - start
                logger.info(f"LLM response in {elapsed:.2f}s ({len(text)} chars)")
                return text

        except Exception as e:
            logger.error(f"LLM generation error: {e}")
            raise

    def summarize(self, content: str, question: Optional[str] = None) -> str:
        """Summarize structured page content, optionally answering a question."""
        if question:
            prompt = f"""Based on this page content, answer the question concisely.

Page content:
{content[:3000]}

Question: {question}
Answer:"""
        else:
            prompt = f"""Summarize this page content in 2-3 spoken sentences. Focus on key data and numbers.

Page content:
{content[:3000]}

Summary:"""

        system = (
            "You are AURA, a voice assistant for blind users. "
            "Give brief, spoken-friendly responses. No markdown, no bullet points. "
            "Just natural speech."
        )
        return self.generate(prompt, max_tokens=200, system=system)


class CloudLLM:
    """Optional cloud LLM — strictly opt-in, only sends structured text."""

    def __init__(self, provider: str = "", api_key: str = "", api_url: str = ""):
        self.provider = provider
        self.api_key = api_key
        self.api_url = api_url
        self.enabled = bool(api_key and api_url)

    def generate(self, prompt: str, max_tokens: int = 512) -> str:
        """Generate via cloud API. Only call when user has explicitly opted in."""
        if not self.enabled:
            raise RuntimeError("Cloud LLM not configured. Enable in settings.")
        # Implementation depends on chosen provider (OpenAI, Anthropic, etc.)
        raise NotImplementedError("Configure your preferred cloud LLM provider")
