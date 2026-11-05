import os, subprocess
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
from datasets import load_dataset
ds = load_dataset("parquet", data_files="/data2/gxw/agent-sandbox-platform/docs/swe-bench-lite-arm.parquet", split="train")
sympy = [x for x in ds if x["repo"] == "sympy/sympy"]
ok = 0
for inst in sympy:
    iid = inst["instance_id"]
    arm = f"sweb.eval.arm64.{iid}:latest"
    want = inst["image"]
    r = subprocess.run(["docker", "images", "-q", arm], capture_output=True, text=True)
    if r.stdout.strip():
        subprocess.run(["docker", "tag", arm, want], capture_output=True)
        ok += 1
print(f"retagged {ok}/77")
