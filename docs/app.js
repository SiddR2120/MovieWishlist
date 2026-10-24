var movies = [];
var local = [];
try { local = JSON.parse(localStorage.getItem("extraTitles") || "[]"); } catch (e) { local = []; }
function normT(s) { return String(s).toLowerCase().replace(/&/g, "and").replace(/[^a-z0-9]/g, ""); }
function saveLocal() { try { localStorage.setItem("extraTitles", JSON.stringify(local)); } catch (e) {} }
function csvCell(s) { s = String(s || ""); return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; }
function allMovies() {
  var seen = {};
  movies.forEach(function (m) { seen[normT(m.title) + (m.year || "")] = true; });
  var extra = local.filter(function (l) { return !seen[normT(l.title) + (l.year || "")]; })
    .map(function (l) {
      return { id: "local", title: l.title, year: l.year, type: "Movie", genres: "", director: "", rating: null,
        added: "9999", imdb: "", letterboxd: "", wikipedia: "", watched: false, note: l.note || "", review: "", local: true };
    });
  return extra.concat(movies);
}
var $ = function (id) { return document.getElementById(id); };

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
  });
}

function link(url, label) {
  return url ? '<a href="' + esc(url) + '">' + label + "</a>" : "";
}

function render() {
  var q = $("q").value.toLowerCase();
  var type = $("type").value, source = $("source").value, sort = $("sort").value;
  var hide = $("hide").checked;

  var list = allMovies().filter(function (m) {
    if (hide && m.watched) return false;
    if (type === "Movie" && m.type !== "Movie" && m.type !== "TV Movie") return false;
    if (type === "TV" && m.type.indexOf("TV") !== 0) return false;
    if (source && !m[source]) return false;
    var hay = (m.title + " " + m.director + " " + m.genres).toLowerCase();
    return hay.indexOf(q) !== -1;
  });

  list.sort(function (a, b) {
    if (sort === "title") return a.title.localeCompare(b.title);
    if (sort === "year") return (b.year || 0) - (a.year || 0);
    if (sort === "rating") return (b.rating || 0) - (a.rating || 0);
    return b.added < a.added ? -1 : b.added > a.added ? 1 : 0;
  });

  $("count").textContent = list.length + " titles";
  $("rows").innerHTML = list.map(function (m) {
    var q2 = encodeURIComponent(m.title + (m.year ? " " + m.year : ""));
    var links = [
      m.imdb ? link(m.imdb, "IMDb") : link("https://www.imdb.com/find/?s=tt&q=" + q2, "IMDb search"),
      link(m.letterboxd, "Letterboxd"),
      m.wikipedia ? link(m.wikipedia, "Wikipedia") : link("https://en.wikipedia.org/w/index.php?search=" + q2 + "+film", "Wikipedia search")
    ]
      .filter(Boolean).join(" · ");
    return "<tr><td>" + esc(m.title) + (m.local ? " <small>(on this device)</small>" : "") +
      (m.review ? ' <small><a href="reviews.html#' + esc(m.review) + '">my review</a></small>' : "") + (m.note ? "<br><small>" + esc(m.note) + "</small>" : "") +
      "</td><td>" + esc(m.year) + "</td><td>" + esc(m.director) + "</td><td>" + esc(m.genres) +
      "</td><td>" + esc(m.rating) + "</td><td>" + links + "</td></tr>";
  }).join("");
}

["q", "type", "source", "sort", "hide"].forEach(function (id) {
  $(id).addEventListener("input", render);
  $(id).addEventListener("change", render);
});

$("addbtn").addEventListener("click", function () {
  $("addbox").hidden = !$("addbox").hidden;
  $("a_csv").value = local.map(function (l) { return [csvCell(l.title), l.year || "", csvCell(l.note)].join(","); }).join("\n");
});
$("a_save").addEventListener("click", function () {
  var t = $("a_title").value.trim();
  if (!t) return;
  local.push({ title: t, year: parseInt($("a_year").value, 10) || null, note: $("a_note").value.trim() });
  saveLocal();
  $("a_title").value = ""; $("a_year").value = ""; $("a_note").value = "";
  $("a_csv").value = local.map(function (l) { return [csvCell(l.title), l.year || "", csvCell(l.note)].join(","); }).join("\n");
  render();
});
$("a_clear").addEventListener("click", function () {
  local = []; saveLocal(); $("a_csv").value = ""; render();
});

fetch("movies.json").then(function (r) { return r.json(); }).then(function (data) {
  movies = data;
  render();
});
