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
  var editEl = document.getElementById("doc-edit"); // v3.1: closeout editor
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
    if (data.phase === "closeout") {
      // closeout: the sheet shows the LATEST version, unmarked — comment
      // offsets belong to the baseline and no longer line up. marked +
      // DOMPurify, same pipeline as the review-phase sheet.
      var csrc = editEl ? editEl.value : data.latest;
      var cout = window.marked ? window.marked.parse(csrc) : esc(csrc);
      sheet.innerHTML = window.DOMPurify ? window.DOMPurify.sanitize(cout) : cout;
      return;
    }
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
    var phase = data.phase;
    var reviewer = r ? r.reviewer : data.me;
    var kind = r ? r.kind : c.kind;
    var card = document.createElement("div");
    card.className = "cp-card " + colorClass(reviewer) + (kind === "SUGG" ? " sugg" : "");
    applyColor(card, reviewer);
    card.setAttribute("data-key", it.key);
    if (phase === "closeout") {
      // collapsed by default: the queue must stay scannable; the head toggles
      card.classList.add("collapsed");
      card.addEventListener("click", function (ev) {
        if (ev.target.closest(".cp-body, .cp-actions, .cp-changes, button, input, textarea, select, label, a, summary")) return;
        card.classList.toggle("collapsed");
      });
    }

    var head = document.createElement("div");
    head.className = "cp-head";
    var metaBits = [];
    if (r) metaBits.push('<span class="cp-rid">' + esc(r.rid) + "</span>");
    metaBits.push(kind === "SUGG" ? "SUGG" : "COMM · " + esc(r ? (r.type || "") : c.type) + " · " + esc(r ? (r.severity || "") : c.sev));
    head.innerHTML =
      chipHtml(reviewer) +
      '<span class="cp-meta">' + metaBits.join(" · ") + "</span>" +
      (r ? ' <span class="st st-' + r.status + '">' + r.status + "</span>" : ' <span class="st st-unsaved">unsaved</span>') +
      (r && r.draft ? ' <span class="st st-draft">draft</span>' : "") +
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

    if (r && r.rework) {
      // v3.2 point 10: an outstanding rework request is a work item, not a log
      // line. It used to reach the owner only as a suffix inside their own
      // reply field, or buried in the history — so it sits right under the
      // comment, before anything else the card has to say.
      var rw = document.createElement("div");
      rw.className = "cp-rework";
      var rwHead = document.createElement("div");
      rwHead.className = "cp-rework-head";
      rwHead.textContent = "Changes requested"
        + (r.rework.by ? " by " + r.rework.by : "")
        + (r.rework.at ? " · " + r.rework.at.slice(0, 10) : "");
      var rwBody = document.createElement("div");
      rwBody.className = "cp-rework-body";
      rwBody.textContent = r.rework.reason || "(no reason recorded)";
      rw.appendChild(rwHead);
      rw.appendChild(rwBody);
      card.appendChild(rw);
    }

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

    if (r && r.changes && r.changes.length) {
      // v3.2 point 9: closed by default, like the history below it. A card in
      // the closeout queue opens with its text, not with a wall of diff.
      var chWrap = document.createElement("details");
      chWrap.className = "cp-changes";
      var chTitle = document.createElement("summary");
      chTitle.className = "cp-changes-title";
      chTitle.textContent = "Changes (" + r.changes.length + ")";
      chWrap.appendChild(chTitle);
      r.changes.forEach(function (ch) {
        var block = document.createElement("div");
        block.className = "cp-change";
        var head = document.createElement("div");
        head.className = "cp-change-head";
        head.textContent = "v" + ch.ordinal + (ch.note ? " — " + ch.note : "");
        block.appendChild(head);
        var body = document.createElement("div");
        // server-built, escaped diff; DOMPurify pass = defense in depth
        body.innerHTML = window.DOMPurify
          ? window.DOMPurify.sanitize(ch.diffHtml)
          : ch.diffHtml;
        block.appendChild(body);
        chWrap.appendChild(block);
      });
      card.appendChild(chWrap);
    }

    var actions = document.createElement("div");
    actions.className = "cp-actions";

    var bin = binFor(c, r);   // v3.2 point 7: one 🗑 per comment, role-aware
    if (bin) actions.appendChild(bin);
    if (data.role || data.isAdmin) { // v3: every member gets a private note on
      // any comment (e.g. the owner annotates a draft they cannot dispose yet)
      var noteKey = String(c ? c.offset : r.offset);
      var noteLabel = document.createElement("label");
      noteLabel.className = "cp-note-label";
      noteLabel.textContent = "My private note";
      var note = document.createElement("textarea");
      note.className = "cp-note";
      note.value = notes[noteKey] || "";
      note.addEventListener("click", function (ev) { ev.stopPropagation(); });
      note.addEventListener("input", debounce(function () { saveNote(noteKey, note.value); }, 500));
      noteLabel.appendChild(note);
      card.appendChild(noteLabel);
    }

    if (r && data.canDispose && r.status === "open" && phase === "in_review" && !r.draft) {
      // ONE button (v3): the dispose form sits inline on an open finding and
      // its single submit reads "Save disposition". Only the special
      // AI-proposal flow keeps a disclosure toggle (confirm/discard pair).
      var dform = disposeForm(r);
      if (r.aiProposal) {
        var toggle = document.createElement("button");
        toggle.type = "button";
        toggle.className = "secondary cp-dispose-toggle";
        toggle.textContent = "Review AI draft…";
        dform.hidden = true;
        toggle.addEventListener("click", function (ev) {
          ev.stopPropagation();
          dform.hidden = !dform.hidden;
        });
        actions.appendChild(toggle);
      }
      card.appendChild(dform);
    }

    if (r && data.canDispose && r.status === "answered" && phase === "in_review") {
      // v3: until the reviewer accepts it, the owner may still fix or change
      // the disposition (typo in the reply, changed mind) — one "Edit
      // disposition" button that reveals the prefilled form; from "closed"
      // onward it is settled (reopen only)
      var editToggle = document.createElement("button");
      editToggle.type = "button";
      editToggle.className = "secondary cp-dispose-toggle";
      editToggle.textContent = "Edit disposition";
      var eform = disposeForm(r);
      // v3.2 point 8: locked means locked. `hidden` takes the form out of the
      // page, but its fields stayed enabled and would still be submitted by a
      // stray Enter; disabling them makes the lock real rather than visual.
      var setLocked = function (locked) {
        eform.hidden = locked;
        eform.querySelectorAll("select, textarea, input, button").forEach(function (f) {
          f.disabled = locked;
        });
      };
      setLocked(true);
      editToggle.addEventListener("click", function (ev) {
        ev.stopPropagation();
        setLocked(!eform.hidden ? true : false);
        editToggle.hidden = !eform.hidden;  // never two dispose buttons at once
      });
      actions.appendChild(editToggle);
      card.appendChild(eform);
    }


    if (r && r.canVerify && phase === "in_review" && r.status === "answered") {
      var accept = document.createElement("button");
      accept.type = "button";
      accept.className = "primary cp-accept";
      accept.textContent = "Accept disposition";
      accept.addEventListener("click", function (ev) {
        ev.stopPropagation();
        post(base + "/rids/" + encodeURIComponent(r.rid) + "/accept", {});
      });
      actions.appendChild(accept);
    }
    if (r && r.canVerify && phase === "in_review" && (r.status === "answered" || r.status === "closed")) {
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
    if (r && r.canVerify && phase === "closeout" && r.status === "implemented") {
      var verify = document.createElement("button");
      verify.type = "button";
      verify.className = "primary cp-verify";
      verify.textContent = "Verify";
      verify.addEventListener("click", function (ev) {
        ev.stopPropagation();
        post(base + "/rids/" + encodeURIComponent(r.rid) + "/verify", {});
      });
      actions.appendChild(verify);
      var rc = document.createElement("button");
      rc.type = "button";
      rc.className = "warn cp-request-changes";
      rc.textContent = "Request changes…";
      rc.addEventListener("click", function (ev) {
        ev.stopPropagation();
        var reason = window.prompt("What still needs work on " + r.rid + "?");
        if (reason) post(base + "/rids/" + encodeURIComponent(r.rid) + "/request-changes", { reason: reason });
      });
      actions.appendChild(rc);
    }
    if (r && r.canVerify && phase === "closeout" && r.status === "verified") {
      // reopen a verdict during closeout = request changes (verified → closed)
      var undo = document.createElement("button");
      undo.type = "button";
      undo.className = "cp-reopen";
      undo.textContent = "Reopen…";
      undo.addEventListener("click", function (ev) {
        ev.stopPropagation();
        var reason = window.prompt("Reopen reason for " + r.rid + ":");
        if (reason) post(base + "/rids/" + encodeURIComponent(r.rid) + "/request-changes", { reason: reason });
      });
      actions.appendChild(undo);
    }
    if (r && data.canEditDoc && (r.queue === "todo" || r.queue === "rework")) {
      // v3.2 point 13: the editor is locked until a finding is opened for
      // implementation, and one session is open at a time. The v3.1 checkbox
      // picker is gone — ticking findings after the fact made the pairing an
      // assertion; a session makes it a fact, which is what lets step 05
      // attribute each hunk of the final diff to the comment behind it.
      var open = session && session.rid === r.rid;
      var impl = document.createElement("button");
      impl.type = "button";
      impl.className = "primary cp-implement";
      impl.textContent = open ? "Close and associate change" : "Implement comment";
      impl.disabled = !!session && !open;
      if (impl.disabled) impl.title = "Close the change in progress first";
      impl.addEventListener("click", function (ev) {
        ev.stopPropagation();
        if (open) openCloseSession(r);
        else startSession(r);
      });
      actions.appendChild(impl);

      if (open) {
        var cancel = document.createElement("button");
        cancel.type = "button";
        cancel.className = "cp-session-cancel";
        cancel.textContent = "Cancel";
        cancel.addEventListener("click", function (ev) {
          ev.stopPropagation();
          if (window.confirm("Abandon this change? The text you typed is lost.")) endSession();
        });
        actions.appendChild(cancel);
      }
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
    // v3: no Resolution here — it records what was implemented (closeout);
    // a dispose is Disposition + Reply, one Save button
    f.innerHTML =
      (r.aiProposal ? '<p class="flash ai-proposal">🤖 AI-drafted — confirm to commit, or discard.</p>' : "") +
      "<label>Disposition <select name=\"disposition\" required>" + opts + "</select></label>" +
      '<label>Reply <textarea name="reply" rows="2">' + esc(r.reply || "") + "</textarea></label>" +
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

  /* ---------------- one implementation session (v3.2 point 13) ---------- */
  /* The closeout editor is locked until a finding is opened for implementation,
     and exactly one session is open at a time. `session` is the single source
     of truth: the textarea's readonly, the card buttons, the hint and the
     submit all read it, so they cannot disagree. It is deliberately client
     state — a reload drops it, with a warning, and the server stays the
     authority on every rule (≥1 accepted finding, text actually changed). */
  var session = null;   // {rid: "<RID>"} while a change is being made

  function startSession(r) {
    session = { rid: r.rid };
    setMode(true);
    syncSession();
    refresh(false);
    if (editEl) editEl.focus();
  }

  function endSession() {
    session = null;
    if (editEl) editEl.value = data.latest;   // discard the unsaved text
    setMode(false);
    syncSession();
    refresh(false);
  }

  function syncSession() {
    if (!editEl) return;
    editEl.readOnly = !session;
    var hint = document.getElementById("doc-edit-hint");
    if (hint) hint.hidden = !!session;
    var modeEditBtn = document.getElementById("doc-mode-edit");
    if (modeEditBtn) modeEditBtn.title = session
      ? "Editing for " + session.rid
      : "Pick a finding to implement first";
    syncSaveButton();
  }

  /* Closing a session: name the duplicates this same edit resolves, record the
     resolution, and post them together. The panel is built on demand rather
     than living in every card, so nothing about it can be half-filled. */
  function openCloseSession(r) {
    var others = (data.rids || []).filter(function (x) {
      return x.rid !== r.rid && (x.queue === "todo" || x.queue === "rework");
    });
    var wrap = document.getElementById("session-close") || document.createElement("dialog");
    wrap.id = "session-close";
    wrap.className = "bin-dlg session-dlg";
    if (!wrap.isConnected) document.body.appendChild(wrap);
    wrap.innerHTML = "";

    var h = document.createElement("h3");
    h.className = "bin-dlg-title";
    h.textContent = "Close and associate change — " + r.rid;
    var p = document.createElement("p");
    p.textContent = "This edit is recorded against " + r.rid
      + " and the finding moves to Awaiting verification.";
    wrap.appendChild(h);
    wrap.appendChild(p);

    var resLabel = document.createElement("label");
    resLabel.className = "session-res";
    resLabel.textContent = "Resolution (optional)";
    var res = document.createElement("input");
    res.type = "text";
    res.placeholder = "what was done";
    resLabel.appendChild(res);
    wrap.appendChild(resLabel);

    var picks = [];
    if (others.length) {
      var dupTitle = document.createElement("p");
      dupTitle.className = "session-dup-title";
      dupTitle.textContent = "Does this same change resolve any of these too?";
      wrap.appendChild(dupTitle);
      others.forEach(function (o) {
        var lab = document.createElement("label");
        lab.className = "session-dup";
        var box = document.createElement("input");
        box.type = "checkbox";
        box.value = o.rid;
        lab.appendChild(box);
        lab.appendChild(document.createTextNode(" " + o.rid + " — " + (o.comment || "").slice(0, 70)));
        wrap.appendChild(lab);
        picks.push(box);
      });
    }

    var row = document.createElement("div");
    row.className = "bin-dlg-actions";
    var ok = document.createElement("button");
    ok.type = "button";
    ok.className = "primary";
    ok.textContent = "Close and associate change";
    ok.disabled = !editEl || editEl.value === data.latest;
    if (ok.disabled) {
      var warn = document.createElement("p");
      warn.className = "session-warn";
      warn.textContent = "The document has not changed yet, so there is nothing to associate.";
      wrap.appendChild(warn);
    }
    ok.addEventListener("click", function () {
      var rids = [r.rid].concat(picks.filter(function (b) { return b.checked; })
        .map(function (b) { return b.value; }));
      wrap.close();
      submitSession(rids, res.value);
    });
    var cancel = document.createElement("button");
    cancel.type = "button";
    cancel.textContent = "Keep editing";
    cancel.addEventListener("click", function () { wrap.close(); });
    row.appendChild(ok);
    row.appendChild(cancel);
    wrap.appendChild(row);
    wrap.showModal();
  }

  function submitSession(rids, resolution) {
    if (!form) return;
    form.querySelectorAll('input[name="rids"], input[name="resolution"]').forEach(function (el) {
      el.remove();
    });
    rids.forEach(function (rid) {
      var h = document.createElement("input");
      h.type = "hidden";
      h.name = "rids";
      h.value = rid;
      form.appendChild(h);
    });
    var rh = document.createElement("input");
    rh.type = "hidden";
    rh.name = "resolution";
    rh.value = resolution || "";
    form.appendChild(rh);
    session = null;          // the page is leaving; do not warn about the text
    form.submit();
  }

  function syncSaveButton() {
    var btn = document.getElementById("closeout-save");
    if (!btn || !editEl) return;
    btn.disabled = !session || editEl.value === data.latest;
  }

  /* v3.1: in closeout the panel IS the work queue — the four groups the
     standalone workspace had, for every role, plus a collapsed disclosure for
     the findings closed with no change (nothing silently disappears). */
  var QUEUE_GROUPS = [
    ["rework", "Rework requested"],
    ["todo", "To implement"],
    ["awaiting", "Awaiting verification"],
    ["done", "Verified"],
  ];
  function renderPanel(its) {
    list.innerHTML = "";
    countEl.textContent = String(its.length);
    emptyEl.hidden = its.length > 0;
    if (data.phase !== "closeout") {
      its.forEach(function (it) { list.appendChild(cardEl(it)); });
      return;
    }
    QUEUE_GROUPS.forEach(function (g) {
      var members = its.filter(function (it) { return it.rid && it.rid.queue === g[0]; });
      var sec = document.createElement("section");
      sec.className = "cq-group cq-" + g[0];
      sec.innerHTML = '<h2>' + esc(g[1]) + ' <span class="badge">' + members.length + "</span></h2>";
      members.forEach(function (it) { sec.appendChild(cardEl(it)); });
      if (!members.length) sec.innerHTML += '<p class="muted">—</p>';
      list.appendChild(sec);
    });
    var closed = its.filter(function (it) { return it.rid && it.rid.queue === "noChange"; });
    if (closed.length) {
      var det = document.createElement("details");
      det.className = "cq-group cq-nochange";
      det.innerHTML = "<summary>Closed — no change (" + closed.length + ")</summary>";
      closed.forEach(function (it) { det.appendChild(cardEl(it)); });
      list.appendChild(det);
    }
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
  /* ---------------- one bin per comment (v3.2 point 7) ------------------ */
  /* Four destructive controls used to share a card — a local delete, the
     reviewer's withdraw, the admin's withdraw and the admin's purge. They are
     one 🗑 now. What it does follows role and state; where an admin has two
     legitimate outcomes on the same comment, the choice lives inside the
     confirmation rather than as a second button. Authority is unchanged: the
     dialog only routes to the services that already guard themselves. */
  var binDlg = null;
  function askBin(opts) {
    if (!window.HTMLDialogElement) {          // no <dialog>: degrade to confirm()
      if (window.confirm(opts.body)) opts.choices[0].onPick();
      return;
    }
    if (!binDlg) {
      binDlg = document.createElement("dialog");
      binDlg.className = "bin-dlg";
      document.body.appendChild(binDlg);
    }
    binDlg.innerHTML = "";
    var h = document.createElement("h3");
    h.className = "bin-dlg-title";
    h.textContent = opts.title;
    var p = document.createElement("p");
    p.textContent = opts.body;
    var row = document.createElement("div");
    row.className = "bin-dlg-actions";
    opts.choices.forEach(function (ch) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = ch.cls || "";
      b.textContent = ch.label;
      b.addEventListener("click", function () { binDlg.close(); ch.onPick(); });
      row.appendChild(b);
    });
    var cancel = document.createElement("button");
    cancel.type = "button";
    cancel.className = "bin-dlg-cancel";
    cancel.textContent = "Cancel";
    cancel.addEventListener("click", function () { binDlg.close(); });
    row.appendChild(cancel);
    binDlg.appendChild(h);
    binDlg.appendChild(p);
    binDlg.appendChild(row);
    binDlg.showModal();
  }

  function binFor(c, r) {
    var local = !!(c && !r);
    // `phase` is local to cardEl; this helper reads the payload directly.
    // retract_comment is open-only and in_review-only (services/core.py) — the
    // v3 rule that stopped a disposed comment being withdrawn behind the graph
    var canRetract = !!(r && data.phase === "in_review" && r.status === "open" &&
                        ((r.mine && data.isReviewer) || r.canPurge));
    var canPurge = !!(r && r.canPurge);       // human global admin, any phase
    if (!local && !canRetract && !canPurge) return null;

    var bin = document.createElement("button");
    bin.type = "button";
    bin.className = "cp-bin";
    bin.textContent = "🗑";
    bin.title = local ? "Delete this unsaved comment"
      : canRetract ? "Withdraw this comment" : "Remove this comment";
    bin.setAttribute("aria-label", bin.title + (r ? " " + r.rid : ""));
    bin.addEventListener("click", function (ev) {
      ev.stopPropagation();
      if (local) {                            // never saved: no server, no dialog
        comments = comments.filter(function (x) { return x.cid !== c.cid; });
        refresh(true);
        return;
      }
      var choices = [];
      if (canRetract) {
        choices.push({ label: "Withdraw", cls: "warn", onPick: function () {
          post(base + "/rids/" + encodeURIComponent(r.rid) + "/retract", {});
        } });
      }
      if (canPurge) {
        choices.push({ label: "Delete permanently", cls: "danger", onPick: function () {
          if (!window.confirm("Really delete " + r.rid + " for good? Only the audit log "
            + "will keep a trace. This cannot be undone.")) return;
          post(base + "/rids/" + encodeURIComponent(r.rid) + "/purge", {});
        } });
      }
      askBin({
        title: r.rid,
        body: canRetract
          ? "Withdrawing keeps an acted-upon finding on record as withdrawn, and "
            + "deletes a pristine one outright."
          : "This finding is past 'open', so it can no longer be withdrawn.",
        choices: choices
      });
    });
    return bin;
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
        // v3.2 point 9: focusing a card opens the card, not its sections.
        // History and Changes stay closed until they are asked for.
        el.classList.remove("collapsed");  // v3.1: ?focus=RID opens its card
        var grp = el.closest("details.cq-group");
        if (grp) grp.open = true;          // …even inside the collapsed group
      }
    });
    if (window.history && history.replaceState) {
      var it = key ? itemByKey(key) : null;
      history.replaceState(null, "", it && it.rid
        ? base + "/document?focus=" + encodeURIComponent(it.rid.rid)
        : base + "/document");
    }
    if (key && opts.scroll !== false) {
      // The card first, inside its own panel, and never with scrollIntoView:
      // that call bubbles to the viewport and would cancel the marker's
      // in-flight smooth scroll a line below — which is why clicking a comment
      // lit its marker up without ever travelling to it (v3.2 point 2).
      var card = list.querySelector('.cp-card[data-key="' + CSS.escape(key) + '"]');
      if (card) revealInPanel(card);
      // The marker last, so the page scroll is the final word. In closeout the
      // sheet renders the latest version unmarked, so there is legitimately
      // no marker to travel to.
      var marker = sheet.querySelector('.marker[data-key="' + CSS.escape(key) + '"]');
      if (marker) { marker.scrollIntoView({ behavior: "smooth", block: "center" }); flashEl(marker); }
    }
  }
  /* Scroll an element into view *within the comments panel only*, leaving the
     page scroll untouched. Measured through getBoundingClientRect so it does
     not depend on which ancestor happens to be the offsetParent. */
  function revealInPanel(el) {
    var panel = el.closest(".comments-panel");
    if (!panel) return;
    var r = el.getBoundingClientRect(), p = panel.getBoundingClientRect();
    var top = r.top - p.top + panel.scrollTop;
    var margin = 8;
    if (top - margin < panel.scrollTop) {
      panel.scrollTop = Math.max(0, top - margin);
    } else if (top + r.height + margin > panel.scrollTop + panel.clientHeight) {
      panel.scrollTop = top + r.height + margin - panel.clientHeight;
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
  function openPop(pageX, pageY, text) {
    document.getElementById("cmt-body").value = "";
    pop.style.left = Math.max(8, Math.min(pageX, window.scrollX + window.innerWidth - 306)) + "px";
    pop.style.top = (pageY + 8) + "px";
    pop.hidden = false;
    document.getElementById("cmt-body").focus();
  }
  if (data.isReviewer && pop) {
    document.getElementById("cmt-cancel").addEventListener("click", function () { pop.hidden = true; pending = null; });
    document.getElementById("cmt-save").addEventListener("click", function () {
      if (!pending) return;
      // v3: the GUI creates comments only (SUGG survives as legacy data)
      var c = { cid: seq++, offset: pending.offset, kind: "COMM", type: "editorial", sev: "minor", body: "", oldText: "", newText: "" };
      c.type = document.getElementById("cmt-type").value;
      c.sev = document.getElementById("cmt-sev").value;
      c.body = document.getElementById("cmt-body").value.trim();
      if (!c.body) return;
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
    if (!data.role && !data.isAdmin) return; // any member (v3), not just reviewers
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
    syncSaveButton();  // v3.1: the queue's checkboxes are rebuilt on every pass
  }
  /* ---------------- closeout: Render | Edit | Changes -------------------- */
  var modeRender = document.getElementById("doc-mode-render");
  var modeEdit = document.getElementById("doc-mode-edit");
  var modeChanges = document.getElementById("doc-mode-changes");
  var changesEl = document.getElementById("doc-changes");

  /* Leaving Edit must not cost the writer their place: the caret and the
     textarea's scroll are remembered and put back, with focus, on return
     (v3.2 — Alberto's explicit requirement). The sheet and the diff keep their
     own scroll positions independently, so switching views never scrolls
     anything the user did not scroll. */
  var caret = { start: 0, end: 0, scroll: 0 };
  var viewScroll = { render: 0, changes: 0 };

  function rememberCaret() {
    if (!editEl || editEl.hidden) return;
    caret.start = editEl.selectionStart;
    caret.end = editEl.selectionEnd;
    caret.scroll = editEl.scrollTop;
  }
  function restoreCaret() {
    if (!editEl) return;
    try { editEl.setSelectionRange(caret.start, caret.end); } catch (e) { /* detached */ }
    editEl.scrollTop = caret.scroll;
    if (!editEl.readOnly) editEl.focus();
  }

  function setMode(mode) {                 // "render" | "edit" | "changes"
    if (!editEl) return;
    if (mode === true) mode = "edit";      // v3.1 callers passed a boolean
    else if (mode === false) mode = "render";
    if (!editEl.hidden) rememberCaret();
    else if (!sheet.hidden) viewScroll.render = sheet.scrollTop;
    else if (changesEl && !changesEl.hidden) viewScroll.changes = changesEl.scrollTop;

    editEl.hidden = mode !== "edit";
    sheet.hidden = mode !== "render";
    if (changesEl) changesEl.hidden = mode !== "changes";
    if (modeEdit) modeEdit.classList.toggle("active", mode === "edit");
    if (modeRender) modeRender.classList.toggle("active", mode === "render");
    if (modeChanges) modeChanges.classList.toggle("active", mode === "changes");

    if (mode === "render") {
      renderSheet(currentItems);           // re-render from the edited text
      sheet.scrollTop = viewScroll.render;
    } else if (mode === "edit") {
      restoreCaret();
    } else {
      changesEl.scrollTop = viewScroll.changes;
      requestDiff(true);
    }
  }

  /* The live diff is computed by the server — the same renderer every other
     diff in the product uses. Debounced, and a newer request always wins: a
     slow response must never overwrite a fresher diff. */
  var diffTimer = null, diffSeq = 0, lastDiffed = null;
  function requestDiff(immediate) {
    if (!changesEl || !editEl) return;
    if (changesEl.hidden) return;          // never poll a view nobody is looking at
    clearTimeout(diffTimer);
    diffTimer = setTimeout(function () {
      var text = editEl.value;
      if (text === lastDiffed) return;
      var seq = ++diffSeq;
      var body = new URLSearchParams();
      body.set("content", text);
      fetch(base + "/diff-preview", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: body.toString(),
        credentials: "same-origin",
      }).then(function (r) { return r.ok ? r.text() : Promise.reject(r.status); })
        .then(function (markup) {
          if (seq !== diffSeq) return;     // a newer request has taken over
          lastDiffed = text;
          changesEl.innerHTML = window.DOMPurify ? window.DOMPurify.sanitize(markup) : markup;
        })
        .catch(function () {
          if (seq !== diffSeq) return;
          changesEl.innerHTML = '<p class="muted">The diff could not be refreshed.</p>';
        });
    }, immediate ? 0 : 400);
  }

  if (modeRender) modeRender.addEventListener("click", function () { setMode("render"); });
  if (modeEdit) modeEdit.addEventListener("click", function () { setMode("edit"); });
  if (modeChanges) modeChanges.addEventListener("click", function () { setMode("changes"); });
  if (editEl) editEl.addEventListener("input", function () {
    syncSaveButton();
    requestDiff(false);                    // live while the Changes view is up
  });

  // v3.2 point 13: the closeout editor starts locked, and a reload drops an
  // open session — so warn before the text goes with it.
  if (editEl) {
    syncSession();
    window.addEventListener("beforeunload", function (ev) {
      if (session && editEl.value !== data.latest) { ev.preventDefault(); ev.returnValue = ""; }
    });
  }

  // v3.1 step 02: Terminate lives in the closeout toolbar, which is inside
  // #rev-form — a nested <form> is invalid HTML, so it posts detached like
  // every other card action. Label/route/confirm come from the template.
  var terminateBtn = document.getElementById("doc-terminate");
  if (terminateBtn) {
    terminateBtn.addEventListener("click", function () {
      post(terminateBtn.dataset.action, {}, terminateBtn.dataset.confirm);
    });
  }

  parseCopy();
  renderLegend();
  refresh(false);
  loadNotes();
})();
