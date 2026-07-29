from malus.diffing import html_diff


def test_equal_texts_yield_empty():
    assert html_diff("a\nb\n", "a\nb\n") == ""


def test_word_level_ins_del():
    out = html_diff("the quick fox\n", "the slow fox\n")
    assert "<del>quick</del>" in out and "<ins>slow</ins>" in out


def test_html_is_escaped():
    out = html_diff("safe\n", "<script>alert(1)</script>\n")
    assert "<script>" not in out and "&lt;script&gt;" in out


def test_context_is_limited():
    old = "\n".join(f"line {i:02d}" for i in range(50)) + "\n"
    new = old.replace("line 10", "line ten").replace("line 40", "line forty")
    out = html_diff(old, new)
    assert "line 07" in out and "line 13" in out       # ±3 kept around hunk 1
    assert "line 25" not in out                        # far context elided
    assert "diff-skip" in out                          # marker between the two hunks
