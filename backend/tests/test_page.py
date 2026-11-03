import pytest

from app.page import PageError, backed_by, extract, fetch_html, from_text, normalize_url

HTML = """<html><head><title>Inboxly | Cold email</title>
<meta name="description" content="Cold email for founders.">
<meta property="og:image" content="/og.png"><script>var x = 1;</script></head>
<body><nav><a>Pricing</a><a>Login</a></nav>
<h1>Cold email that lands</h1><p>Warm up your domain and send at <b>safe limits</b>.</p>
<ul><li>4,000 teams</li><li>62% open rate</li></ul><button>Start free trial</button>
<footer>Copyright</footer></body></html>"""


def test_extract_keeps_content_and_drops_chrome():
    p = extract(HTML, "https://www.inboxly.com/")
    assert p.title == "Inboxly | Cold email"
    assert p.domain == "inboxly.com"
    assert p.image == "https://www.inboxly.com/og.png"
    assert p.headings == ["Cold email that lands"]
    assert "Warm up your domain and send at safe limits." in p.text
    assert "Start free trial" in p.text
    assert "Pricing" not in p.text and "Copyright" not in p.text and "var x" not in p.text


def test_backed_by_ignores_case_and_punctuation():
    p = extract(HTML, "https://inboxly.com")
    assert backed_by("warm up your domain, and send at SAFE limits", p)
    assert not backed_by("trusted by Fortune 500 companies", p)
    assert not backed_by("cold", p)  # too short to count


def test_normalize_url():
    assert normalize_url("inboxly.com") == "https://inboxly.com"
    with pytest.raises(PageError):
        normalize_url("ftp://x.com")
    with pytest.raises(PageError):
        normalize_url("https://user:pw@x.com")


@pytest.mark.parametrize("url", ["http://127.0.0.1:8000", "http://localhost", "http://10.0.0.5", "http://169.254.169.254/latest"])
async def test_private_addresses_are_refused(url):
    with pytest.raises(PageError):
        await fetch_html(url)


def test_from_text():
    p = from_text("Inboxly\n\n  Cold   email for founders  \n")
    assert p.title == "Inboxly" and p.text == "Inboxly\nCold email for founders"
