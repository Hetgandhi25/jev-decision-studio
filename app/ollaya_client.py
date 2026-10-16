import time
import httpx
from typing import Dict, Any, Tuple
from app.config import settings

class OllayaClient:
    def __init__(self, base_url: str = settings.OLLAYA_URL, timeout: float = settings.TIMEOUT_SECONDS):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def get_models(self) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(f"{self.base_url}/v1/models")
            resp.raise_for_status()
            return resp.json()

    async def check_health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{self.base_url}/")
                return resp.status_code == 200 and "Ollaya is running" in resp.text
        except Exception:
            return False

    async def decide_systemone(self, payload: Dict[str, Any]) -> Tuple[bool, Dict[str, Any], float]:
        t0 = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/v1/systemone",
                    json=payload
                )
                t1 = time.perf_counter()
                latency_ms = (t1 - t0) * 1000
                if resp.status_code == 200:
                    data = resp.json()
                    return True, data, latency_ms
                else:
                    return False, {"error": resp.text, "status_code": resp.status_code}, latency_ms
        except Exception as e:
            t1 = time.perf_counter()
            return False, {"error": str(e), "exception": type(e).__name__}, (t1 - t0) * 1000

ollaya_client = OllayaClient()
