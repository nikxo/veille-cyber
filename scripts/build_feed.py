#!/usr/bin/env python3
"""Génère docs/feed.xml (RSS 2.0) et docs/index.html à partir de data/stories.json.

Bibliothèque standard uniquement. Sort en erreur (code 1) si stories.json est mal formé,
pour que la tâche planifiée ne publie jamais un flux cassé.
"""
import json
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import format_datetime
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORIES = ROOT / "data" / "stories.json"
DOCS = ROOT / "docs"
SITE_URL = "https://nikxo.github.io/veille-cyber"
MAX_ITEMS = 100

REQUIRED = ["id", "title", "created", "updated", "version", "resume", "vecteur", "chaine",
            "mitre", "cves", "acteurs", "cibles", "sources"]
NON_PRECISE = "Non précisé par les sources."


def fail(msg):
    print(f"ERREUR: {msg}", file=sys.stderr)
    sys.exit(1)


def parse_dt(value, field, sid):
    try:
        dt = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        fail(f"story {sid}: champ {field} invalide ({value!r}), format ISO 8601 attendu")
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def validate(stories):
    ids = set()
    for s in stories:
        sid = s.get("id", "?")
        for key in REQUIRED:
            if key not in s:
                fail(f"story {sid}: champ manquant {key}")
        if sid in ids:
            fail(f"story {sid}: id en double")
        ids.add(sid)
        if not s["sources"]:
            fail(f"story {sid}: aucune source (interdit)")
        for src in s["sources"]:
            for key in ("titre", "site", "url"):
                if not src.get(key):
                    fail(f"story {sid}: source sans {key}")
        for section in ("vecteur", "chaine"):
            for point in s[section]:
                if not point.get("texte") or not point.get("source"):
                    fail(f"story {sid}: un point de '{section}' n'a pas de texte ou de source")
        s["_created"] = parse_dt(s["created"], "created", sid)
        s["_updated"] = parse_dt(s["updated"], "updated", sid)


def points_html(points):
    if not points:
        return f"<p><em>{NON_PRECISE}</em></p>"
    items = "".join(f"<li>{escape(p['texte'])} <em>({escape(p['source'])})</em></li>" for p in points)
    return f"<ul>{items}</ul>"


def list_html(values):
    if not values:
        return f"<p><em>{NON_PRECISE}</em></p>"
    return "<ul>" + "".join(f"<li>{escape(v)}</li>" for v in values) + "</ul>"


def cves_html(cves):
    if not cves:
        return f"<p><em>Aucune CVE citée.</em></p>"
    links = ", ".join(
        f'<a href="https://www.cve.org/CVERecord?id={escape(c)}">{escape(c)}</a>' for c in cves)
    return f"<p>{links}</p>"


def story_html(s):
    sources = "".join(
        f'<li><a href="{escape(src["url"])}">{escape(src["titre"])}</a> ({escape(src["site"])}'
        + (f", {escape(src['date'][:10])}" if src.get("date") else "") + ")</li>"
        for src in s["sources"])
    parts = [
        f"<p>{escape(s['resume'])}</p>",
        "<h3>Comment les attaquants sont entrés</h3>", points_html(s["vecteur"]),
        "<h3>Déroulé de l'attaque</h3>", points_html(s["chaine"]),
        "<h3>Techniques MITRE ATT&amp;CK citées par les sources</h3>", list_html(s["mitre"]),
        "<h3>Vulnérabilités</h3>", cves_html(s["cves"]),
        "<h3>Attaquant</h3>", list_html(s["acteurs"]),
        "<h3>Victimes / cibles</h3>", list_html(s["cibles"]),
        f"<h3>Sources ({len(s['sources'])})</h3><ul>{sources}</ul>",
    ]
    if s["version"] > 1:
        parts.insert(0, f"<p><strong>Mise à jour n°{s['version'] - 1}</strong> : nouvelles sources ajoutées.</p>")
    return "".join(parts)


def build_rss(stories, now):
    rss = ET.Element("rss", version="2.0", attrib={"xmlns:atom": "http://www.w3.org/2005/Atom"})
    ch = ET.SubElement(rss, "channel")
    ET.SubElement(ch, "title").text = "Veille cyber : attaques et vecteurs d'intrusion"
    ET.SubElement(ch, "link").text = SITE_URL + "/"
    ET.SubElement(ch, "description").text = (
        "Synthèses en français des attaques récentes, regroupées par sujet, à partir de "
        "sources publiques (éditeurs de sécurité, CERT, presse spécialisée). Générées par IA.")
    ET.SubElement(ch, "language").text = "fr-fr"
    ET.SubElement(ch, "lastBuildDate").text = format_datetime(now)
    ET.SubElement(ch, "ttl").text = "60"
    ET.SubElement(ch, "atom:link", href=SITE_URL + "/feed.xml", rel="self", type="application/rss+xml")
    for s in stories:
        it = ET.SubElement(ch, "item")
        prefix = "[MàJ] " if s["version"] > 1 else ""
        ET.SubElement(it, "title").text = prefix + s["title"]
        ET.SubElement(it, "link").text = s["sources"][0]["url"]
        ET.SubElement(it, "guid", isPermaLink="false").text = f"{s['id']}-v{s['version']}"
        ET.SubElement(it, "pubDate").text = format_datetime(s["_updated"])
        ET.SubElement(it, "description").text = story_html(s)
        for c in s["cves"]:
            ET.SubElement(it, "category").text = c
    ET.indent(rss)
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(rss, encoding="utf-8")


def build_index(stories, now):
    rows = "".join(
        f'<li><a href="{escape(s["sources"][0]["url"])}">{escape(s["title"])}</a>'
        f' <small>{s["_updated"].strftime("%d/%m/%Y %H:%M")} UTC, {len(s["sources"])} source(s)</small></li>'
        for s in stories[:30])
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Veille cyber</title>
<link rel="alternate" type="application/rss+xml" title="Veille cyber" href="feed.xml">
<style>body{{font-family:system-ui,sans-serif;max-width:760px;margin:2rem auto;padding:0 16px;line-height:1.5}}
small{{color:#666}}li{{margin:.4rem 0}}code{{background:#eee;padding:2px 4px}}</style></head>
<body><h1>Veille cyber</h1>
<p>Flux RSS : <a href="feed.xml"><code>{SITE_URL}/feed.xml</code></a></p>
<p>Dernière génération : {now.strftime("%d/%m/%Y %H:%M")} UTC</p>
<h2>Derniers sujets</h2><ul>{rows or "<li>Aucun sujet pour l'instant.</li>"}</ul>
</body></html>
"""


def main():
    data = json.loads(STORIES.read_text(encoding="utf-8")) if STORIES.exists() else {"stories": []}
    stories = data.get("stories")
    if not isinstance(stories, list):
        fail("data/stories.json doit contenir {\"stories\": [...]}")
    validate(stories)
    stories.sort(key=lambda s: s["_updated"], reverse=True)
    stories = stories[:MAX_ITEMS]
    now = datetime.now(timezone.utc)
    DOCS.mkdir(exist_ok=True)
    xml_bytes = build_rss(stories, now)
    ET.fromstring(xml_bytes)  # vérifie que le XML produit est bien formé
    (DOCS / "feed.xml").write_bytes(xml_bytes)
    (DOCS / "index.html").write_text(build_index(stories, now), encoding="utf-8")
    (DOCS / ".nojekyll").touch()
    print(f"feed.xml généré : {len(stories)} sujets")


if __name__ == "__main__":
    main()
