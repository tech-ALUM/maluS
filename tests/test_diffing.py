from malus.diffing import html_diff


def test_equal_texts_yield_empty():
    assert html_diff("a\nb\n", "a\nb\n") == ""


def test_word_level_ins_del():
    out = html_diff("the quick fox\n", "the slow fox\n")
    assert "<del>quick</del>" in out and "<ins>slow</ins>" in out


def test_html_is_escaped():
    out = html_diff("safe\n", "<script>alert(1)</script>\n")
    assert "<script>" not in out and "&lt;script&gt;" in out


def test_html_is_escaped_on_insert_and_delete():
    # "<b>bold</b>" is removed (pure delete opcode) and
    # "<script>alert(1)</script>" is appended (pure insert opcode) —
    # neither pairs with a same-length replacement, so both take the
    # non-refined else branch of html_diff.
    old = "keep one\n<b>bold</b>\nkeep two\n"
    new = "keep one\nkeep two\n<script>alert(1)</script>\n"
    out = html_diff(old, new)
    assert "<script>" not in out and "<b>" not in out
    assert "&lt;script&gt;" in out and "&lt;b&gt;" in out
    assert '<div class="diff-del"><del>&lt;b&gt;bold&lt;/b&gt;</del></div>' in out
    assert (
        '<div class="diff-ins"><ins>&lt;script&gt;alert(1)&lt;/script&gt;</ins></div>'
        in out
    )


def test_html_is_escaped_in_context_lines():
    # The first line is unchanged, so it is emitted via the equal/context
    # branch — it must still be escaped.
    old = "Tom & Jerry <inc>\nold line\n"
    new = "Tom & Jerry <inc>\nnew line\n"
    out = html_diff(old, new)
    assert '<div class="diff-ctx">Tom &amp; Jerry &lt;inc&gt;</div>' in out
    assert "<inc>" not in out


def test_context_is_limited():
    old = "\n".join(f"line {i:02d}" for i in range(50)) + "\n"
    new = old.replace("line 10", "line ten").replace("line 40", "line forty")
    out = html_diff(old, new)
    assert "line 07" in out and "line 13" in out       # ±3 kept around hunk 1
    assert "line 25" not in out                        # far context elided
    assert "diff-skip" in out                          # marker between the two hunks
