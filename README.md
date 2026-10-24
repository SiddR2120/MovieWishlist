# Movies to Watch

A merged watchlist from IMDb, Letterboxd and Wikipedia, shown as a plain HTML page.

## Setup
1. Create a new GitHub repo and push these files to it.
2. Settings → Pages → Deploy from a branch → `main` / `/docs`.
3. Settings → Actions → General → Workflow permissions → Read and write.
4. Run the "Update watchlist" action once (Actions tab → Run workflow).

## Updating
- **Letterboxd:** export your data, then replace `data/letterboxd-watchlist.csv` and `data/letterboxd-watched.csv` with `watchlist.csv` and `watched.csv` from the zip.
- **IMDb:** replace `data/imdb.csv` with a fresh export, or set up the automatic fetch below.
- **Wikipedia:** add article titles to `data/wikipedia.txt`, one per line, e.g. `Blade Runner (1982 film)`.
- **Notes / watched:** edit `data/notes.json`, e.g. `{"tt1856101": {"watched": true, "note": "great"}}`.

Every push to `data/` rebuilds `docs/movies.json`. It also rebuilds every Monday.

## Adding titles
- **Quick, this device only:** use the "Add a title" button on the site. It saves in your browser.
- **Permanent:** copy the lines the button shows into `data/extra.csv` (columns `Title,Year,Note`) and commit. The build adds them and fills in ratings where it can.

## Reviews
Put `reviews.csv` and `ratings.csv` from your Letterboxd export into `data/` as `letterboxd-reviews.csv` and `letterboxd-ratings.csv`. The build creates `docs/reviews.json`, shown on `reviews.html`, and adds a "my review" link next to matching titles.

Titles you add without a year get their year, director, genres and rating filled in on the next rebuild, from IMDb's public datasets.

## Adding reviews from the site
On `reviews.html`, click "Add a review". With a GitHub token saved (same one as for adding titles), the review is committed to `data/my-reviews.csv` and the site rebuilds. To edit or delete a review later, edit that file on GitHub. Titles you review are marked watched.

## Optional: automatic IMDb refresh
On your IMDb watchlist page, find the Export button and copy its link. Add it in
Settings → Secrets and variables → Actions → Variables as `IMDB_EXPORT_URL`.
IMDb sometimes blocks automated downloads; if so, the step is skipped and the committed CSV is used.

## Ratings for Letterboxd-only films
`enrich.py` downloads IMDb's free public datasets (datasets.imdbws.com) in the Action and fills in IMDb link, rating, genres and runtime for films that only came from Letterboxd. Director isn't included. No account or key is needed. Results are saved to `data/enriched.json`.

## Run locally
`python3 build.py`, then open `docs/index.html` through any local server (`python3 -m http.server -d docs`).
