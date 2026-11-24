#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "pyyaml>=6.0.2",
#   "httpx>=0.28.1",
#   "trafilatura>=2.3.1",
#   "youtube-transcript-api>=1.2.4",
#   "markitdown[pdf,docx,pptx,xlsx]>=0.1.8",
# ]
# ///
"""Copy a source into Sources/ verbatim, with content-hash and URL dedup (D38, D75).

  source.py fetch URL|FILE [--title T]          fetch or read, convert to text, dedup, write
  source.py add --kind K --title T [--url U] [--author A] [--published D]
                [--capture-scope partial] [--attach IMAGE] [--refuse-secrets] --body-file -
                                                content Claude got another way (Confluence via
                                                MCP, pasted text, an image it transcribed)
  source.py lookup URL                          source notes already in the vault for a URL
  source.py scan FOLDER [--limit 5]             files in a folder not ingested yet, a started one first
  source.py quote-check --file SOURCE "quote" ...
                                                whether each quote is in the source word for word
                                                (case, markup, typographic quotes and spacing
                                                ignored; `...` stands for left-out text); a missing
                                                one comes with the `closest` sentence (D125)

Offline inputs (tests, or a page saved another way): `fetch URL --html-file page.html`,
`fetch YOUTUBE_URL --transcript-json t.json --title T` (a list of {"text", "start"}).

Prints one JSON object. `status`: new | unchanged (already in the vault, nothing written) |
changed (a new version of a known URL; the new note `supersedes` the old one). `chunks` are
1-based line ranges of the written file, about 40k characters each, for splitting the reading.
Exit 2 = bad input or refused URL, 4 = nothing could be extracted (see `fallback`).
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import ipaddress
import json
import logging
import re
import shutil
import socket
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urljoin, urlsplit

from synapsidianlib import config, frontmatter, schema, sources, vault
from validate import secret_problems

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) synapsidian-ingest"
)
MAX_BYTES = 25 * 1024 * 1024
MAX_REDIRECTS = 5
MIN_ARTICLE_CHARS = 200
TRANSCRIPT_PARAGRAPH_SECONDS = 60
DOCUMENT_KINDS = {".pdf": "pdf", ".docx": "document", ".xlsx": "document", ".epub": "document", ".pptx": "slides"}
TEXT_SUFFIXES = {".md", ".markdown", ".txt"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif", ".svg", ".bmp"}
HTML_SUFFIXES = {".html", ".htm"}
CONTENT_TYPES = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
}
CHROME_XPATH = ".//nav|.//header|.//footer|.//aside|.//script|.//style|.//noscript|.//button|.//svg|.//form|.//iframe"
# Heading anchors such as [ZWSP](#fields): their text is often just a zero-width space.
EMPTY_ANCHOR = re.compile(r"\[[\s" + "\N{ZERO WIDTH SPACE}" + r"]*\]\(#[^)]*\)\s?")
PAGE_LINK = re.compile(r"\[([^\]]+)\]\(#[^)]*\)")
RELATIVE_LINK = re.compile(r"\]\((/[^)\s]*|\.{1,2}/[^)\s]*)\)")
PUBLISH_PRELOAD = re.compile(
    r"window\.preloadPage\s*=\s*\w+\(\s*\"(https://publish-\d+\.obsidian\.md/access/[0-9a-f]+/[^\"]+\.md)\"\s*\)"
)
GENERIC_NAMES = frozenset({"readme", "index", "home", "main", "changelog", "docs"})
WIKILINK = re.compile(r"!?\[\[([^\]|#]+)(#[^\]|]*)?(?:\|([^\]]*))?\]\]")
FALLBACK = (
    "Read the content another way (WebFetch for a page, Read for a file, the Atlassian tools for "
    "Confluence) and store what you got with `synapsidian source add --capture-scope partial`."
)


class SourceError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(slots=True)
class Extracted:
    kind: str
    title: str
    text: str
    url: str | None
    author: str | None = None
    published: dt.date | None = None
    scope: str = "full"
    language: str | None = None


# --- fetching -------------------------------------------------------------------------


def check_public(url: str) -> tuple[str, int, str]:
    """Refuse anything but http(s) to public addresses (no localhost, LAN, link-local, metadata).

    Returns (host, port, the checked address), so the connection goes to that address and a
    second DNS answer (rebinding) can't send it somewhere else.
    """
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise SourceError(2, f"only http(s) URLs can be fetched, got {url!r}")
    port = parts.port or (443 if parts.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(parts.hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise SourceError(4, f"cannot resolve {parts.hostname}: {exc}") from exc
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if not address.is_global:
            raise SourceError(2, f"{parts.hostname} resolves to a non-public address ({address}); refusing")
    if not infos:
        raise SourceError(4, f"cannot resolve {parts.hostname}")
    return parts.hostname, port, str(infos[0][4][0])


def pinned_transport(pins: dict[tuple[str, int], str]) -> Any:
    """An httpx transport that connects only to addresses `check_public` vetted.

    httpcore opens the TCP connection through its network backend, while TLS (SNI,
    certificate check) and the Host header keep using the URL's name, so swapping the
    address there pins the connection without weakening HTTPS.
    """
    import httpcore
    import httpx

    class PinnedBackend(httpcore.SyncBackend):
        def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):  # type: ignore[no-untyped-def]
            address = pins.get((host.strip("[]"), port))
            if address is None:
                raise httpcore.ConnectError(f"{host}:{port} was not checked before connecting")
            return super().connect_tcp(address, port, timeout, local_address, socket_options)

    transport = httpx.HTTPTransport()
    # HTTPTransport takes no network backend, so its pool is replaced with one that has ours.
    transport._pool = httpcore.ConnectionPool(ssl_context=httpx.create_ssl_context(), network_backend=PinnedBackend())
    return transport


def http_get(url: str, transport: Any = None) -> tuple[str, str, bytes]:
    """(final URL, content type, body), following redirects by hand so every hop is checked.

    No proxy from the environment (`trust_env=False`): a proxy would resolve the name itself.
    """
    import httpx

    pins: dict[tuple[str, int], str] = {}
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "en,pl;q=0.8"}
    transport = transport or pinned_transport(pins)
    with httpx.Client(
        headers=headers, timeout=30, follow_redirects=False, transport=transport, trust_env=False
    ) as client:
        for _ in range(MAX_REDIRECTS + 1):
            host, port, address = check_public(url)
            pins[(host, port)] = address
            try:
                with client.stream("GET", url) as response:
                    if response.is_redirect:
                        url = urljoin(url, response.headers["location"])
                        continue
                    if response.status_code >= 400:
                        raise SourceError(4, f"HTTP {response.status_code} for {url}")
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        body += chunk
                        if len(body) > MAX_BYTES:
                            raise SourceError(4, f"{url} is larger than {MAX_BYTES // 2**20} MB")
                    return url, response.headers.get("content-type", ""), bytes(body)
            except httpx.HTTPError as exc:
                raise SourceError(4, f"fetching {url} failed: {exc}") from exc
    raise SourceError(4, f"more than {MAX_REDIRECTS} redirects")


# --- extraction -------------------------------------------------------------------------


def main_element_markdown(html: str, url: str | None) -> str | None:
    """The page's <article> or <main>, minus navigation chrome, converted by markitdown.

    trafilatura finds the article body reliably but drops tables and code blocks on many
    documentation sites; markitdown keeps them but needs the main element cut out first.
    """
    from lxml import etree
    from lxml import html as lxml_html
    from markitdown import MarkItDown, StreamInfo

    try:
        doc = lxml_html.fromstring(html)
    except (ValueError, etree.ParserError):
        return None
    candidates = doc.xpath("//article") or doc.xpath("//main") or doc.xpath("//*[@role='main']")
    if not candidates:
        return None
    node = max(candidates, key=lambda n: len(n.text_content()))
    for chrome in node.xpath(CHROME_XPATH):
        chrome.drop_tree()
    fragment = lxml_html.tostring(node, encoding="unicode").encode("utf-8")
    result = MarkItDown(enable_plugins=False).convert_stream(
        io.BytesIO(fragment), stream_info=StreamInfo(extension=".html", charset="utf-8")
    )
    return tidy_links(result.text_content or "", url)


def tidy_links(markdown: str, url: str | None) -> str:
    """Drop heading anchors and in-page links (keeping their text); make relative links absolute."""
    markdown = EMPTY_ANCHOR.sub("", markdown)
    markdown = PAGE_LINK.sub(r"\1", markdown)
    if url:
        markdown = RELATIVE_LINK.sub(lambda m: f"]({urljoin(url, m.group(1))})", markdown)
    return markdown


def from_html(html: str, url: str | None, title: str | None) -> Extracted:
    import trafilatura

    text = trafilatura.extract(
        html,
        url=url,
        output_format="markdown",
        include_tables=True,
        include_formatting=True,
        include_links=False,
        include_comments=False,
        favor_recall=True,
    )
    # Prefer the main element when it holds the same text plus what trafilatura dropped
    # (tables, code), but not when it is most of the page (then it is chrome, not article).
    full = main_element_markdown(html, url)
    if full and (not text or len(text) * 0.8 <= len(full) <= len(text) * 3):
        text = full
    if not text or len(text.strip()) < MIN_ARTICLE_CHARS:
        raise SourceError(4, "no article text found (a JavaScript-only page, a paywall or a login wall?)")
    meta = trafilatura.extract_metadata(html, default_url=url)
    return Extracted(
        kind="article",
        title=title or (meta.title if meta and meta.title else None) or urlsplit(url or "").path or "Untitled page",
        text=text,
        url=url,
        author=meta.author if meta else None,
        published=schema.as_date(meta.date) if meta and meta.date else None,
    )


def from_document(path: Path, url: str | None, title: str | None) -> Extracted:
    suffix = path.suffix.lower()
    if suffix in TEXT_SUFFIXES:
        text = path.read_text(encoding="utf-8", errors="replace")
        return Extracted("text", title or path.stem, text, url or path.resolve().as_uri())
    if suffix in HTML_SUFFIXES:
        return from_html(path.read_text(encoding="utf-8", errors="replace"), url or path.resolve().as_uri(), title)
    if suffix not in DOCUMENT_KINDS:
        raise SourceError(2, f"unsupported file type {suffix!r}; supported: pdf, docx, pptx, xlsx, epub, html, md, txt")
    from markitdown import MarkItDown

    logging.getLogger("pdfminer").setLevel(logging.ERROR)
    try:
        result = MarkItDown(enable_plugins=False).convert(str(path))
    except Exception as exc:  # markitdown raises a range of converter-specific errors
        raise SourceError(4, f"could not convert {path.name}: {exc}") from exc
    text = result.text_content or ""
    if len(text.strip()) < MIN_ARTICLE_CHARS:
        raise SourceError(4, f"{path.name} has (almost) no text layer; a scanned document?")
    return Extracted(DOCUMENT_KINDS[suffix], title or result.title or path.stem, text, url or path.resolve().as_uri())


def youtube_metadata(video: str) -> dict[str, Any]:
    """Title and channel from YouTube's keyless oEmbed endpoint; empty when it fails."""
    watch = f"https://www.youtube.com/watch?v={video}"
    try:
        _, _, body = http_get(f"https://www.youtube.com/oembed?format=json&url={watch}")
        return json.loads(body)
    except (SourceError, ValueError):
        return {}


def youtube_snippets(video: str) -> tuple[list[dict[str, Any]], str | None]:
    """Transcript snippets in the spoken language: a manual track in that language beats the
    auto-generated one; without a generated track, English or Polish, then anything."""
    from youtube_transcript_api import YouTubeTranscriptApi, YouTubeTranscriptApiException

    try:
        listing = list(YouTubeTranscriptApi().list(video))
    except YouTubeTranscriptApiException as exc:
        raise SourceError(4, f"no transcript for {video}: {type(exc).__name__}") from exc
    generated = [t for t in listing if t.is_generated]
    manual = [t for t in listing if not t.is_generated]
    spoken = generated[0].language_code.split("-")[0] if generated else None
    pick = (
        next((t for t in manual if t.language_code.split("-")[0] == spoken), None)
        or (generated[0] if generated else None)
        or next((t for t in manual if t.language_code.split("-")[0] in ("en", "pl")), None)
        or (manual[0] if manual else None)
    )
    if pick is None:
        raise SourceError(4, f"video {video} has no captions; try the `visual` option to read its frames")
    try:
        fetched = pick.fetch()
    except YouTubeTranscriptApiException as exc:
        raise SourceError(4, f"transcript download failed: {type(exc).__name__}") from exc
    return [{"text": s.text, "start": s.start} for s in fetched.snippets], pick.language_code


def transcript_text(snippets: list[dict[str, Any]]) -> str:
    """Snippets grouped into paragraphs of about a minute, each led by its timestamp."""
    paragraphs: list[str] = []
    current: list[str] = []
    started = 0.0
    for snippet in snippets:
        start = float(snippet.get("start", 0))
        if current and start - started >= TRANSCRIPT_PARAGRAPH_SECONDS:
            paragraphs.append(f"**[{timestamp(started)}]** {' '.join(current)}")
            current = []
        if not current:
            started = start
        if words := " ".join(str(snippet.get("text", "")).split()):
            current.append(words)
    if current:
        paragraphs.append(f"**[{timestamp(started)}]** {' '.join(current)}")
    return "\n\n".join(paragraphs) + "\n"


def timestamp(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


def from_youtube(video: str, transcript_json: str | None, title: str | None) -> Extracted:
    if transcript_json:
        snippets, language, meta = json.loads(Path(transcript_json).read_text(encoding="utf-8")), None, {}
    else:
        snippets, language = youtube_snippets(video)
        meta = youtube_metadata(video)
    if not snippets:
        raise SourceError(4, f"the transcript of {video} is empty")
    return Extracted(
        kind="youtube",
        title=title or meta.get("title") or f"YouTube {video}",
        text=transcript_text(snippets),
        url=f"https://www.youtube.com/watch?v={video}",
        author=meta.get("author_name"),
        language=language,
    )


def extract(target: str, args: argparse.Namespace, scratch: Path) -> Extracted:
    if video := sources.youtube_id(target):
        return from_youtube(video, args.transcript_json, args.title)
    path = Path(target).expanduser()
    if "://" not in target and path.is_file():
        return from_document(path, None, args.title)
    if "://" not in target:
        raise SourceError(2, f"{target!r} is neither a URL nor an existing file")
    if args.html_file:
        return from_html(Path(args.html_file).read_text(encoding="utf-8", errors="replace"), target, args.title)

    final_url, content_type, body = http_get(target)
    mime = content_type.split(";")[0].strip().lower()
    suffix = CONTENT_TYPES.get(mime) or next(
        (s for s in DOCUMENT_KINDS if urlsplit(final_url).path.lower().endswith(s)), None
    )
    if suffix:
        download = scratch / f"download{suffix}"
        download.write_bytes(body)
        return from_document(download, target, args.title or Path(urlsplit(final_url).path).stem)
    name = url_title(final_url)
    is_markdown_file = urlsplit(final_url).path.lower().endswith((".md", ".markdown"))
    if mime == "text/markdown" or (mime.startswith("text/plain") and is_markdown_file):
        # A generic file name ("exceljs README") says more than the README's own "# ExcelJS".
        generic = Path(urlsplit(final_url).path).stem.casefold() in GENERIC_NAMES
        return from_markdown(
            body.decode("utf-8", errors="replace"), target, args.title or (name if generic else None), name
        )
    if mime.startswith("text/plain"):
        return Extracted("text", args.title or name, body.decode("utf-8", errors="replace"), target)
    html = body.decode("utf-8", errors="replace")
    if published := publish_page(html):
        # An Obsidian Publish site ships an empty shell and loads the note's markdown by script.
        _, _, markdown = http_get(published)
        page = publish_title(published)
        return from_markdown(markdown.decode("utf-8", errors="replace"), target, args.title or page, page)
    return from_html(html, target, args.title)


def url_title(url: str) -> str:
    """A title from a URL's file name; a generic one (README, index) gets the repository or
    site section in front: raw.githubusercontent.com/exceljs/exceljs/master/README.md ->
    'exceljs README'."""
    parts = [unquote(p) for p in urlsplit(url).path.split("/") if p]
    if not parts:
        return urlsplit(url).hostname or url
    stem = Path(parts[-1]).stem
    if stem.casefold() in GENERIC_NAMES and len(parts) >= 3:
        return f"{parts[1]} {stem}"
    return stem


def publish_page(html: str) -> str | None:
    """The raw-markdown URL an Obsidian Publish page preloads, if this is one."""
    match = PUBLISH_PRELOAD.search(html)
    return match.group(1) if match else None


def publish_title(markdown_url: str) -> str:
    """In Obsidian the note name is the title; a generic one ("Functions") gets its folder
    in front ("Bases Functions") unless it already names it ("Bases syntax")."""
    path = Path(unquote(urlsplit(markdown_url).path))
    name, folder = path.stem, path.parent.name
    is_site_root = path.parent.parent.name == "access"  # /access/<site id>/<note>.md
    return name if is_site_root or folder.casefold() in name.casefold() else f"{folder} {name}"


def from_markdown(markdown: str, url: str, title: str | None, fallback_title: str) -> Extracted:
    """A markdown page: its own frontmatter dropped, its wikilinks turned into plain text so
    they never become unresolved links in this vault."""
    parsed = frontmatter.parse(markdown)
    text = WIKILINK.sub(lambda m: m.group(3) or m.group(1).strip(), parsed.body).strip() + "\n"
    if len(text.strip()) < MIN_ARTICLE_CHARS:
        raise SourceError(4, "the page's markdown is (almost) empty")
    return Extracted("article", title or first_heading(text) or fallback_title, text, url)


def first_heading(markdown: str) -> str | None:
    """The first level-1 heading outside fenced code (a `# comment` in a YAML block isn't one)."""
    fence: str | None = None
    for line in markdown.splitlines():
        marker = line.lstrip()[:3]
        if marker in ("```", "~~~"):
            fence = None if fence == marker else fence or marker
        elif fence is None and line.startswith("# "):
            return line[2:].strip()
    return None


# --- writing -----------------------------------------------------------------------------


def write(vault_root: Path, ex: Extracted, previous: vault.Note | None) -> Path:
    today = dt.date.today()
    meta: dict[str, Any] = {"type": "source", "created": today}
    if ex.url:
        meta["url"] = ex.url
    meta |= {
        "source_kind": ex.kind,
        "content_hash": sources.content_hash(ex.text),
        "fetched_at": today,
        "capture_scope": ex.scope,
    }
    if ex.author:
        meta["author"] = " ".join(str(ex.author).split())
    if ex.published:
        meta["published"] = ex.published
    if previous is not None:
        meta["supersedes"] = schema.as_link(previous.title)

    s = schema.load(vault_root)
    note_type = s.types["source"]
    title = sources.short_title(ex.title) or "Untitled source"
    base = schema.filename_for(note_type, meta, title, dt.datetime.now())
    if problems := schema.validate(meta, f"{note_type.folder}/{base}.md", s):
        raise SourceError(2, "; ".join(problems))
    folder = vault_root / note_type.folder
    folder.mkdir(parents=True, exist_ok=True)
    for n in range(1, 100):
        target = folder / (f"{base}.md" if n == 1 else f"{base} ({n}).md")
        try:
            with target.open("x", encoding="utf-8") as handle:
                handle.write(frontmatter.dump(meta, ex.text))
            return target
        except FileExistsError:
            continue
    raise SourceError(2, f"too many sources named {base!r}")


def store(vault_root: Path, ex: Extracted) -> dict[str, Any]:
    status, previous = sources.match(vault_root, url=ex.url, text=ex.text)
    if status == "unchanged" and previous is not None:
        # Enough to resume an ingest that stopped before it set `integrated`.
        return {
            "ok": True,
            "status": "unchanged",
            "rel": previous.rel,
            "title": previous.title,
            "kind": previous.get("source_kind"),
            "capture_scope": previous.get("capture_scope"),
            "fetched_at": str(previous.get("fetched_at")),
            "summary": previous.get("summary"),
            "integrated": _date_or_none(previous.get("integrated")),
            "chunks": sources.chunks(previous.path.read_text(encoding="utf-8")),
        }
    target = write(vault_root, ex, previous if status == "changed" else None)
    text = target.read_text(encoding="utf-8")
    return {
        "ok": True,
        "status": status,
        "rel": vault.rel_path(vault_root, target),
        "title": target.stem,
        "kind": ex.kind,
        "capture_scope": ex.scope,
        "content_hash": sources.content_hash(ex.text),
        "chars": len(ex.text),
        "language": ex.language,
        "supersedes": previous.rel if previous is not None and status == "changed" else None,
        "chunks": sources.chunks(text),
    }


# --- commands ----------------------------------------------------------------------------


INGESTED_FILES = "ingested-files.json"  # state dir: sha256 of a local file's bytes -> its source note
SCANNED_SUFFIXES = {*DOCUMENT_KINDS, *TEXT_SUFFIXES, *HTML_SUFFIXES}


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ingested(vault_root: Path) -> dict[str, dict[str, str]]:
    try:
        data = json.loads((config.state_dir(vault_root) / INGESTED_FILES).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def cmd_fetch(args: argparse.Namespace, vault_root: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(dir=config.state_dir(vault_root)) as scratch:
        ex = extract(args.target, args, Path(scratch))
    result = store(vault_root, ex)
    path = Path(args.target).expanduser()
    if "://" not in args.target and path.is_file():
        # A folder ingest (`scan`) recognises the file by its bytes, whatever it is called now.
        record = _ingested(vault_root) | {file_digest(path): {"rel": result["rel"], "path": str(path)}}
        (config.state_dir(vault_root) / INGESTED_FILES).write_text(json.dumps(record, indent=0), encoding="utf-8")
    return result


def cmd_scan(args: argparse.Namespace, vault_root: Path) -> dict[str, Any]:
    """The files under a folder still to ingest, for an ingest that runs in batches (D135).

    A file counts as done once `fetch` stored it (by its bytes, so a renamed or moved copy is
    still done) and its source note has `integrated`; one stored but not integrated is
    `started` and comes first, since an ingest stopped half-way. Read only.
    """
    root = Path(args.folder).expanduser()
    if not root.is_dir():
        raise SourceError(2, f"{args.folder} is not a folder")
    if vault.is_inside(vault_root, root):
        raise SourceError(2, "scan a folder outside the vault; notes in it are already notes")
    known = _ingested(vault_root)
    integrated = {n.rel: bool(n.get("integrated")) for n in sources.existing(vault_root)}
    pending, started, done = [], [], 0
    for path in sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in SCANNED_SUFFIXES):
        if any(part.startswith(".") for part in path.relative_to(root).parts):
            continue
        entry = known.get(file_digest(path))
        if entry and integrated.get(entry.get("rel", "")):
            done += 1
        elif entry and entry.get("rel") in integrated:
            started.append({"path": str(path), "rel": entry["rel"]})
        else:
            pending.append({"path": str(path), "size": path.stat().st_size})
    todo = [*started, *pending]
    return {
        "ok": True,
        "folder": str(root),
        "done": done,
        "started": len(started),
        "pending": len(pending),
        "next": todo[: args.limit],
    }


def cmd_add(args: argparse.Namespace, vault_root: Path) -> dict[str, Any]:
    text = sys.stdin.read() if args.body_file == "-" else Path(args.body_file).read_text(encoding="utf-8")
    if not text.strip():
        raise SourceError(2, "the body is empty")
    # Sources are exempt from the write hook's check; opt in for material nobody vetted (transcripts).
    if args.refuse_secrets and (problems := secret_problems(text)):
        raise SourceError(2, f"nothing written: {'; '.join(problems)}")
    published = schema.as_date(args.published) if args.published else None
    if args.published and published is None:
        raise SourceError(2, f"--published {args.published!r} is not YYYY-MM-DD")
    url = args.url
    if url and (video := sources.youtube_id(url)):
        url = f"https://www.youtube.com/watch?v={video}"
    image = None
    if args.attach:
        image = Path(args.attach).expanduser()
        if not image.is_file() or image.suffix.lower() not in IMAGE_SUFFIXES:
            raise SourceError(2, f"--attach needs an image file ({', '.join(sorted(IMAGE_SUFFIXES))})")
        # Named by content, so the same image added twice still hashes (and dedups) the same.
        name = f"source-{hashlib.sha256(image.read_bytes()).hexdigest()[:12]}{image.suffix.lower()}"
        text = f"![[{name}]]\n\n{text}"
    ex = Extracted(args.kind, args.title, text, url, args.author, published, args.capture_scope)
    result = store(vault_root, ex)
    if image is not None:
        target = vault_root / "Attachments" / name
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(image, target)
        result["attachment"] = vault.rel_path(vault_root, target)
    return result


def cmd_lookup(args: argparse.Namespace, vault_root: Path) -> dict[str, Any]:
    same = sources.by_url(sources.existing(vault_root), args.url)
    return {
        "ok": True,
        "key": sources.normalize_url(args.url),
        "found": [
            {
                "rel": n.rel,
                "fetched_at": str(n.get("fetched_at")),
                "summary": n.get("summary"),
                "integrated": _date_or_none(n.get("integrated")),
            }
            for n in same
        ],
    }


def cmd_quote_check(args: argparse.Namespace, vault_root: Path) -> dict[str, Any]:
    """Are these quotes really in the source note? Read-only (D125)."""
    path = (vault_root / args.file).resolve()
    if not path.is_file() or not vault.is_inside(vault_root, path):
        found = vault.find_by_stem(vault_root, Path(args.file).stem)
        if found is None:
            raise SourceError(2, f"no source note {args.file}")
        path = found
    note = vault.read_note(vault_root, path)
    if note.type != "source":
        raise SourceError(2, f"{note.rel} is not a source note")
    checked = []
    for quote in args.quotes:
        found = sources.quote_found(note.body, quote)
        checked.append(
            {
                "quote": quote,
                "found": found,
                **({} if found else {"closest": sources.closest_passage(note.body, quote)}),
            }
        )
    return {"ok": True, "rel": note.rel, "all_found": all(c["found"] for c in checked), "checked": checked}


def _date_or_none(value: object) -> str | None:
    return None if value in (None, "") else str(value)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--vault")
    sub = parser.add_subparsers(dest="cmd", required=True)

    fetch = sub.add_parser("fetch")
    fetch.add_argument("target", help="URL, YouTube link or local file")
    fetch.add_argument("--title", help="override the detected title")
    fetch.add_argument("--html-file", help="use this saved HTML instead of downloading the URL")
    fetch.add_argument("--transcript-json", help="use this transcript instead of downloading it")

    add = sub.add_parser("add")
    add.add_argument("--kind", required=True, choices=schema.load().types["source"].fields["source_kind"].enum)
    add.add_argument("--title", required=True)
    add.add_argument("--url")
    add.add_argument("--author")
    add.add_argument("--published")
    add.add_argument("--capture-scope", choices=["full", "partial"], default="full")
    add.add_argument("--body-file", required=True, help="file with the content, or - for stdin")
    add.add_argument("--attach", help="image to copy into Attachments/ and embed at the top of the note")
    add.add_argument(
        "--refuse-secrets", action="store_true", help="exit 2 when the body looks like it holds a credential"
    )

    lookup = sub.add_parser("lookup")
    lookup.add_argument("url")

    scan = sub.add_parser("scan")
    scan.add_argument("folder", help="a folder outside the vault holding files to ingest")
    scan.add_argument("--limit", type=int, default=5, help="how many to return in `next`")

    quote = sub.add_parser("quote-check")
    quote.add_argument("--file", required=True, help="the source note: vault-relative path or its title")
    quote.add_argument("quotes", nargs="+", help="text claimed to be in the source, word for word")

    args = parser.parse_args()
    vault_root = config.write_vault(args.vault)
    if vault_root is None or not vault_root.is_dir():
        print(json.dumps({"ok": False, "error": "vault not found; run /synapsidian:setup"}))
        sys.exit(2)
    try:
        match args.cmd:
            case "fetch":
                result = cmd_fetch(args, vault_root)
            case "add":
                result = cmd_add(args, vault_root)
            case "lookup":
                result = cmd_lookup(args, vault_root)
            case "quote-check":
                result = cmd_quote_check(args, vault_root)
            case "scan":
                result = cmd_scan(args, vault_root)
    except SourceError as exc:
        extra = {"fallback": FALLBACK} if exc.code == 4 else {}
        print(json.dumps({"ok": False, "error": str(exc), **extra}, ensure_ascii=False))
        sys.exit(exc.code)
    print(json.dumps(result, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
