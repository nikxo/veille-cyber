"""Schéma du parcours de l'attaquant à travers l'infrastructure (PNG vertical, lisible sur téléphone).

Chaque nœud est une machine ou un système (icône + nom + note courte), chaque flèche porte le
numéro de l'étape de la chaîne d'attaque qu'elle représente et un libellé court.
Les détails restent dans le texte de l'article.

Ne bloque jamais la publication : en cas d'échec, `make_diagram` renvoie None.
"""
from pathlib import Path

TYPES = {"attaquant", "utilisateur", "messagerie", "application", "serveur", "passerelle",
         "poste", "postes", "annuaire", "cloud", "donnees", "inconnu"}

W = 1080
BG = (246, 247, 249)
TEXT = (28, 32, 40)
MUTED = (96, 104, 118)
ACCENT = (201, 100, 66)
TILE = (44, 56, 74)
TILE_ATT = (176, 52, 52)
WHITE = (255, 255, 255)
FONT_DIRS = ["/usr/share/fonts/opentype/inter", "/usr/share/fonts/truetype/inter"]


def _font(name, size):
    from PIL import ImageFont
    for d in FONT_DIRS:
        p = Path(d) / name
        if p.exists():
            return ImageFont.truetype(str(p), size)
    for fb in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
               "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if Path(fb).exists():
            return ImageFont.truetype(fb, size)
    return ImageFont.load_default(size=size)


def _wrap(draw, text, font, width):
    lines, line = [], ""
    for word in text.split():
        test = f"{line} {word}".strip()
        if draw.textlength(test, font=font) <= width:
            line = test
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


# ---------- icônes (dessinées en blanc dans une tuile de 120 px centrée en cx, cy) ----------

def _person(d, cx, cy, hood=False):
    d.ellipse([cx - 17, cy - 38, cx + 17, cy - 4], fill=WHITE)
    d.pieslice([cx - 36, cy + 2, cx + 36, cy + 70], 180, 360, fill=WHITE)
    if hood:  # capuche : contour de tête plus large, visage sombre
        d.ellipse([cx - 24, cy - 44, cx + 24, cy + 4], outline=WHITE, width=6)
        d.ellipse([cx - 11, cy - 30, cx + 11, cy - 10], fill=TILE_ATT)


def _monitor(d, cx, cy, s=1.0, width=5):
    w, h = 60 * s, 40 * s
    d.rounded_rectangle([cx - w / 2, cy - h / 2 - 8 * s, cx + w / 2, cy + h / 2 - 8 * s], radius=5 * s,
                        outline=WHITE, width=width)
    d.line([cx, cy + h / 2 - 8 * s, cx, cy + h / 2 + 6 * s], fill=WHITE, width=width)
    d.line([cx - 16 * s, cy + h / 2 + 6 * s, cx + 16 * s, cy + h / 2 + 6 * s], fill=WHITE, width=width)


def _server(d, cx, cy):
    for i in range(3):
        y = cy - 34 + i * 24
        d.rounded_rectangle([cx - 30, y, cx + 30, y + 18], radius=4, outline=WHITE, width=4)
        d.ellipse([cx + 14, y + 6, cx + 20, y + 12], fill=WHITE)


def _icon(d, kind, cx, cy):
    if kind == "attaquant":
        _person(d, cx, cy)
    elif kind == "utilisateur":
        _person(d, cx, cy)
    elif kind == "messagerie":
        d.rounded_rectangle([cx - 34, cy - 22, cx + 34, cy + 24], radius=5, outline=WHITE, width=5)
        d.line([cx - 32, cy - 19, cx, cy + 4, cx + 32, cy - 19], fill=WHITE, width=5, joint="curve")
    elif kind == "application":
        d.rounded_rectangle([cx - 34, cy - 28, cx + 34, cy + 28], radius=6, outline=WHITE, width=5)
        d.line([cx - 32, cy - 12, cx + 32, cy - 12], fill=WHITE, width=4)
        for i in range(3):
            d.ellipse([cx - 26 + i * 10, cy - 23, cx - 20 + i * 10, cy - 17], fill=WHITE)
    elif kind == "serveur":
        _server(d, cx, cy)
    elif kind == "passerelle":  # bouclier
        d.polygon([(cx, cy - 36), (cx + 30, cy - 24), (cx + 26, cy + 10), (cx, cy + 36),
                   (cx - 26, cy + 10), (cx - 30, cy - 24)], outline=WHITE, width=5)
        d.line([cx, cy - 30, cx, cy + 28], fill=WHITE, width=4)
    elif kind == "poste":
        _monitor(d, cx, cy + 6)
    elif kind == "postes":
        _monitor(d, cx - 20, cy - 14, 0.6, 4)
        _monitor(d, cx + 20, cy - 14, 0.6, 4)
        _monitor(d, cx, cy + 22, 0.6, 4)
    elif kind == "annuaire":  # un nœud central relié à trois autres
        d.ellipse([cx - 12, cy - 38, cx + 12, cy - 14], fill=WHITE)
        for dx in (-30, 0, 30):
            d.line([cx, cy - 18, cx + dx, cy + 14], fill=WHITE, width=4)
            d.ellipse([cx + dx - 10, cy + 12, cx + dx + 10, cy + 32], fill=WHITE)
    elif kind == "cloud":
        d.ellipse([cx - 36, cy - 6, cx - 4, cy + 22], fill=WHITE)
        d.ellipse([cx - 18, cy - 24, cx + 18, cy + 12], fill=WHITE)
        d.ellipse([cx + 2, cy - 10, cx + 36, cy + 22], fill=WHITE)
        d.rectangle([cx - 20, cy + 4, cx + 20, cy + 22], fill=WHITE)
    elif kind == "donnees":  # cylindre
        d.rectangle([cx - 28, cy - 22, cx + 28, cy + 22], fill=WHITE)
        d.ellipse([cx - 28, cy + 12, cx + 28, cy + 32], fill=WHITE)
        d.ellipse([cx - 28, cy - 32, cx + 28, cy - 12], fill=WHITE, outline=TILE, width=4)
        d.arc([cx - 28, cy - 8, cx + 28, cy + 12], 0, 180, fill=TILE, width=4)
    else:
        d.text((cx - 12, cy - 30), "?", font=_font("Inter-Bold.otf", 52), fill=WHITE)


def path_order(parcours):
    """Nœuds dans l'ordre du parcours (depuis l'attaquant), ou None si ce n'est pas une chaîne simple."""
    nodes = {n["id"]: n for n in parcours.get("noeuds", [])}
    nxt = {}
    for l in parcours.get("liens", []):
        if l["de"] in nxt:
            return None
        nxt[l["de"]] = l
    start = parcours["noeuds"][0]["id"] if parcours.get("noeuds") else None
    order, seen, cur = [], set(), start
    while cur is not None:
        if cur in seen or cur not in nodes:
            return None
        seen.add(cur)
        order.append((nodes[cur], nxt.get(cur)))
        cur = nxt[cur]["vers"] if cur in nxt else None
    return order if len(order) == len(nodes) else None


def make_diagram(story, out_dir):
    """Crée le schéma si besoin et renvoie son nom de fichier, ou None."""
    parcours = story.get("parcours")
    if not parcours:
        return None
    name = f"{story['id']}-v{story['version']}.png"
    path = Path(out_dir) / name
    if path.exists():
        return name
    try:
        from PIL import Image, ImageDraw
        order = path_order(parcours)
        if not order:
            return None
        f_head = _font("Inter-Bold.otf", 30)
        f_name = _font("Inter-Bold.otf", 36)
        f_note = _font("Inter-Regular.otf", 29)
        f_edge = _font("Inter-SemiBold.otf", 29)
        f_num = _font("Inter-Bold.otf", 24)
        probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))

        M, T = 56, 120                    # marge, taille de tuile
        tx = M + T + 32                   # début du texte des nœuds
        tw = W - M - tx
        ex = M + T // 2 + 36              # début du libellé des flèches
        ew = W - M - ex - 44

        rows = []
        for node, link in order:
            n_lines = _wrap(probe, node.get("nom", ""), f_name, tw)
            note = node.get("note", "")
            if node.get("etapes"):
                et = node["etapes"]
                label = f"étape {et[0]}" if len(et) == 1 else "étapes " + ", ".join(str(e) for e in et)
                note = (note + " " if note else "") + f"({label})"
            note_lines = _wrap(probe, note, f_note, tw) if note else []
            h = max(T, len(n_lines) * 44 + len(note_lines) * 38 + 8)
            e_lines = _wrap(probe, link["texte"], f_edge, ew) if link else []
            eh = max(110, len(e_lines) * 38 + 50) if link else 0
            rows.append((node, link, n_lines, note_lines, h, e_lines, eh))

        H = M + 56 + sum(r[4] + r[6] for r in rows) + M
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        d.text((M, M - 8), "PARCOURS DE L'ATTAQUANT", font=f_head, fill=ACCENT)

        y = M + 56
        for node, link, n_lines, note_lines, h, e_lines, eh in rows:
            ty0 = y + (h - T) // 2
            kind = node.get("type", "inconnu")
            d.rounded_rectangle([M, ty0, M + T, ty0 + T], radius=26,
                                fill=TILE_ATT if kind == "attaquant" else TILE)
            _icon(d, kind if kind in TYPES else "inconnu", M + T // 2, ty0 + T // 2)
            text_h = len(n_lines) * 44 + len(note_lines) * 38
            yy = y + (h - text_h) // 2
            for line in n_lines:
                d.text((tx, yy), line, font=f_name, fill=TEXT)
                yy += 44
            for line in note_lines:
                d.text((tx, yy + 2), line, font=f_note, fill=MUTED)
                yy += 38
            y += h
            if link:
                cx = M + T // 2
                d.line([cx, y + 12, cx, y + eh - 22], fill=ACCENT, width=6)
                d.polygon([(cx - 15, y + eh - 28), (cx + 15, y + eh - 28), (cx, y + eh - 8)], fill=ACCENT)
                # pastille du numéro d'étape + libellé
                by = y + (eh - len(e_lines) * 38) // 2 - 2
                d.ellipse([ex, by, ex + 36, by + 36], fill=ACCENT)
                num = str(link.get("etape", ""))
                d.text((ex + (36 - d.textlength(num, font=f_num)) / 2, by + 5), num, font=f_num, fill=WHITE)
                ly = by
                for line in e_lines:
                    d.text((ex + 48, ly), line, font=f_edge, fill=ACCENT)
                    ly += 38
                y += eh

        Path(out_dir).mkdir(parents=True, exist_ok=True)
        img.save(path, optimize=True)
        return name
    except Exception as exc:  # un schéma raté ne doit jamais empêcher la publication
        print(f"AVERTISSEMENT: schéma non généré pour {story.get('id')}: {exc}")
        return None


def prune(out_dir, keep):
    p = Path(out_dir)
    if p.exists():
        for f in p.glob("*.png"):
            if f.name not in keep:
                f.unlink()
