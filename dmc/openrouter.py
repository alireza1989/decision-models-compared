"""A small client for OpenRouter's Decisions endpoint (alpha), standard library only.

Keys are read from .env by a strict KEY=value parser; the file is never executed or printed.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request

from dmc.common import ROOT

ENDPOINT = "https://openrouter.ai/api/alpha/decisions"
RETRY_CODES = {408, 409, 425, 429, 500, 502, 503, 504}


def load_env(path=ROOT / ".env") -> dict:
    env = {}
    for line in open(path):
        m = re.fullmatch(r"([A-Z_][A-Z0-9_]*)=(\S+)", line.strip())
        if m:
            env[m.group(1)] = m.group(2)
    return env


class DecisionError(Exception):
    def __init__(self, message: str, fatal: bool = False, status: int | None = None):
        super().__init__(message)
        self.fatal = fatal
        self.status = status


class DecisionsClient:
    def __init__(self, key: str | None = None, timeout: float = 60.0):
        self.key = key or load_env()["OPENROUTER_API_KEY"]
        self.timeout = timeout

    def _post(self, body: dict) -> dict:
        req = urllib.request.Request(
            ENDPOINT, data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json",
                     "X-Title": "decision-models-compared"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            text = e.read().decode(errors="replace")[:300]
            raise DecisionError(f"HTTP {e.code}: {text}", fatal=e.code not in RETRY_CODES, status=e.code) from None
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            raise DecisionError(f"{type(e).__name__}: {e}") from None

    def decide(self, model: str, state, questions: dict, attempts: int = 4) -> tuple[dict | None, float, str | None, int]:
        """Returns (response or None, latency_ms of the last attempt, error or None, attempts used)."""
        last = None
        for attempt in range(attempts):
            start = time.perf_counter()
            try:
                data = self._post({"model": model, "state": state, "questions": questions})
                return data, (time.perf_counter() - start) * 1000, None, attempt + 1
            except DecisionError as e:
                last = str(e)
                if e.fatal:
                    return None, (time.perf_counter() - start) * 1000, last, attempt + 1
                time.sleep(min(2 ** attempt, 20))
        return None, 0.0, last, attempts
