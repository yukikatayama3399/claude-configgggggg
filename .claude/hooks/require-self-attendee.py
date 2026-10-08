#!/usr/bin/env python3
# ============================================================
# PreToolUse hook: カレンダー予定を作るとき、本人を必ず参加者に入れる
#
# 経緯: gog で作った予定で、主催者である本人(yuki.katayama@fout.jp)が
# 参加者リストに入っていなかった (2026-10-08 発覚)。
# API で予定を作ると、attendees に自分を書かない限り主催者は参加者に入らない。
#
# 対象 (自分が attendees に入っていなければ実行前にブロックする):
#   - gog calendar create/add/new           … --attendees に本人が必須
#   - gog calendar update/edit/set --attendees … 置き換えなので本人が必須
#   - gws calendar +insert                   … --attendee に本人が必須
#   - gws calendar events insert/import      … --json の attendees に本人が必須
#   - gws calendar events update/patch       … attendees を渡すなら本人が必須
#   - gws calendar events quickAdd           … attendees を渡せないので禁止
#   - MCP Google_Calendar create_event       … attendees に本人が必須
#   - MCP Google_Calendar update_event       … 本人を removedAttendeeEmails に入れたら禁止
#
# 本人のアドレスは環境変数 CALENDAR_SELF_EMAIL で上書きできる。
# ブロックは exit 2 + stderr (Claude にそのまま理由が返る)。
# ============================================================
import json
import os
import re
import shlex
import sys

SELF = os.environ.get("CALENDAR_SELF_EMAIL", "yuki.katayama@fout.jp").lower()

SEPARATORS = {";", "&&", "||", "|", "&", "(", ")", "`"}


def deny(reason: str) -> None:
    print(
        f"[require-self-attendee] ブロック: {reason}\n"
        f"予定を作る/参加者を置き換えるときは、本人 {SELF} を必ず参加者に含めること。"
        " (CLAUDE.md「カレンダー予定には本人を必ず参加者に入れる」参照)",
        file=sys.stderr,
    )
    sys.exit(2)


def has_self(values) -> bool:
    for v in values:
        for part in re.split(r"[,\s]+", str(v)):
            if part.strip().lower() == SELF:
                return True
    return False


def tokenize(text: str):
    lex = shlex.shlex(text, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    return list(lex)


def segments(cmd: str):
    """コマンド文字列を単純コマンド(トークン列)に分割する。"""
    cmd = cmd.replace("\\\n", " ")
    try:
        # 行ごとに切れるならそうする(改行もコマンド区切りなので)
        tokens = []
        for line in cmd.split("\n"):
            tokens += tokenize(line) + [";"]
    except ValueError:
        # 複数行にまたがるクォートなど
        try:
            tokens = tokenize(cmd)
        except ValueError:
            tokens = cmd.split()
    seg = []
    for t in tokens:
        if t in SEPARATORS:
            if seg:
                yield seg
            seg = []
        else:
            seg.append(t)
    if seg:
        yield seg


def flag_values(args, *names):
    """--name=value / --name value の値を全部集める。"""
    out = []
    for i, a in enumerate(args):
        for n in names:
            if a == n and i + 1 < len(args):
                out.append(args[i + 1])
            elif a.startswith(n + "="):
                out.append(a[len(n) + 1:])
    return out


def has_flag(args, name):
    return any(a == name or a.startswith(name + "=") for a in args)


def positional_after(args, start):
    """args[start:] から最初の非フラグトークンの位置。"""
    for i in range(start, len(args)):
        if not args[i].startswith("-"):
            return i
    return None


# 値を取る gog のグローバルフラグ (--flag value 形式のとき値を読み飛ばす)
GOG_VALUE_FLAGS = {
    "-a", "--account", "--client", "--home", "--access-token",
    "--enable-commands", "--disable-commands", "--select", "--color",
}


def first_command(args, value_flags):
    """グローバルフラグを読み飛ばして最初のサブコマンドの位置を返す。"""
    i = 0
    while i < len(args):
        a = args[i]
        if a.startswith("-"):
            i += 2 if (a in value_flags) else 1
            continue
        return i
    return None


def check_gog(args):
    ci = first_command(args, GOG_VALUE_FLAGS)
    if ci is None or args[ci] not in ("calendar", "cal"):
        return
    si = positional_after(args, ci + 1)
    if si is None:
        return
    sub = args[si]
    rest = args[si + 1:]
    if sub in ("create", "add", "new"):
        vals = flag_values(rest, "--attendees")
        if not vals or not has_self(vals):
            deny("gog calendar create の --attendees に本人が入っていない")
    elif sub in ("update", "edit", "set"):
        vals = flag_values(rest, "--attendees")
        if has_flag(rest, "--attendees") and not has_self(vals):
            deny("gog calendar update --attendees は参加者を置き換えるため、本人が外れる")


def attendees_in_json(text):
    """JSON 文字列から attendees のメールを取り出す。None = attendees キー無し。"""
    try:
        body = json.loads(text)
    except (ValueError, TypeError):
        if '"attendees"' not in text:
            return None
        return re.findall(r"[\w.+-]+@[\w.-]+", text.split('"attendees"', 1)[1])
    if not isinstance(body, dict) or "attendees" not in body:
        return None
    return [a.get("email", "") for a in body.get("attendees") or [] if isinstance(a, dict)]


def check_gws(args):
    ci = first_command(args, set())
    if ci is None or args[ci] != "calendar":
        return
    rest = args[ci + 1:]
    if not rest:
        return
    if rest[0] == "+insert":
        if not has_self(flag_values(rest, "--attendee")):
            deny("gws calendar +insert の --attendee に本人が入っていない")
        return
    if rest[0] != "events" or len(rest) < 2:
        return
    method = rest[1]
    if method == "quickAdd":
        deny("gws calendar events quickAdd は参加者を指定できない。events insert か +insert を使う")
    jsons = flag_values(rest, "--json")
    emails = None
    for j in jsons:
        found = attendees_in_json(j)
        if found is not None:
            emails = (emails or []) + found
    if method in ("insert", "import"):
        if not emails or not has_self(emails):
            deny(f"gws calendar events {method} の --json に attendees(本人入り) が無い")
    elif method in ("update", "patch"):
        if emails is not None and not has_self(emails):
            deny(f"gws calendar events {method} で attendees を置き換えると本人が外れる")


def check_bash(cmd: str):
    if "gog" not in cmd and "gws" not in cmd:
        return
    for seg in segments(cmd):
        for i, tok in enumerate(seg):
            base = os.path.basename(tok)
            if base == "gog":
                check_gog(seg[i + 1:])
                break
            if base == "gws":
                check_gws(seg[i + 1:])
                break


def check_mcp_create(inp):
    emails = [a.get("email", "") for a in inp.get("attendees") or [] if isinstance(a, dict)]
    emails += inp.get("attendeeEmails") or []
    if not has_self(emails):
        deny("Google Calendar create_event の attendees に本人が入っていない")


def check_mcp_update(inp):
    if has_self(inp.get("removedAttendeeEmails") or []):
        deny("Google Calendar update_event で本人を参加者から外そうとしている")


def main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return
    tool = data.get("tool_name", "")
    inp = data.get("tool_input") or {}
    if tool == "Bash":
        check_bash(inp.get("command", ""))
    elif tool.endswith("Google_Calendar__create_event"):
        check_mcp_create(inp)
    elif tool.endswith("Google_Calendar__update_event"):
        check_mcp_update(inp)


if __name__ == "__main__":
    main()
