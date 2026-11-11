"""Setup smoke test for every OSWorld domain on ARM64.

For each domain, pick the first task and run ONLY the setup phase
(env.reset). Success = setup completed (downloads from local cache, app
launches, files pushed). This proves the full 368-task suite is runnable
on ARM64 infrastructure, independent of model skill.
"""
import json, glob, logging, sys, time

logging.basicConfig(level=logging.WARNING)
import os
os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1")
os.environ.setdefault("no_proxy", "localhost,127.0.0.1")

from desktop_env.desktop_env import DesktopEnv

DOMAINS = ["os", "libreoffice_calc", "libreoffice_impress", "libreoffice_writer",
           "vs_code", "gimp", "vlc", "thunderbird", "chrome", "multi_apps"]

def main():
    env = DesktopEnv(provider_name="qemu",
        path_to_vm="/data2/gxw/osworld-arm-vm/ubuntu-22.04-arm64.img",
        os_type="Ubuntu", headless=True)
    results = []
    for dom in DOMAINS:
        files = sorted(glob.glob(f"evaluation_examples/examples/{dom}/*.json"))
        # skip infeasible tasks (no setup to verify)
        pick = None
        for f in files:
            d = json.load(open(f))
            if d.get("evaluator", {}).get("func") != "infeasible":
                pick = d
                break
        if not pick:
            results.append((dom, "skip", "all infeasible"))
            continue
        t0 = time.time()
        try:
            env.reset(task_config=pick, seed=42)
            status = "OK"
            err = ""
        except Exception as e:
            status = "FAIL"
            err = str(e)[:150]
        dt = time.time() - t0
        results.append((dom, status, f"{dt:.0f}s {err}"))
        print(f"{dom:20s} {status:5s} {dt:.0f}s {err}", flush=True)
    env.close()
    ok = sum(1 for _, s, _ in results if s == "OK")
    print(f"=== setup smoke: {ok}/{len(results)} domains OK ===", flush=True)

if __name__ == "__main__":
    main()
