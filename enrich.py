#!/usr/bin/env python3
"""Fill in IMDb ID, rating, genres and runtime for films that only came from
Letterboxd, using IMDb's free public datasets (https://datasets.imdbws.com).
Reads docs/movies.json, writes data/enriched.json."""
import csv, gzip, io, json, os, re, urllib.request
from pathlib import Path

BASE = os.environ.get("IMDB_DATASETS", "https://datasets.imdbws.com")
TYPES = {"movie", "tvMovie", "short", "video", "tvSpecial", "tvShort"}

def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower().replace("&", "and"))

def rows(name):
    req = urllib.request.Request(f"{BASE}/{name}", headers={"User-Agent": "movie-watchlist"})
    with urllib.request.urlopen(req) as r, gzip.open(r, "rt", encoding="utf-8") as f:
        yield from csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE)

movies = json.loads(Path("docs/movies.json").read_text(encoding="utf-8"))
todo = [m for m in movies if m["id"].startswith(("lb-", "x-")) and m["year"]]
wanted = {}
for m in todo:
    for y in (m["year"] - 1, m["year"], m["year"] + 1):
        wanted.setdefault((norm(m["title"]), y), []).append(m["id"])
print(f"{len(todo)} Letterboxd-only / hand-added films to look up")

cands = {}  # film id -> list of basics rows
scanned = 0
for r in rows("title.basics.tsv.gz"):
    scanned += 1
    if r["titleType"] not in TYPES or r["startYear"] == "\\N":
        continue
    y = int(r["startYear"])
    for t in {norm(r["primaryTitle"]), norm(r["originalTitle"])}:
        for mid in wanted.get((t, y), []):
            cands.setdefault(mid, []).append(r)

print(f"scanned {scanned} IMDb titles")
ids = {r["tconst"] for rs in cands.values() for r in rs}
ratings = {}
for r in rows("title.ratings.tsv.gz"):
    if r["tconst"] in ids:
        ratings[r["tconst"]] = (float(r["averageRating"]), int(r["numVotes"]))

by_id = {m["id"]: m for m in todo}
out = {}
for mid, rs in cands.items():
    year = by_id[mid]["year"]
    best = max(rs, key=lambda r: (int(r["startYear"]) == year, ratings.get(r["tconst"], (0, 0))[1]))
    rating = ratings.get(best["tconst"], (None, 0))[0]
    out[mid] = {
        "imdb_id": best["tconst"],
        "rating": rating,
        "genres": best["genres"].replace(",", ", ") if best["genres"] != "\\N" else "",
        "runtime": int(best["runtimeMinutes"]) if best["runtimeMinutes"] != "\\N" else None,
    }
# Directors: title.crew gives name IDs, name.basics turns them into names
want = {v["imdb_id"] for v in out.values()}
crew = {}
for r in rows("title.crew.tsv.gz"):
    if r["tconst"] in want and r["directors"] != "\\N":
        crew[r["tconst"]] = r["directors"].split(",")[:3]
need = {n for ns in crew.values() for n in ns}
names = {}
for r in rows("name.basics.tsv.gz"):
    if r["nconst"] in need:
        names[r["nconst"]] = r["primaryName"]
for v in out.values():
    v["director"] = ", ".join(names[n] for n in crew.get(v["imdb_id"], []) if n in names)
print(f"directors found for {sum(1 for v in out.values() if v['director'])} films")

Path("data/enriched.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
print(f"matched {len(out)} of {len(todo)}")