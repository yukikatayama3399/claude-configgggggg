#!/usr/bin/env python3
"""PreToolUse フック: Slack 送信を「決まった宛先」だけ自動許可する。

CLAUDE.md「送信の絶対ルール」の例外（片山さん本人への DM と、
あらかじめ決めたチャンネルへの定期投稿）だけを、確認なしで通す。
それ以外の宛先は何もしない（= 通常どおり許可確認が出る）。
2026-11-04 片山さん承認。
"""
import json
import sys

ALLOWED_CHANNELS = {
    "U0B7FMCR8JU",  # 片山さん本人への DM
    "C0B8U7F95A6",  # #ai-news
    "C0B9NH3JUTS",  # #competitor-watch
}

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)

if not data.get("tool_name", "").endswith("slack_send_message"):
    sys.exit(0)
channel = str((data.get("tool_input") or {}).get("channel_id", "")).strip()
if channel in ALLOWED_CHANNELS:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": f"決まった宛先 {channel} への定期投稿（CLAUDE.md 送信ルールの例外）",
        }
    }, ensure_ascii=False))
sys.exit(0)
