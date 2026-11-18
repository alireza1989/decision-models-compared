"""Claude as a gate, behind the same decide() call as the decision models (standard library only).

The Messages API returns no probabilities, so this is post 1's stated-confidence arm: the model
writes its answer and a confidence from 0 to 100 as JSON, structured output pins the answer to the
allowed names, and thinking is off. For the routing gate the prompt is post 1's, word for word
(harness-decision-gates, gates/llm.py and gates/claude.py), so post 1's Claude results stay
comparable. The reply is turned into the decision models' response shape, with the stated
confidence on the chosen answer and the rest spread evenly over the other answers, as in post 1.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from dmc.openrouter import RETRY_CODES, DecisionError, load_env

ENDPOINT = "https://api.anthropic.com/v1/messages"
ROUTING_SYSTEM = "You are the router for a banking support agent. You decide which skill should handle a customer message."
W2C_SYSTEM = "You decide the next step of an AI assistant that can call tools."
# Claude Haiku 5.5 list price per million tokens for prompts under 100,000 tokens (platform.claude.com, Nov 2026).
PRICE_PER_M = {"claude-haiku-5-5": (0.10, 0.50)}


def routing_prompt(state, criteria: dict) -> str:
    skills = "\n".join(f"- {label}: {desc}" for label, desc in criteria.items())
    if isinstance(state, dict):
        message = f"Account: {json.dumps(state['account'])}\nCustomer message: {state['customer_message']}"
    else:
        message = f"Customer message: {state}"
    return (f"Skills:\n{skills}\n\n{message}\n\n"
            "Which skill should handle this message, and how confident are you? Reply with JSON only, "
            'like {"skill": "<skill name>", "confidence": <number from 0 to 100>}.')


def w2c_prompt(state: dict, criteria: dict) -> str:
    options = "\n".join(f"- {label}: {desc}" for label, desc in criteria.items())
    return (f"Options:\n{options}\n\nTools the assistant has:\n{json.dumps(state['available_tools'], indent=1)}\n\n"
            f"User message: {state['user_message']}\n\n"
            "What should the assistant do next, and how confident are you? Reply with JSON only, "
            'like {"next_step": "<option name>", "confidence": <number from 0 to 100>}.')


class AnthropicClient:
    def __init__(self, key: str | None = None, timeout: float = 60.0):
        self.key = key or load_env()["ANTHROPIC_API_KEY"]
        self.timeout = timeout

    def _post(self, body: dict) -> dict:
        req = urllib.request.Request(
            ENDPOINT, data=json.dumps(body).encode(),
            headers={"x-api-key": self.key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            text = e.read().decode(errors="replace")[:300]
            raise DecisionError(f"HTTP {e.code}: {text}", fatal=e.code not in RETRY_CODES | {529}, status=e.code) from None
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            raise DecisionError(f"{type(e).__name__}: {e}") from None

    def decide(self, model: str, state, questions: dict, attempts: int = 4):
        (qname, q), = questions.items()
        labels = list(q["criteria"])
        if qname == "skill":
            system, prompt = ROUTING_SYSTEM, routing_prompt(state, q["criteria"])
        else:
            system, prompt = W2C_SYSTEM, w2c_prompt(state, q["criteria"])
        schema = {"type": "object", "additionalProperties": False, "required": [qname, "confidence"],
                  "properties": {qname: {"type": "string", "enum": labels}, "confidence": {"type": "integer"}}}
        body = {"model": model, "max_tokens": 200, "system": system,
                "messages": [{"role": "user", "content": prompt}],
                "thinking": {"type": "disabled"},
                "output_config": {"format": {"type": "json_schema", "schema": schema}}}
        last = None
        for attempt in range(attempts):
            start = time.perf_counter()
            try:
                data = self._post(body)
                latency = (time.perf_counter() - start) * 1000
                return self._shape(data, qname, labels), latency, None, attempt + 1
            except DecisionError as e:
                last = str(e)
                if e.fatal:
                    return None, (time.perf_counter() - start) * 1000, last, attempt + 1
                time.sleep(min(2 ** attempt, 20))
        return None, 0.0, last, attempts

    @staticmethod
    def _shape(data: dict, qname: str, labels: list[str]) -> dict:
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        usage = data.get("usage") or {}
        price_in, price_out = next((v for k, v in PRICE_PER_M.items() if (data.get("model") or "").startswith(k)), (None, None))
        cost = None if price_in is None else ((usage.get("input_tokens") or 0) * price_in + (usage.get("output_tokens") or 0) * price_out) / 1e6
        out = {"id": data.get("id"), "model": data.get("model"), "provider": "Anthropic",
               "usage": {"input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"), "cost": cost},
               "raw_text": text, "stop_reason": data.get("stop_reason")}
        try:
            obj = json.loads(text)
            choice, conf = obj[qname], float(obj["confidence"]) / 100
            assert choice in labels and 0 <= conf <= 1
        except (ValueError, KeyError, TypeError, AssertionError):
            out["answers"] = {qname: {"choice": None, "raw": text}}
            return out
        rest = (1 - conf) / (len(labels) - 1)
        probs = {label: (conf if label == choice else rest) for label in labels}
        out["answers"] = {qname: {"choice": choice, "probabilities": probs, "confidence": conf}}
        return out
