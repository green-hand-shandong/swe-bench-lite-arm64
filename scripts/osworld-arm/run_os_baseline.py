"""OSWorld ARM baseline: run os-domain tasks with a vllm-served model.

Simple agentic loop: screenshot -> model decides action (pyautogui code or
bash) -> execute -> repeat. Uses the same env/eval as official OSWorld.
"""
import json, os, re, sys, time, glob, base64, logging

logging.basicConfig(level=logging.WARNING)
os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1")
os.environ.setdefault("no_proxy", "localhost,127.0.0.1")

import requests
from desktop_env.desktop_env import DesktopEnv

API_BASE = os.environ.get("OSWORLD_API_BASE", "http://127.0.0.1:8000/v1")
MODEL = os.environ.get("OSWORLD_MODEL", "/model")
MAX_STEPS = int(os.environ.get("OSWORLD_MAX_STEPS", 8))
DOMAIN = os.environ.get("OSWORLD_DOMAIN", "os")
OUT = os.environ.get("OSWORLD_OUT", "/data2/gxw/osworld-arm/results-os.jsonl")

SYSTEM = """You are a GUI agent controlling an Ubuntu 22.04 (XFCE) desktop via pyautogui.
Each turn you get a screenshot and the user's goal. Reply with ONE action, in exactly one of these forms:

PYAUTOGUI: <single python statement using pyautogui, e.g. pyautogui.hotkey('ctrl','alt','t')>
BASH: <one shell command to run in a terminal>

/no_think — reply with ONLY the action line, no explanation. Rules: one action per turn; prefer terminal (ctrl+alt+t) for file tasks; use absolute paths; when the goal is achieved or impossible, reply exactly DONE."""

def chat(messages, max_tokens=512):
    r = requests.post(f"{API_BASE}/chat/completions", json={
        "model": MODEL, "messages": messages, "max_tokens": max_tokens,
        "temperature": 0.0}, timeout=600)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def parse_action(text):
    m = re.search(r"PYAUTOGUI\s*:\s*(.+)", text, re.I)
    if m: return ("pyautogui", m.group(1).strip())
    m = re.search(r"BASH\s*:\s*(.+)", text, re.I)
    if m: return ("bash", m.group(1).strip())
    if re.search(r"\bDONE\b", text, re.I): return ("done", "")
    return ("unknown", text[:200])

def run_task(env, cfg):
    obs = env.reset(task_config=cfg, seed=42)
    instruction = cfg["instruction"]
    history = []
    USE_VISION = os.environ.get("OSWORLD_VISION", "0") == "1"
    for step in range(MAX_STEPS):
        msgs = [{"role": "system", "content": SYSTEM}]
        if USE_VISION:
            shot = env.render(mode="rgb_array")
            b64 = base64.b64encode(shot).decode() if shot else ""
            content = [{"type": "text", "text": f"Goal: {instruction}\nHistory: {history[-4:]}\nScreenshot attached. Next single action?"}]
            if b64:
                content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})
            msgs.append({"role": "user", "content": content})
        else:
            msgs.append({"role": "user", "content": f"Goal: {instruction}\nHistory: {history[-4:]}\nNext single action?"})
        try:
            reply = chat(msgs)
        except Exception as e:
            history.append(f"step{step}: api-error {e}")
            continue
        kind, arg = parse_action(reply)
        history.append(f"step{step}: {kind} {arg[:80]}")
        if kind == "done":
            break
        if kind == "pyautogui":
            env.controller.execute_python_command(arg)
        elif kind == "bash":
            env.controller.execute_python_command(
                f"import pyautogui,time; pyautogui.hotkey('ctrl','alt','t'); time.sleep(1); "
                f"pyautogui.typewrite({arg!r}, interval=0.02); pyautogui.press('enter'); time.sleep(1)")
        time.sleep(2)
    return env.evaluate(), history

def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    files = sorted(glob.glob(f"evaluation_examples/examples/{DOMAIN}/*.json"))
    env = DesktopEnv(provider_name="qemu",
        path_to_vm="/data2/gxw/osworld-arm-vm/ubuntu-22.04-arm64.img",
        os_type="Ubuntu", headless=True)
    results = []
    for f in files:
        cfg = json.load(open(f))
        tid = cfg["id"]
        if only and only != tid: continue
        if cfg.get("evaluator", {}).get("func") == "infeasible":
            continue
        t0 = time.time()
        try:
            score, history = run_task(env, cfg)
        except Exception as e:
            score, history = None, [f"fatal: {e}"]
        dt = time.time() - t0
        rec = {"id": tid, "score": score, "seconds": round(dt), "history": history}
        results.append(rec)
        print(f"{tid} score={score} {dt:.0f}s", flush=True)
        with open(OUT, "a") as fh:
            fh.write(json.dumps(rec) + "\n")
    env.close()
    ok = [r for r in results if r["score"] == 1.0]
    print(f"=== {DOMAIN} baseline: {len(ok)}/{len(results)} resolved ===", flush=True)

if __name__ == "__main__":
    main()
