/* maluS reviewer editor (v1.4): single rendered A4 view + Word-style comments.

   The reviewer copy is still baseline + inserted {COMM}/{SUGG} blocks. This
   script parses it into comments anchored by a baseline character offset,
   renders the A4 sheet with red inline markers, adds comments from a text
   selection, drives the comments panel (jump + highlight, private notes), and
   reconstructs the Markdown into a hidden field on submit. The server contract
   (freeze validation + harvest) is unchanged. `marked` is vendored. */
(function () {
  "use strict";
  var form = document.getElementById("rev-form");
  var src = document.getElementById("content-src");
  if (!form || !src) return;
  var sheet = document.getElementById("sheet");
  var list = document.getElementById("cp-list");
  var countEl = document.getElementById("cp-count");
  var emptyEl = document.getElementById("cp-empty");
  var pop = document.getElementById("cmt-pop");
  var reviewId = form.getAttribute("data-review");
  var baseline = src.getAttribute("data-baseline") || "";

  var comments = []; // {cid, offset, kind, type, sev, body, oldText, newText}
  var seq = 1;
  var notes = {}; // anchor_key(offset as string) -> body
  var dirty = false;
  var pending = null; // {offset, text} for the open popover

  function blockRe() { return /\{(?:COMM|SUGG)\b[\s\S]*?\}/g; }
  function esc(s) {
    return (s || "").replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function unesc(s) { return s.replace(/\\"/g, '"').replace(/\\}/g, "}"); }
  function escq(s) { return s.replace(/"/g, '\\"').replace(/}/g, "\\}"); }

  // ---- parse the stored copy into comments + baseline offsets ----
  function parse() {
    comments = [];
    var content = src.value, re = blockRe(), m, baseOff = 0, last = 0;
    while ((m = re.exec(content)) !== null) {
      baseOff += m.index - last;
      last = m.index + m[0].length;
      comments.push(blockToComment(m[0], baseOff));
    }
  }
  function blockToComment(raw, offset) {
    var c = { cid: seq++, offset: offset, body: "", type: "editorial", sev: "minor", oldText: "", newText: "" };
    if (raw.indexOf("{SUGG") === 0) {
      c.kind = "SUGG";
      var sm = raw.match(/\{SUGG:\s*"((?:[^"\\]|\\.)*)"\s*->\s*"((?:[^"\\]|\\.)*)"\s*\}/);
      if (sm) { c.oldText = unesc(sm[1]); c.newText = unesc(sm[2]); }
    } else {
      c.kind = "COMM";
      var tm = raw.match(/type=(typo|editorial|technical|process)/);
      var sv = raw.match(/sev=(minor|major|critical)/);
      if (tm) c.type = tm[1];
      if (sv) c.sev = sv[1];
      var bm = raw.match(/:\s*([\s\S]*?)\}$/);
      c.body = bm ? bm[1].trim() : "";
    }
    return c;
  }

  // ---- serialize back to the Markdown copy ----
  function blockText(c) {
    if (c.kind === "SUGG") return '{SUGG: "' + escq(c.oldText) + '" -> "' + escq(c.newText) + '"}';
    return "{COMM|type=" + c.type + "|sev=" + c.sev + ": " + c.body.replace(/}/g, "\\}") + "}";
  }
  function sorted() { return comments.slice().sort(function (a, b) { return a.offset - b.offset; }); }
  function reconstruct() {
    var out = "", prev = 0, cs = sorted();
    for (var i = 0; i < cs.length; i++) {
      out += baseline.slice(prev, cs[i].offset) + blockText(cs[i]);
      prev = cs[i].offset;
    }
    src.value = out + baseline.slice(prev);
  }

  // ---- render the A4 sheet with red markers ----
  function markerHtml(c) {
    var inner = c.kind === "SUGG"
      ? '"' + esc(c.oldText) + '"→"' + esc(c.newText) + '"'
      : esc(c.body);
    return '<span class="cmt cmt-' + (c.kind === "SUGG" ? "sugg" : "comm") +
      '" data-cid="' + c.cid + '">' + inner + "</span>";
  }
  function renderSheet() {
    var out = "", prev = 0, cs = sorted();
    for (var i = 0; i < cs.length; i++) {
      out += baseline.slice(prev, cs[i].offset) + markerHtml(cs[i]);
      prev = cs[i].offset;
    }
    out += baseline.slice(prev);
    sheet.innerHTML = window.marked ? window.marked.parse(out) : out;
    sheet.querySelectorAll(".cmt").forEach(function (el) {
      el.addEventListener("click", function (ev) {
        ev.stopPropagation();
        selectCard(+el.getAttribute("data-cid"));
      });
    });
  }

  // ---- comments panel ----
  function quoteFor(c) {
    var q = baseline.slice(Math.max(0, c.offset - 60), c.offset).replace(/\s+/g, " ").trim();
    return q ? "…" + q : "(start of document)";
  }
  function renderPanel() {
    list.innerHTML = "";
    var cs = sorted();
    countEl.textContent = String(cs.length);
    emptyEl.hidden = cs.length > 0;
    cs.forEach(function (c) {
      var card = document.createElement("div");
      card.className = "cp-card" + (c.kind === "SUGG" ? " sugg" : "");
      card.setAttribute("data-cid", c.cid);
      var meta = c.kind === "SUGG" ? "SUGG" : "COMM · " + c.type + " · " + c.sev;
      var body = c.kind === "SUGG"
        ? '"' + esc(c.oldText) + '" → "' + esc(c.newText) + '"'
        : esc(c.body);
      card.innerHTML =
        '<button type="button" class="linkbtn cp-del" data-cid="' + c.cid + '">delete</button>' +
        '<div class="cp-meta">' + meta + "</div>" +
        '<div class="cp-body">' + body + "</div>" +
        '<div class="cp-quote">' + esc(quoteFor(c)) + "</div>" +
        '<label class="cp-note-label">My private note' +
        '<textarea class="cp-note" data-key="' + c.offset + '">' + esc(notes[c.offset] || "") + "</textarea></label>";
      card.addEventListener("click", function (ev) {
        var t = ev.target;
        if (t.classList.contains("cp-del") || t.classList.contains("cp-note")) return;
        selectCard(c.cid);
      });
      list.appendChild(card);
    });
    list.querySelectorAll(".cp-del").forEach(function (b) {
      b.addEventListener("click", function () { deleteComment(+b.getAttribute("data-cid")); });
    });
    list.querySelectorAll(".cp-note").forEach(function (t) {
      t.addEventListener("input", debounce(function () { saveNote(t.getAttribute("data-key"), t.value); }, 500));
    });
  }
  function selectCard(cid) {
    jumpTo(cid);
    list.querySelectorAll(".cp-card.active").forEach(function (c) { c.classList.remove("active"); });
    var card = list.querySelector('.cp-card[data-cid="' + cid + '"]');
    if (card) { card.classList.add("active"); card.scrollIntoView({ block: "nearest" }); }
  }
  function jumpTo(cid) {
    var el = sheet.querySelector('.cmt[data-cid="' + cid + '"]');
    if (!el) return;
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    el.classList.remove("flash");
    void el.offsetWidth; // restart the animation
    el.classList.add("flash");
    setTimeout(function () { el.classList.remove("flash"); }, 2300);
  }
  function deleteComment(cid) {
    comments = comments.filter(function (c) { return c.cid !== cid; });
    refresh();
  }

  // ---- add a comment from a text selection ----
  function countOcc(hay, needle) {
    if (!needle) return 0;
    var n = 0, i = 0;
    while ((i = hay.indexOf(needle, i)) !== -1) { n++; i += needle.length; }
    return n;
  }
  function nthIndex(hay, needle, n) {
    var i = -1;
    for (var k = 0; k <= n; k++) { i = hay.indexOf(needle, i + 1); if (i === -1) return -1; }
    return i;
  }
  function selectionOffset() {
    var sel = window.getSelection();
    if (!sel || sel.rangeCount === 0 || sel.isCollapsed) return null;
    var r = sel.getRangeAt(0);
    if (!sheet.contains(r.commonAncestorContainer)) return null;
    var text = sel.toString().trim();
    if (!text) return null;
    var pre = document.createRange();
    pre.selectNodeContents(sheet);
    pre.setEnd(r.startContainer, r.startOffset);
    var occ = countOcc(pre.toString(), text);
    var idx = nthIndex(baseline, text, occ);
    if (idx === -1) return { text: text, offset: baseline.length }; // fallback: end
    return { text: text, offset: idx + text.length };
  }

  function toggleKind() {
    var sugg = document.getElementById("cmt-kind").value === "SUGG";
    document.getElementById("cmt-sugg-fields").hidden = !sugg;
    document.getElementById("cmt-comm-fields").hidden = sugg;
    document.getElementById("cmt-body").hidden = sugg;
  }
  function openPop(pageX, pageY, text) {
    document.getElementById("cmt-kind").value = "COMM";
    document.getElementById("cmt-body").value = "";
    document.getElementById("cmt-old").value = text;
    document.getElementById("cmt-new").value = "";
    toggleKind();
    pop.style.left = Math.max(8, Math.min(pageX, window.scrollX + window.innerWidth - 306)) + "px";
    pop.style.top = (pageY + 8) + "px";
    pop.hidden = false;
    document.getElementById("cmt-body").focus();
  }

  document.getElementById("cmt-kind").addEventListener("change", toggleKind);
  document.getElementById("cmt-cancel").addEventListener("click", function () { pop.hidden = true; pending = null; });
  document.getElementById("cmt-save").addEventListener("click", function () {
    if (!pending) return;
    var kind = document.getElementById("cmt-kind").value;
    var c = { cid: seq++, offset: pending.offset, kind: kind, type: "editorial", sev: "minor", body: "", oldText: "", newText: "" };
    if (kind === "SUGG") {
      c.oldText = document.getElementById("cmt-old").value;
      c.newText = document.getElementById("cmt-new").value;
      if (!c.oldText) return;
    } else {
      c.type = document.getElementById("cmt-type").value;
      c.sev = document.getElementById("cmt-sev").value;
      c.body = document.getElementById("cmt-body").value.trim();
      if (!c.body) return;
    }
    comments.push(c);
    pop.hidden = true; pending = null;
    window.getSelection().removeAllRanges();
    refresh();
  });
  sheet.addEventListener("mouseup", function (ev) {
    if (!pop.hidden) return;
    var a = selectionOffset();
    if (!a) return;
    pending = a;
    openPop(ev.pageX, ev.pageY, a.text);
  });
  document.addEventListener("mousedown", function (ev) {
    if (!pop.hidden && !pop.contains(ev.target)) { pop.hidden = true; pending = null; }
  });

  // ---- private notes (per reviewer, server-side) ----
  function loadNotes() {
    fetch("/ui/reviews/" + encodeURIComponent(reviewId) + "/my-notes", { credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.json() : {}; })
      .then(function (d) { notes = d || {}; renderPanel(); })
      .catch(function () {});
  }
  function saveNote(key, body) {
    notes[key] = body;
    var fd = new FormData();
    fd.append("anchor_key", key);
    fd.append("body", body);
    fetch("/ui/reviews/" + encodeURIComponent(reviewId) + "/my-notes",
      { method: "PUT", body: fd, credentials: "same-origin" });
  }
  function debounce(fn, ms) {
    var t;
    return function () { var a = arguments, self = this; clearTimeout(t); t = setTimeout(function () { fn.apply(self, a); }, ms); };
  }

  // ---- submit (reconstruct + client freeze pre-check) ----
  function stripBlocks(s) { return s.replace(blockRe(), ""); }
  function norm(s) { return s.replace(/\s+/g, " ").trim(); }
  function refresh() { reconstruct(); renderSheet(); renderPanel(); dirty = true; }
  form.addEventListener("submit", function (ev) {
    reconstruct();
    if (norm(stripBlocks(src.value)) !== norm(baseline)) {
      ev.preventDefault();
      var w = document.getElementById("freeze-warning");
      if (w) w.hidden = false;
    } else {
      dirty = false;
    }
  });
  window.addEventListener("beforeunload", function (ev) { if (dirty) { ev.preventDefault(); ev.returnValue = ""; } });

  // ---- init ----
  parse();
  renderSheet();
  renderPanel();
  loadNotes();
})();
