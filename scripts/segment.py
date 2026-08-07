#!/usr/bin/env python3
"""Sightings -> flights.  segment.py [YYYY-MM-DD] [--keep-raw]

Run two ways:
  during the day, every few minutes, on TODAY with --keep-raw, so finished trips
    show up on the site within minutes of landing instead of after midnight;
  once at 00:20 NZT on the day that just ended, without --keep-raw, which also
    compacts that day's raw sightings to .gz.

A trace only becomes a flight once its distance is actually known: seen moving,
and snapped to two different aerodromes.  Anything still in the air, or seen
only once, is dropped rather than archived with a distance we guessed.

The day being segmented is rebuilt from its raw file each run.  Every other day
in the archive is left untouched - those are still never deleted."""
import csv, gzip, json, math, os, sys
from datetime import datetime, timezone, timedelta

BASE = os.path.join(os.path.dirname(__file__), '..')
NZT = timezone(timedelta(hours=12))
GAP = 35 * 60          # >35 min between sightings = new flight
SNAP_KM = 20           # a flight end may be this far from the aerodrome ...
SNAP_AGL = 8000        # ... but must also be this low above it (ft), or it is overflying

def hav(a, b, c, d):
    p = math.pi / 180
    x = math.sin((c - a) * p / 2) ** 2 + math.cos(a * p) * math.cos(c * p) * math.sin((d - b) * p / 2) ** 2
    return 12742 * math.asin(math.sqrt(x))

keep_raw = '--keep-raw' in sys.argv
days = [a for a in sys.argv[1:] if not a.startswith('--')]
day = days[0] if days else (datetime.now(NZT) - timedelta(days=1)).strftime('%Y-%m-%d')
raw_path = f'{BASE}/data/raw/{day}.jsonl'
if not os.path.exists(raw_path):
    print(f'no raw for {day}'); sys.exit(0)

watch = {r['hex']: r for r in csv.DictReader(open(f'{BASE}/data/watchlist.csv'))}
aero = [(r['icao'], float(r['lat']), float(r['lon']),
         float(r['elev_ft']) if r.get('elev_ft') else 0.0)
        for r in csv.DictReader(open(f'{BASE}/data/aerodromes.csv'))]
AC = {a[0]: (a[1], a[2]) for a in aero}

def snap(s):
    """The aerodrome this sighting is departing from or arriving at, else None.
    Needs proximity AND a low height above that field. 8 km alone was far too
    tight - sampling never catches an aircraft that close, only 32% of sightings
    ever landed inside it - while 20 km alone would grab cruising traffic that
    merely passes over a field. Together they select climb-out and approach."""
    best, bd, belev = None, SNAP_KM, 0.0
    for icao, alat, alon, elev in aero:
        d = hav(s['lat'], s['lon'], alat, alon)
        if d < bd:
            best, bd, belev = icao, d, elev
    if best is None:
        return None
    alt = s.get('alt')
    if not isinstance(alt, (int, float)) or alt - belev > SNAP_AGL:
        return None
    return best

byhex = {}
for line in open(raw_path):
    s = json.loads(line)
    byhex.setdefault(s['hex'], []).append(s)

flights = json.load(open(f'{BASE}/data/flights.json'))
flights = [f for f in flights if f.get('date') != day]   # this day gets rebuilt below
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
        orig, dest = snap(f0), snap(f1)
        # Only log a trip whose total distance we actually know: it must have been seen
        # moving (>=2 sightings) and have snapped to two DIFFERENT aerodromes. A single
        # sighting, or one that ends mid-air or back where it started, tells us nothing
        # about how far the aircraft went - the raw stays in the .gz, but no flight is
        # written. Better an empty archive than a fabricated distance.
        if len(r) < 2 or not orig or not dest or orig == dest:
            unknown += 1
            continue
        # Aerodrome to aerodrome, NOT first sighting to last: sampling starts after
        # takeoff and stops before landing, which understated every route (NZHS-NZNR
        # came out 8 km against a true 22) and so made trips look more reachable than
        # they are - the opposite of the error this site can afford.
        km = round(hav(AC[orig][0], AC[orig][1], AC[dest][0], AC[dest][1]))
        track = round(sum(hav(a['lat'], a['lon'], b['lat'], b['lon'])     # actually flown
                          for a, b in zip(r, r[1:])))
        rec = {'date': day, 'hex': h, 'rego': w['rego'], 'type': w['type'], 'ac': w['aircraft'],
               'seats': int(w['seats']), 't0': f0['t'], 't1': f1['t'], 'orig': orig, 'dest': dest,
               'km': km, 'track_km': track, 'n': len(r), 'complete': True,
               'pts': [[s['lat'], s['lon']] for s in r][:200]}
        flights.append(rec); new += 1

flights.sort(key=lambda f: (f['date'], f['t0']))
json.dump(flights, open(f'{BASE}/data/flights.json', 'w'), separators=(',', ':'))
if not keep_raw:      # the day is over: compact its sightings, keep the flights forever
    with open(raw_path, 'rb') as fi, gzip.open(raw_path + '.gz', 'wb') as fo:
        fo.write(fi.read())
    os.remove(raw_path)
print(f'{day}: +{new} flights (total {len(flights)}), {len(byhex)} airframes active, '
      f'{unknown} traces dropped (trip distance unknown)')
