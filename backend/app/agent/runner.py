"""Esegue l'agente in modalità headless.

- claude-cli: `claude -p` con la tua sessione/abbonamento Claude Code (nessuna API key)
- codex-cli:  `codex exec` con la tua sessione Codex
- anthropic-api: Messages API con ANTHROPIC_API_KEY
"""
import json
import os
import re
import subprocess
import tempfile

import httpx

from ..config import settings


class AgentError(RuntimeError):
    pass


def _claude_cli(system: str, prompt: str) -> str:
    cmd = [
        settings.claude_bin, "-p",
        "--output-format", "json",
        "--model", settings.agent_model,
        "--system-prompt", system,
        "--tools", "",
        "--no-session-persistence",
        "--setting-sources", "",
        # nessun server MCP, plugin, skill o Chrome: all'agente basta il testo
        "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
        "--disable-slash-commands",
        "--no-chrome",
    ]
    env = {**os.environ, "ENABLE_CLAUDEAI_MCP_SERVERS": "false"}  # niente connettori di claude.ai
    # cwd temporanea: non deve leggere CLAUDE.md o file del progetto
    with tempfile.TemporaryDirectory() as tmp:
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                              timeout=settings.agent_timeout, cwd=tmp, env=env)
    if proc.returncode != 0:
        raise AgentError(f"claude -p fallito: {(proc.stderr or proc.stdout).strip()[-800:]}")
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise AgentError(f"Output di claude non è JSON: {proc.stdout[-500:]}") from e
    if data.get("is_error"):
        raise AgentError(f"claude ha restituito un errore: {data.get('result')}")
    return data.get("result", "")


def _codex_cli(system: str, prompt: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        out_file = f"{tmp}/last.txt"
        proc = subprocess.run(
            [settings.codex_bin, "exec", "--skip-git-repo-check", "--output-last-message", out_file, "-"],
            input=f"{system}\n\n---\n\n{prompt}", capture_output=True, text=True,
            timeout=settings.agent_timeout, cwd=tmp,
        )
        if proc.returncode != 0:
            raise AgentError(f"codex exec fallito: {proc.stderr.strip()[-800:]}")
        with open(out_file) as f:
            return f.read()


def _anthropic_api(system: str, prompt: str) -> str:
    if not settings.anthropic_api_key:
        raise AgentError("ANTHROPIC_API_KEY mancante")
    r = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": settings.anthropic_api_key, "anthropic-version": "2023-06-01"},
        json={
            "model": settings.anthropic_model,
            "max_tokens": 16000,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=settings.agent_timeout,
    )
    if r.status_code >= 400:
        raise AgentError(f"API Anthropic {r.status_code}: {r.text[:500]}")
    return "".join(b.get("text", "") for b in r.json()["content"] if b["type"] == "text")


PROVIDERS = {"claude-cli": _claude_cli, "codex-cli": _codex_cli, "anthropic-api": _anthropic_api}


def run(system: str, prompt: str) -> str:
    provider = PROVIDERS.get(settings.agent_provider)
    if provider is None:
        raise AgentError(f"Provider sconosciuto: {settings.agent_provider}")
    try:
        return provider(system, prompt)
    except subprocess.TimeoutExpired as e:
        raise AgentError(f"L'agente non ha risposto entro {settings.agent_timeout}s") from e


def extract_json(text: str):
    """Estrae il primo oggetto JSON dalla risposta (accetta blocchi ```json)."""
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = m.group(1) if m else text[text.find("{"): text.rfind("}") + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as e:
        raise AgentError(f"Risposta non in JSON valido: {e}. Inizio risposta: {text[:300]}") from e


def run_json(system: str, prompt: str, validate=None, retries: int = 1):
    """Chiede JSON all'agente; se la validazione fallisce, rimanda l'errore all'agente."""
    attempt_prompt = prompt
    last_error: Exception | None = None
    for _ in range(retries + 1):
        raw = run(system, attempt_prompt)
        try:
            data = extract_json(raw)
            return validate(data) if validate else data
        except Exception as e:  # noqa: BLE001 - qualsiasi errore di validazione va rimandato all'agente
            last_error = e
            attempt_prompt = (
                f"{prompt}\n\n---\nLa tua risposta precedente era:\n{raw[:6000]}\n\n"
                f"È stata rifiutata con questo errore:\n{e}\n\nCorreggi e rispondi di nuovo solo con il JSON."
            )
    raise AgentError(str(last_error))
