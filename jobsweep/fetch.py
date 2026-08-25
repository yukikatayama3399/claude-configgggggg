# -*- coding: utf-8 -*-
"""HTTP取得。媒体に負荷をかけないようレート制限とリトライを入れる。"""
import time
import random
import urllib.request
import urllib.error

from . import config

_last_call = [0.0]


def get(url: str, retries: int = 3) -> str:
    """URLを取得して本文を返す。失敗時は空文字。"""
    wait = config.REQUEST_INTERVAL_SEC - (time.time() - _last_call[0])
    if wait > 0:
        time.sleep(wait)

    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": config.USER_AGENT,
                    "Accept-Language": "ja,en;q=0.8",
                    "Accept": "text/html,application/xhtml+xml",
                },
            )
            with urllib.request.urlopen(req, timeout=config.REQUEST_TIMEOUT_SEC) as r:
                body = r.read()
            _last_call[0] = time.time()
            return body.decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (404, 410):
                break
            time.sleep(2 ** attempt + random.random())
        except Exception as e:  # noqa: BLE001
            last_err = e
            # エージェントプロキシのポリシー拒否(403/407)はリトライしない。
            # クラウドセッションでは各社サイトへのCONNECTが拒否されるため、
            # フォーム探索は GitHub Actions 側で実行する。
            if "403" in str(e) or "407" in str(e):
                break
            time.sleep(2 ** attempt + random.random())
    _last_call[0] = time.time()
    if last_err:
        print(f"    [fetch] 失敗 {url[:90]} : {last_err}")
    return ""
