#!/usr/bin/env python3
"""Every 5 min (GitHub Actions): fetch NZ traffic from adsb.lol, keep only the
6-13-seat watchlist, append sightings to today's raw file + refresh latest.json.
Cost: $0. Data licence: ODbL (adsb.lol) - this public repo satisfies share-alike."""
import csv, json, os, time, urllib.request
from datetime import datetime, timezone, timedelta

BASE = os.path.join(os.path.dirname(__file__), '..')
NZT = timezone(timedelta(hours=12))          # NZST; NZDT drift only shifts file boundaries, harmless
CIRCLES = [(-38.0, 175.5, 250), (-44.5, 169.8, 250), (-41.6, 173.8, 150)]

def fetch(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'nz-class-tracker (github actions; ODbL attributed)'})
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            if i == tries - 1:
                print(f'give up {url}: {e}')
                return None
            time.sleep(8 * (i + 1))

watch = {r['hex']: r for r in csv.DictReader(open(f'{BASE}/data/watchlist.csv'))}
now = int(time.time())
seen = {}
for lat, lon, rad in CIRCLES:
    d = fetch(f'https://api.adsb.lol/v2/point/{lat}/{lon}/{rad}')
    if not d:
        continue
    for a in d.get('ac', []):
        h = (a.get('hex') or '').lower().lstrip('~')
        if h not in watch or h in seen:            # watchlist = the size class; ground stations never match
            continue
        if a.get('alt_baro') == 'ground' or a.get('lat') is None:
            continue
        seen[h] = {'t': now, 'hex': h, 'lat': round(a['lat'], 4), 'lon': round(a['lon'], 4),
                   'alt': a.get('alt_baro'), 'gs': a.get('gs'), 'fl': (a.get('flight') or '').strip()}
    time.sleep(2)

day = datetime.now(NZT).strftime('%Y-%m-%d')
os.makedirs(f'{BASE}/data/raw', exist_ok=True)
if seen:
    with open(f'{BASE}/data/raw/{day}.jsonl', 'a') as f:
        for s in seen.values():
            f.write(json.dumps(s, separators=(',', ':')) + '\n')

latest = {'t': now, 'ac': [dict(s, rego=watch[s['hex']]['rego'], type=watch[s['hex']]['type'],
                                ac=watch[s['hex']]['aircraft'], seats=watch[s['hex']]['seats'])
                           for s in seen.values()]}
json.dump(latest, open(f'{BASE}/data/latest.json', 'w'), separators=(',', ':'))
print(f'{day} sweep: {len(seen)} in-class airborne')
