"""从构建失败的 Dockerfile 中松绑 aarch64 缺失的 conda 包。
对每个失败实例：提取 environment.yml → 试解 → 从 PackagesNotFoundError 移除缺失包 → 重试（最多3轮）。"""
import re, subprocess, sys
from pathlib import Path

MC_SETUP = """
apt-get update -qq > /dev/null 2>&1; apt-get install -y -qq wget bzip2 > /dev/null 2>&1
wget -q https://mirrors.tuna.tsinghua.edu.cn/anaconda/miniconda/Miniconda3-py311_23.11.0-2-Linux-aarch64.sh -O /tmp/mc.sh
bash /tmp/mc.sh -b -p /opt/mc > /dev/null 2>&1
"""

def solve(env_path: str) -> tuple[bool, list[str]]:
    r = subprocess.run(
        ["docker", "run", "--rm", "-v", f"{env_path}:/root/environment.yml",
         "python:3.12-slim-bookworm", "bash", "-c",
         MC_SETUP + "timeout 500 /opt/mc/bin/conda env create -f /root/environment.yml 2>&1"],
        capture_output=True, text=True, timeout=700)
    out = r.stdout
    if "PackagesNotFoundError" not in out:
        return ("done" in out.lower() or "conda deactivate" in out), []
    missing = []
    in_block = False
    for line in out.splitlines():
        if "PackagesNotFoundError" in line:
            in_block = True; continue
        if in_block:
            if line.startswith("  - "):
                missing.append(line.strip().split("=")[0])
            elif line.strip() and not line.startswith("  - "):
                break
    return False, missing


def fix_instance(ctx: Path, iid: str) -> str:
    df = ctx / f"Dockerfile.{iid}"
    s = df.read_text()
    # 提取内层 environment.yml
    m = re.search(r"cat <<'EOF_\w+'[^\n]*\n(.*?)\nprefix: /opt/miniconda3/envs/testbed\n", s, re.S)
    if not m:
        return "no-env"
    env = m.group(1)
    tmp = Path("/tmp/fix-env.yml")
    tmp.write_text(env)
    for round_ in range(3):
        ok, missing = solve(str(tmp))
        if ok:
            break
        if not missing:
            return "solve-crash"
        # 从 env 文本移除缺失包（conda 主依赖段和 pip 段都试）
        for pkg in missing:
            base = pkg.split("=")[0]
            env = re.sub(rf"^  - {re.escape(base)}=.*\n", "", env, flags=re.M)
            env = re.sub(rf"^      - {re.escape(base)}==.*\n", "", env, flags=re.M)
        tmp.write_text(env)
    else:
        return "still-failing"
    # 写回 Dockerfile：替换 environment.yml heredoc 内容
    s = df.read_text()
    s = re.sub(r"(cat <<'EOF_\w+'[^\n]*\n).*?(\nprefix: /opt/miniconda3/envs/testbed\n)",
               lambda m2: m2.group(1) + tmp.read_text() + m2.group(2), s, flags=re.S)
    df.write_text(s)
    return f"fixed-remove:{len(missing)}"


if __name__ == "__main__":
    ctx = Path(sys.argv[1])
    fails = Path(sys.argv[2]).read_text().splitlines()
    for line in fails:
        iid = line.split()[0]
        if line.split()[-1] == "skip-exists":
            continue
        r = fix_instance(ctx, iid)
        print(iid, "->", r)
