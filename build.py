#!/usr/bin/env python3
"""Merge IMDb, Letterboxd and Wikipedia lists into docs/movies.json."""
import csv, json, re
from pathlib import Path
from urllib.parse import quote

D = Path("data")

def norm(s):
    s = s.lower().replace("&", "and")
    return re.sub(r"[^a-z0-9]", "", s)

def read_csv(name):
    p = D / name
    if not p.exists():
        return []
    with open(p, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def year_of(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None

movies = {}   # id -> record
index = {}    # (normtitle, year) -> id

def find(title, year):
    for y in (year, (year or 0) + 1, (year or 0) - 1):
        if y and (norm(title), y) in index:
            return index[(norm(title), y)]
    return None

def add(title, year, mid):
    m = {"id": mid, "title": title, "year": year, "type": "Movie", "genres": "",
         "director": "", "runtime": None, "rating": None, "added": "",
         "imdb": "", "letterboxd": "", "wikipedia": "", "watched": False, "note": "", "review": ""}
    movies[mid] = m
    index[(norm(title), year)] = mid
    return m

# IMDb
for r in read_csv("imdb.csv"):
    year = year_of(r.get("Year"))
    m = add(r["Title"], year, r["Const"])
    m.update(type=r.get("Title Type") or "Movie", genres=r.get("Genres") or "",
             director=r.get("Directors") or "", imdb=r.get("URL") or "",
             runtime=year_of(r.get("Runtime (mins)")), added=r.get("Created") or "")
    try:
        m["rating"] = float(r["IMDb Rating"])
    except (TypeError, ValueError, KeyError):
        pass

# Letterboxd watchlist
for r in read_csv("letterboxd-watchlist.csv"):
    year = year_of(r["Year"])
    mid = find(r["Name"], year)
    m = movies[mid] if mid else add(r["Name"], year, "lb-" + r["Letterboxd URI"].rsplit("/", 1)[-1])
    m["letterboxd"] = r["Letterboxd URI"]
    m["added"] = min(filter(None, [m["added"], r["Date"]]), default="")

# Titles you added by hand: data/extra.csv (Title,Year,Note)
for r in read_csv("extra.csv"):
    if not (r.get("Title") or "").strip():
        continue
    year = year_of(r.get("Year"))
    mid = find(r["Title"].strip(), year)
    m = movies[mid] if mid else add(r["Title"].strip(), year, "x-%s%s" % (norm(r["Title"]), year or ""))
    if r.get("Note"):
        m["note"] = r["Note"]
    m["added"] = m["added"] or "9999"  # newest first until a date is known

# IMDb data for Letterboxd-only films (written by enrich.py)
ep = D / "enriched.json"
for mid, e in (json.loads(ep.read_text()) if ep.exists() else {}).items():
    m = movies.get(mid)
    if not m:
        continue
    tt = e["imdb_id"]
    if tt in movies:  # already on the IMDb watchlist under a slightly different title
        t = movies[tt]
        t["letterboxd"] = m["letterboxd"]
        t["added"] = min(filter(None, [t["added"], m["added"]]), default="")
        del movies[mid]
        for k, v in index.items():
            if v == mid:
                index[k] = tt
    else:
        m.update(imdb="https://www.imdb.com/title/%s/" % tt, rating=e["rating"],
                 genres=e["genres"], runtime=e["runtime"])

# Wikipedia (one article title per line)
wp = D / "wikipedia.txt"
for line in (wp.read_text(encoding="utf-8").splitlines() if wp.exists() else []):
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    url = "https://en.wikipedia.org/wiki/" + quote(line.replace(" ", "_"))
    ym = re.search(r"\((\d{4}) film\)", line)
    year = int(ym.group(1)) if ym else None
    title = re.sub(r"\s*\((\d{4} )?film\)$", "", line)
    mid = find(title, year) if year else next(
        (i for (t, _), i in index.items() if t == norm(title)), None)
    m = movies[mid] if mid else add(title, year, "wp-" + norm(line))
    m["wikipedia"] = url

# Mark films already watched on Letterboxd
for r in read_csv("letterboxd-watched.csv"):
    mid = find(r["Name"], year_of(r["Year"]))
    if mid:
        movies[mid]["watched"] = True

# Your own notes / manual watched flags: data/notes.json
# {"tt1856101": {"watched": true, "note": "saw it in theaters"}}
notes = json.loads((D / "notes.json").read_text() or "{}")
for mid, n in notes.items():
    if mid in movies:
        movies[mid]["watched"] = n.get("watched", movies[mid]["watched"])
        movies[mid]["note"] = n.get("note", "")

# Your Letterboxd reviews -> docs/reviews.json
my_ratings = {}
for r in read_csv("letterboxd-ratings.csv"):
    my_ratings[(norm(r["Name"]), year_of(r["Year"]))] = r["Rating"]
reviews = []
for r in read_csv("letterboxd-reviews.csv"):
    year = year_of(r["Year"])
    rating = r.get("Rating") or my_ratings.get((norm(r["Name"]), year))
    code = r["Letterboxd URI"].rstrip("/").rsplit("/", 1)[-1]
    mid = find(r["Name"], year)
    if mid:
        movies[mid]["review"] = code
    reviews.append({
        "id": code, "title": r["Name"], "year": year,
        "rating": float(rating) if rating else None,
        "date": r.get("Watched Date") or r["Date"], "rewatch": bool(r.get("Rewatch")),
        "review": r.get("Review") or "", "tags": r.get("Tags") or "",
        "url": r["Letterboxd URI"], "on_list": bool(mid),
    })
reviews.sort(key=lambda x: x["date"], reverse=True)
Path("docs/reviews.json").write_text(json.dumps(reviews, ensure_ascii=False), encoding="utf-8")
print(f"{len(reviews)} reviews written to docs/reviews.json")

out = sorted(movies.values(), key=lambda m: m["added"], reverse=True)
Path("docs/movies.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
print(f"{len(out)} titles written to docs/movies.json")
