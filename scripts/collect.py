#!/usr/bin/env python3
"""Collecte des flux RSS/Atom (exécuté par GitHub Actions, à la demande de la routine Claude).

- Lit feeds.json
- Pour chaque nouvel article (jamais vu), écrit un fichier data/inbox/<id>.json
- Tient à jour data/seen.json (articles déjà vus) et data/health.json (état de chaque flux)

Bibliothèque standard uniquement, aucune IA : ce script est déterministe.
La synthèse est faite ensuite par la routine Claude, qui lit data/inbox/.
"""
import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
INBOX = DATA / "inbox"
SEEN_FILE = DATA / "seen.json"
HEALTH_FILE = DATA / "health.json"

MAX_AGE_HOURS = 72          # on ignore les articles publiés il y a plus de 72 h
BOOTSTRAP_AGE_HOURS = 24    # au tout premier passage d'un flux, seulement les 24 dernières heures
SEEN_RETENTION_DAYS = 45
USER_AGENT = "Mozilla/5.0 (compatible; veille-cyber/1.0; +https://github.com/nikxo/veille-cyber)"
SPONSORED = re.compile(r"\b(sponsored|webinar|livestream|podcast)\b", re.I)
ATOM = "{http://www.w3.org/2005/Atom}"
DC = "{http://purl.org/dc/elements/1.1/}"


def now_utc():
    return datetime.now(timezone.utc)


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def normalize_link(link):
    link = (link or "").strip()
    link = re.sub(r"[?#].*$", "", link)  # retire les paramètres de suivi
    return link.rstrip("/")


def item_id(link):
    return hashlib.sha1(normalize_link(link).encode("utf-8")).hexdigest()[:16]


def clean(text, limit=800):
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = unescape(re.sub(r"\s+", " ", text)).strip()
    return text[:limit]


def parse_date(value):
    if not value:
        return None
    value = value.strip()
    try:
        dt = parsedate_to_datetime(value)  # format RSS (RFC 822)
    except (TypeError, ValueError, IndexError):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))  # format Atom (ISO 8601)
        except ValueError:
            return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def text_of(el, *tags):
    for tag in tags:
        child = el.find(tag)
        if child is not None:
            value = "".join(child.itertext()).strip()
            if value:
                return value
    return ""


def parse_xml(content):
    """Retourne une liste de dicts {title, link, date, summary, author}."""
    root = ET.fromstring(content)
    entries = []
    for item in root.iter("item"):  # RSS 2.0 / RSS 1.0 sans namespace
        entries.append({
            "title": text_of(item, "title"),
            "link": text_of(item, "link") or text_of(item, "guid"),
            "date": parse_date(text_of(item, "pubDate", f"{DC}date")),
            "summary": text_of(item, "description"),
            "author": text_of(item, "author", f"{DC}creator"),
        })
    for entry in root.iter(f"{ATOM}entry"):  # Atom
        link = ""
        for l in entry.findall(f"{ATOM}link"):
            if l.get("rel", "alternate") == "alternate":
                link = l.get("href", "")
                break
        author = entry.find(f"{ATOM}author")
        entries.append({
            "title": text_of(entry, f"{ATOM}title"),
            "link": link,
            "date": parse_date(text_of(entry, f"{ATOM}published", f"{ATOM}updated")),
            "summary": text_of(entry, f"{ATOM}summary", f"{ATOM}content"),
            "author": text_of(author, f"{ATOM}name") if author is not None else "",
        })
    return entries


def parse_regex(content):
    """Secours si le XML est mal formé (entités HTML non déclarées, etc.)."""
    text = content.decode("utf-8", errors="replace")
    entries = []
    for block in re.findall(r"<item\b.*?</item>", text, re.S | re.I):
        def grab(tag):
            m = re.search(rf"<{tag}\b[^>]*>(.*?)</{tag}>", block, re.S | re.I)
            if not m:
                return ""
            return re.sub(r"^<!\[CDATA\[|\]\]>$", "", m.group(1).strip(), flags=re.S).strip()
        entries.append({
            "title": grab("title"), "link": grab("link") or grab("guid"),
            "date": parse_date(grab("pubDate") or grab("dc:date")),
            "summary": grab("description"), "author": grab("author") or grab("dc:creator"),
        })
    return entries


META_IMAGE_RE = re.compile(
    r'<meta[^>]+(?:property|name)=["\'](?:og:image(?::secure_url)?|twitter:image)["\'][^>]*>', re.I)
CONTENT_RE = re.compile(r'content=["\']([^"\']+)["\']', re.I)


def preview_image(url):
    """URL de l'image d'aperçu de l'article (balise og:image ou twitter:image), ou None."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
        with urllib.request.urlopen(req, timeout=12) as resp:
            head = resp.read(400_000).decode("utf-8", errors="replace")
    except Exception:
        return None
    for tag in META_IMAGE_RE.findall(head):
        m = CONTENT_RE.search(tag)
        if m:
            img = unescape(m.group(1)).strip()
            if img.startswith("//"):
                img = "https:" + img
            if img.startswith("https://"):
                return img
    return None


def fetch(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
    })
    with urllib.request.urlopen(req, timeout=25) as resp:
        return resp.status, resp.read()


def main():
    config = load_json(ROOT / "feeds.json", {"feeds": []})
    seen = load_json(SEEN_FILE, {})
    health = {}
    INBOX.mkdir(parents=True, exist_ok=True)
    known_sources = {v.get("source") for v in seen.values()}
    added = 0

    for feed in config["feeds"]:
        if not feed.get("enabled", True):
            continue
        name = feed["name"]
        status = {"url": feed["url"], "checked_at": now_utc().isoformat(timespec="seconds")}
        try:
            code, content = fetch(feed["url"])
            status["http"] = code
        except urllib.error.HTTPError as exc:
            status.update(ok=False, http=exc.code, error=f"HTTP {exc.code}")
            health[name] = status
            continue
        except Exception as exc:  # réseau, timeout, TLS...
            status.update(ok=False, error=f"{type(exc).__name__}: {exc}")
            health[name] = status
            continue
        try:
            entries = parse_xml(content)
            status["parser"] = "xml"
        except ET.ParseError:
            entries = parse_regex(content)
            status["parser"] = "regex"
        if not entries:
            status.update(ok=False, error="aucun article trouvé (page HTML au lieu d'un flux ?)")
            health[name] = status
            continue

        bootstrap = name not in known_sources
        cutoff = now_utc() - timedelta(hours=BOOTSTRAP_AGE_HOURS if bootstrap else MAX_AGE_HOURS)
        new_here = 0
        for entry in entries:
            link = clean(entry["link"], 1000)
            if not link.startswith("http"):
                continue
            iid = item_id(link)
            if iid in seen:
                continue
            seen[iid] = {"source": name, "seen_at": now_utc().isoformat(timespec="seconds")}
            if entry["date"] and entry["date"] < cutoff:
                continue
            if SPONSORED.search(entry["title"]) or "sponsored" in entry["author"].lower():
                continue
            item = {
                "id": iid,
                "source": name,
                "source_type": feed.get("type"),
                "lang": feed.get("lang"),
                "title": clean(entry["title"], 300),
                "link": link,
                "published": entry["date"].isoformat(timespec="seconds") if entry["date"] else None,
                "feed_summary": clean(entry["summary"]),
                "image": preview_image(link),
                "collected_at": now_utc().isoformat(timespec="seconds"),
            }
            save_json(INBOX / f"{iid}.json", item)
            new_here += 1
            added += 1
        status.update(ok=True, entries=len(entries), new=new_here, bootstrap=bootstrap)
        health[name] = status

    limit = now_utc() - timedelta(days=SEEN_RETENTION_DAYS)
    seen = {k: v for k, v in seen.items() if datetime.fromisoformat(v["seen_at"]) >= limit}

    save_json(SEEN_FILE, seen)
    save_json(HEALTH_FILE, health)
    failed = [n for n, s in health.items() if not s.get("ok")]
    print(f"Nouveaux articles: {added} | flux OK: {len(health) - len(failed)} | en échec: {len(failed)}")
    for n in failed:
        print(f"  ECHEC {n}: {health[n].get('error')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
