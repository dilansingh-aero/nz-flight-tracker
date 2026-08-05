# NZ 6–13-seat class flight tracker — runs on $0/month, forever

A one-page website that shows **every flight flown in NZ by aircraft in our size class
(6–13 seats)** with a window toggle — **Live · Today · Week · Month · All-time** — and marks
each flight **green when our aircraft could have flown it** (range slider, default 900 km;
return-trip and minimum-runway gates included). Flights accumulate every night and are
**never deleted**.

No servers, no database, no subscriptions, no card on file:

- **GitHub Actions** (free on public repos) polls [adsb.lol](https://adsb.lol) every 5 minutes
  from **first light to last light NZ time**, committing sightings of the 160-aircraft civil
  watchlist. GitHub throttles 5-minutely crons hard — a `*/5` schedule was observed firing
  every 60–145 min — so an hourly job loops internally instead of trusting the schedule.
- Trips are segmented **as they land**, so the map fills during the day. A **nightly job**
  (00:20 NZT) re-runs the finished day and compacts its raw sightings → `data/flights.json`
  (append-only; only the day currently being segmented is ever rebuilt).
- A trip is archived only once its distance is **measured**, not guessed: seen moving, and
  snapped to two different aerodromes. Anything still airborne is left for the next run.
- **GitHub Pages** (free) serves `index.html`, which reads that archive.
- Keeping the repo **public** is what makes Actions free — and it automatically satisfies
  adsb.lol's ODbL share-alike licence, so it's a legal requirement solved for free too.

## Go live (~10 minutes)

**Option A — let Claude Code do it.** Open Claude Code in this folder and say:

> Create a new public GitHub repo called `nz-flight-tracker` from this folder, push it,
> enable GitHub Pages (deploy from branch: main, root), then run the "sweep" workflow once
> and confirm it committed data/latest.json.

**Option B — by hand.**
1. Create a free account at github.com → **New repository** → name `nz-flight-tracker` →
   **Public** → Create.
2. Get this folder into the repo (GitHub Desktop app is the easiest free way; note the
   hidden `.github` folder must come along — if drag-and-drop upload skips it, use
   *Add file → Create new file*, type `.github/workflows/sweep.yml` as the name and paste
   that file's contents, then the same for `nightly.yml`).
3. **Settings → Pages** → Source: *Deploy from a branch* → `main` / `(root)` → Save.
4. **Actions** tab → enable workflows → open *sweep* → **Run workflow** (first run makes
   the Live tab work immediately).
5. Your site: `https://<your-username>.github.io/nz-flight-tracker`

Day 1: Live works right away and Today fills after the first night. Week and Month fill as
the archive grows — and the archive can also be seeded with previously collected flights by
appending them to `data/flights.json` (rows in the same format).

## What's in here

| File | What it does |
|---|---|
| `index.html` | The whole website (map, toggles, feasibility gates, flight table) |
| `scripts/sweep.py` | Every 5 min in daylight: fetch NZ traffic, keep watchlist sightings |
| `scripts/segment.py` | Sightings → flights. `--keep-raw` for the intra-day runs; without it the nightly run also gzips the raw |
| `.github/workflows/` | The two free schedules that run the scripts |
| `data/watchlist.csv` | The class: 160 civil NZ airframes, 6–13 seats (military excluded) |
| `data/aerodromes.csv` | NZ aerodromes + runway lengths (for snapping and runway gates) |
| `data/flights.json` | The forever-growing archive (starts empty) |

## Honest limits (also stated in the site footer)

- 5-minute sampling is GitHub's floor, and its scheduler will not even honour that on a
  cron — hence the internal loop. Hops that start and finish between two sweeps can still be
  missed, so leg counts are lower bounds (skydive quick-cycles undercount most).
- A trip that never snaps to two different aerodromes is never archived. That is deliberate —
  it keeps invented distances out of the record — but it means the archive undercounts rather
  than estimates. Trips still airborne at last light are simply not recorded.
- Community receiver coverage is thin at low level in Fiordland, Stewart Island and the
  West Coast — flights there under-count until receivers are added.
- GitHub's scheduler sometimes runs a few minutes late and can skip a cycle under load;
  it self-heals on the next run.

Data © adsb.lol contributors (ODbL). Aerodromes: OurAirports. Class list: NZ CAA register.
