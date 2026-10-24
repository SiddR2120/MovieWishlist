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
        if not m["year"] and e.get("year"):
            m["year"] = e["year"]
            index[(norm(m["title"]), m["year"])] = mid
        m.update(imdb="https://www.imdb.com/title/%s/" % tt, rating=e["rating"],
                 genres=e["genres"], runtime=e["runtime"], director=e.get("director", ""))

# Merge rows that ended up on the same IMDb page (e.g. a hand-added title that is also on Letterboxd)
groups = {}
for mid, m in movies.items():
    t = re.search(r"tt\d+", m["imdb"] or "")
    if t:
        groups.setdefault(t.group(0), []).append(mid)
for ids in groups.values():
    if len(ids) < 2:
        continue
    ids.sort(key=lambda i: 0 if i.startswith("tt") else 1 if i.startswith("lb-") else 2)
    keep = movies[ids[0]]
    for dup_id in ids[1:]:
        d = movies.pop(dup_id)
        for k in ("letterboxd", "wikipedia", "note", "review"):
            keep[k] = keep[k] or d[k]
        keep["watched"] = keep["watched"] or d["watched"]
        keep["added"] = min(filter(None, [keep["added"], d["added"]]), default="")
        for k, v in list(index.items()):
            if v == dup_id:
                index[k] = ids[0]

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
# Reviews written on the site: data/my-reviews.csv (Title,Year,Rating,Date,Review,Tags)
for i, r in enumerate(read_csv("my-reviews.csv")):
    if not (r.get("Title") or "").strip():
        continue
    title, year = r["Title"].strip(), year_of(r.get("Year"))
    mid = find(title, year)
    rid = "m-%s%s-%s" % (norm(title), year or "", (r.get("Date") or "").replace("-", ""))
    try:
        rating = float(r["Rating"]) if r.get("Rating") else None
    except ValueError:
        rating = None
    if mid:
        movies[mid]["review"] = rid
        movies[mid]["watched"] = True  # reviewed means watched
    reviews.append({
        "id": rid, "title": title, "year": year, "rating": rating,
        "date": r.get("Date") or "", "rewatch": False, "review": r.get("Review") or "",
        "tags": r.get("Tags") or "", "url": "", "on_list": bool(mid),
    })
# Reviews added from the site: data/my-reviews.csv
for r in read_csv("my-reviews.csv"):
    if not (r.get("Name") or "").strip():
        continue
    year = year_of(r.get("Year"))
    code = r.get("ID") or "my-" + norm(r["Name"]) + (r.get("Date") or "")
    mid = find(r["Name"], year)
    if mid:
        movies[mid]["review"] = code
        if mid not in notes:
            movies[mid]["watched"] = True
    reviews.append({
        "id": code, "title": r["Name"].strip(), "year": year,
        "rating": float(r["Rating"]) if r.get("Rating") else None,
        "date": r.get("Date") or "", "rewatch": bool(r.get("Rewatch")),
        "review": (r.get("Review") or "").replace("\r\n", "\n"), "tags": r.get("Tags") or "",
        "url": "", "on_list": bool(mid),
    })
reviews.sort(key=lambda x: x["date"], reverse=True)
Path("docs/reviews.json").write_text(json.dumps(reviews, ensure_ascii=False), encoding="utf-8")
print(f"{len(reviews)} reviews written to docs/reviews.json")

out = sorted(movies.values(), key=lambda m: m["added"], reverse=True)
Path("docs/movies.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
print(f"{len(out)} titles written to docs/movies.json")
