#!/usr/bin/env python3
"""Génère docs/veille.xml (RSS 2.0) et docs/index.html à partir de data/stories.json.

Bibliothèque standard uniquement. Sort en erreur (code 1) si stories.json ne respecte pas
le format (schéma 2, voir ROUTINE.md), pour que la routine ne publie jamais un flux cassé.

Contrôles :
- chaque référence [n] renvoie à une source existante, chaque source est citée au moins une fois ;
- chaque texte (résumé, vecteur, étapes, CVE, techniques, acteurs, cibles) porte au moins une référence ;
- chaque sigle employé dans les textes figure dans le glossaire `abreviations` ;
- aucun tiret cadratin.
"""
import json
import re
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
SCHEMA = 3
# Limites de longueur (en mots, références [n] non comptées)
MAX_WORDS = {"resume": 45, "etape_titre": 4, "etape_texte": 30, "limites": 35,
             "cve": 30, "mitre": 20, "acteur": 25, "cible": 25, "definition": 15}
MIN_STEPS, MAX_STEPS = 1, 6

REF_RE = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")
# Un sigle : au moins deux caractères, majuscules et chiffres, sans minuscule (RCE, BYOVD, C2, AD).
ACRONYM_RE = re.compile(r"(?<![\w-])(?=[A-Z0-9]*[A-Z][A-Z0-9]*[A-Z0-9])[A-Z][A-Z0-9]+(?![\w-])")
IGNORED_ACRONYMS = {"MITRE", "ATT", "CK"}  # "MITRE ATT&CK" est expliqué dans l'en-tête de section
NON_PRECISE = "Non précisé par les sources."

errors = []


def err(sid, msg):
    errors.append(f"story {sid}: {msg}")


def parse_dt(value, field, sid):
    try:
        dt = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        err(sid, f"champ {field} invalide ({value!r}), format ISO 8601 attendu")
        return datetime.now(timezone.utc)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def refs_in(text):
    found = []
    for group in REF_RE.findall(text):
        found += [int(n) for n in re.split(r"\s*,\s*", group)]
    return found


def story_texts(s):
    """(libellé, texte) de chaque champ rédigé qui doit être sourcé."""
    texts = [("resume", s["resume"])]
    texts += [(f"chaine[{i}]", e.get("texte", "")) for i, e in enumerate(s["chaine"], 1)]
    if s["limites"]:
        texts.append(("limites", s["limites"]))
    texts += [(f"cves[{c.get('id')}]", c.get("explication", "")) for c in s["cves"]]
    texts += [(f"mitre[{i}]", t) for i, t in enumerate(s["mitre"], 1)]
    texts += [(f"acteurs[{i}]", t) for i, t in enumerate(s["acteurs"], 1)]
    texts += [(f"cibles[{i}]", t) for i, t in enumerate(s["cibles"], 1)]
    return texts


def validate(stories):
    ids = set()
    required = {"schema": int, "id": str, "title": str, "created": str, "updated": str, "version": int,
                "resume": str, "chaine": list, "limites": str, "cves": list, "mitre": list,
                "acteurs": list, "cibles": list, "abreviations": list, "sources": list}
    for s in stories:
        sid = s.get("id", "?")
        missing = [k for k, t in required.items() if not isinstance(s.get(k), t)]
        if missing:
            err(sid, f"champs manquants ou de mauvais type : {', '.join(missing)}")
            continue
        if s["schema"] != SCHEMA:
            err(sid, f"schema {s['schema']} au lieu de {SCHEMA} (sujet à réécrire au nouveau format)")
        if sid in ids:
            err(sid, "id en double")
        ids.add(sid)
        if not s["resume"].strip():
            err(sid, "résumé vide")
        if not s["sources"]:
            err(sid, "aucune source (interdit)")
        for i, src in enumerate(s["sources"], 1):
            for key in ("titre", "site", "url"):
                if not src.get(key):
                    err(sid, f"source [{i}] sans {key}")
        for c in s["cves"]:
            if not re.fullmatch(r"CVE-\d{4}-\d{4,}", c.get("id", "")):
                err(sid, f"identifiant CVE invalide : {c.get('id')!r}")
            if not c.get("explication", "").strip():
                err(sid, f"{c.get('id')} sans explication")
        for a in s["abreviations"]:
            if not a.get("sigle") or not a.get("definition"):
                err(sid, "entrée du glossaire sans sigle ou sans définition")

        def too_long(label, text, key):
            n = len(REF_RE.sub(" ", text).split())
            if n > MAX_WORDS[key]:
                err(sid, f"{label} trop long : {n} mots (maximum {MAX_WORDS[key]})")
        too_long("resume", s["resume"], "resume")
        if not MIN_STEPS <= len(s["chaine"]) <= MAX_STEPS:
            err(sid, f"chaine : {len(s['chaine'])} étapes (entre {MIN_STEPS} et {MAX_STEPS} attendues)")
        for i, e in enumerate(s["chaine"], 1):
            if not e.get("etape") or not e.get("texte"):
                err(sid, f"chaine[{i}] : champs 'etape' et 'texte' obligatoires")
                continue
            too_long(f"chaine[{i}].etape", e["etape"], "etape_titre")
            too_long(f"chaine[{i}].texte", e["texte"], "etape_texte")
        if s["limites"]:
            too_long("limites", s["limites"], "limites")
        for c in s["cves"]:
            too_long(f"cves[{c.get('id')}]", c.get("explication", ""), "cve")
        for i, x in enumerate(s["mitre"], 1):
            too_long(f"mitre[{i}]", x, "mitre")
        for i, x in enumerate(s["acteurs"], 1):
            too_long(f"acteurs[{i}]", x, "acteur")
        for i, x in enumerate(s["cibles"], 1):
            too_long(f"cibles[{i}]", x, "cible")
        for a in s["abreviations"]:
            too_long(f"abreviations[{a.get('sigle')}]", a.get("definition", ""), "definition")

        n_sources = len(s["sources"])
        cited = set()
        texts = story_texts(s) + [("title", s["title"])]
        texts += [(f"title_etape[{i}]", e.get("etape", "")) for i, e in enumerate(s["chaine"], 1)]
        for label, text in texts:
            if "—" in text:
                err(sid, f"{label} : tiret cadratin interdit")
            if label == "title" or label.startswith("title_etape"):
                continue
            refs = refs_in(text)
            if not refs:
                err(sid, f"{label} : aucune référence [n]")
            for n in refs:
                if not 1 <= n <= n_sources:
                    err(sid, f"{label} : référence [{n}] inexistante ({n_sources} sources)")
            cited.update(refs)
        for n in range(1, n_sources + 1):
            if n not in cited:
                err(sid, f"source [{n}] jamais citée dans le texte")

        glossary = set()
        for a in s["abreviations"]:
            glossary.update(ACRONYM_RE.findall(a.get("sigle", "")))
        site_words = set(ACRONYM_RE.findall(" ".join(src.get("site", "") for src in s["sources"])))
        used = set()
        for label, text in texts:
            text = re.sub(r"CVE-\d{4}-\d+", " ", text)
            text = re.sub(r"\bT\d{4}(?:\.\d{3})?\b", " ", text)
            used.update(ACRONYM_RE.findall(REF_RE.sub(" ", text)))
        used.discard("CVE")  # sigle expliqué dans l'en-tête de section
        missing_gloss = sorted(used - glossary - site_words - IGNORED_ACRONYMS)
        if missing_gloss:
            err(sid, f"sigles absents du glossaire 'abreviations' : {', '.join(missing_gloss)}")

        s["_created"] = parse_dt(s["created"], "created", sid)
        s["_updated"] = parse_dt(s["updated"], "updated", sid)


def linkify(text, sources):
    """Échappe le texte et transforme [1] ou [1, 2] en liens vers les sources."""
    out, last = [], 0
    for m in REF_RE.finditer(text):
        out.append(escape(text[last:m.start()]))
        links = []
        for n in (int(x) for x in re.split(r"\s*,\s*", m.group(1))):
            url = escape(sources[n - 1]["url"]) if 1 <= n <= len(sources) else "#"
            links.append(f'<a href="{url}">{n}</a>')
        out.append("[" + ", ".join(links) + "]")
        last = m.end()
    out.append(escape(text[last:]))
    return "".join(out)


def story_html(s):
    src = s["sources"]
    L = lambda t: linkify(t, src)
    parts = []
    if s["version"] > 1:
        parts.append(f"<p><strong>Mise à jour n°{s['version'] - 1}</strong> : nouvelles informations ou sources ajoutées.</p>")
    parts.append(f"<p>{L(s['resume'])}</p>")

    parts.append("<h3>Chaîne d'attaque</h3><ol>")
    parts += [f"<li><strong>{escape(e['etape'])}</strong> : {L(e['texte'])}</li>" for e in s["chaine"]]
    parts.append("</ol>")
    if s["limites"]:
        parts.append(f"<p><em>{L(s['limites'])}</em></p>")

    if s["cves"]:
        parts.append("<h3>Vulnérabilités exploitées (CVE, identifiants publics de failles)</h3><ul>")
        for c in s["cves"]:
            cid = escape(c["id"])
            parts.append(f'<li><a href="https://www.cve.org/CVERecord?id={cid}"><strong>{cid}</strong></a> : {L(c["explication"])}</li>')
        parts.append("</ul>")

    if s["mitre"]:
        parts.append("<h3>Techniques MITRE ATT&amp;CK citées (référentiel des techniques d'attaque)</h3><ul>")
        parts += [f"<li>{L(t)}</li>" for t in s["mitre"]]
        parts.append("</ul>")

    parts.append("<h3>Attaquant</h3>")
    parts.append("<ul>" + "".join(f"<li>{L(t)}</li>" for t in s["acteurs"]) + "</ul>"
                 if s["acteurs"] else f"<p><em>{NON_PRECISE}</em></p>")
    parts.append("<h3>Victimes et cibles</h3>")
    parts.append("<ul>" + "".join(f"<li>{L(t)}</li>" for t in s["cibles"]) + "</ul>"
                 if s["cibles"] else f"<p><em>{NON_PRECISE}</em></p>")

    if s["abreviations"]:
        parts.append("<h3>Abréviations</h3><ul>")
        for a in sorted(s["abreviations"], key=lambda a: a["sigle"].lower()):
            parts.append(f"<li><strong>{escape(a['sigle'])}</strong> : {escape(a['definition'])}</li>")
        parts.append("</ul>")

    parts.append("<h3>Sources</h3><ol>")
    for item in src:
        date = f", {escape(item['date'][:10])}" if item.get("date") else ""
        parts.append(f'<li><a href="{escape(item["url"])}">{escape(item["titre"])}</a> ({escape(item["site"])}{date})</li>')
    parts.append("</ol>")
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
    ET.SubElement(ch, "atom:link", href=SITE_URL + "/veille.xml", rel="self", type="application/rss+xml")
    for s in stories:
        it = ET.SubElement(ch, "item")
        prefix = "[MàJ] " if s["version"] > 1 else ""
        ET.SubElement(it, "title").text = prefix + s["title"]
        ET.SubElement(it, "link").text = s["sources"][0]["url"]
        ET.SubElement(it, "guid", isPermaLink="false").text = s["id"]  # stable : ne change jamais
        ET.SubElement(it, "pubDate").text = format_datetime(s["_updated"])
        ET.SubElement(it, "description").text = story_html(s)
        for c in s["cves"]:
            ET.SubElement(it, "category").text = c["id"]
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
<link rel="alternate" type="application/rss+xml" title="Veille cyber" href="veille.xml">
<style>body{{font-family:system-ui,sans-serif;max-width:760px;margin:2rem auto;padding:0 16px;line-height:1.5}}
small{{color:#666}}li{{margin:.4rem 0}}code{{background:#eee;padding:2px 4px}}</style></head>
<body><h1>Veille cyber</h1>
<p>Flux RSS : <a href="veille.xml"><code>{SITE_URL}/veille.xml</code></a></p>
<p>Dernière génération : {now.strftime("%d/%m/%Y %H:%M")} UTC</p>
<h2>Derniers sujets</h2><ul>{rows or "<li>Aucun sujet pour l'instant.</li>"}</ul>
</body></html>
"""


def main():
    data = json.loads(STORIES.read_text(encoding="utf-8")) if STORIES.exists() else {"stories": []}
    stories = data.get("stories")
    if not isinstance(stories, list):
        print("ERREUR: data/stories.json doit contenir {\"stories\": [...]}", file=sys.stderr)
        sys.exit(1)
    validate(stories)
    if errors:
        print(f"ERREUR: {len(errors)} problème(s), flux NON généré :", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)
    stories.sort(key=lambda s: s["_updated"], reverse=True)
    stories = stories[:MAX_ITEMS]
    now = datetime.now(timezone.utc)
    DOCS.mkdir(exist_ok=True)
    xml_bytes = build_rss(stories, now)
    ET.fromstring(xml_bytes)  # vérifie que le XML produit est bien formé
    (DOCS / "veille.xml").write_bytes(xml_bytes)
    (DOCS / "index.html").write_text(build_index(stories, now), encoding="utf-8")
    (DOCS / ".nojekyll").touch()
    print(f"veille.xml généré : {len(stories)} sujets")


if __name__ == "__main__":
    main()
