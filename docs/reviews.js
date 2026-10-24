var reviews = [];
var $ = function (id) { return document.getElementById(id); };

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
  });
}

function stars(r) {
  if (!r) return "";
  var s = "";
  for (var i = 1; i <= Math.floor(r); i++) s += "\u2605";
  if (r % 1) s += "\u00bd";
  return s;
}

function render() {
  var q = $("q").value.toLowerCase(), sort = $("sort").value;
  var list = reviews.filter(function (r) {
    return (r.title + " " + r.review + " " + r.tags).toLowerCase().indexOf(q) !== -1;
  });
  list.sort(function (a, b) {
    if (sort === "title") return a.title.localeCompare(b.title);
    if (sort === "rating") return (b.rating || 0) - (a.rating || 0);
    return a.date < b.date ? 1 : a.date > b.date ? -1 : 0;
  });
  $("count").textContent = list.length + " reviews";
  $("list").innerHTML = list.map(function (r) {
    return '<div id="' + esc(r.id) + '"><h3>' + esc(r.title) + (r.year ? " (" + esc(r.year) + ")" : "") + "</h3>" +
      "<p>" + stars(r.rating) + (r.rating ? " " : "") + esc(r.date) + (r.rewatch ? " &middot; rewatch" : "") +
      (r.tags ? " &middot; " + esc(r.tags) : "") + ' &middot; <a href="' + esc(r.url) + '">Letterboxd</a></p>' +
      "<p>" + esc(r.review).replace(/\n/g, "<br>") + "</p><hr></div>";
  }).join("");
  if (location.hash && $(location.hash.slice(1))) $(location.hash.slice(1)).scrollIntoView();
}

$("q").addEventListener("input", render);
$("sort").addEventListener("change", render);

fetch("reviews.json").then(function (r) { return r.json(); }).then(function (data) {
  reviews = data;
  render();
});
