import json, logging
logging.basicConfig(level=logging.WARNING)

from desktop_env.desktop_env import DesktopEnv

task_id = "37887e8c-da15-4192-923c-08fa390a176d"
cfg = json.load(open(f"/data2/gxw/osworld-arm/evaluation_examples/examples/os/{task_id}.json"))

env = DesktopEnv(
    provider_name="qemu",
    path_to_vm="/data2/gxw/osworld-arm-vm/ubuntu-22.04-arm64.img",
    os_type="Ubuntu",
    headless=True,
)
env.reset(task_config=cfg, seed=42)
print("=== TASK SETUP DONE ===", flush=True)

oracle = r"""
cd /tmp/test_files/old_files
for f in *.txt; do tar czf "${f%.txt}.tar.gz" "$f" && rm "$f"; done
echo ORACLE-DONE
"""
r = env.controller.run_bash_script(oracle, timeout=60)
print("oracle result:", str(r)[:150], flush=True)

result = env.evaluate()
print("=== EVALUATION RESULT ===", flush=True)
print("score:", result, flush=True)

env.close()
