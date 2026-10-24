#!/usr/bin/env python3
"""Fill in IMDb ID, rating, genres, runtime and director for films that only came
from Letterboxd or the site, using IMDb's free public datasets
(https://datasets.imdbws.com). Reads docs/movies.json, writes data/enriched.json.

By default only films not looked up before are processed, and if there are none the
big downloads are skipped entirely (fast). Set ENRICH_FULL=1 to redo everything
(the weekly run does this, which also refreshes ratings)."""
import csv, gzip, json, os, re, sys, urllib.request
from pathlib import Path

BASE = os.environ.get("IMDB_DATASETS", "https://datasets.imdbws.com")
FULL = os.environ.get("ENRICH_FULL") == "1"
TYPES = {"movie", "tvMovie", "short", "video", "tvSpecial", "tvShort"}
OUT = Path("data/enriched.json")

def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower().replace("&", "and"))

def rows(name):
    req = urllib.request.Request(f"{BASE}/{name}", headers={"User-Agent": "movie-watchlist"})
    with urllib.request.urlopen(req) as r, gzip.open(r, "rt", encoding="utf-8") as f:
        yield from csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE)

movies = json.loads(Path("docs/movies.json").read_text(encoding="utf-8"))
old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() and not FULL else {}
misses = set(old.pop("_misses", []))

candidates = [m for m in movies if m["id"].startswith(("lb-", "x-"))]
todo = [m for m in candidates if m["id"] not in old and m["id"] not in misses]
print(f"{len(candidates)} Letterboxd-only / hand-added films, {len(todo)} to look up"
      f" ({'full refresh' if FULL else 'only new ones'})")
if not todo:
    print("nothing new to look up, skipping the IMDb downloads")
    sys.exit(0)

wanted = {}      # (title, year) -> film ids, for films with a known year
wanted_any = {}  # title -> film ids, for hand-added films with no year yet
for m in todo:
    if m["year"]:
        for y in (m["year"] - 1, m["year"], m["year"] + 1):
            wanted.setdefault((norm(m["title"]), y), []).append(m["id"])
    else:
        wanted_any.setdefault(norm(m["title"]), []).append(m["id"])

cands = {}  # film id -> list of basics rows
scanned = 0
for r in rows("title.basics.tsv.gz"):
    scanned += 1
    if r["titleType"] not in TYPES or r["startYear"] == "\\N":
        continue
    y = int(r["startYear"])
    for t in {norm(r["primaryTitle"]), norm(r["originalTitle"])}:
        for mid in wanted.get((t, y), []) + wanted_any.get(t, []):
            if r not in cands.setdefault(mid, []):
                cands[mid].append(r)
print(f"scanned {scanned} IMDb titles")

ids = {r["tconst"] for rs in cands.values() for r in rs}
ratings = {}
for r in rows("title.ratings.tsv.gz"):
    if r["tconst"] in ids:
        ratings[r["tconst"]] = (float(r["averageRating"]), int(r["numVotes"]))

by_id = {m["id"]: m for m in todo}
new = {}
for mid, rs in cands.items():
    year = by_id[mid]["year"]
    # known year: prefer an exact match; otherwise prefer real movies, then the most-voted title
    best = max(rs, key=lambda r: (int(r["startYear"]) == year if year else r["titleType"] == "movie",
                                  ratings.get(r["tconst"], (0, 0))[1]))
    new[mid] = {
        "imdb_id": best["tconst"],
        "year": int(best["startYear"]),
        "rating": ratings.get(best["tconst"], (None, 0))[0],
        "genres": best["genres"].replace(",", ", ") if best["genres"] != "\\N" else "",
        "runtime": int(best["runtimeMinutes"]) if best["runtimeMinutes"] != "\\N" else None,
    }

# Directors: title.crew gives name IDs, name.basics turns them into names
if new:
    want = {v["imdb_id"] for v in new.values()}
    crew = {}
    for r in rows("title.crew.tsv.gz"):
        if r["tconst"] in want and r["directors"] != "\\N":
            crew[r["tconst"]] = r["directors"].split(",")[:3]
    need = {n for ns in crew.values() for n in ns}
    names = {}
    if need:
        for r in rows("name.basics.tsv.gz"):
            if r["nconst"] in need:
                names[r["nconst"]] = r["primaryName"]
    for v in new.values():
        v["director"] = ", ".join(names[n] for n in crew.get(v["imdb_id"], []) if n in names)
    print(f"directors found for {sum(1 for v in new.values() if v['director'])} films")

out = dict(old)
out.update(new)
out["_misses"] = sorted(misses | {m["id"] for m in todo if m["id"] not in new})
OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
print(f"matched {len(new)} of {len(todo)} new films")
