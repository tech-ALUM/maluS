/* maluS in-browser editor helpers (vendored; no CDN at runtime).

   - Block-insert buttons for reviewers ({COMM|…} / {SUGG:…}).
   - Live Markdown preview via the vendored `marked`.
   - A client-side freeze-rule pre-check: on submit, strip comment blocks and
     compare the residue to the frozen baseline. This is the *client* layer of
     tamper rejection; the server re-validates with the real parser (authority).
*/
(function () {
  "use strict";
  var ta = document.getElementById("editor");
  if (!ta) return;

  var preview = document.getElementById("preview");
  var baseline = ta.getAttribute("data-baseline");
  var form = ta.form;

  function render() {
    if (preview && window.marked) preview.innerHTML = window.marked.parse(ta.value);
  }

  function insert(text, caretBack) {
    var s = ta.selectionStart, e = ta.selectionEnd;
    ta.value = ta.value.slice(0, s) + text + ta.value.slice(e);
    var pos = s + text.length - (caretBack || 0);
    ta.focus();
    ta.setSelectionRange(pos, pos);
    render();
  }

  document.querySelectorAll("[data-insert]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var kind = btn.getAttribute("data-insert");
      if (kind === "comm") insert("{COMM|type=technical|sev=major: }", 1);
      else if (kind === "sugg") insert('{SUGG: "" -> ""}', 7);
    });
  });

  function stripBlocks(s) {
    return s.replace(/\{(?:COMM|SUGG)\b[\s\S]*?\}/g, "");
  }
  function norm(s) {
    return s.replace(/\s+/g, " ").trim();
  }

  if (form && baseline !== null) {
    form.addEventListener("submit", function (ev) {
      if (norm(stripBlocks(ta.value)) !== norm(baseline)) {
        ev.preventDefault();
        var warn = document.getElementById("freeze-warning");
        if (warn) warn.hidden = false;
      }
    });
  }

  ta.addEventListener("input", render);
  render();
})();
