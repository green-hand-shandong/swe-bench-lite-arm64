"""SWE-ARM 通用 Dockerfile 转换器：把 sympy 验证过的 ARM 化原则参数化。

用法: python3 arm_convert.py <repo_slug>   # repo_slug 如 matplotlib/matplotlib
"""
import os
import re
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
from datasets import load_dataset

PARQUET = "/data2/gxw/agent-sandbox-platform/docs/swe-bench-lite-arm.parquet"
TASKS_DIR = Path("/tmp/swe-tasks/tasks")
CTX_DIR = Path("/tmp/arm-contexts")
MIRROR_DIR = Path("/tmp/arm-mirrors")
CONDA_URL = "https://mirrors.tuna.tsinghua.edu.cn/anaconda/miniconda/"
ENV_CHANNELS = """channels:
  - https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main/
  - https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/free/
  - https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/conda-forge/
  - nodefaults
"""


def gh_slug_to_dir(slug: str) -> str:
    return slug.replace("/", "__")


def make_mirror(slug: str) -> Path:
    """github mirror：本地裸仓，供构建内 clone（绕开 github 不稳）。"""
    d = gh_slug_to_dir(slug)
    mdir = MIRROR_DIR / d
    if not (mdir / "HEAD").exists():
        mdir.parent.mkdir(parents=True, exist_ok=True)
        print(f"[mirror] cloning {slug} ...", flush=True)
        subprocess.run(["git", "clone", "--mirror",
                        f"https://github.com/{slug}", str(mdir)], check=True)
    return mdir


def convert_dockerfile(slug: str, iid: str, df_path: Path) -> Path | None:
    s = df_path.read_text()
    orig = s

    # 1. platform
    s = s.replace("FROM --platform=linux/amd64", "FROM --platform=linux/arm64")

    # 2. miniconda x86 -> aarch64 (tuna)
    s = re.sub(r"https://repo\.anaconda\.com/miniconda/(Miniconda3-[\w.\-]+)Linux-x86_64\.sh",
               CONDA_URL + r"\1Linux-aarch64.sh", s)

    # 3. conda channels（幂等）
    s = s.replace("RUN conda config --append channels conda-forge",
                  "RUN conda config --append channels conda-forge && "
                  "conda config --remove channels defaults 2>/dev/null || true && "
                  "conda config --add channels " + CONDA_URL.replace("/miniconda/", "/pkgs/main/") + " && "
                  "conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/free/ && "
                  "conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/conda-forge/ && "
                  "conda config --set show_channel_urls yes")

    # 4. environment.yml channels → tuna + nodefaults（conda env create 会读文件内的 channels，
    #    优先级高于 conda config）
    s = re.sub(r"channels:\n(?:  - .*\n)+?(?=dependencies:)", ENV_CHANNELS, s, count=1)

    # 5. conda build pin 松绑：只处理 environment.yml 的依赖行（=x=y 三段式），
    #    用行级替换而非 heredoc 范围匹配（嵌套 heredoc 会错位）
    def fix_line(m):
        parts = m.group(2).split("=")
        if len(parts) >= 2:
            return f"{m.group(1)}{parts[0]}={'='.join(parts[1:2])}"
        return m.group(0)
    s = re.sub(r"^(  - )(\S+=\S+=\S+)$", fix_line, s, flags=re.M)

    # 6. pip 换清华源（所有 pip install 命令统一加速 + 容错）
    s = re.sub(r"pip install(?!.*-i https://pypi)", 
               "pip install -i https://pypi.tuna.tsinghua.edu.cn/simple", s)

    # 7. github clone → 本地 mirror（正则匹配任意 github URL，防个别 Dockerfile URL 笔误）
    mdir = f"/tmp/{gh_slug_to_dir(slug)}-mirror"
    s = re.sub(r"git clone -o origin --single-branch https://github\.com/\S+ /testbed",
               f"git clone {mdir} /testbed", s)
    s = s.replace("git remote remove origin", f"rm -rf {mdir}")

    # 8. 删除新鲜度守卫（COMMIT_COUNT / TARGET_EPOCH / tag 清理）
    s = re.sub(r"\nAFTER_TIMESTAMP=.*?COMMIT_COUNT=.*?\[ \"\$COMMIT_COUNT\" -eq 0 \] \|\| exit 1\n", "\n", s, flags=re.S)
    s = re.sub(r"\nTARGET_TIMESTAMP=.*?TARGET_EPOCH=.*?\n", "\n", s, flags=re.S)
    s = re.sub(r"\nfor tag in .*?git tag -d.*?\n", "\n", s, flags=re.S)

    # 9. COPY mirror 注入（首个 RUN <<EOF_ 前）
    if f"/tmp/{gh_slug_to_dir(slug)}-mirror" in s and "COPY" not in s:
        lines = s.splitlines()
        out, inserted = [], False
        for line in lines:
            if not inserted and line.startswith("RUN <<EOF_"):
                out.append(f"COPY {gh_slug_to_dir(slug)}-mirror /tmp/{gh_slug_to_dir(slug)}-mirror")
                out.append("")
                inserted = True
            out.append(line)
        s = "\n".join(out) + "\n"

    if s == orig:
        return None  # 无变化（如纯 apt/pip 仓库），调用方仍可用
    out = CTX_DIR / gh_slug_to_dir(slug)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"Dockerfile.{iid}").write_text(s)
    return out / f"Dockerfile.{iid}"


def main(slug: str):
    ds = load_dataset("parquet", data_files=PARQUET, split="train")
    insts = [x for x in ds if x["repo"] == slug]
    print(f"[{slug}] instances: {len(insts)}", flush=True)

    mirror = make_mirror(slug)
    d = gh_slug_to_dir(slug)
    ctx = CTX_DIR / d
    ctx.mkdir(parents=True, exist_ok=True)
    # mirror 放进构建 context（COPY 源）
    ctx_mirror = ctx / f"{d}-mirror"
    if not (ctx_mirror / "HEAD").exists():
        print(f"[{slug}] copying mirror into context ...", flush=True)
        subprocess.run(["cp", "-r", str(mirror), str(ctx_mirror)], check=True)

    ok, nofile = 0, []
    for inst in insts:
        iid = inst["instance_id"]
        df = TASKS_DIR / iid / "Dockerfile"
        if not df.exists():
            nofile.append(iid)
            continue
        p = convert_dockerfile(slug, iid, df)
        if p:
            ok += 1
        else:
            nofile.append(iid + "(nochange)")
    print(f"[{slug}] converted: {ok}, issues: {nofile[:3] if nofile else 'none'}")


if __name__ == "__main__":
    main(sys.argv[1])
