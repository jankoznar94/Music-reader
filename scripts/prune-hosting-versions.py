#!/usr/bin/env python3
"""Smaže staré Hosting verze (nechá N nejnovějších), REST API.

Token: additionalAccounts (harlekynovypodcasty@gmail.com) — default `tokens`
na Hosting API vrací 403. Verze se řadí podle `createTime`, ne podle pořadí
v odpovědi (to není garantované). Mazání stovek verzí trvá minuty, proto se
spouští na pozadí a průběh se flushuje.

Použití: python3 scripts/prune-hosting-versions.py [--keep 4] [--dry-run]
"""
import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request

CFG = os.path.expanduser('~/.config/configstore/firebase-tools.json')
SITE = 'harlequin-music-reader'
API = 'https://firebasehosting.googleapis.com/v1beta1'
CLIENT_ID = '563584335869-fgrhgmd47bqnekij5i8b5pr03ho849e6.apps.googleusercontent.com'
CLIENT_SECRET = 'j9iVZfS8kkCEFUPaAeJV0sAi'


def refresh(cfg):
    tok = cfg['additionalAccounts'][0]['tokens']
    body = urllib.parse.urlencode({
        'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET,
        'refresh_token': tok['refresh_token'], 'grant_type': 'refresh_token',
    }).encode()
    with urllib.request.urlopen(
            urllib.request.Request('https://oauth2.googleapis.com/token', data=body),
            timeout=25) as r:
        new = json.load(r)
    tok['access_token'] = new['access_token']
    json.dump(cfg, open(CFG, 'w'), indent=2)
    return new['access_token']


def call(url, method='GET', token=None, cfg=None):
    def once(tk):
        req = urllib.request.Request(url, method=method,
                                     headers={'Authorization': 'Bearer ' + str(tk)})
        with urllib.request.urlopen(req, timeout=25) as r:
            raw = r.read().decode() or '{}'
            return json.loads(raw)
    try:
        return once(token)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403) and cfg is not None:
            return once(refresh(cfg))
        raise


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--keep', type=int, default=4)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    cfg = json.load(open(CFG))
    token = cfg['additionalAccounts'][0]['tokens'].get('access_token')

    versions, page, pages = [], None, 0
    while True:
        url = f'{API}/sites/{SITE}/versions?pageSize=100'
        if page:
            url += '&pageToken=' + page
        data = call(url, token=token, cfg=cfg)
        versions += data.get('versions', [])
        pages += 1
        page = data.get('nextPageToken')
        if not page or pages > 40:
            break

    versions.sort(key=lambda v: v.get('createTime', ''), reverse=True)
    doomed = versions[args.keep:]
    print(f'verzí celkem: {len(versions)}, nechávám {args.keep}, mažu {len(doomed)}', flush=True)
    for v in versions[:args.keep]:
        print('  nechávám:', v['name'], v.get('createTime'), flush=True)
    if args.dry_run:
        return

    for i, v in enumerate(doomed, 1):
        try:
            call(f'{API}/{v["name"]}', method='DELETE', token=token, cfg=cfg)
        except urllib.error.HTTPError as e:
            print('  CHYBA', v['name'], e.code, e.read()[:160], flush=True)
        if i % 20 == 0:
            print(f'  smazáno {i}/{len(doomed)}', flush=True)
    print('hotovo', flush=True)


if __name__ == '__main__':
    main()
