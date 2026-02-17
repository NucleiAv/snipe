"""
AI-powered diagnostic explainer using Claude or Gemini API.
Provides clear, concise explanations for code errors and warnings.
Tries Claude first, falls back to Gemini.
"""
from __future__ import annotations
import os
import logging
from typing import Optional

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not required, env vars can be set directly

log = logging.getLogger(__name__)

# Try importing both APIs
try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False
    anthropic = None

try:
    from google import genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False
    genai = None


class AIExplainer:
    """
    Uses Claude or Gemini to explain diagnostics in simple terms.
    Tries Claude first, falls back to Gemini.
    """

    def __init__(self, anthropic_key: Optional[str] = None, google_key: Optional[str] = None):
        """
        Initialize AI explainer with Claude or Gemini API.

        Args:
            anthropic_key: Anthropic API key. If not provided, reads from ANTHROPIC_API_KEY env var.
            google_key: Google API key. If not provided, reads from GOOGLE_API_KEY env var.
        """
        self.anthropic_key = anthropic_key or os.getenv("ANTHROPIC_API_KEY")
        self.google_key = google_key or os.getenv("GOOGLE_API_KEY")

        self.claude_client = None
        self.gemini_client = None
        self.enabled = False
        self.provider = None

        # Try Claude first
        if HAS_ANTHROPIC and self.anthropic_key:
            try:
                self.claude_client = anthropic.Anthropic(api_key=self.anthropic_key)
                self.enabled = True
                self.provider = "claude"
                log.info("AI Explainer initialized with Claude")
                return
            except Exception as e:
                log.warning(f"Failed to initialize Claude: {e}")

        # Fall back to Gemini
        if HAS_GEMINI and self.google_key:
            try:
                self.gemini_client = genai.Client(api_key=self.google_key)
                self.enabled = True
                self.provider = "gemini"
                log.info("AI Explainer initialized with Gemini")
                return
            except Exception as e:
                log.warning(f"Failed to initialize Gemini: {e}")

        # No API available
        if not HAS_ANTHROPIC and not HAS_GEMINI:
            log.warning("Neither anthropic nor google-genai installed. AI explanations disabled.")
        elif not self.anthropic_key and not self.google_key:
            log.warning("Neither ANTHROPIC_API_KEY nor GOOGLE_API_KEY found. AI explanations disabled.")
        else:
            log.warning("Failed to initialize any AI provider. AI explanations disabled.")

    def explain_diagnostic(
        self,
        diagnostic: dict,
        code_context: str
    ) -> Optional[str]:
        """
        Generate a clear explanation for a diagnostic error/warning.

        Args:
            diagnostic: Dictionary with keys: message, severity, code, file, line
            code_context: Relevant code snippet around the error

        Returns:
            AI-generated explanation or None if disabled/failed
        """
        if not self.enabled:
            return None

        # Build prompt
        error_message = diagnostic.get("message", "Unknown error")
        severity = diagnostic.get("severity", "error")
        code = diagnostic.get("code", "")
        file = diagnostic.get("file", "")
        line = diagnostic.get("line", 0)

        prompt = f"""You are a helpful programming assistant explaining code errors.

Error: {error_message}
Severity: {severity}
Code: {code}
File: {file}
Line: {line}

Code Context:
```
{code_context}
```

Explain this error in exactly this format (plain text only, no markdown):

- WHAT IT MEANS: [one sentence explanation]
- HOW TO FIX IT: [one sentence fix]

Use exactly these headers. Keep it under 50 words total. Be direct and actionable."""

        # Try Claude first
        if self.provider == "claude" and self.claude_client:
            try:
                response = self.claude_client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=300,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )

                if response and response.content:
                    explanation = response.content[0].text.strip()
                    log.info(f"Generated AI explanation (Claude) for: {error_message[:50]}")
                    return explanation
                else:
                    log.warning("Empty response from Claude")
                    return None
            except Exception as e:
                log.error(f"Failed to generate Claude explanation: {e}")
                log.info("Falling back to Gemini...")

        # Fall back to Gemini (initialize if not already done)
        if not self.gemini_client and HAS_GEMINI and self.google_key:
            try:
                self.gemini_client = genai.Client(api_key=self.google_key)
            except Exception as e:
                log.error(f"Failed to initialize Gemini fallback: {e}")
                return None
        if self.gemini_client:
            try:
                response = self.gemini_client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt
                )

                if response and response.text:
                    explanation = response.text.strip()
                    log.info(f"Generated AI explanation (Gemini) for: {error_message[:50]}")
                    return explanation
                else:
                    log.warning("Empty response from Gemini")
                    return None
            except Exception as e:
                log.error(f"Failed to generate Gemini explanation: {e}")
                return None

        return None

    def explain_batch(
        self,
        diagnostics: list[dict],
        code_contexts: list[str]
    ) -> list[Optional[str]]:
        """
        Explain multiple diagnostics in batch.

        Args:
            diagnostics: List of diagnostic dictionaries
            code_contexts: List of code context strings (same length as diagnostics)

        Returns:
            List of explanations (or None for failed ones)
        """
        if not self.enabled:
            return [None] * len(diagnostics)

        explanations = []
        for diagnostic, context in zip(diagnostics, code_contexts):
            explanation = self.explain_diagnostic(diagnostic, context)
            explanations.append(explanation)

        return explanations

    def is_available(self) -> bool:
        """
        Check if AI explanations are available.

        Returns:
            True if Claude or Gemini API is configured and working
        """
        return self.enabled

    def get_provider(self) -> Optional[str]:
        """
        Get the name of the active AI provider.

        Returns:
            "claude", "gemini", or None if disabled
        """
        return self.provider


# Singleton instance
_explainer: Optional[AIExplainer] = None


def get_explainer() -> AIExplainer:
    """
    Get or create the singleton AIExplainer instance.

    Returns:
        AIExplainer instance
    """
    global _explainer
    if _explainer is None:
        _explainer = AIExplainer()
    return _explainer
