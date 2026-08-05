#!/usr/bin/env python3
"""Nightly (00:20 NZT): turn yesterday's raw sightings into flights, append to
data/flights.json (append-only - flights are NEVER deleted), gzip the raw file.
A trace is only logged as a flight once its total trip distance is known: seen
moving, and snapped to two different aerodromes. Anything still in the air, or
seen only once, is dropped rather than archived with a distance we guessed."""
import csv, gzip, json, math, os, sys
from datetime import datetime, timezone, timedelta

BASE = os.path.join(os.path.dirname(__file__), '..')
NZT = timezone(timedelta(hours=12))
GAP = 35 * 60          # >35 min between sightings = new flight
SNAP_KM = 8            # snap flight ends to an aerodrome within 8 km

def hav(a, b, c, d):
    p = math.pi / 180
    x = math.sin((c - a) * p / 2) ** 2 + math.cos(a * p) * math.cos(c * p) * math.sin((d - b) * p / 2) ** 2
    return 12742 * math.asin(math.sqrt(x))

day = sys.argv[1] if len(sys.argv) > 1 else (datetime.now(NZT) - timedelta(days=1)).strftime('%Y-%m-%d')
raw_path = f'{BASE}/data/raw/{day}.jsonl'
if not os.path.exists(raw_path):
    print(f'no raw for {day}'); sys.exit(0)

watch = {r['hex']: r for r in csv.DictReader(open(f'{BASE}/data/watchlist.csv'))}
aero = [(r['icao'], float(r['lat']), float(r['lon'])) for r in csv.DictReader(open(f'{BASE}/data/aerodromes.csv'))]

def snap(lat, lon):
    best, bd = None, SNAP_KM
    for icao, alat, alon in aero:
        d = hav(lat, lon, alat, alon)
        if d < bd:
            best, bd = icao, d
    return best

byhex = {}
for line in open(raw_path):
    s = json.loads(line)
    byhex.setdefault(s['hex'], []).append(s)

flights = json.load(open(f'{BASE}/data/flights.json'))
have = {(f['date'], f['hex'], f['t0']) for f in flights}
new, unknown = 0, 0
for h, sights in byhex.items():
    sights.sort(key=lambda s: s['t'])
    runs, cur = [], [sights[0]]
    for s in sights[1:]:
        if s['t'] - cur[-1]['t'] > GAP:
            runs.append(cur); cur = [s]
        else:
            cur.append(s)
    runs.append(cur)
    w = watch[h]
    for r in runs:
        f0, f1 = r[0], r[-1]
        orig, dest = snap(f0['lat'], f0['lon']), snap(f1['lat'], f1['lon'])
        # Only log a trip whose total distance we actually know: it must have been seen
        # moving (>=2 sightings) and have snapped to two DIFFERENT aerodromes. A single
        # sighting, or one that ends mid-air or back where it started, tells us nothing
        # about how far the aircraft went - the raw stays in the .gz, but no flight is
        # written. Better an empty archive than a fabricated distance.
        if len(r) < 2 or not orig or not dest or orig == dest:
            unknown += 1
            continue
        km = round(hav(f0['lat'], f0['lon'], f1['lat'], f1['lon']))
        rec = {'date': day, 'hex': h, 'rego': w['rego'], 'type': w['type'], 'ac': w['aircraft'],
               'seats': int(w['seats']), 't0': f0['t'], 't1': f1['t'], 'orig': orig, 'dest': dest,
               'km': km, 'n': len(r), 'complete': True,
               'pts': [[s['lat'], s['lon']] for s in r][:50]}
        if (day, h, f0['t']) not in have:
            flights.append(rec); new += 1

json.dump(flights, open(f'{BASE}/data/flights.json', 'w'), separators=(',', ':'))
with open(raw_path, 'rb') as fi, gzip.open(raw_path + '.gz', 'wb') as fo:
    fo.write(fi.read())
os.remove(raw_path)   # raw compacted; FLIGHTS are kept forever
print(f'{day}: +{new} flights (total {len(flights)}), {len(byhex)} airframes active, '
      f'{unknown} traces dropped (trip distance unknown)')
