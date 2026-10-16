import os
import urllib.request
import json
import math

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://127.0.0.1:8000")

def run_regression():
    print("=" * 80)
    print("FINAL AUDIT REGRESSION TEST SUITE")
    print("=" * 80)

    # 1. Health Endpoint
    print("\n[TEST 1] Gateway Health Check")
    with urllib.request.urlopen(f"{GATEWAY_URL}/health") as resp:
        h = json.loads(resp.read().decode())
        assert h["status"] == "ok" and h["ollaya_primary"] == "up" and h["ollama_fallback"] == "up"
        print("  --> PASS: Health status OK (Ollaya=up, Ollama=up)")

    # 2. Native Multi-Primitive Evaluation
    print("\n[TEST 2] Native Decision Evaluation & Metadata Contract")
    payload = {
        "model": "laya:en",
        "state": "The primary database server in us-east-1 crashed due to disk exhaustion. All customer write transactions are failing.",
        "questions": {
            "category": {
                "type": "choice",
                "criteria": {
                    "infrastructure": "Database, server, network, cloud down",
                    "billing": "Invoice, refund, payments",
                    "application_bug": "Defect, latency, exception",
                    "security_incident": "Breach, leak, auth",
                    "other": "General, cosmetic"
                }
            },
            "urgency": {
                "type": "noul",
                "instructions": "Is this an urgent production situation requiring immediate response?"
            },
            "severity": {
                "type": "score",
                "criteria": [
                    "Level 0: Minor inconvenience",
                    "Level 1: Medium - degraded functionality",
                    "Level 2: High - significant service degradation",
                    "Level 3: Critical - major outage"
                ]
            }
        }
    }
    req = urllib.request.Request(f"{GATEWAY_URL}/v1/systemone", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode())
    
    ans = res["answers"]
    meta = res["decision_meta"]

    # Category checks
    cat = ans["category"]
    probs = cat["probabilities"]
    prob_sum = sum(probs.values())
    max_k = max(probs, key=probs.get)
    print(f"  Category: Choice={cat['choice']}, WinnerProb={probs[max_k]:.4f}, MarginConf={cat['confidence']:.4f}")
    assert cat["choice"] == "infrastructure"
    assert cat["choice"] == max_k, "Argmax mismatch"
    assert abs(prob_sum - 1.0) < 1e-3, "Probability sum != 1.0"
    print(f"  --> PASS: Category probabilities sum to {prob_sum:.6f}, argmax matches winner.")

    # Noul checks
    urg = ans["urgency"]
    print(f"  Urgency: noul={urg['noul']:.4f}")
    assert 0.0 <= urg["noul"] <= 1.0
    assert urg["noul"] > 0.65, "Urgent DB crash should have noul >= 0.65"
    print("  --> PASS: Noul is finite, bounded in [0, 1], and correctly reflects High urgency.")

    # Score checks
    sev = ans["severity"]
    s_probs = sev["probabilities"]
    exp_s = sum(int(k) * p for k, p in s_probs.items())
    diff_s = abs(sev["score"] - exp_s)
    print(f"  Severity: Score={sev['score']:.4f}, ExpectedVal={exp_s:.4f}, Diff={diff_s:.6e}")
    assert diff_s < 1e-3, f"Severity score != expected value: diff={diff_s}"
    print("  --> PASS: Severity score strictly matches expected value within serialization tolerance.")

    # Metadata checks (Honest calibration and CPU reality)
    print("\n[TEST 3] Metadata Contract Verification (Calibration & Hardware)")
    print(f"  Backend:          {meta.get('backend')}")
    print(f"  is_calibrated:    {meta.get('is_calibrated')}")
    print(f"  confidence_type:  {meta.get('confidence_type')}")
    print(f"  runtime_device:   {meta.get('runtime_device')}")
    print(f"  calibration_note: {meta.get('calibration_note')}")
    
    assert meta.get("is_calibrated") is False, "is_calibrated must be False until large-scale calibration is established!"
    assert meta.get("confidence_type") == "forward_pass_normalized", "confidence_type mismatch"
    assert "cpu" in meta.get("runtime_device", "").lower(), "runtime_device must identify CPU"
    assert "Model probabilities are normalized" in meta.get("calibration_note", ""), "Missing calibration note"
    print("  --> PASS: Decision metadata accurately reflects normalized CPU execution.")

    # 4. Fallback Verification
    print("\n[TEST 4] Fallback Behavior and Metadata")
    fb_payload = dict(payload)
    fb_payload["model"] = "force-fallback"
    req_fb = urllib.request.Request(f"{GATEWAY_URL}/v1/systemone", data=json.dumps(fb_payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req_fb) as resp_fb:
        res_fb = json.loads(resp_fb.read().decode())
    meta_fb = res_fb["decision_meta"]
    print(f"  Fallback Backend:       {meta_fb.get('backend')}")
    print(f"  Fallback Model:         {meta_fb.get('model_used')}")
    print(f"  Fallback is_calibrated: {meta_fb.get('is_calibrated')}")
    print(f"  Fallback conf_type:     {meta_fb.get('confidence_type')}")
    assert meta_fb.get("backend") == "ollama_fallback"
    assert meta_fb.get("model_used") == "nemotron-3-nano:4b"
    assert meta_fb.get("is_calibrated") is False
    assert meta_fb.get("confidence_type") == "heuristic_uncalibrated"
    print("  --> PASS: Fallback cleanly engaged and labeled as heuristic uncalibrated.")

    # 5. UI HTML Content Check
    print("\n[TEST 5] Decision Studio UI Labels Check")
    with urllib.request.urlopen(f"{GATEWAY_URL}/") as resp_ui:
        ui_html = resp_ui.read().decode("utf-8")
    assert "Ollaya + Laya CPU" in ui_html, "Missing CPU label in UI header"
    assert "ARM64 CPU" in ui_html, "Missing ARM64 CPU label in UI"
    assert "Statistical calibration has not yet been established" in ui_html, "Missing honest calibration note in UI"
    assert "valCatWinProb" in ui_html, "Missing winning probability ID in UI"
    print("  --> PASS: UI accurately renders CPU hardware, normalized calibration note, and winning probability.")

    print("\n=======================================================")
    print(" ALL 5 AUDIT REGRESSION TESTS PASSED CLEANLY! ")
    print("=======================================================")

if __name__ == "__main__":
    run_regression()
