#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_STATE_FILE = ".runtime/admin-login-guard/state.json"


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "devices": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_ban_until(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def is_active(device: dict[str, Any], now: datetime) -> bool:
    ban_until = parse_ban_until(device.get("banUntil"))
    return bool(ban_until and ban_until > now)


def command_list(args: argparse.Namespace) -> int:
    state = load_state(Path(args.state_file))
    devices = state.get("devices", {})
    now = datetime.now(timezone.utc)

    rows: list[tuple[str, dict[str, Any]]] = []
    for fingerprint, device in devices.items():
        if args.active_only and not is_active(device, now):
            continue
        rows.append((fingerprint, device))

    if not rows:
        print("No matching admin login guard records.")
        return 0

    for fingerprint, device in sorted(rows, key=lambda item: item[1].get("banUntil") or "", reverse=True):
        print(f"device_key={device.get('deviceKey', '-')}")
        print(f"fingerprint={fingerprint}")
        print(f"failure_count={device.get('failureCount', 0)}")
        print(f"ban_level={device.get('banLevel', 0)}")
        print(f"ban_until={device.get('banUntil') or '-'}")
        print(f"active_ban={'yes' if is_active(device, now) else 'no'}")
        print(f"last_username={device.get('lastUsername') or '-'}")
        print(f"last_ip={device.get('lastIp') or '-'}")
        print(f"last_failure_at={device.get('lastFailureAt') or '-'}")
        print(f"last_success_at={device.get('lastSuccessAt') or '-'}")
        print("")
    return 0


def command_unblock(args: argparse.Namespace) -> int:
    state_path = Path(args.state_file)
    state = load_state(state_path)
    devices = state.get("devices", {})

    target_fingerprint: str | None = None
    if args.fingerprint:
        target_fingerprint = args.fingerprint
    else:
        for fingerprint, device in devices.items():
            if device.get("deviceKey") == args.device_key:
                target_fingerprint = fingerprint
                break

    if not target_fingerprint or target_fingerprint not in devices:
        raise SystemExit("Target device record not found.")

    device = devices[target_fingerprint]
    device["failureCount"] = 0
    device["banLevel"] = 0
    device["banUntil"] = None
    save_state(state_path, state)
    print(f"Unblocked device_key={device.get('deviceKey', '-')}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Admin console login guard inspector")
    parser.add_argument("--state-file", default=DEFAULT_STATE_FILE)
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--active-only", action="store_true")
    list_parser.set_defaults(func=command_list)

    unblock_parser = subparsers.add_parser("unblock")
    unblock_group = unblock_parser.add_mutually_exclusive_group(required=True)
    unblock_group.add_argument("--device-key")
    unblock_group.add_argument("--fingerprint")
    unblock_parser.set_defaults(func=command_unblock)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
