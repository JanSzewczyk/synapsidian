from __future__ import annotations

import itertools
import json
from pathlib import Path

import httpx
import pytest
import yaml

import source
from synapsidianlib import frontmatter, sources

PARAGRAPHS = [
    f"Paragraph {n}: pay equity exports need a stable column order so that analysts can diff two runs "
    f"of the same report, and the XLSX writer keeps the order of the model's fields (fact {n})."
    for n in range(1, 41)
]


def article(paragraphs: list[str], title: str = "Export formats explained") -> str:
    body = "".join(f"<p>{p}</p>" for p in paragraphs)
    return (
        f"<html><head><title>{title}</title><meta name='author' content='Anna Nowak'>"
        "<meta property='article:published_time' content='2026-09-30'></head>"
        f"<body><nav><a href='/'>Home</a> <a href='/blog'>Blog</a></nav><article><h1>{title}</h1>{body}</article>"
        "<footer>We use cookies. Accept all?</footer></body></html>"
    )


def save_html(tmp_path: Path, html: str, name: str = "page.html") -> str:
    path = tmp_path / name
    path.write_text(html, encoding="utf-8")
    return str(path)


# --- pure functions -------------------------------------------------------------------------


def test_hash_ignores_capture_noise():
    text = "# Title\n\n* one\n+ two\n- three\n\nSome   text\nwrapped here.\n"
    noisy = "﻿# Title\r\n\r\n- one\r\n- two\r\n* three\r\n\r\nSome text wrapped   here.  "
    assert sources.content_hash(text) == sources.content_hash(noisy)
    assert sources.content_hash(text) != sources.content_hash(text.replace("three", "four"))
    assert len(sources.content_hash(text)) == 16


@pytest.mark.parametrize(
    "variant",
    [
        "https://www.example.com/blog/post/",
        "http://example.com/blog/post?utm_source=x&utm_medium=y",
        "https://example.com/blog/post#comments",
        "HTTPS://WWW.Example.com:443/blog/post?fbclid=1",
    ],
)
def test_url_variants_share_a_key(variant):
    assert sources.normalize_url(variant) == "example.com/blog/post"


def test_url_keeps_meaningful_query_and_youtube_forms_collapse():
    assert sources.normalize_url("https://example.com/?p=2&a=1") == "example.com?a=1&p=2"
    key = "youtube.com/watch?v=aircAruvnKk"
    for url in (
        "https://www.youtube.com/watch?v=aircAruvnKk&t=42s",
        "https://youtu.be/aircAruvnKk?si=abc",
        "https://m.youtube.com/shorts/aircAruvnKk",
        "youtube.com/embed/aircAruvnKk",
    ):
        assert sources.normalize_url(url) == key, url
    assert sources.youtube_id("https://example.com/watch?v=aircAruvnKk") is None
    assert sources.youtube_id("https://www.youtube.com/watch?v=short") is None


def test_chunks_cover_every_line_once():
    text = "\n".join("x" * 99 for _ in range(1000))
    ranges = sources.chunks(text, budget=10_000)
    assert ranges[0][0] == 1 and ranges[-1][1] == 1000 and len(ranges) == 10
    assert all(b[0] == a[1] + 1 for a, b in itertools.pairwise(ranges))
    assert sources.chunks("short") == [(1, 1)]
    assert sources.chunks("x" * 50 + "\n" + "y" * 5, budget=40) == [(1, 2)]  # small tail joins


def test_title_is_cut_at_a_word_and_made_filename_safe():
    assert sources.short_title("A: very/long " + "word " * 40, limit=30) == "A very long word word word"
    title = "Obsidian Bases + Web Clipper \N{MEMO} The Perfect Pair \N{ROCKET}\N{VARIATION SELECTOR-16}"
    assert sources.short_title(title) == "Obsidian Bases + Web Clipper The Perfect Pair"
    assert sources.short_title("Zażółć · gęślą & jaźń") == "Zażółć · gęślą & jaźń"


# --- fetch / add / lookup ---------------------------------------------------------------------


def test_article_is_copied_once_then_recognised(run, vault, tmp_path):
    url = "https://www.example.com/blog/export-formats/?utm_source=newsletter"
    html = save_html(tmp_path, article(PARAGRAPHS))
    code, out = run("source", "fetch", url, "--html-file", html, vault=vault)
    assert code == 0 and out["status"] == "new" and out["kind"] == "article"
    note = frontmatter.parse((vault / out["rel"]).read_text())
    assert out["rel"].startswith("Sources/") and out["rel"].endswith("Export formats explained.md")
    assert note.meta["url"] == url and note.meta["capture_scope"] == "full"
    assert note.meta["content_hash"] == out["content_hash"] == sources.content_hash(note.body)
    assert str(note.meta["published"]) == "2026-09-30" and note.meta["author"] == "Anna Nowak"
    assert "Paragraph 40" in note.body and "cookies" not in note.body and "Blog" not in note.body
    assert out["chunks"][0][0] == 1

    code, again = run("source", "fetch", "https://example.com/blog/export-formats", "--html-file", html, vault=vault)
    assert code == 0 and again["status"] == "unchanged" and again["rel"] == out["rel"]
    assert again["chunks"] == out["chunks"] and again["kind"] == "article"  # enough to resume an ingest
    assert len(list((vault / "Sources").glob("*.md"))) == 1
    # Not integrated yet: the key is absent, which the To integrate view tests with hasProperty (D84).
    assert again["integrated"] is None and "integrated" not in note.meta

    code, _ = run("note", "set", "--file", out["rel"], "--field", "integrated=2026-10-14", vault=vault)
    assert code == 0
    _, done = run("source", "fetch", url, "--html-file", html, vault=vault)
    assert done["status"] == "unchanged" and done["integrated"] == "2026-10-14"
    _, found = run("source", "lookup", url, vault=vault)
    assert found["found"][0]["integrated"] == "2026-10-14"
    code, bad = run("note", "set", "--file", out["rel"], "--field", "integrated=yesterday", vault=vault)
    assert code == 2 and not bad["ok"]


def test_sources_base_has_a_to_integrate_view_and_one_per_kind():
    base = yaml.safe_load(
        (Path(__file__).parents[1] / "plugins" / "synapsidian" / "bases" / "Sources.base").read_text(encoding="utf-8")
    )
    views = {v["name"]: v for v in base["views"]}
    assert views["To integrate"]["filters"] == {"not": ['file.hasProperty("integrated")']}
    kinds = {"article", "pdf", "document", "slides", "youtube", "confluence", "text", "image", "other"}
    filtered = " ".join(str(v.get("filters", "")) for v in base["views"])
    assert all(f'source_kind == "{kind}"' in filtered for kind in kinds)  # every kind has a view


def test_docs_page_keeps_tables_and_code_and_drops_chrome(run, vault, tmp_path):
    html = (
        "<html><head><title>Manifest reference</title></head><body>"
        "<header>Site header</header><nav><a href='/docs'>Docs home</a></nav><main>"
        "<h1>Manifest reference</h1><h2><a href='#fields'>\N{ZERO WIDTH SPACE}</a>Fields</h2>"
        + "".join(f"<p>{p}</p>" for p in PARAGRAPHS[:6])
        + "<table><tr><th>Field</th><th>Type</th></tr><tr><td>name</td><td>string</td></tr></table>"
        '<pre><code>{"name": "deploy-tools"}</code></pre>'
        "<p>See <a href='/docs/en/plugins/create'>Create a plugin</a> and <a href='#fields'>Fields</a>.</p>"
        "<footer>Was this page helpful?</footer></main><aside>On this page</aside></body></html>"
    )
    url = "https://code.example.com/docs/en/plugins-reference"
    code, out = run("source", "fetch", url, "--html-file", save_html(tmp_path, html), vault=vault)
    assert code == 0, out
    body = frontmatter.parse((vault / out["rel"]).read_text()).body
    assert "| name | string |" in body and '{"name": "deploy-tools"}' in body
    assert "[Create a plugin](https://code.example.com/docs/en/plugins/create)" in body
    assert "and Fields." in body and "](#" not in body
    for chrome in ("Site header", "Docs home", "helpful", "On this page"):
        assert chrome not in body


def test_obsidian_publish_shell_points_to_its_markdown():
    shell = (
        '<html><head><script>window.siteInfo={"uid":"f786"};'
        'window.preloadPage=f("https://publish-01.obsidian.md/access/f786db9f/Bases/Bases%20syntax.md");'
        "</script></head><body></body></html>"
    )
    assert source.publish_page(shell) == "https://publish-01.obsidian.md/access/f786db9f/Bases/Bases%20syntax.md"
    assert source.publish_page("<html><body><p>plain page</p></body></html>") is None
    base = "https://publish-01.obsidian.md/access/f786db9f"
    assert source.publish_title(f"{base}/Bases/Functions.md") == "Bases Functions"
    assert source.publish_title(f"{base}/Bases/Bases%20syntax.md") == "Bases syntax"
    assert source.publish_title(f"{base}/Home.md") == "Home"


def test_url_titles_name_the_repository_for_generic_files():
    assert source.url_title("https://raw.githubusercontent.com/exceljs/exceljs/master/README.md") == "exceljs README"
    raw = "https://gitlab.com/catamphetamine/write-excel-file/-/raw/main/README.md"
    assert source.url_title(raw) == "write-excel-file README"
    assert source.url_title("https://example.com/blog/export-formats") == "export-formats"
    assert source.url_title("https://example.com/") == "example.com"


def test_markdown_page_drops_its_frontmatter_and_wikilinks():
    page = (
        "---\npermalink: bases/syntax\npublish: true\n---\n"
        "When you [[Create a base|create a base]], it is saved as a `.base` file. See [[Views]] and "
        "[[Formulas#Functions]]. ![[bases-example.png]]\n\n" + "\n".join(PARAGRAPHS[:3])
    )
    ex = source.from_markdown(page, "https://obsidian.md/help/bases/syntax", None, "Bases syntax")
    assert ex.title == "Bases syntax" and ex.kind == "article"
    assert "permalink" not in ex.text and "[[" not in ex.text
    assert ex.text.startswith("When you create a base, it is saved") and "See Views and Formulas." in ex.text
    assert source.first_heading("```yaml\n# Simple filter\n```\n# Real title\n") == "Real title"
    assert source.first_heading("no heading\n## Sub\n") is None


def test_small_edit_is_unchanged_real_edit_supersedes(run, vault, tmp_path):
    url = "https://example.com/post"
    run("source", "fetch", url, "--html-file", save_html(tmp_path, article(PARAGRAPHS)), vault=vault)

    tweaked = [*PARAGRAPHS[:-1], PARAGRAPHS[-1].replace("fact 40", "fact forty")]
    _, small = run("source", "fetch", url, "--html-file", save_html(tmp_path, article(tweaked), "b.html"), vault=vault)
    assert small["status"] == "unchanged"

    rewritten = [p.replace("XLSX", "CSV") for p in PARAGRAPHS[:20]] + PARAGRAPHS[20:]
    _, changed = run(
        "source", "fetch", url, "--html-file", save_html(tmp_path, article(rewritten), "c.html"), vault=vault
    )
    assert changed["status"] == "changed" and changed["supersedes"].startswith("Sources/")
    assert changed["rel"].endswith("(2).md")  # same day, same title
    meta = frontmatter.parse((vault / changed["rel"]).read_text()).meta
    assert meta["supersedes"] == f"[[{Path(changed['supersedes']).stem}]]"

    _, found = run("source", "lookup", "http://www.example.com/post/", vault=vault)
    assert [f["rel"] for f in found["found"]] == [changed["rel"], changed["supersedes"]]


def test_add_dedups_by_hash_whatever_the_title(run, vault):
    body = "Confluence page body.\n\n" + "\n".join(PARAGRAPHS[:5])
    args = ("source", "add", "--kind", "confluence", "--url", "https://example.atlassian.net/wiki/x/1")
    code, out = run(*args, "--title", "Export spec", "--body-file", "-", stdin=body, vault=vault)
    assert code == 0 and out["status"] == "new" and out["kind"] == "confluence"
    _, again = run("source", "add", "--kind", "text", "--title", "Other", "--body-file", "-", stdin=body, vault=vault)
    assert again["status"] == "unchanged" and again["rel"] == out["rel"]
    code, empty = run("source", "add", "--kind", "text", "--title", "x", "--body-file", "-", stdin="  ", vault=vault)
    assert code == 2 and not empty["ok"]


def test_add_refuses_credentials_only_when_asked(run, vault):
    body = "Meeting notes.\nThe key is sk-ant-" + "x" * 30 + "\n"
    args = ("source", "add", "--kind", "document", "--title", "Call", "--body-file", "-")
    code, out = run(*args, "--refuse-secrets", stdin=body, vault=vault)
    assert code == 2 and "credential" in out["error"] and not (vault / "Sources").exists()
    assert run(*args, stdin=body, vault=vault)[0] == 0  # a verbatim source stays verbatim by default


def test_image_is_attached_once_and_embedded(run, vault, tmp_path):
    image = tmp_path / "Whiteboard.PNG"
    image.write_bytes(b"\x89PNG fake image bytes")
    args = ("source", "add", "--kind", "image", "--capture-scope", "partial", "--attach", str(image))
    code, out = run(*args, "--title", "Export flow sketch", "--body-file", "-", stdin="Box A -> Box B", vault=vault)
    assert code == 0 and out["attachment"].startswith("Attachments/source-") and out["attachment"].endswith(".png")
    assert (vault / out["attachment"]).read_bytes() == image.read_bytes()
    body = frontmatter.parse((vault / out["rel"]).read_text()).body
    assert body.startswith(f"![[{Path(out['attachment']).name}]]") and "Box A -> Box B" in body
    _, again = run(*args, "--title", "Same sketch", "--body-file", "-", stdin="Box A -> Box B", vault=vault)
    assert again["status"] == "unchanged" and len(list((vault / "Attachments").iterdir())) == 1
    rc, bad = run(*args[:-1], str(tmp_path), "--title", "x", "--body-file", "-", stdin="x", vault=vault)
    assert rc == 2 and "--attach" in bad["error"]


def test_youtube_transcript_becomes_timestamped_paragraphs(run, vault, tmp_path):
    snippets = [{"text": f"sentence {i}", "start": i * 15.0} for i in range(10)]
    transcript = tmp_path / "t.json"
    transcript.write_text(json.dumps(snippets))
    code, out = run(
        "source", "fetch", "https://youtu.be/aircAruvnKk?t=3", "--transcript-json", str(transcript),
        "--title", "But what is a neural network", vault=vault,
    )  # fmt: skip
    assert code == 0 and out["kind"] == "youtube"
    note = frontmatter.parse((vault / out["rel"]).read_text())
    assert note.meta["url"] == "https://www.youtube.com/watch?v=aircAruvnKk"
    paragraphs = note.body.strip().split("\n\n")
    assert paragraphs[0].startswith("**[00:00]** sentence 0 sentence 1")
    assert paragraphs[1].startswith("**[01:00]** sentence 4")


def test_local_text_file(run, vault, tmp_path):
    doc = tmp_path / "notes from vendor.md"
    doc.write_text("\n".join(PARAGRAPHS[:3]))
    code, out = run("source", "fetch", str(doc), vault=vault)
    assert code == 0 and out["kind"] == "text" and out["rel"].endswith("notes from vendor.md")
    assert frontmatter.parse((vault / out["rel"]).read_text()).meta["url"] == doc.resolve().as_uri()


@pytest.mark.parametrize(
    ("target", "code"),
    [
        ("http://127.0.0.1:8080/admin", 2),
        ("http://localhost/", 2),
        ("http://169.254.169.254/latest/meta-data/", 2),
        ("file:///etc/passwd", 2),
        ("/no/such/file.pdf", 2),
    ],
)
def test_refuses_local_targets(run, vault, target, code):
    rc, out = run("source", "fetch", target, vault=vault)
    assert rc == code and not out["ok"]
    assert not (vault / "Sources").exists()


def test_every_redirect_hop_is_checked():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://127.0.0.1/secret"})

    with pytest.raises(source.SourceError, match="non-public"):
        source.http_get("http://93.184.215.14/", transport=httpx.MockTransport(handler))


def test_the_connection_goes_to_the_checked_address_not_a_second_dns_answer(monkeypatch):
    """DNS rebinding: the name resolves to a public address for the check and to a local one
    when connecting. The connection must use the address that was checked."""
    import http.server
    import socket
    import threading

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(f"host={self.headers['Host']}".encode())

        def log_message(self, *args: object) -> None:
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        # The vetted address is the local test server; DNS for the name points nowhere usable.
        monkeypatch.setattr(source, "check_public", lambda url: ("rebind.invalid", port, "127.0.0.1"))
        real = socket.getaddrinfo

        def no_dns(host, *args, **kwargs):  # type: ignore[no-untyped-def]
            if host == "rebind.invalid":
                raise AssertionError("connected by resolving the name again")
            return real(host, *args, **kwargs)

        monkeypatch.setattr(socket, "getaddrinfo", no_dns)
        _, _, body = source.http_get(f"http://rebind.invalid:{port}/")
        assert body == f"host=rebind.invalid:{port}".encode()  # Host header keeps the name
    finally:
        server.shutdown()


def test_quote_check_finds_real_quotes_and_shows_what_the_source_says(run, vault):
    """D125: a claimed quote is checked against the verbatim copy before anyone relies on it."""
    body = (
        "# Release notes\n\nThe **new scheduler** retries a failed job “three times” before it gives up.\n\n"
        "Older versions retried once. Jobs that time out are never retried.\n"
    )
    _, added = run("source", "add", "--kind", "text", "--title", "Scheduler notes", "--body-file", "-",
                   stdin=body, vault=vault)  # fmt: skip
    rel = added["rel"]
    _, out = run(
        "source", "quote-check", "--file", rel,
        '"The new scheduler retries a failed job "three times""',
        "retries a failed job ... before it gives up",
        "Jobs that time out are retried twice",
        vault=vault,
    )  # fmt: skip
    found = [c["found"] for c in out["checked"]]
    assert found == [True, True, False] and out["all_found"] is False
    assert out["checked"][2]["closest"] == "Jobs that time out are never retried."
    _, by_title = run("source", "quote-check", "--file", Path(rel).stem, "Older versions retried once", vault=vault)
    assert by_title["all_found"] is True
    assert run("source", "quote-check", "--file", "Nope", "x", vault=vault)[0] == 2


def test_folder_scan_resumes_where_the_last_batch_stopped(run, vault, tmp_path):
    """D135: files are known by their bytes; stored-but-not-integrated comes first."""
    folder = tmp_path / "export"
    (folder / "sub").mkdir(parents=True)
    for name, text in (
        ("a.md", "# Alpha\n\nFirst note body."),
        ("b.txt", "Bravo text."),
        ("sub/c.md", "# Charlie\n\nx"),
    ):
        (folder / name).write_text(text)
    (folder / "photo.jpg").write_bytes(b"\xff")
    (folder / ".hidden.md").write_text("no")
    _, first = run("source", "scan", str(folder), "--limit", "2", vault=vault)
    assert (first["pending"], first["done"], first["started"]) == (3, 0, 0)
    assert [Path(n["path"]).name for n in first["next"]] == ["a.md", "b.txt"]

    _, fetched = run("source", "fetch", str(folder / "a.md"), vault=vault)
    _, after = run("source", "scan", str(folder), vault=vault)
    assert after["started"] == 1 and after["next"][0]["rel"] == fetched["rel"]  # stored, not integrated yet
    run("note", "set", "--file", fetched["rel"], "--field", "integrated=2026-10-30", vault=vault)
    (folder / "a.md").rename(folder / "renamed.md")
    _, last = run("source", "scan", str(folder), vault=vault)
    assert (last["done"], last["started"], last["pending"]) == (1, 0, 2)
    assert run("source", "scan", str(vault), vault=vault)[0] == 2  # never the vault itself


def test_skill_rejects_unknown_file_types(run, vault, tmp_path):
    odd = tmp_path / "data.bin"
    odd.write_bytes(b"\x00\x01")
    rc, out = run("source", "fetch", str(odd), vault=vault)
    assert rc == 2 and "unsupported file type" in out["error"]
