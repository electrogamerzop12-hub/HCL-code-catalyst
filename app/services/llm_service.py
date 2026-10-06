"""
app/services/llm_service.py
===============================================================================
Multi-Provider LLM Service Module.

Interacts with LLM providers:
1. Local Ollama (llama3.1:8b, qwen2.5:7b-instruct)
2. Groq Cloud API (llama-3.1-70b-versatile, llama-3.1-8b-instant)
3. OpenAI API (gpt-4o-mini, gpt-4o)
4. Google Gemini API (gemini-1.5-flash)
5. OpenRouter API

Features automatic fallback switch (MOCK_LLM) if external LLMs are unreachable.
===============================================================================
"""

import os
import logging
import httpx
from typing import Optional, Dict, Any
from app.config import settings

logger = logging.getLogger("llm_service")


class LLMService:
    """
    Interface for calling local Ollama or Cloud LLM instances (Groq, OpenAI, Gemini)
    with graceful fallback handling.
    """

    def __init__(self):
        self.ollama_base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
        self.mock_mode = os.getenv("MOCK_LLM", "false").lower() in ("true", "1", "yes")

    def _call_openai_compatible(
        self, 
        endpoint_url: str, 
        api_key: str, 
        model: str, 
        prompt: str, 
        system_prompt: Optional[str] = None, 
        timeout: float = 30.0
    ) -> Optional[str]:
        """Generic handler for OpenAI-compatible Chat Completions API endpoints (OpenAI, Groq, OpenRouter, Bedrock Mantle)."""
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.2
        }

        try:
            with httpx.Client(timeout=timeout) as client:
                res = client.post(endpoint_url, json=payload, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    content = data["choices"][0]["message"]["content"].strip()
                    logger.info(f"Cloud LLM ({model}) response generated successfully.")
                    return content
                else:
                    logger.warning(f"Cloud LLM API error ({res.status_code}): {res.text}")
                    return None
        except Exception as e:
            logger.warning(f"Cloud LLM connection error ({endpoint_url}): {e}")
            return None

    def _call_gemini(
        self, 
        api_key: str, 
        model: str, 
        prompt: str, 
        system_prompt: Optional[str] = None, 
        timeout: float = 30.0
    ) -> Optional[str]:
        """Handler for Google Gemini API endpoint."""
        gemini_model = model or "gemini-1.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent?key={api_key}"
        
        contents = []
        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": f"System Instruction: {system_prompt}"}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        payload = {"contents": contents}

        try:
            with httpx.Client(timeout=timeout) as client:
                res = client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    content = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    logger.info(f"Gemini LLM ({gemini_model}) response generated successfully.")
                    return content
                else:
                    logger.warning(f"Gemini API error ({res.status_code}): {res.text}")
                    return None
        except Exception as e:
            logger.warning(f"Gemini API connection error: {e}")
            return None

    def _call_ollama(
        self, 
        base_url: str, 
        model: str, 
        prompt: str, 
        system_prompt: Optional[str] = None, 
        timeout: float = 3.0
    ) -> Optional[str]:
        """Handler for local Ollama instance."""
        url = f"{base_url.rstrip('/')}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(url, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    response_text = data.get("response", "").strip()
                    logger.info(f"Ollama ({model}) generated response successfully.")
                    return response_text
                else:
                    logger.warning(f"Ollama returned status {response.status_code}: {response.text}")
                    return None
        except Exception as e:
            logger.info(f"Ollama endpoint at {base_url} unreachable ({e}).")
            return None

    def generate_response(self, prompt: str, system_prompt: Optional[str] = None, timeout: float = 30.0) -> Optional[str]:
        """
        Generates response using available LLM provider in exact order:
        1. Local Ollama (if running)
        2. AWS Bedrock Mantle (using google.gemma-3-27b-it)
        3. Groq / OpenAI / Gemini / OpenRouter
        4. Fallback to deterministic RAG synthesis engine
        """
        if self.mock_mode:
            logger.info("MOCK_LLM mode enabled. Skipping LLM API calls.")
            return None

        # 1. Try Local Ollama First
        ollama_urls = [self.ollama_base_url, "http://localhost:11434", "http://127.0.0.1:11434"]
        ollama_model = settings.LLM_MODEL or self.ollama_model

        for url in set(ollama_urls):
            res = self._call_ollama(url, ollama_model, prompt, system_prompt, timeout=1.5)
            if res:
                return res

        # 2. AWS Bedrock Mantle API (google.gemma-3-27b-it)
        bedrock_key = os.getenv("BEDROCK_MANTLE_API_KEY", settings.BEDROCK_MANTLE_API_KEY).strip()
        if bedrock_key:
            bedrock_url = f"{settings.BEDROCK_MANTLE_BASE_URL.rstrip('/')}/chat/completions"
            bedrock_model = settings.BEDROCK_MANTLE_MODEL or "google.gemma-3-27b-it"
            logger.info(f"Ollama offline. Calling AWS Bedrock Mantle ({bedrock_model})...")
            res = self._call_openai_compatible(bedrock_url, bedrock_key, bedrock_model, prompt, system_prompt, timeout=timeout)
            if res:
                return res

        # 3. Other Cloud APIs (Groq, OpenAI, Gemini, OpenRouter)
        groq_key = os.getenv("GROQ_API_KEY", settings.GROQ_API_KEY).strip()
        openai_key = os.getenv("OPENAI_API_KEY", settings.OPENAI_API_KEY).strip()
        gemini_key = os.getenv("GEMINI_API_KEY", settings.GEMINI_API_KEY).strip()
        openrouter_key = os.getenv("OPENROUTER_API_KEY", settings.OPENROUTER_API_KEY).strip()

        if groq_key:
            model = settings.LLM_MODEL or "llama-3.1-70b-versatile"
            return self._call_openai_compatible("https://api.groq.com/openai/v1/chat/completions", groq_key, model, prompt, system_prompt, timeout)

        if openai_key:
            model = settings.LLM_MODEL or "gpt-4o-mini"
            return self._call_openai_compatible("https://api.openai.com/v1/chat/completions", openai_key, model, prompt, system_prompt, timeout)

        if gemini_key:
            model = settings.LLM_MODEL or "gemini-1.5-flash"
            return self._call_gemini(gemini_key, model, prompt, system_prompt, timeout)

        if openrouter_key:
            model = settings.LLM_MODEL or "meta-llama/llama-3.1-8b-instruct:free"
            return self._call_openai_compatible("https://openrouter.ai/api/v1/chat/completions", openrouter_key, model, prompt, system_prompt, timeout)

        logger.info("No active local Ollama or Cloud LLM endpoints responded. Using deterministic RAG synthesis engine.")
        return None


# Global LLMService singleton instance
llm_service = LLMService()
