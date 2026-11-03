from app.formats import PIECE_IDS, clean, fit, problems, trim


def test_clean_fills_every_field_and_picks_allowed_ctas():
    d = clean({"meta": {"primary": "Hi", "headline": "Go", "cta": "BUY IT NOW"}, "google": {"headlines": ["a"]}})
    assert set(d) == set(PIECE_IDS)
    assert d["meta"]["cta"] == "Learn more"
    assert d["google"]["headlines"] == ["a", "", ""]
    assert d["email1"]["subject"] == ""


def test_problems_and_fit_enforce_limits():
    d = clean({"google": {"headlines": ["x" * 10, "This headline is far too long for Google", "ok"], "descriptions": ["d", "e"]}})
    issues = problems("google", d["google"])
    assert any("headlines[1]" in i and "max 30" in i for i in issues)
    fixed = fit("google", d["google"])
    assert all(len(h) <= 30 for h in fixed["headlines"])
    assert not fixed["headlines"][1].endswith(" ")


def test_trim_cuts_on_a_word():
    assert trim("one two three four", 9) == "one two"
    assert trim("short", 10) == "short"


def test_trim_prefers_a_sentence_end():
    text = "Plans start at $9 a month with a free trial. Try a simple, privacy-friendly analytics tool today."
    assert trim(text, 80) == "Plans start at $9 a month with a free trial."
