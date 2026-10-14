"""Google API の薄いラッパー（Slides / Drive の REST を直接叩く）。

認証は setup_gws_remote.sh が作る ~/.config/gws/credentials.json（gog のトークン流用）を使う。
gws CLI は --json を引数で渡すため、数百リクエストの batchUpdate だと
「Argument list too long」で落ちる。大きいリクエストはこちらを使う。
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

CRED = os.path.expanduser('~/.config/gws/credentials.json')
_TOKEN = None


def token():
    global _TOKEN
    if _TOKEN is None:
        c = json.load(open(CRED))
        body = urllib.parse.urlencode({
            'client_id': c['client_id'], 'client_secret': c['client_secret'],
            'refresh_token': c['refresh_token'], 'grant_type': 'refresh_token',
        }).encode()
        _TOKEN = json.load(urllib.request.urlopen('https://oauth2.googleapis.com/token', body))['access_token']
    return _TOKEN


def request(method, url, body=None, raw=None, content_type='application/json'):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={'Authorization': 'Bearer ' + token(), 'Content-Type': content_type})
    try:
        res = urllib.request.urlopen(req).read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'{method} {url} -> {e.code}: {e.read().decode()[:1500]}')
    return res


def call(method, url, body=None):
    res = request(method, url, body)
    return json.loads(res) if res else {}


SLIDES = 'https://slides.googleapis.com/v1/presentations'
DRIVE = 'https://www.googleapis.com/drive/v3/files'


def get_presentation(pid):
    return call('GET', f'{SLIDES}/{pid}')


def batch(pid, requests):
    return call('POST', f'{SLIDES}/{pid}:batchUpdate', {'requests': requests})


def copy_file(fid, name, parent=None):
    body = {'name': name}
    if parent:
        body['parents'] = [parent]
    return call('POST', f'{DRIVE}/{fid}/copy?supportsAllDrives=true', body)['id']


def upload(path, mime):
    boundary = 'hawkagenda'
    meta = json.dumps({'name': os.path.basename(path)}).encode()
    raw = (f'--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n'.encode() + meta +
           f'\r\n--{boundary}\r\nContent-Type: {mime}\r\n\r\n'.encode() + open(path, 'rb').read() +
           f'\r\n--{boundary}--'.encode())
    res = request('POST', 'https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart',
                  raw=raw, content_type=f'multipart/related; boundary={boundary}')
    return json.loads(res)['id']


def share_anyone(fid):
    return call('POST', f'{DRIVE}/{fid}/permissions?supportsAllDrives=true', {'role': 'reader', 'type': 'anyone'})['id']


def unshare(fid, perm_id):
    request('DELETE', f'{DRIVE}/{fid}/permissions/{perm_id}?supportsAllDrives=true')


def trash(fid):
    call('PATCH', f'{DRIVE}/{fid}?supportsAllDrives=true', {'trashed': True})


def export_pdf(fid, out):
    open(out, 'wb').write(request('GET', f'{DRIVE}/{fid}/export?mimeType=application/pdf'))
