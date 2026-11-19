#!/usr/bin/env python3
"""Connectivity smoke: start every MCP server from commands.json, discover tools.

Run from repo root: mcpbench-env/bin/python check_all_servers.py
Prints one line per server: OK <n> tools / FAIL <reason>.
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp_modules.server_manager_persistent import PersistentMultiServerManager
from utils.local_server_config import LocalServerConfigLoader

# API-key servers fail without keys; still count connection if tools discovered
# (some servers list tools without valid keys).
TIMEOUT_PER_SERVER = 60


async def check_one(name, cfg):
    cwd = cfg.get("cwd", "")
    if cwd.startswith("../"):
        cwd = f"mcp_servers/{cwd[3:]}"  # same conversion as benchmark.runner
    manager = PersistentMultiServerManager([{
        "name": name,
        "command": cfg["cmd"].split(),
        "env": {k: os.environ.get(k, "") for k in cfg.get("env", [])},
        "cwd": cwd,
        **({"transport": "http", "port": cfg["port"], "endpoint": cfg.get("endpoint", "/mcp")}
           if cfg.get("transport") == "http" else {}),
    }], filter_problematic_tools=False)
    try:
        tools = await asyncio.wait_for(manager.connect_all_servers(), timeout=TIMEOUT_PER_SERVER)
        return name, len(tools), None
    except asyncio.TimeoutError:
        return name, 0, "timeout"
    except Exception as e:
        return name, 0, f"{type(e).__name__}: {str(e)[:70]}"
    finally:
        try:
            await manager.close_all_connections()
        except Exception:
            pass


async def main():
    loader = LocalServerConfigLoader()
    servers = loader.local_commands
    only = sys.argv[1:] if len(sys.argv) > 1 else None

    ok, fail = [], []
    for name, cfg in servers.items():
        if only and name not in only:
            continue
        name_r, ntools, err = await check_one(name, cfg)
        if err is None and ntools > 0:
            ok.append(name_r)
            print(f"[OK] {name_r}: {ntools} tools", flush=True)
        else:
            fail.append((name_r, err or "0 tools"))
            print(f"[FAIL] {name_r}: {err or '0 tools'}", flush=True)

    print(f"\n=== {len(ok)} OK / {len(fail)} FAIL / {len(ok)+len(fail)} total ===")
    if fail:
        print("Failed:", ", ".join(n for n, _ in fail))


if __name__ == "__main__":
    asyncio.run(main())
