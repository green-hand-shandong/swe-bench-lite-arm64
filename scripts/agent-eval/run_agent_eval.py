#!/usr/bin/env python3
"""SWE-Lite-ARM 自动化测评管线：模型 API → 逐题智能体循环 → 自动判分 → 报告。

用法:
  # 1. 单模型自动化（OpenAI 兼容 API，如 vllm-ascend 本地服务）
  python3 run_agent_eval.py \
    --api-base http://127.0.0.1:8000/v1 \
    --model Qwen2.5-32B-Instruct \
    --run_id qwen30b-v1 \
    --max_instances 30        # 0=全部300题

  # 2. 已有预测文件，只跑判分
  python3 run_agent_eval.py --predictions my.jsonl --run_id xxx --judge-only

流程:
  逐题: 起容器(题目镜像) → 喂 problem_statement → 模型生成 patch(单轮/多轮可选)
       → git diff 收集 → 汇总 predictions.jsonl → swebench 判分 → resolved 报告
"""
import argparse, json, os, subprocess, time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
DATASET = ROOT / 'docs' / 'swe-bench-lite-arm.parquet'
WORKDIR = Path('/data2/swe-agent-eval')


def load_instances(limit):
    df = pd.read_parquet(DATASET)
    if limit:
        df = df.head(limit)
    return df.to_dict('records')


def run_single_turn(args, inst, out_dir):
    """单轮模式：把题目描述直接给模型，要求输出完整 patch。
    带指数退避重试：vllm 长推理服务偶发连接重置/超时，重试后通常恢复。"""
    import requests as rq
    import time as _time
    prompt = f"""You are a software engineer fixing a bug in a real repository.

The repository is checked out at /testbed in a Docker container. Below is the bug
report. Reply with ONLY the patch in unified git diff format (git apply compatible),
no explanations.

<bug_report>
{inst['problem_statement'][:12000]}
</bug_report>"""
    payload = {
        'model': args.model,
        'messages': [{'role': 'user', 'content': prompt}],
        'max_tokens': args.max_tokens,
        'temperature': args.temperature,
    }
    last_err = None
    for attempt in range(1, 6):  # 最多 5 次尝试
        try:
            r = rq.post(f'{args.api_base}/chat/completions', json=payload,
                        timeout=args.api_timeout)
            r.raise_for_status()
            break
        except (rq.exceptions.ConnectionError, rq.exceptions.ReadTimeout,
                rq.exceptions.HTTPError) as e:
            last_err = e
            wait = min(30 * (2 ** (attempt - 1)), 300)  # 30/60/120/240/300s
            print(f'  [retry {attempt}/5] {type(e).__name__}: {e} -> wait {wait}s')
            _time.sleep(wait)
    else:
        raise RuntimeError(f'API failed after 5 retries: {last_err}')
    content = r.json()['choices'][0]['message']['content']
    # 剥离思考段（Qwen3/DeepSeek-R1 类思考模型）
    if '</think' in content:
        content = content.split('</think')[-1]
    # 提取 diff：优先找 diff --git 开头的代码块
    if '```' in content:
        blocks = content.split('```')
        for block in blocks:
            b = block.strip()
            if b.startswith('diff --git'):
                return b
    # 没有代码块标记时，找 diff --git 行到结尾
    if 'diff --git' in content:
        idx = content.find('diff --git')
        return content[idx:]
    return content


def collect_patch_from_container(container, inst_id):
    """多轮模式后从容器收集 git diff。"""
    r = subprocess.run(['docker', 'exec', container, 'git', '-C', '/testbed', 'diff'],
                       capture_output=True, text=True)
    return r.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--api-base', default='http://127.0.0.1:8000/v1')
    ap.add_argument('--model', required=False)
    ap.add_argument('--run_id', required=True)
    ap.add_argument('--max_instances', type=int, default=0, help='0=全部300题')
    ap.add_argument('--max_tokens', type=int, default=4096)
    ap.add_argument('--temperature', type=float, default=0.0)
    ap.add_argument('--api_timeout', type=int, default=600)
    ap.add_argument('--predictions', help='已有预测文件（跳过推理直接判分）')
    ap.add_argument('--judge-only', action='store_true')
    ap.add_argument('--max_workers', type=int, default=4)
    ap.add_argument('--instance_ids', nargs='*', help='指定题目')
    args = ap.parse_args()

    out_dir = WORKDIR / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    pred_file = out_dir / 'predictions.jsonl'

    # ---------- 阶段 1: 推理（生成预测） ----------
    if args.predictions:
        pred_file = Path(args.predictions)
    elif not args.judge_only:
        insts = load_instances(args.max_instances)
        if args.instance_ids:
            insts = [i for i in insts if i['instance_id'] in args.instance_ids]
        done = set()
        if pred_file.exists():  # 断点续跑
            for line in open(pred_file):
                done.add(json.loads(line)['instance_id'])
        print(f'[infer] {len(insts)} instances, {len(done)} already done')
        with open(pred_file, 'a') as f:
            for n, inst in enumerate(insts):
                iid = inst['instance_id']
                if iid in done:
                    continue
                print(f'[{n+1}/{len(insts)}] {iid}')
                try:
                    patch = run_single_turn(args, inst, out_dir)
                except Exception as e:
                    print(f'  API error: {e}')
                    patch = ''
                f.write(json.dumps({'instance_id': iid, 'model_patch': patch,
                                    'model_name_or_path': args.model}) + '\n')
                f.flush()

    # ---------- 阶段 2: 判分 ----------
    print('[judge] running swebench evaluation...')
    env = dict(os.environ, HF_ENDPOINT='https://hf-mirror.com')
    cmd = [
        'python3', '-m', 'swebench.harness.run_evaluation',
        '--dataset_name', str(DATASET),
        '--predictions_path', str(pred_file),
        '--run_id', args.run_id,
        '--max_workers', str(args.max_workers),
    ]
    if args.instance_ids:
        cmd += ['--instance_ids'] + args.instance_ids
    subprocess.run(cmd, env=env, cwd=ROOT)

    # ---------- 阶段 3: 报告 ----------
    report = ROOT / f'{args.run_id}.{args.run_id}.json'
    if report.exists():
        r = json.load(open(report))
        total = r['total_instances']
        resolved = r['resolved_instances']
        print(f"\n===== RESULT: {args.model or args.run_id} =====")
        print(f"resolved: {resolved}/{total} = {resolved/total*100:.1f}%")
        print(f"report: {report}")


if __name__ == '__main__':
    main()
