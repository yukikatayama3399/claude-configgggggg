#!/usr/bin/env python3
"""自分主催＋ゲストありの予定に guestsCanModify=true を付けて回る。

Google Calendar には「ゲストに予定の変更を許可する」のデフォルト設定が存在せず
(API の guestsCanModify は既定 false)、予定ごとに手でチェックするしかない。
このスクリプトはその取りこぼしを後追いで潰す。

対象の条件（すべて満たすものだけ）:
  - 主催者が自分 (organizer.self)
  - 自分以外の人間のゲストが1人以上いる（会議室などのリソースは数えない）
  - guestsCanModify がまだ true でない
  - status が cancelled でない

既定はドライラン。実際に書き込むには --apply を付ける。
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys

# ゲストを持てない種類の予定。API 上も guestsCanModify は意味を持たない。
SKIP_EVENT_TYPES = {"workingLocation", "outOfOffice", "focusTime", "birthday", "fromGmail"}

LIST_FIELDS = (
    "nextPageToken,"
    "items(id,summary,status,eventType,guestsCanModify,recurringEventId,"
    "organizer(email,self),attendees(email,self,resource))"
)


def gws(args: list[str]) -> dict:
    proc = subprocess.run(["gws", *args], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"gws {' '.join(args)} failed:\n{proc.stderr.strip()}")
    out = proc.stdout.strip()
    return json.loads(out) if out else {}


def list_events(calendar_id: str, time_min: str, time_max: str) -> list[dict]:
    """対象期間に実体のある予定を集める。

    singleEvents=false にしているのは、繰り返し予定を展開せず「親」だけを
    掴むため。展開してしまうと1回ぶんの例外インスタンスばかり patch することに
    なり、本体の既定が変わらない。例外インスタンス自体は親とは別に
    recurringEventId 付きで返ってくるので、そちらもそのまま対象になる。
    """
    events: list[dict] = []
    page_token: str | None = None
    while True:
        params = {
            "calendarId": calendar_id,
            "singleEvents": False,
            "showDeleted": False,
            "maxResults": 250,
            "timeMin": time_min,
            "timeMax": time_max,
            "fields": LIST_FIELDS,
        }
        if page_token:
            params["pageToken"] = page_token
        page = gws(["calendar", "events", "list", "--params", json.dumps(params)])
        events.extend(page.get("items", []))
        page_token = page.get("nextPageToken")
        if not page_token:
            return events


def needs_patch(event: dict) -> bool:
    if event.get("status") == "cancelled":
        return False
    if event.get("eventType") in SKIP_EVENT_TYPES:
        return False
    if event.get("guestsCanModify") is True:
        return False
    if not event.get("organizer", {}).get("self"):
        return False
    guests = [
        a
        for a in event.get("attendees", [])
        if not a.get("self") and not a.get("resource")
    ]
    return bool(guests)


def patch(calendar_id: str, event_id: str) -> None:
    gws(
        [
            "calendar",
            "events",
            "patch",
            "--params",
            json.dumps(
                # sendUpdates=none: 権限を付け替えただけでゲストに通知を飛ばさない。
                {"calendarId": calendar_id, "eventId": event_id, "sendUpdates": "none"}
            ),
            "--json",
            json.dumps({"guestsCanModify": True}),
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calendar", default="primary", help="対象カレンダー (既定: primary)")
    parser.add_argument("--days", type=int, default=120, help="今日から何日先まで見るか (既定: 120)")
    parser.add_argument("--apply", action="store_true", help="実際に書き込む (既定はドライラン)")
    args = parser.parse_args()

    now = dt.datetime.now(dt.timezone.utc)
    time_min = now.isoformat(timespec="seconds").replace("+00:00", "Z")
    time_max = (now + dt.timedelta(days=args.days)).isoformat(timespec="seconds").replace("+00:00", "Z")

    try:
        events = list_events(args.calendar, time_min, time_max)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 1

    targets = [e for e in events if needs_patch(e)]
    print(f"走査: {len(events)} 件 / 対象: {len(targets)} 件 ({args.days} 日先まで)")

    if not args.apply:
        for e in targets:
            print(f"  [dry-run] {e['id']}  {e.get('summary', '(無題)')}")
        if targets:
            print("書き込むには --apply を付けて再実行。")
        return 0

    failed = 0
    for e in targets:
        try:
            patch(args.calendar, e["id"])
        except RuntimeError as exc:
            failed += 1
            print(f"  NG  {e['id']}  {e.get('summary', '(無題)')}\n{exc}", file=sys.stderr)
        else:
            print(f"  OK  {e['id']}  {e.get('summary', '(無題)')}")

    print(f"完了: {len(targets) - failed} 件更新 / {failed} 件失敗")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
