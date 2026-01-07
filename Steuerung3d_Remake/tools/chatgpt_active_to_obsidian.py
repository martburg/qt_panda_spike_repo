
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChatGPT / Email / Web → Obsidian local saver (HTTP)

Endpoints
  GET  /ping
  GET  /projects
  GET  /version
  GET  /shutdown

  POST /                 -> Chat: {title, project?, messages:[{role,text}]}
  POST /email            -> Email: {subject, from, body, project?, [to],[cc],[bodyType]}

  POST /web              -> Web:
     { mode: "link" | "readable" | "snapshot" | "readable_html",
       url: "https://...",
       project: "Inbox",
       title?: "Override title",
       html?: "<!doctype html>..."            # for snapshot/readable_html
       tags?: [...], note?: "your comment"   # optional
     }

Storage
  Projects/<Project>/Chat[/YYYY[/MM]]/...
  Projects/<Project>/Email[/YYYY[/MM]]/...
  Projects/<Project>/Web/Links/YYYY/...
  Projects/<Project>/Web/Clips/YYYY/slug/index.md (+ assets/)
  Projects/<Project>/Web/Snapshots/YYYY/slug.html (plus tiny .md index)
"""

import os, re, json, time, datetime, pathlib, threading, sys, atexit, hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import logging
from logging.handlers import RotatingFileHandler
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
from pathlib import Path

import sys
READABILITY_INFO = ""
BS4_INFO = ""
MDIFY_INFO = ""
H2T_INFO = ""

try:
    import readability  # provided by readability-lxml
    from readability import Document as ReadabilityDocument
    READABILITY_INFO = getattr(readability, "__file__", "unknown")
except Exception as e:
    ReadabilityDocument = None
    READABILITY_INFO = f"ERROR: {e!r}"

try:
    from bs4 import BeautifulSoup
    import bs4 as _bs4
    BS4_INFO = getattr(_bs4, "__file__", "unknown")
except Exception as e:
    BeautifulSoup = None
    BS4_INFO = f"ERROR: {e!r}"

# prefer markdownify, then html2text as fallback
_md_from_html = None
try:
    from markdownify import markdownify as _md1
    MDIFY_INFO = getattr(sys.modules.get("markdownify"), "__file__", "unknown")
    def _md_from_html(html: str) -> str: return _md1(html or "", heading_style="ATX")
except Exception as e:
    MDIFY_INFO = f"ERROR: {e!r}"
    try:
        import html2text  # pip install html2text
        H2T_INFO = getattr(sys.modules.get("html2text"), "__file__", "unknown")
        def _md_from_html(html: str) -> str:
            h = html2text.HTML2Text()
            h.ignore_links = False
            h.ignore_images = False
            h.body_width = 0
            return h.handle(html or "")
    except Exception as e2:
        H2T_INFO = f"ERROR: {e2!r}"
        _md_from_html = None

# Optional libs for Readable + Markdown
try:
    from readability import Document as ReadabilityDocument  # pip install readability-lxml
except Exception:
    ReadabilityDocument = None


try:
    from bs4 import BeautifulSoup  # pip install beautifulsoup4 lxml
except Exception:
    BeautifulSoup = None

# prefer markdownify, then html2text as fallback
_md_from_html = None
try:
    from markdownify import markdownify as _md1  # pip install markdownify
    def _md_from_html(html: str) -> str: return _md1(html or "", heading_style="ATX")
except Exception:
    try:
        import html2text  # pip install html2text
        def _md_from_html(html: str) -> str:
            h = html2text.HTML2Text()
            h.ignore_links = False
            h.ignore_images = False
            h.body_width = 0
            return h.handle(html or "")
    except Exception:
        _md_from_html = None


# =================== CONFIG ===================


VAULT_DIR = r"C:\Users\MartinDev\Documents\obsidian"
#VAULT_DIR        = str(Path(__file__).resolve().parents[1] / "vault")
PROJECTS_DIR     = "Projects"
CHAT_SUBDIR      = "Chat"         # per-project chat folder name
INDEX_NOTE       = "Master Project Index.md"  # parsed for [[Project]] links
PROJECT_DEFAULT  = "Inbox"

# Email container + nesting
EMAIL_CONTAINER  = ["Email"]
EMAIL_NESTING    = "year"   # "flat" | "year" | "year_month"

# Chat container + nesting
CHAT_CONTAINER  = "Chat"
CHAT_NESTING    = "year"    # "flat" | "year" | "year_month"

# Web containers
WEB_ROOT        = "Web"
WEB_LINKS_DIR   = "Links"
WEB_CLIPS_DIR   = "Clips"
WEB_SNAP_DIR    = "Snapshots"

HOST             = "127.0.0.1"
PORT             = 8765

# Logs next to the vault
LOG_DIR          = os.path.join(VAULT_DIR, "Logs")
LOG_FILE         = "server.log"

# Single-instance lock (set to None to disable)
LOCKFILE         = os.path.join(LOG_DIR, "server.lock")

# /projects cache (seconds)
CACHE_SECS       = 10
# ==============================================


# ---------- Logging ----------
def _ensure_dirs():
    os.makedirs(LOG_DIR, exist_ok=True)

def _setup_logging():
    _ensure_dirs()
    logger = logging.getLogger("obsidian_saver")
    logger.setLevel(logging.INFO)
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(ch)
    fh = RotatingFileHandler(os.path.join(LOG_DIR, LOG_FILE),
                             maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(fh)
    return logger

log = _setup_logging()


# ---------- Lockfile ----------
def _acquire_lock():
    if not LOCKFILE:
        return True
    _ensure_dirs()
    try:
        fd = os.open(LOCKFILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode("utf-8"))
        os.close(fd)
        return True
    except FileExistsError:
        try:
            pid_txt = pathlib.Path(LOCKFILE).read_text(encoding="utf-8", errors="ignore").strip()
            pid = int(pid_txt or "0")
        except Exception:
            pid = 0
        if pid <= 0:
            try:
                os.remove(LOCKFILE)
                fd = os.open(LOCKFILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode("utf-8"))
                os.close(fd)
                return True
            except Exception:
                pass
        log.error("Lockfile exists (%s). Another instance may be running (pid=%s).", LOCKFILE, pid)
        return False

def _release_lock():
    try:
        if LOCKFILE and os.path.exists(LOCKFILE):
            os.remove(LOCKFILE)
    except Exception as e:
        log.error("Failed to remove lockfile: %s", e)


log.info("I'm using Python: %s", sys.executable)


# ---------- Helpers ----------
WIKILINK_RE = re.compile(r"\[\[([^\]\|#]+)")
SAFE_CHARS = r"[^\w\-\[\]/ .,&+()]" # used by safe_segment (keep for filenames where needed)
_projects_cache = {"ts": 0.0, "items": []}

def slugify(s: str) -> str:
    s = s.strip().lower()
    # keep [] in slugs
    s = re.sub(r"[^\w\s\-\[\]]", "", s)
    s = re.sub(r"[\s_\-]+", "-", s).strip("-")
    return s or "note"

def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def _esc(s: str) -> str:
    return (s or "").replace('"', '\\"')

def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")

def sha1(s: str) -> str:
    return hashlib.sha1((s or "").encode("utf-8")).hexdigest()

def _coerce_text(x):
    if x is None:
        return ""
    if isinstance(x, (str, int, float)):
        return str(x)
    if isinstance(x, (list, tuple)):
        return _coerce_text(x[0]) if x else ""
    if isinstance(x, dict):
        for k in ("name", "value", "label", "text", "project", "title"):
            if k in x:
                return _coerce_text(x[k])
        return json.dumps(x, ensure_ascii=False)
    return str(x)

def safe_segment(s: str) -> str:
    s = _coerce_text(s)
    s = (s or "").strip().replace("\\", "/")
    s = re.sub(SAFE_CHARS, "", s)
    s = re.sub(r"/{2,}", "/", s)
    return s.strip(" /") or PROJECT_DEFAULT

def safe_project(name: str) -> str:
    """Sanitize a project name into a single folder segment while allowing [ and ]."""
    s = _coerce_text(name)
    s = (s or "").strip()

    # prevent nesting / traversal
    s = s.replace("\\", "/").replace("/", " ")
    s = s.replace("..", "")

    # KEEP brackets; allow common safe chars including [ ]
    s = re.sub(r"[^\w\-\s.&+,\[\]()]", "", s)

    # normalize whitespace and trim dots/spaces
    s = re.sub(r"\s+", " ", s).strip(" .")
    return s or PROJECT_DEFAULT

def _read_file_safe(path):
    try:
        return pathlib.Path(path).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""

def _scan_projects_from_index(vault_path: pathlib.Path):
    idx = vault_path / INDEX_NOTE
    if not idx.exists():
        return []
    text = _read_file_safe(idx)
    names = [m.group(1).strip() for m in WIKILINK_RE.finditer(text)]
    seen, out = set(), []
    for n in names:
        if n and n not in seen:
            seen.add(n); out.append(n)
    return out

def _scan_projects_from_folders(vault_path: pathlib.Path):
    out = set()
    proj_root = vault_path / PROJECTS_DIR
    if proj_root.exists():
        for p in proj_root.iterdir():
            if p.is_dir():
                out.add(p.name)
            elif p.is_file() and p.suffix.lower() == ".md":
                out.add(p.stem)
    if proj_root.exists():
        for p in proj_root.iterdir():
            if p.is_dir() and (p / CHAT_SUBDIR).exists():
                out.add(p.name)
    return sorted(out)

def list_projects(vault_path: pathlib.Path):
    now = time.time()
    if now - _projects_cache["ts"] < CACHE_SECS and _projects_cache["items"]:
        return _projects_cache["items"]
    names = _scan_projects_from_index(vault_path) or _scan_projects_from_folders(vault_path)
    if PROJECT_DEFAULT not in names:
        names = [PROJECT_DEFAULT] + names
    seen, out = set(), []
    for n in names:
        if n and n not in seen:
            seen.add(n); out.append(n)
    _projects_cache.update(ts=now, items=out)
    return out

def resolve_project_name(vault_path: pathlib.Path, name: str) -> str:
    """
    Prefer exact project folder names (including brackets).
    If no exact or case-insensitive exact match exists, keep the sanitized input (create new).
    """
    proj_root = vault_path / PROJECTS_DIR
    candidates = [p.name for p in proj_root.iterdir() if p.is_dir()] if proj_root.exists() else []

    # Exact match (preserves brackets)
    if name in candidates:
        return name

    # Case-insensitive exact match
    lower_map = {c.lower(): c for c in candidates}
    if name.lower() in lower_map:
        return lower_map[name.lower()]

    # DO NOT map to "bracketless" anymore; let new folders be created with the given name
    return name


# URL helpers
_TRACKERS = {"utm_source","utm_medium","utm_campaign","utm_term","utm_content","utm_id","gclid","fbclid","mc_cid","mc_eid","igshid"}

def strip_tracking_params(url: str) -> str:
    try:
        u = urlparse(url)
        q = [(k,v) for (k,v) in parse_qsl(u.query, keep_blank_values=True) if k.lower() not in _TRACKERS]
        u2 = u._replace(query=urlencode(q))
        return urlunparse(u2)
    except Exception:
        return url

def canonical_from_html(html: str) -> str:
    try:
        if not html or not BeautifulSoup:
            return ""
        soup = BeautifulSoup(html, "lxml")
        link = soup.find("link", rel=lambda x: x and "canonical" in x)
        href = (link.get("href") if link else "") or ""
        return href.strip()
    except Exception:
        return ""

# ---------- Markdown builders ----------
def build_chat_markdown(title: str, project: str, messages: list):
    dt = datetime.datetime.now()
    proj_val = (project or PROJECT_DEFAULT).replace('"', '\\"')
    fm = [
        "---",
        f"date: {dt.date().isoformat()}",
        f"time: {dt.strftime('%H:%M')}",
        f"topic: {title}",
        f'project: "{proj_val}"',
        "tags: [chatgpt, obsidian, active]",
        "---",
        "",
        f"# {title}",
        ""
    ]
    body = []
    for m in messages:
        role = (m.get("role") or "assistant").strip()
        text = (m.get("text") or "").rstrip()
        body.append(f"## {role.capitalize()}")
        body.append(text if text else "_(empty)_")
        body.append("")
    return "\n".join(fm + body)

def build_email_markdown(subject: str, project: str, data: dict):
    dt = datetime.datetime.now()
    fm = [
        "---",
        "type: email",
        f"date: {dt.date().isoformat()}",
        f"time: {dt.strftime('%H:%M')}",
        f"project: {project or PROJECT_DEFAULT}",
        f"from: {data.get('from','')}",
        f"to: {data.get('to','')}",
        f"cc: {data.get('cc','')}",
        f"subject: {subject}",
        "tags: [email, inbox]",
        "---",
        "",
        f"# {subject}",
        "",
        "## Content",
    ]
    body_type = (data.get("bodyType") or "text/plain").lower()
    body = data.get("body") or ""
    if body_type.startswith("text/html"):
        body_block = f"\n```html\n{body}\n```\n"
    else:
        body_block = "\n" + body + "\n"
    return "\n".join(fm) + body_block

def build_web_link_markdown(meta: dict) -> str:
    dt = datetime.datetime.now()
    fm = [
        "---",
        "type: web",
        "mode: link",
        f"title: {meta.get('title','')!r}",
        f"url: {meta.get('url','')!r}",
        f"canonical_url: {meta.get('canonical_url','')!r}",
        f"domain: {meta.get('domain','')!r}",
        f"retrieved_at: {meta.get('retrieved_at','')}",
        f"project: {meta.get('project','')!r}",
        f"url_sha1: {meta.get('url_sha1','')}",
        "tags: " + json.dumps(meta.get("tags") or ["web","link", meta.get("domain","")]),
        "---",
        "",
        f"# {meta.get('title') or meta.get('url')}",
        "",
        f"**Source:** {meta.get('url')}",
        ""
    ]
    note = meta.get("note") or ""
    if note:
        fm += ["## Notes", note, ""]
    return "\n".join(fm)

def build_web_readable_markdown(meta: dict, content_md: str, warn: str = "") -> str:
    dt = datetime.datetime.now()
    fm = [
        "---",
        "type: web",
        f"mode: {meta.get('mode','readable')}",
        f"title: {meta.get('title','')!r}",
        f"url: {meta.get('url','')!r}",
        f"canonical_url: {meta.get('canonical_url','')!r}",
        f"domain: {meta.get('domain','')!r}",
        f"retrieved_at: {meta.get('retrieved_at','')}",
        f"project: {meta.get('project','')!r}",
        f"status_code: {meta.get('status_code','')}",
        f"url_sha1: {meta.get('url_sha1','')}",
        f"content_sha1: {meta.get('content_sha1','')}",
        f"word_count: {meta.get('word_count',0)}",
        "tags: " + json.dumps(meta.get("tags") or ["web","clipped", meta.get("domain","")]),
        "---",
        "",
        f"# {meta.get('title') or meta.get('url')}",
        "",
        f"> **Source**: {meta.get('url')}  \n> **Captured**: {meta.get('retrieved_at')}  \n> **Domain**: {meta.get('domain')}",
        "",
    ]
    if warn:
        fm += [f"> ⚠️ {warn}", ""]
    note = meta.get("note") or ""
    if note:
        fm += ["## Notes", note, ""]
    fm += ["---", "", content_md.strip(), ""]
    return "\n".join(fm)

def build_web_clip_index_minimal(meta: dict, *, excerpt: str = "", warn: str = "") -> str:
    """
    Minimal frontmatter so hover preview stays fast.
    Does NOT include raw HTML or big blobs in YAML.
    Sidecars (readable.md / page.html) hold the heavy content.
    """
    # Keep tags short; optionally include domain as a tag
    domain_tag = meta.get("domain") or ""
    tags = ["web", "clip"] + ([domain_tag] if domain_tag else [])
    # YAML
    fm = [
        "---",
        'type: webclip',
        f'mode: {meta.get("mode","readable")}',
        f'title: "{_esc(meta.get("title",""))}"',
        f'url: "{_esc(meta.get("url",""))}"',
        f'domain: "{_esc(meta.get("domain",""))}"',
        f'retrieved_at: {meta.get("retrieved_at","")}',
        # keep project if you like seeing it in Properties; it’s small
        f'project: "{_esc(meta.get("project",""))}"',
        "tags: [" + ", ".join(t for t in tags) + "]",
        "---",
        ""
    ]
    # Body (light)
    body = [
        f'# {meta.get("title") or meta.get("url") or "Clip"}',
        "",
        f'> **Source**: {meta.get("url") or ""}  ',
        f'> **Captured**: {meta.get("retrieved_at") or ""}  ',
        f'> **Domain**: {meta.get("domain") or ""}',
        ""
    ]
    if warn:
        body += [f"> ⚠️ {warn}", ""]
    if excerpt:
        body += ["## Excerpt", "", excerpt.strip(), ""]
    # Mention sidecars (so it’s obvious where the content lives)
    body += [
        "---",
        "_This clip stores content in sidecar files:_  ",
        "- `readable.md` (markdown extraction)  ",
        "- `page.html` (original HTML, if provided)",
        ""
    ]
    return "\n".join(fm + body)

# ---------- HTTP Handler ----------
class Handler(BaseHTTPRequestHandler):
    # --- utilities ---
    def _set_common_headers(self, code=200, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        origin = self.headers.get("Origin", "*")
        self.send_header("Access-Control-Allow-Origin", origin if origin else "*")
        self.send_header("Vary", "Origin")
        req_hdrs = self.headers.get("Access-Control-Request-Headers", "")
        allow_hdrs = req_hdrs or "content-type"
        self.send_header("Access-Control-Allow-Headers", allow_hdrs)
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS, GET")
        if self.headers.get("Access-Control-Request-Private-Network") == "true":
            self.send_header("Access-Control-Allow-Private-Network", "true")
        self.end_headers()

    def log_message(self, fmt, *args):
        ct = self.headers.get("Content-Type", "-")
        log.info("%s %s %s - " + fmt, self.command, self.path, ct, *args)
        log.info("%s - %s", self.address_string(), fmt % args)

    # --- verbs ---
    def do_OPTIONS(self):
        self._set_common_headers(204)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        vault_path = pathlib.Path(VAULT_DIR).resolve()

        if path == "/ping":
            self._set_common_headers(200)
            self.wfile.write(b'{"ok": true, "msg": "pong"}'); return

        if path == "/version":
            self._set_common_headers(200)
            self.wfile.write(json.dumps({
                "ok": True,
                "name": "obsidian-local-saver",
                "version": "1.4.0",
                "port": PORT,
                "vault": str(vault_path),
                "projects_dir": PROJECTS_DIR,
                "python": sys.executable,
                "libs": {
                    "readability": READABILITY_INFO,
                    "bs4": BS4_INFO,
                    "markdownify": MDIFY_INFO,
                    "html2text": H2T_INFO
        }}).encode("utf-8")); return

        if path == "/shutdown":
            self._set_common_headers(200)
            self.wfile.write(b'{"ok": true, "msg": "shutting down"}')
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return

        if path == "/projects":
            items = list_projects(vault_path)
            self._set_common_headers(200)
            self.wfile.write(json.dumps({"ok": True, "projects": items}).encode("utf-8")); return

        self._set_common_headers(404)
        self.wfile.write(b'{"ok": false, "error": "not found"}')

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        vault_path = pathlib.Path(VAULT_DIR).resolve()

        # parse body (tolerant)
        try:
            length = int(self.headers.get("content-length", "0"))
        except ValueError:
            length = 0
        raw = self.rfile.read(length).decode("utf-8", "replace")
        ctype = (self.headers.get("content-type") or "").lower()

        data = None; parse_err = None
        try:
            data = json.loads(raw) if raw else {}
        except Exception as e:
            parse_err = e
        if data is None and ("application/x-www-form-urlencoded" in ctype or "=" in raw):
            try:
                from urllib.parse import parse_qs
                qs = parse_qs(raw, keep_blank_values=True)
                data = {k: v[0] if isinstance(v, list) and len(v) == 1 else v for k, v in qs.items()}
                if isinstance(data.get("data"), str):
                    try: data = json.loads(data["data"])
                    except Exception: pass
            except Exception as e:
                parse_err = e
        if data is None and "text/plain" in ctype:
            try:
                data = json.loads(raw)
            except Exception as e:
                parse_err = e

        if data is None:
            log.error("Failed to parse request. CT=%s Raw=%r Err=%s", ctype, raw[:200], parse_err)
            self._set_common_headers(400)
            self.wfile.write(json.dumps({"ok": False, "error": f"Bad request body: {parse_err}"}).encode("utf-8"))
            return

        # route
        try:
            if path == "/email":
                self._handle_email(vault_path, data); return
            elif path == "/":
                self._handle_chat(vault_path, data); return
            elif path == "/web":
                self._handle_web(vault_path, data); return
            else:
                self._set_common_headers(404)
                self.wfile.write(b'{"ok": false, "error": "Unknown endpoint"}'); return
        except Exception as e:
            log.exception("POST handler failed")
            self._set_common_headers(500)
            self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode("utf-8"))

    # --- route handlers ---
    def _handle_email(self, vault_path: pathlib.Path, data: dict):
        subject = _coerce_text(data.get("subject") or "(no subject)")
        incoming = safe_project(data.get("project") or PROJECT_DEFAULT)
        project  = resolve_project_name(vault_path, incoming)

        dt = datetime.datetime.now()
        parts = [vault_path, PROJECTS_DIR, project] + EMAIL_CONTAINER
        base = pathlib.Path(*parts)
        if EMAIL_NESTING == "year":
            base = base / f"{dt.year:04d}"
        elif EMAIL_NESTING == "year_month":
            base = base / f"{dt.year:04d}" / f"{dt.month:02d}"
        base.mkdir(parents=True, exist_ok=True)

        name = f"{dt.date().isoformat()}-{slugify(subject)}.md"
        dest = (base / name).resolve()

        content = build_email_markdown(subject, project, data)
        log.info("[EMAIL] Project: %s (incoming=%s)", project, incoming)
        log.info("[EMAIL] Writing: %s", str(dest))
        dest.write_text(content, encoding="utf-8")
        log.info("[EMAIL] OK")

        rel = str(dest).replace(str(vault_path) + os.sep, "").replace("\\", "/")
        self._set_common_headers(200)
        self.wfile.write(json.dumps({"ok": True, "vault_rel": rel, "project": project}).encode("utf-8"))

    def _handle_chat(self, vault_path: pathlib.Path, data: dict):
        title    = _coerce_text(data.get("title") or "chat")
        incoming = safe_project(data.get("project") or PROJECT_DEFAULT)
        project  = resolve_project_name(vault_path, incoming)
        messages = data.get("messages") or []
        if isinstance(messages, str):
            try: messages = json.loads(messages)
            except Exception: messages = [{"role": "assistant", "text": messages}]
        norm = []
        for m in messages:
            if isinstance(m, dict):
                r = _coerce_text(m.get("role") or "assistant")
                t = _coerce_text(m.get("text") or "")
            else:
                r, t = "assistant", _coerce_text(m)
            norm.append({"role": r, "text": t})
        messages = norm

        dt = datetime.datetime.now()
        base = vault_path / PROJECTS_DIR / project / CHAT_CONTAINER
        if CHAT_NESTING == "year":
            base = base / f"{dt.year:04d}"
        elif CHAT_NESTING == "year_month":
            base = base / f"{dt.year:04d}" / f"{dt.month:02d}"
        base.mkdir(parents=True, exist_ok=True)

        name = f"{dt.date().isoformat()}-{slugify(title)}.md"
        dest = (base / name).resolve()

        content = build_chat_markdown(title, project, messages)
        log.info("[CHAT] Project: %s (incoming=%s)", project, incoming)
        log.info("[CHAT] Writing: %s", str(dest))
        log.info("[CHAT] Messages: %s", len(messages))
        dest.write_text(content, encoding="utf-8")
        log.info("[CHAT] OK")

        rel = str(dest).replace(str(vault_path) + os.sep, "").replace("\\", "/")
        self._set_common_headers(200)
        self.wfile.write(json.dumps({"ok": True, "vault_rel": rel, "project": project}).encode("utf-8"))

    def _handle_web(self, vault_path: pathlib.Path, data: dict):
        # ---- normalize inputs FIRST ----
        raw_proj = data.get("project")
        log.info("[WEB] RAW project=%r (%s)", raw_proj, type(raw_proj).__name__)
        incoming = safe_project(data.get("project") or PROJECT_DEFAULT)
        project  = resolve_project_name(vault_path, incoming)

        # coerce texty fields (guards against dict/list/event objects)
        mode     = _coerce_text(data.get("mode") or "readable").lower().strip()
        url_in   = _coerce_text(data.get("url") or "")
        title_in = _coerce_text(data.get("title") or "")
        html_in  = data.get("html") or ""
        tags     = data.get("tags") or []
        note     = _coerce_text(data.get("note") or "")

        if not isinstance(tags, list):  # be tolerant
            tags = [ _coerce_text(tags) ] if tags else []

        # fallback to known modes
        if mode not in ("link", "readable", "snapshot", "readable_html"):
            mode = "readable"

        # now it is safe to log
        log.info("[WEB] mode=%s url=%s html_in=%s title_in=%s project=%s",
                mode, (url_in or "")[:120], "yes" if bool(html_in) else "no", (title_in or "")[:120], incoming)

        # ---- common metadata ----
        dt = datetime.datetime.now()
        retrieved = dt.isoformat(timespec="seconds")

        # canonicalize URL (ok if empty)
        url_clean = strip_tracking_params(url_in) if url_in else ""
        canon = canonical_from_html(html_in) if html_in else ""
        canonical_url = canon or url_clean or url_in
        parsed = urlparse(canonical_url or url_in or "")
        domain = parsed.hostname or ""
        url_hash = sha1(canonical_url or url_in)

        proj_root = pathlib.Path(VAULT_DIR) / PROJECTS_DIR / project / WEB_ROOT
        proj_root.mkdir(parents=True, exist_ok=True)
            # Default paths per mode
        if mode == "link":
            base = proj_root / WEB_LINKS_DIR / f"{dt.year:04d}"
            base.mkdir(parents=True, exist_ok=True)
            slug = slugify(title_in or domain or "link")
            dest = base / f"{dt.date().isoformat()}-{slug}.md"
            meta = {
                "title": title_in or "",
                "url": url_in,
                "canonical_url": canonical_url,
                "domain": domain,
                "retrieved_at": retrieved,
                "project": project,
                "url_sha1": url_hash,
                "tags": tags,
                "note": note,
            }
            md = build_web_link_markdown(meta)
            log.info("[WEB-LINK] Project: %s (incoming=%s)", project, incoming)
            log.info("[WEB-LINK] Writing: %s", str(dest))
            dest.write_text(md, encoding="utf-8")
            rel = str(dest).replace(str(pathlib.Path(VAULT_DIR)) + os.sep, "").replace("\\", "/")
            self._set_common_headers(200)
            self.wfile.write(json.dumps({"ok": True, "vault_rel": rel, "project": project}).encode("utf-8"))
            return

        # readable / snapshot / readable_html
        # Clip folder with assets
        clips_base = proj_root / WEB_CLIPS_DIR / f"{dt.year:04d}"
        snap_base  = proj_root / WEB_SNAP_DIR / f"{dt.year:04d}"
        slug = slugify(title_in or domain or (parsed.path.strip("/").split("/")[-1] if parsed.path else "") or "page")

        # SNAPSHOT (browser-supplied HTML as-is)
        if mode == "snapshot":
            snap_base.mkdir(parents=True, exist_ok=True)
            html_out = snap_base / f"{dt.date().isoformat()}-{slug}.html"
            html_out.write_text(html_in or "", encoding="utf-8")

            # Sidecar index.md for metadata/backlink
            idx = snap_base / f"{dt.date().isoformat()}-{slug}.md"
            meta = {
                "mode": "snapshot",
                "title": title_in or "",
                "url": url_in,
                "canonical_url": canonical_url,
                "domain": domain,
                "retrieved_at": retrieved,
                "project": project,
                "url_sha1": url_hash,
                "content_sha1": sha1(html_in or ""),
                "tags": tags,
                "note": note,
            }
            md = build_web_link_markdown(meta).replace("mode: link", "mode: snapshot") + f"\n> **Snapshot file:** {html_out.name}\n"
            log.info("[WEB-SNAPSHOT] Project: %s (incoming=%s)", project, incoming)
            log.info("[WEB-SNAPSHOT] Writing HTML: %s", str(html_out))
            log.info("[WEB-SNAPSHOT] Writing index: %s", str(idx))
            idx.write_text(md, encoding="utf-8")
            rel = str(idx).replace(str(pathlib.Path(VAULT_DIR)) + os.sep, "").replace("\\", "/")
            self._set_common_headers(200)
            self.wfile.write(json.dumps({"ok": True, "vault_rel": rel, "project": project}).encode("utf-8"))
            return

        # READABLE: provided HTML from the browser, or fall back to link
        html_source = html_in
        warn = ""
        if not html_source:
            # No HTML → write a simple link note and exit fast
            base = proj_root / WEB_LINKS_DIR / f"{dt.year:04d}"
            base.mkdir(parents=True, exist_ok=True)
            dest = base / f"{dt.date().isoformat()}-{slug}.md"
            meta = {
                "mode": "link",
                "title": title_in or "",
                "url": url_in,
                "canonical_url": canonical_url,
                "domain": domain,
                "retrieved_at": retrieved,
                "project": project,
                "url_sha1": url_hash,
                "tags": (tags or []) + ["fallback"],
                "note": note,
            }
            md = build_web_link_markdown(meta)
            dest.write_text(md, encoding="utf-8")
            rel = str(dest).replace(str(pathlib.Path(VAULT_DIR)) + os.sep, "").replace("\\", "/")
            self._set_common_headers(200)
            self.wfile.write(json.dumps({"ok": True, "vault_rel": rel, "project": project, "fallback": True}).encode("utf-8"))
            return

        # Try readability right here (don’t depend on a global)
        content_html = ""
        title_used = title_in
        try:
            from readability import Document as _Doc
            doc = _Doc(html_source)
            title_used = title_used or (doc.short_title() or "")
            content_html = doc.summary(html_partial=True) or ""
        except Exception as e:
            warn = f"readability extraction failed: {e}"

        # Convert extracted HTML → Markdown if we have any
        content_md = ""
        if content_html and _md_from_html:
            try:
                content_md = _md_from_html(content_html)
            except Exception as e:
                warn = (warn + " | " if warn else "") + f"markdownify failed: {e}"

        # IMPORTANT: never dump raw HTML into markdown; keep it in page.html only
        if not content_md:
            if not warn:
                warn = "Saved full HTML to page.html (no markdown converter available)."

        # ---- Write to Clips/<YYYY>/<date>-slug with tiny index + sidecars ----
        clips_year = proj_root / WEB_CLIPS_DIR / f"{dt.year:04d}"
        clips_year.mkdir(parents=True, exist_ok=True)
        clip_dir = clips_year / f"{dt.date().isoformat()}-{slug}"
        clip_dir.mkdir(parents=True, exist_ok=True)

        # Sidecars
        (clip_dir / "page.html").write_text(html_source, encoding="utf-8")

        # readable.md: lightweight preview (or pointer) so opening is snappy
        preview_text = ""
        if not content_md and BeautifulSoup:
            try:
                preview_text = BeautifulSoup(html_source, "lxml").get_text("\n")[:2500].rstrip()
            except Exception:
                preview_text = ""

        if content_md:
            # Small/full markdown extract goes here; if you prefer a hard cap, add it.
            (clip_dir / "readable.md").write_text(content_md.replace("\x00",""), encoding="utf-8")
        else:
            (clip_dir / "readable.md").write_text(
                ("## Preview\n\n" + preview_text + "\n\n---\n") * bool(preview_text)
                + "Open **page.html** for the full content.\n",
                encoding="utf-8"
            )

        # Minimal index.md (no heavy YAML/body)
        idx = clip_dir / "index.md"
        meta_small = {
            "mode": "readable",
            "title": title_used or title_in or "",
            "url": url_in,
            "canonical_url": canonical_url,
            "domain": domain,
            "retrieved_at": retrieved,
            "project": project,
        }
        # If you use the minimal index builder:
        idx_md = build_web_clip_index_minimal(meta_small, excerpt=(note or preview_text)[:2500], warn=warn)
        idx.write_text(idx_md, encoding="utf-8")

        log.info("[WEB-READABLE] Wrote clip dir: %s", str(clip_dir))
        rel = str(idx).replace(str(pathlib.Path(VAULT_DIR)) + os.sep, "").replace("\\", "/")
        self._set_common_headers(200)
        self.wfile.write(json.dumps({"ok": True, "vault_rel": rel, "project": project}).encode("utf-8"))
        return


# ---------- Main ----------
def main():
    if not os.path.isdir(VAULT_DIR):
        log.error("VAULT_DIR does not exist: %s", VAULT_DIR)
        sys.exit(2)

    if not _acquire_lock():
        sys.exit(1)
    atexit.register(_release_lock)

    httpd = HTTPServer((HOST, PORT), Handler)
    log.info("Python exe    : %s", sys.executable)
    log.info("readability   : %s", READABILITY_INFO)
    log.info("bs4           : %s", BS4_INFO)
    log.info("markdownify   : %s", MDIFY_INFO)
    log.info("html2text     : %s", H2T_INFO)

    log.info("Listening on http://%s:%s  →  %s", HOST, PORT, VAULT_DIR)
    try:
        httpd.serve_forever()
    finally:
        log.info("Server exiting.")
        _release_lock()

if __name__ == "__main__":
    main()
