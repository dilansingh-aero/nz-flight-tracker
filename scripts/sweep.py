#!/usr/bin/env python3
"""Every 5 min (GitHub Actions): fetch NZ traffic from adsb.lol, keep only the
6-13-seat watchlist, append sightings to today's raw file + refresh latest.json.
Skips when it is dark over the whole country - first light to last light only.
Cost: $0. Data licence: ODbL (adsb.lol) - this public repo satisfies share-alike."""
import csv, json, math, os, sys, time, urllib.request
from datetime import datetime, timezone, timedelta

BASE = os.path.join(os.path.dirname(__file__), '..')
NZT = timezone(timedelta(hours=12))          # NZST; NZDT drift only shifts file boundaries, harmless
CIRCLES = [(-38.0, 175.5, 250), (-44.5, 169.8, 250), (-41.6, 173.8, 150)]

ENDS = [(-34.4, 173.0), (-46.6, 168.3)]   # North Cape and Bluff: if either has light, sweep
CIVIL = -6.0                              # civil twilight = first light / last light

def sun_elev(lat, lon, ts):
    """Solar elevation in degrees. Low-precision (~0.1 deg) - far finer than a
    twilight gate needs. Checked against published NZ sunrise/sunset to ~4 min."""
    n = ts / 86400.0 - 10957.5                                  # days from J2000.0
    L = math.radians((280.460 + 0.9856474 * n) % 360)
    g = math.radians((357.528 + 0.9856003 * n) % 360)
    lam = L + math.radians(1.915) * math.sin(g) + math.radians(0.020) * math.sin(2 * g)
    eps = math.radians(23.439 - 3.6e-7 * n)
    ra = math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam))
    dec = math.asin(math.sin(eps) * math.sin(lam))
    gmst = (18.697374558 + 24.06570982441908 * n) % 24
    ha = math.radians((gmst * 15 + lon) % 360) - ra
    la = math.radians(lat)
    return math.degrees(math.asin(math.sin(la) * math.sin(dec) +
                                  math.cos(la) * math.cos(dec) * math.cos(ha)))

def daylight(ts):
    """True if anywhere in NZ is at or past first light. Fails OPEN: if the maths
    ever throws we sweep anyway, because a wrong gate that skips the day is far
    worse than a few wasted night runs."""
    try:
        return any(sun_elev(la, lo, ts) > CIVIL for la, lo in ENDS)
    except Exception as e:
        print(f'sun check failed ({e}) - sweeping anyway')
        return True

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

if not daylight(now):
    print(f'{datetime.now(NZT):%H:%M} NZT - dark over all of NZ, skipping')
    sys.exit(0)

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
