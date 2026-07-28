/* maluS unified document viewer (v2 step 4).

   One page for every role. The baseline Markdown is parsed CLEAN by marked:
   markers are injected as invisible sentinel tokens (U+E000 key U+E000) at
   their baseline character offsets BEFORE parsing — a text token cannot
   break tables, fences or lists — then the sentinels are swapped for marker
   elements in the rendered DOM, after DOMPurify sanitization.

   Capabilities are mirrored from the server payload (#viewer-data) and are
   UI sugar only — every mutation posts to the same server endpoints that
   enforce authorization regardless of what this script renders.

   A reviewer's own comments render from their local copy (editable, the
   Save/Submit contract of v1.6 is unchanged); everyone else's come from the
   harvested RTD, colored per reviewer. */
(function () {
  "use strict";
  var dataEl = document.getElementById("viewer-data");
  if (!dataEl) return;
  var data = JSON.parse(dataEl.textContent);
  var sheet = document.getElementById("sheet");
  var list = document.getElementById("cp-list");
  var countEl = document.getElementById("cp-count");
  var emptyEl = document.getElementById("cp-empty");
  var legendEl = document.getElementById("legend");
  var form = document.getElementById("rev-form");
  var src = document.getElementById("content-src");
  var pop = document.getElementById("cmt-pop");

  var S = "\uE000"; // sentinel (Unicode private use)
  var baseline = data.baseline;
  var base = "/ui/reviews/" + encodeURIComponent(data.reviewId);

  var revIdx = {};
  data.reviewers.forEach(function (n, i) { revIdx[n] = i % 8; });
  function colorClass(reviewer) {
    return "rev-" + (revIdx[reviewer] !== undefined ? revIdx[reviewer] : 0);
  }
  function customColor(reviewer) { // v2.1: resolved override/global, else null
    return (data.colors && data.colors[reviewer]) || null;
  }
  function applyColor(el, reviewer) {
    var c = customColor(reviewer);
    if (c) el.style.setProperty("--rev-color", c);
  }
  function chipHtml(reviewer, extra) {
    var c = customColor(reviewer);
    return '<span class="rev-chip ' + colorClass(reviewer) + '"' +
      (c ? ' style="--rev-color: ' + esc(c) + '"' : "") + ">" +
      esc(reviewer) + (extra || "") + "</span>";
  }

  function esc(s) {
    return (s || "").replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  /* ---------------- local copy (reviewer only) — v1.4 logic carried over */
  var comments = []; // {cid, offset, kind, type, sev, body, oldText, newText}
  var seq = 1;
  var notes = {};
  var dirty = false;
  var pending = null;

  function blockReSimple() { return /\{(?:COMM|SUGG)\b[\s\S]*?\}/g; }
  function unesc(s) { return s.replace(/\\"/g, '"').replace(/\\\}/g, "}"); }
  function escq(s) { return s.replace(/"/g, '\\"').replace(/\}/g, "\\}"); }

  function parseCopy() {
    comments = [];
    if (!data.isReviewer || !data.myCopy) return;
    var content = data.myCopy, re = blockReSimple(), m, baseOff = 0, last = 0;
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
  function blockText(c) {
    if (c.kind === "SUGG") return '{SUGG: "' + escq(c.oldText) + '" -> "' + escq(c.newText) + '"}';
    return "{COMM|type=" + c.type + "|sev=" + c.sev + ": " + c.body.replace(/\}/g, "\\}") + "}";
  }
  function reconstruct() {
    if (!src) return;
    var out = "", prev = 0;
    var cs = comments.slice().sort(function (a, b) { return a.offset - b.offset; });
    for (var i = 0; i < cs.length; i++) {
      out += baseline.slice(prev, cs[i].offset) + blockText(cs[i]);
      prev = cs[i].offset;
    }
    src.value = out + baseline.slice(prev);
  }

  /* identity match: local comment ⇄ its harvested RID (same rule as server) */
  function suggRepr(oldText, newText) { return '"' + escq(oldText) + '" -> "' + escq(newText) + '"'; }
  function localIdentity(c) {
    if (c.kind === "SUGG") return ["SUGG", "", "", suggRepr(c.oldText, c.newText)].join("");
    return ["COMM", c.type, c.sev, c.body].join("");
  }
  function ridIdentity(r) {
    return [r.kind, r.type || "", r.severity || "", r.comment].join("");
  }

  /* ---------------- unified item list (document order) ------------------ */
  function lineOffset(line) {
    if (!line || line < 2) return 0;
    var idx = -1;
    for (var k = 1; k < line; k++) {
      idx = baseline.indexOf("\n", idx + 1);
      if (idx === -1) return baseline.length;
    }
    return idx + 1;
  }
  function items() {
    var out = [];
    var ridByIdentity = {};
    data.rids.forEach(function (r) {
      if (data.isReviewer && r.mine) { ridByIdentity[ridIdentity(r)] = r; return; }
      out.push({
        key: "r:" + r.rid,
        offset: r.offset !== null && r.offset !== undefined ? r.offset : lineOffset(r.lineHint),
        rid: r,
        local: null,
      });
    });
    comments.forEach(function (c) {
      out.push({
        key: "c:" + c.cid,
        offset: c.offset,
        rid: ridByIdentity[localIdentity(c)] || null,
        local: c,
      });
    });
    out.sort(function (a, b) { return a.offset - b.offset || a.key.localeCompare(b.key); });
    return out;
  }

  /* ---------------- rendering ------------------------------------------ */
  function renderSheet(its) {
    var outSrc = "", prev = 0;
    its.forEach(function (it) {
      var off = Math.max(0, Math.min(it.offset, baseline.length));
      outSrc += baseline.slice(prev, off) + S + it.key + S;
      prev = off;
    });
    outSrc += baseline.slice(prev);
    var html = window.marked ? window.marked.parse(outSrc) : esc(outSrc);
    if (window.DOMPurify) html = window.DOMPurify.sanitize(html);
    sheet.innerHTML = html;

    var walker = document.createTreeWalker(sheet, NodeFilter.SHOW_TEXT);
    var nodes = [];
    while (walker.nextNode()) {
      if (walker.currentNode.nodeValue.indexOf(S) !== -1) nodes.push(walker.currentNode);
    }
    var byKey = {};
    its.forEach(function (it) { byKey[it.key] = it; });
    nodes.forEach(function (node) {
      var parts = node.nodeValue.split(S);
      var frag = document.createDocumentFragment();
      for (var i = 0; i < parts.length; i++) {
        if (i % 2 === 0) {
          if (parts[i]) frag.appendChild(document.createTextNode(parts[i]));
        } else if (byKey[parts[i]]) {
          frag.appendChild(markerEl(byKey[parts[i]]));
        }
      }
      node.parentNode.replaceChild(frag, node);
    });
  }
  function markerEl(it) {
    var el = document.createElement("button");
    el.type = "button";
    var reviewer = it.rid ? it.rid.reviewer : data.me;
    var kind = it.rid ? it.rid.kind : it.local.kind;
    el.className = "marker " + colorClass(reviewer) + (kind === "SUGG" ? " sugg" : "") +
      (it.local && !it.rid ? " unsaved" : "");
    applyColor(el, reviewer);
    el.setAttribute("data-key", it.key);
    el.title = reviewer + (it.rid ? " · " + it.rid.rid : " · not saved yet");
    el.addEventListener("click", function (ev) {
      ev.stopPropagation();
      selectCard(it.key);
    });
    return el;
  }

  function renderLegend() {
    legendEl.innerHTML = "";
    data.reviewers.forEach(function (n) {
      var chip = document.createElement("span");
      chip.className = "rev-chip " + colorClass(n);
      applyColor(chip, n);
      chip.textContent = n + (n === data.me ? " (you)" : "");
      legendEl.appendChild(chip);
    });
  }

  function post(action, fields, confirmMsg) {
    if (confirmMsg && !window.confirm(confirmMsg)) return null;
    var f = document.createElement("form");
    f.method = "post";
    f.action = action;
    Object.keys(fields || {}).forEach(function (k) {
      var input = document.createElement("input");
      input.type = "hidden";
      input.name = k;
      input.value = fields[k];
      f.appendChild(input);
    });
    document.body.appendChild(f);
    f.submit();
    return f;
  }

  function cardEl(it) {
    var r = it.rid, c = it.local;
    var reviewer = r ? r.reviewer : data.me;
    var kind = r ? r.kind : c.kind;
    var card = document.createElement("div");
    card.className = "cp-card " + colorClass(reviewer) + (kind === "SUGG" ? " sugg" : "");
    applyColor(card, reviewer);
    card.setAttribute("data-key", it.key);

    var head = document.createElement("div");
    head.className = "cp-head";
    var metaBits = [];
    if (r) metaBits.push('<span class="cp-rid">' + esc(r.rid) + "</span>");
    metaBits.push(kind === "SUGG" ? "SUGG" : "COMM · " + esc(r ? (r.type || "") : c.type) + " · " + esc(r ? (r.severity || "") : c.sev));
    head.innerHTML =
      chipHtml(reviewer) +
      '<span class="cp-meta">' + metaBits.join(" · ") + "</span>" +
      (r ? ' <span class="st st-' + r.status + '">' + r.status + "</span>" : ' <span class="st st-unsaved">unsaved</span>') +
      (r && r.disposition ? ' <span class="st">' + esc(r.disposition) + "</span>" : "") +
      (r && r.aiProposal ? ' <span class="badge ai-badge">AI</span>' : "");
    card.appendChild(head);

    var body = document.createElement("div");
    body.className = "cp-body";
    if (kind === "SUGG") {
      body.innerHTML = c
        ? '"' + esc(c.oldText) + '" → "' + esc(c.newText) + '"'
        : esc(r.comment);
    } else {
      body.textContent = c ? c.body : r.comment;
    }
    card.appendChild(body);

    if (r) { // fixed record: anchor context + owner-side values, read-only
      var bits = [];
      if (r.section) bits.push("§ " + r.section);
      if (r.lineHint) bits.push("line " + r.lineHint);
      if (bits.length) {
        var det = document.createElement("div");
        det.className = "cp-detail";
        det.textContent = bits.join(" · ");
        card.appendChild(det);
      }
      var record = [];
      if (r.reply) record.push("<div class='cp-record'><b>Owner reply:</b> " + esc(r.reply) + "</div>");
      if (r.resolution) record.push("<div class='cp-record'><b>Resolution:</b> " + esc(r.resolution) + "</div>");
      if (r.verifiedBy) record.push("<div class='cp-record'><b>Verified by:</b> " + esc(r.verifiedBy) + (r.verifiedOn ? " on " + esc(r.verifiedOn) : "") + "</div>");
      if (record.length) {
        var rec = document.createElement("div");
        rec.className = "cp-records";
        rec.innerHTML = record.join("");
        card.appendChild(rec);
      }
      if (r.history && r.history.length) card.appendChild(historyEl(r));
    }

    var actions = document.createElement("div");
    actions.className = "cp-actions";

    if (c) { // own local comment: edit/delete + private note
      var del = document.createElement("button");
      del.type = "button";
      del.className = "linkbtn cp-del";
      del.textContent = "delete";
      del.addEventListener("click", function (ev) {
        ev.stopPropagation();
        comments = comments.filter(function (x) { return x.cid !== c.cid; });
        refresh(true);
      });
      actions.appendChild(del);

      var noteLabel = document.createElement("label");
      noteLabel.className = "cp-note-label";
      noteLabel.textContent = "My private note";
      var note = document.createElement("textarea");
      note.className = "cp-note";
      note.value = notes[c.offset] || "";
      note.addEventListener("click", function (ev) { ev.stopPropagation(); });
      note.addEventListener("input", debounce(function () { saveNote(String(c.offset), note.value); }, 500));
      noteLabel.appendChild(note);
      card.appendChild(noteLabel);
    }

    if (r && data.canDispose) { // owner/admin: inline disposition
      var toggle = document.createElement("button");
      toggle.type = "button";
      toggle.className = "secondary cp-dispose-toggle";
      toggle.textContent = r.aiProposal ? "Review AI draft…" : (r.disposition ? "Change disposition…" : "Dispose…");
      var dform = disposeForm(r);
      dform.hidden = true;
      toggle.addEventListener("click", function (ev) {
        ev.stopPropagation();
        dform.hidden = !dform.hidden;
      });
      actions.appendChild(toggle);
      card.appendChild(dform);
    }

    if (r && r.canVerify && (r.status === "answered" || r.status === "implemented")) {
      var verify = document.createElement("button");
      verify.type = "button";
      verify.className = "primary cp-verify";
      verify.textContent = "Verify";
      verify.addEventListener("click", function (ev) {
        ev.stopPropagation();
        post(base + "/rids/" + encodeURIComponent(r.rid) + "/verify", {});
      });
      actions.appendChild(verify);
    }
    if (r && r.canVerify && r.status === "verified") {
      var reopen = document.createElement("button");
      reopen.type = "button";
      reopen.className = "cp-reopen";
      reopen.textContent = "Reopen…";
      reopen.addEventListener("click", function (ev) {
        ev.stopPropagation();
        var reason = window.prompt("Reopen reason for " + r.rid + ":");
        if (reason) post(base + "/rids/" + encodeURIComponent(r.rid) + "/reopen", { reason: reason });
      });
      actions.appendChild(reopen);
    }
    if (r && r.canRetract && !c) { // harvested comment retraction (own OPEN / admin any)
      var retract = document.createElement("button");
      retract.type = "button";
      retract.className = "linkbtn retract-btn";
      retract.textContent = "✕ delete";
      retract.addEventListener("click", function (ev) {
        ev.stopPropagation();
        post(base + "/rids/" + encodeURIComponent(r.rid) + "/retract", {},
          "Delete comment " + r.rid + "? An acted-upon comment becomes withdrawn.");
      });
      actions.appendChild(retract);
    }
    if (r && r.canPurge) { // v2.2: admin-only permanent removal, double confirm
      var purge = document.createElement("button");
      purge.type = "button";
      purge.className = "danger cp-purge";
      purge.textContent = "Purge permanently";
      purge.addEventListener("click", function (ev) {
        ev.stopPropagation();
        if (!window.confirm("PERMANENTLY remove " + r.rid + "? It disappears from the review and the RTD.")) return;
        if (!window.confirm("Really purge " + r.rid + "? Only the audit log will keep a trace. This cannot be undone.")) return;
        post(base + "/rids/" + encodeURIComponent(r.rid) + "/purge", {});
      });
      actions.appendChild(purge);
    }
    if (actions.childNodes.length) card.appendChild(actions);

    card.addEventListener("click", function (ev) {
      var t = ev.target;
      // ignore interactive children only — the whole viewer sits inside the
      // outer #rev-form, so matching bare "form" would swallow every click
      if (t.closest && t.closest(".cp-dispose, .cp-history, button, textarea, select, input, label, a")) return;
      selectCard(it.key);
    });
    return card;
  }

  function historyLine(e) {
    var what = e.action.replace(/_/g, " ");
    var extra = "";
    if (e.detail) {
      if (e.detail.disposition) extra = " → " + e.detail.disposition;
      else if (e.detail.changed) {
        extra = " → " + Object.keys(e.detail.changed).map(function (k) {
          return k + ": " + e.detail.changed[k];
        }).join(", ");
      } else if (e.detail.reason) extra = " — " + e.detail.reason;
    }
    return "<li><span class='hist-ts'>" + esc((e.ts || "").replace("T", " ")) +
      "</span> <b>" + esc(what) + "</b>" + esc(extra) +
      (e.actor ? " <span class='hist-actor'>· " + esc(e.actor) + "</span>" : "") + "</li>";
  }
  function historyEl(r) {
    var det = document.createElement("details");
    det.className = "cp-history";
    det.innerHTML = "<summary>History (" + r.history.length + ")</summary><ul>" +
      r.history.map(historyLine).join("") + "</ul>";
    det.addEventListener("click", function (ev) { ev.stopPropagation(); });
    return det;
  }

  function disposeForm(r) {
    var f = document.createElement("form");
    f.method = "post";
    f.action = base + "/rids/" + encodeURIComponent(r.rid) + "/dispose";
    f.className = "stack cp-dispose";
    f.setAttribute("hx-boost", "false");
    var opts = ["accepted", "rejected", "deferred"].map(function (d) {
      return '<option value="' + d + '"' + (r.disposition === d ? " selected" : "") + ">" + d + "</option>";
    }).join("");
    f.innerHTML =
      (r.aiProposal ? '<p class="flash ai-proposal">🤖 AI-drafted — confirm to commit, or discard.</p>' : "") +
      "<label>Disposition <select name=\"disposition\" required>" + opts + "</select></label>" +
      '<label>Reply <textarea name="reply" rows="2">' + esc(r.reply || "") + "</textarea></label>" +
      '<label>Resolution <textarea name="resolution" rows="2">' + esc(r.resolution || "") + "</textarea></label>" +
      '<button class="primary">' + (r.aiProposal ? "Confirm disposition" : "Save disposition") + "</button>";
    if (r.aiProposal) {
      var discard = document.createElement("button");
      discard.type = "button";
      discard.className = "danger";
      discard.textContent = "Discard AI draft";
      discard.addEventListener("click", function (ev) {
        ev.stopPropagation();
        post(base + "/rids/" + encodeURIComponent(r.rid) + "/discard-draft", {},
          "Discard the AI draft for " + r.rid + "?");
      });
      f.appendChild(discard);
    }
    f.addEventListener("click", function (ev) { ev.stopPropagation(); });
    return f;
  }

  function renderPanel(its) {
    list.innerHTML = "";
    countEl.textContent = String(its.length);
    emptyEl.hidden = its.length > 0;
    its.forEach(function (it) { list.appendChild(cardEl(it)); });
  }

  /* ------- focus: click a comment to focus it, click away / ESC to exit --
     (v2.1: no explicit enter/exit controls; clicking another comment moves
     the focus; a text selection never exits) */
  var focusKey = null;
  var currentItems = [];

  function itemByKey(key) {
    for (var i = 0; i < currentItems.length; i++) {
      if (currentItems[i].key === key) return currentItems[i];
    }
    return null;
  }
  function keyForRid(ridStr) {
    for (var i = 0; i < currentItems.length; i++) {
      var it = currentItems[i];
      if (it.rid && it.rid.rid === ridStr) return it.key;
    }
    return null;
  }
  function flashEl(el) {
    el.classList.remove("flash");
    void el.offsetWidth;
    el.classList.add("flash");
    setTimeout(function () { el.classList.remove("flash"); }, 2300);
  }
  function setFocus(key, opts) {
    opts = opts || {};
    focusKey = key;
    sheet.classList.toggle("focus-mode", !!key);
    sheet.querySelectorAll(".marker").forEach(function (m) {
      m.classList.toggle("focused", m.getAttribute("data-key") === key);
    });
    list.querySelectorAll(".cp-card").forEach(function (el) {
      var on = el.getAttribute("data-key") === key;
      el.classList.toggle("active", on);
      el.classList.toggle("focus-card", on);
      if (on) {
        var h = el.querySelector(".cp-history");
        if (h) h.open = true;
      }
    });
    if (window.history && history.replaceState) {
      var it = key ? itemByKey(key) : null;
      history.replaceState(null, "", it && it.rid
        ? base + "/document?focus=" + encodeURIComponent(it.rid.rid)
        : base + "/document");
    }
    if (key && opts.scroll !== false) {
      var marker = sheet.querySelector('.marker[data-key="' + CSS.escape(key) + '"]');
      if (marker) { marker.scrollIntoView({ behavior: "smooth", block: "center" }); flashEl(marker); }
      var card = list.querySelector('.cp-card[data-key="' + CSS.escape(key) + '"]');
      if (card) card.scrollIntoView({ block: "nearest" });
    }
  }
  function selectCard(key) { setFocus(key, { scroll: true }); }

  document.addEventListener("click", function (ev) {
    if (!focusKey) return;
    var t = ev.target;
    // interactive targets and comment surfaces keep the focus; the outer
    // #rev-form wraps everything, so bare "form" must NOT be matched here
    if (t.closest && t.closest(".marker, .cp-card, .cmt-pop, button, input, select, textarea, label, summary, a")) return;
    var sel = window.getSelection();
    if (sel && !sel.isCollapsed) return; // selecting text is not "clicking away"
    setFocus(null);
  });
  document.addEventListener("keydown", function (ev) {
    if (ev.key !== "Escape") return;
    if (pop && !pop.hidden) { pop.hidden = true; pending = null; return; }
    if (focusKey) setFocus(null);
  });

  /* ---------------- add-comment popover (reviewer) ---------------------- */
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
    if (idx === -1) return { text: text, offset: baseline.length };
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
  if (data.isReviewer && pop) {
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
      pop.hidden = true;
      pending = null;
      window.getSelection().removeAllRanges();
      refresh(true);
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
  }

  /* ---------------- private notes (reviewer) ---------------------------- */
  function loadNotes() {
    if (!data.isReviewer) return;
    fetch(base + "/my-notes", { credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.json() : {}; })
      .then(function (d) { notes = d || {}; refresh(false); })
      .catch(function () {});
  }
  function saveNote(key, body) {
    notes[key] = body;
    var fd = new FormData();
    fd.append("anchor_key", key);
    fd.append("body", body);
    fetch(base + "/my-notes", { method: "PUT", body: fd, credentials: "same-origin" });
  }
  function debounce(fn, ms) {
    var t;
    return function () {
      var a = arguments, self = this;
      clearTimeout(t);
      t = setTimeout(function () { fn.apply(self, a); }, ms);
    };
  }

  /* ---------------- submit: reconstruct + client freeze pre-check ------- */
  function stripBlocks(s) { return s.replace(blockReSimple(), ""); }
  function norm(s) { return s.replace(/\s+/g, " ").trim(); }
  if (form && data.isReviewer) {
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
    window.addEventListener("beforeunload", function (ev) {
      if (dirty) { ev.preventDefault(); ev.returnValue = ""; }
    });
  }

  /* ---------------- init ------------------------------------------------ */
  function refresh(markDirty) {
    if (markDirty) dirty = true;
    reconstruct();
    currentItems = items();
    renderSheet(currentItems);
    renderPanel(currentItems);
    if (data.focus) { // deep link / post-action redirect: focus once, scrolled
      var key = keyForRid(data.focus);
      data.focus = null;
      if (key) { setTimeout(function () { setFocus(key, { scroll: true }); }, 60); return; }
    }
    // re-apply the current focus across re-renders (no scroll jump)
    setFocus(focusKey && itemByKey(focusKey) ? focusKey : null, { scroll: false });
  }
  parseCopy();
  renderLegend();
  refresh(false);
  loadNotes();
})();
