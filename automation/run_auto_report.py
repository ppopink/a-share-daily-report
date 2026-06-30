#!/usr/bin/env python3
"""
本地自动运行每日选股报告。

用途：
- 14:30 生成盘中预览版；
- 16:00 生成收盘正式版；
- 跑完后同步前端数据，并自动 git commit / push。
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable


PROJECT_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DATA_DIR = PROJECT_DIR / "A股每日选股报告页面设计" / "public" / "data"
STATUS_FILE = FRONTEND_DATA_DIR / "automation_status.json"


def now_shanghai() -> dt.datetime:
    return dt.datetime.now()


def is_weekday(date_value: dt.date) -> bool:
    return date_value.weekday() < 5


def run_command(args: Iterable[str], *, allow_fail: bool = False) -> subprocess.CompletedProcess[str]:
    cmd = [str(item) for item in args]
    print(f"$ {' '.join(cmd)}", flush=True)
    result = subprocess.run(
        cmd,
        cwd=PROJECT_DIR,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n", flush=True)
    if result.returncode != 0 and not allow_fail:
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(cmd)}")
    return result


def git_output(args: Iterable[str], default: str = "") -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=PROJECT_DIR,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return default


def has_git_changes() -> bool:
    return bool(git_output(["status", "--porcelain"]))


def write_status(payload: dict) -> None:
    FRONTEND_DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def build_main_command(args: argparse.Namespace) -> list[str]:
    cmd = [
        args.python,
        "main.py",
        "--mode",
        args.mode,
    ]
    if args.test:
        cmd.extend(["--test", str(args.test)])
    if args.refresh_cache:
        cmd.append("--refresh-cache")
    if args.no_money_flow_api:
        cmd.append("--no-money-flow-api")
    return cmd


def commit_and_push(run_type: str, run_at: dt.datetime, skip_push: bool) -> str:
    if not has_git_changes():
        print("[自动化] 没有检测到需要提交的变更。")
        return git_output(["rev-parse", "--short", "HEAD"], "unknown")

    run_command(["git", "add", "."])
    message = f"auto {run_type} stock report {run_at.strftime('%Y-%m-%d %H:%M')}"
    run_command(["git", "commit", "-m", message], allow_fail=True)
    commit = git_output(["rev-parse", "--short", "HEAD"], "unknown")
    if skip_push:
        print("[自动化] 已跳过 git push。")
    else:
        run_command(["git", "push", "origin", "main"])
    return commit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="本地定时生成并发布 A股每日选股报告")
    parser.add_argument("--run-type", choices=["intraday", "close"], required=True, help="intraday=14:30盘中预览；close=16:00收盘正式")
    parser.add_argument("--mode", choices=["normal", "strict", "loose"], default="normal", help="主运行模式，默认 normal；main.py 仍会生成三种模式前端数据")
    parser.add_argument("--python", default=sys.executable or "/usr/bin/python3", help="Python 解释器路径")
    parser.add_argument("--test", type=int, default=None, help="测试运行时只扫描 N 只股票")
    parser.add_argument("--no-refresh-cache", dest="refresh_cache", action="store_false", help="不强制刷新缓存")
    parser.add_argument("--no-money-flow-api", action="store_true", help="跳过资金流 API，缩短运行时间")
    parser.add_argument("--skip-push", action="store_true", help="只提交不推送")
    parser.add_argument("--dry-run", action="store_true", help="只打印将执行的动作")
    parser.set_defaults(refresh_cache=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_at = now_shanghai()
    today = run_at.date()

    print("=" * 80)
    print(f"[自动化] A股每日选股报告: {args.run_type}")
    print(f"[自动化] 时间: {run_at.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[自动化] 项目: {PROJECT_DIR}")
    print("=" * 80)

    if not is_weekday(today):
        payload = {
            "lastRunAt": run_at.strftime("%Y-%m-%d %H:%M:%S"),
            "runType": args.run_type,
            "status": "skipped",
            "reason": "weekend",
            "note": "周末休市，未执行选股。",
        }
        write_status(payload)
        print("[自动化] 周末休市，跳过。")
        return 0

    cmd = build_main_command(args)
    payload = {
        "lastRunAt": run_at.strftime("%Y-%m-%d %H:%M:%S"),
        "runType": args.run_type,
        "status": "dry_run" if args.dry_run else "running",
        "reason": "",
        "note": "盘中预览版，收盘后还会更新。" if args.run_type == "intraday" else "收盘正式版。",
        "command": " ".join(cmd),
    }
    write_status(payload)

    if args.dry_run:
        print("[自动化] dry-run，仅打印命令，不执行。")
        print(" ".join(cmd))
        return 0

    try:
        run_command(cmd)
        commit = commit_and_push(args.run_type, run_at, args.skip_push)
        payload.update({
            "status": "success",
            "commitSha": commit,
            "finishedAt": now_shanghai().strftime("%Y-%m-%d %H:%M:%S"),
        })
        write_status(payload)
        print(f"[自动化] 完成，commit={commit}")
        return 0
    except Exception as exc:
        payload.update({
            "status": "failed",
            "reason": str(exc),
            "finishedAt": now_shanghai().strftime("%Y-%m-%d %H:%M:%S"),
        })
        write_status(payload)
        print(f"[自动化] 失败: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
