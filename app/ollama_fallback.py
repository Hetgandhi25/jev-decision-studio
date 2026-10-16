import re
import json
import time
import httpx
from typing import Dict, Any, Tuple
from app.config import settings

class OllamaFallbackClient:
    def __init__(self, base_url: str = settings.OLLAMA_URL, timeout: float = settings.TIMEOUT_SECONDS):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def check_health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False

    async def decide_question(self, state: str, q_name: str, q_data: Dict[str, Any], model_name: str) -> Dict[str, Any]:
        q_type = q_data.get("type")
        instructions = q_data.get("instructions", "")
        criteria = q_data.get("criteria")

        prompt = f"You are a strict decision classifier. Evaluate the text against the question.\n"
        prompt += f"Input text: \"{state}\"\n"
        prompt += f"Question: \"{instructions}\"\n"
        prompt += f"Decision type: \"{q_type}\"\n"

        if q_type == "choice":
            prompt += f"Allowed choices: {list(criteria.keys())}\n"
            prompt += f"Criteria: {json.dumps(criteria)}\n"
            prompt += 'Respond with ONLY a JSON object: {"choice": "<selected_key>", "estimated_confidence": 0.85}\n'
        elif q_type == "noul":
            prompt += 'Respond with ONLY a JSON object: {"noul": 0.95} where noul is your probability estimation (0.0 to 1.0) that the condition is Yes/True.\n'
        elif q_type == "score":
            prompt += f"Rubric levels (0 to {len(criteria)-1}): {json.dumps(criteria)}\n"
            prompt += f'Respond with ONLY a JSON object: {{"score": 1.0, "level": 1}}\n'

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": model_name,
                    "prompt": prompt,
                    "stream": False
                }
            )
            resp.raise_for_status()
            res_json = resp.json()
            raw_text = res_json.get("response", "")

            # Extract JSON block
            match = re.search(r"\{.*?\}", raw_text, re.DOTALL)
            if not match:
                raise ValueError(f"No JSON found in LLM fallback output: {raw_text[:100]}")
            parsed = json.loads(match.group(0))

            if q_type == "choice":
                selected = parsed.get("choice")
                if selected not in criteria:
                    # fallback to first key if hallucinated
                    selected = list(criteria.keys())[0]
                conf = float(parsed.get("estimated_confidence", 0.70))
                return {
                    "type": "choice",
                    "choice": selected,
                    "confidence": conf,
                    "probabilities": {k: (conf if k == selected else round((1.0 - conf) / max(1, len(criteria) - 1), 4)) for k in criteria}
                }
            elif q_type == "noul":
                val = float(parsed.get("noul", 0.50))
                val = max(0.0, min(1.0, val))
                return {
                    "type": "noul",
                    "noul": val
                }
            elif q_type == "score":
                score_val = float(parsed.get("score", parsed.get("level", 0.0)))
                max_score = float(len(criteria) - 1)
                score_val = max(0.0, min(max_score, score_val))
                legend = {str(i): criteria[i] for i in range(len(criteria))}
                return {
                    "type": "score",
                    "score": score_val,
                    "confidence": 0.65,
                    "legend": legend,
                    "probabilities": {str(i): (0.7 if i == int(round(score_val)) else 0.1) for i in range(len(criteria))}
                }

    async def decide_all(self, state: str, questions: Dict[str, Any], model_name: str = settings.FALLBACK_MODEL) -> Tuple[bool, Dict[str, Any], float]:
        t0 = time.perf_counter()
        try:
            answers = {}
            for q_name, q_data in questions.items():
                ans = await self.decide_question(state, q_name, q_data, model_name)
                answers[q_name] = ans
            t1 = time.perf_counter()
            return True, {
                "model": model_name,
                "answers": answers,
                "usage": {"input_tokens": 0, "output_tokens": 0}
            }, (t1 - t0) * 1000
        except Exception as e:
            t1 = time.perf_counter()
            return False, {"error": str(e), "exception": type(e).__name__}, (t1 - t0) * 1000

ollama_fallback = OllamaFallbackClient()
