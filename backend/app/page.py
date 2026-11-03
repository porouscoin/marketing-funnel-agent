"""Fetching a web page safely and pulling out the words that matter.

Visitors type any URL, so the fetch refuses anything that resolves to a private
or local address (the server must not be used to poke at internal services),
follows at most a few redirects (each one checked again), and stops reading
after a size cap.
"""

import asyncio
import ipaddress
import re
import socket
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx

from .providers import http

MAX_BYTES = 1_500_000
UA = "Mozilla/5.0 (compatible; MarketingFunnelAgent/0.1; +https://github.com/porouscoin/marketing-funnel-agent)"


class PageError(Exception):
    pass


@dataclass
class Page:
    url: str
    domain: str
    title: str = ""
    description: str = ""
    image: str = ""
    site_name: str = ""
    headings: list[str] = field(default_factory=list)
    text: str = ""

    def as_dict(self) -> dict:
        return asdict(self)

    def for_prompt(self, limit: int = 6000) -> str:
        parts = [
            f"URL: {self.url}" if self.url else "",
            f"Title: {self.title}" if self.title else "",
            f"Meta description: {self.description}" if self.description else "",
            "Headings:\n" + "\n".join(f"- {h}" for h in self.headings[:25]) if self.headings else "",
            "Text:\n" + self.text[:limit],
        ]
        return "\n\n".join(p for p in parts if p)


def normalize_url(raw: str) -> str:
    raw = raw.strip()
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", raw):
        raw = "https://" + raw
    u = urlparse(raw)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise PageError("That doesn't look like a web address.")
    if u.username or u.password:
        raise PageError("Addresses with a username or password aren't supported.")
    return raw


def domain_of(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


async def _check_host(host: str) -> None:
    try:
        infos = await asyncio.to_thread(socket.getaddrinfo, host, None)
    except socket.gaierror:
        raise PageError(f"Couldn't find {host}.")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global or ip.is_multicast:
            raise PageError("That address points somewhere private, so it can't be read.")


async def fetch_html(url: str, timeout: float = 12.0) -> tuple[str, str]:
    """The page's HTML and its final URL after redirects."""
    url = normalize_url(url)
    for _ in range(5):
        await _check_host(urlparse(url).hostname or "")
        try:
            async with http().stream(
                "GET",
                url,
                headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml"},
                timeout=timeout,
                follow_redirects=False,
            ) as resp:
                if resp.status_code in (301, 302, 303, 307, 308) and resp.headers.get("location"):
                    url = normalize_url(urljoin(url, resp.headers["location"]))
                    continue
                if resp.status_code >= 400:
                    raise PageError(f"The site answered with an error ({resp.status_code}). Paste the page text instead.")
                kind = resp.headers.get("content-type", "")
                if "html" not in kind and "xml" not in kind:
                    raise PageError("That address isn't a web page.")
                chunks, size = [], 0
                async for chunk in resp.aiter_bytes():
                    chunks.append(chunk)
                    size += len(chunk)
                    if size > MAX_BYTES:
                        break
                raw = b"".join(chunks)
                return raw.decode(resp.encoding or "utf-8", errors="replace"), url
        except httpx.TimeoutException:
            raise PageError("The site took too long to answer. Paste the page text instead.")
        except httpx.HTTPError as e:
            raise PageError(f"Couldn't reach the site ({type(e).__name__}). Paste the page text instead.")
    raise PageError("Too many redirects.")


SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "template", "iframe", "form", "select"}
BLOCK = {"p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "div", "section", "article", "td", "th", "blockquote", "dd", "dt", "br", "tr", "header", "main"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


class _Extractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.in_title = False
        self.heading: list[str] | None = None
        self.title = ""
        self.meta: dict[str, str] = {}
        self.headings: list[str] = []
        self.lines: list[str] = []
        self.buf: list[str] = []

    def flush(self) -> None:
        line = re.sub(r"\s+", " ", "".join(self.buf)).strip()
        if line:
            self.lines.append(line)
        self.buf = []

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "meta":
            key = (a.get("property") or a.get("name") or "").lower()
            if key in ("description", "og:description", "og:title", "og:image", "og:site_name", "twitter:image"):
                self.meta.setdefault(key, a.get("content", "").strip())
            return
        if tag in VOID:
            if tag == "br":
                self.flush()
            return
        if tag in SKIP:
            self.skip += 1
            return
        if tag == "title":
            self.in_title = True
        if tag in BLOCK:
            self.flush()
        if tag in ("h1", "h2", "h3") and not self.skip:
            self.heading = []

    def handle_endtag(self, tag):
        if tag in SKIP:
            self.skip = max(0, self.skip - 1)
            return
        if tag == "title":
            self.in_title = False
        if tag in ("h1", "h2", "h3") and self.heading is not None:
            h = re.sub(r"\s+", " ", "".join(self.heading)).strip()
            if h and h not in self.headings:
                self.headings.append(h)
            self.heading = None
        if tag in BLOCK:
            self.flush()

    def handle_data(self, data):
        if self.in_title:
            self.title += data
            return
        if self.skip:
            return
        self.buf.append(data)
        if self.heading is not None:
            self.heading.append(data)


def extract(html: str, url: str = "") -> Page:
    p = _Extractor()
    try:
        p.feed(html)
        p.close()
    except Exception:  # broken markup: keep whatever was read
        pass
    p.flush()
    # Drop repeated lines (menus, cookie banners repeated per section) and very short scraps.
    seen: set[str] = set()
    lines = []
    for line in p.lines:
        if line in seen or len(line) < 3:
            continue
        seen.add(line)
        lines.append(line)
    image = p.meta.get("og:image") or p.meta.get("twitter:image") or ""
    if image and url:
        image = urljoin(url, image)
    if not image.startswith("https://"):
        image = ""
    return Page(
        url=url,
        domain=domain_of(url) if url else "",
        title=re.sub(r"\s+", " ", p.title).strip()[:200],
        description=(p.meta.get("description") or p.meta.get("og:description") or "")[:400],
        image=image,
        site_name=(p.meta.get("og:site_name") or "")[:80],
        headings=[h[:160] for h in p.headings[:40]],
        text="\n".join(lines),
    )


def from_text(text: str) -> Page:
    lines = [re.sub(r"\s+", " ", l).strip() for l in text.splitlines()]
    lines = [l for l in lines if l]
    return Page(url="", domain="", title=lines[0][:200] if lines else "", text="\n".join(lines))


async def read_page(url: str) -> Page:
    html, final = await fetch_html(url)
    page = extract(html, final)
    if len(page.text) < 200 and not page.description:
        raise PageError(
            "The page came back almost empty. It probably builds itself with JavaScript. Paste the page text instead."
        )
    return page


def norm_words(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def backed_by(quote: str, page: Page) -> bool:
    """Whether a quote really appears on the page (ignoring case, punctuation and spacing)."""
    q = norm_words(quote)
    if len(q) < 8:
        return False
    hay = norm_words(" ".join([page.title, page.description, *page.headings, page.text]))
    return q in hay
