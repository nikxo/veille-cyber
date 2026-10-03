"""Schéma réseau de l'attaque : machines placées par zone, liaisons numérotées, légende.

Zones (colonnes, de gauche à droite) :
  internet  : l'attaquant et les services externes qu'il utilise
  expose    : systèmes de la victime exposés sur Internet (seulement si une source le dit)
  victime   : réseau et systèmes de la victime
Chaque lien porte le numéro de l'étape de la chaîne d'attaque ; la légende reprend son libellé.
Ne bloque jamais la publication : en cas d'échec, `make_diagram` renvoie None.
"""
import math
from pathlib import Path

TYPES = {"attaquant", "utilisateur", "messagerie", "application", "serveur", "passerelle",
         "poste", "postes", "annuaire", "cloud", "donnees", "inconnu"}
ZONES = [("internet", "INTERNET"), ("expose", "EXPOSÉ SUR INTERNET"), ("victime", "RÉSEAU DE LA VICTIME")]
ZONE_IDS = {z for z, _ in ZONES}

W = 1200
BG = (246, 247, 249)
ZONE_BG = {"internet": (236, 238, 242), "expose": (250, 238, 230), "victime": (230, 238, 246)}
ZONE_FG = {"internet": (96, 104, 118), "expose": (176, 92, 56), "victime": (52, 86, 128)}
TEXT = (28, 32, 40)
MUTED = (96, 104, 118)
ACCENT = (201, 100, 66)
TILE = (44, 56, 74)
TILE_ATT = (176, 52, 52)
WHITE = (255, 255, 255)
FONT_DIRS = ["/usr/share/fonts/opentype/inter", "/usr/share/fonts/truetype/inter"]

T = 96          # taille d'une tuile d'icône
CELL_W = 250    # largeur d'une cellule de nœud
CELL_H = 340    # hauteur d'une cellule de nœud


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


def _wrap(draw, text, font, width, max_lines=3):
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
    return lines[:max_lines]


# ---------------- icônes, dessinées en blanc au centre (cx, cy) d'une tuile ----------------

def _person(d, cx, cy):
    d.ellipse([cx - 15, cy - 32, cx + 15, cy - 2], fill=WHITE)
    d.pieslice([cx - 31, cy + 2, cx + 31, cy + 60], 180, 360, fill=WHITE)


def _monitor(d, cx, cy, s=1.0, width=5):
    w, h = 52 * s, 34 * s
    d.rounded_rectangle([cx - w / 2, cy - h / 2 - 7 * s, cx + w / 2, cy + h / 2 - 7 * s], radius=4 * s,
                        outline=WHITE, width=width)
    d.line([cx, cy + h / 2 - 7 * s, cx, cy + h / 2 + 5 * s], fill=WHITE, width=width)
    d.line([cx - 14 * s, cy + h / 2 + 5 * s, cx + 14 * s, cy + h / 2 + 5 * s], fill=WHITE, width=width)


def _icon(d, kind, cx, cy):
    if kind in ("attaquant", "utilisateur"):
        _person(d, cx, cy)
    elif kind == "messagerie":
        d.rounded_rectangle([cx - 29, cy - 19, cx + 29, cy + 21], radius=4, outline=WHITE, width=5)
        d.line([cx - 27, cy - 16, cx, cy + 4, cx + 27, cy - 16], fill=WHITE, width=5, joint="curve")
    elif kind == "application":
        d.rounded_rectangle([cx - 29, cy - 24, cx + 29, cy + 24], radius=5, outline=WHITE, width=5)
        d.line([cx - 27, cy - 10, cx + 27, cy - 10], fill=WHITE, width=4)
        for i in range(3):
            d.ellipse([cx - 22 + i * 9, cy - 20, cx - 17 + i * 9, cy - 15], fill=WHITE)
    elif kind == "serveur":
        for i in range(3):
            y = cy - 29 + i * 21
            d.rounded_rectangle([cx - 26, y, cx + 26, y + 15], radius=3, outline=WHITE, width=4)
            d.ellipse([cx + 12, y + 5, cx + 17, y + 10], fill=WHITE)
    elif kind == "passerelle":  # bouclier
        d.polygon([(cx, cy - 31), (cx + 26, cy - 21), (cx + 22, cy + 9), (cx, cy + 31),
                   (cx - 22, cy + 9), (cx - 26, cy - 21)], outline=WHITE, width=5)
        d.line([cx, cy - 25, cx, cy + 24], fill=WHITE, width=4)
    elif kind == "poste":
        _monitor(d, cx, cy + 5)
    elif kind == "postes":
        _monitor(d, cx - 17, cy - 12, 0.55, 4)
        _monitor(d, cx + 17, cy - 12, 0.55, 4)
        _monitor(d, cx, cy + 19, 0.55, 4)
    elif kind == "annuaire":
        d.ellipse([cx - 10, cy - 32, cx + 10, cy - 12], fill=WHITE)
        for dx in (-26, 0, 26):
            d.line([cx, cy - 16, cx + dx, cy + 12], fill=WHITE, width=4)
            d.ellipse([cx + dx - 9, cy + 10, cx + dx + 9, cy + 28], fill=WHITE)
    elif kind == "cloud":
        d.ellipse([cx - 31, cy - 5, cx - 3, cy + 19], fill=WHITE)
        d.ellipse([cx - 15, cy - 21, cx + 15, cy + 9], fill=WHITE)
        d.ellipse([cx + 2, cy - 8, cx + 31, cy + 19], fill=WHITE)
        d.rectangle([cx - 17, cy + 4, cx + 17, cy + 19], fill=WHITE)
    elif kind == "donnees":
        d.rectangle([cx - 24, cy - 19, cx + 24, cy + 19], fill=WHITE)
        d.ellipse([cx - 24, cy + 10, cx + 24, cy + 28], fill=WHITE)
        d.ellipse([cx - 24, cy - 28, cx + 24, cy - 10], fill=WHITE, outline=TILE, width=4)
        d.arc([cx - 24, cy - 7, cx + 24, cy + 11], 0, 180, fill=TILE, width=4)
    else:
        d.text((cx - 11, cy - 28), "?", font=_font("Inter-Bold.otf", 46), fill=WHITE)


# ---------------- mise en page ----------------

def _layout(nodes):
    """Position (x, y du centre de la tuile) de chaque nœud, colonnes de zones et hauteur utile."""
    present = [z for z, _ in ZONES if any(n.get("zone") == z for n in nodes)]
    weights = {"internet": 1, "expose": 1, "victime": 2}
    total = sum(weights[z] for z in present)
    M, GAP = 40, 24
    usable = W - 2 * M - GAP * (len(present) - 1)
    cols, x = {}, M
    for z in present:
        w = usable * weights[z] / total
        cols[z] = (x, x + w)
        x += w + GAP
    pos, zone_rows = {}, {}
    for z in present:
        zn = [n for n in nodes if n.get("zone") == z]
        x0, x1 = cols[z]
        ncols = max(1, min(len(zn), int((x1 - x0) // CELL_W)))
        rows = math.ceil(len(zn) / ncols)
        zone_rows[z] = rows
        for i, n in enumerate(zn):
            r, c = divmod(i, ncols)
            in_row = min(ncols, len(zn) - r * ncols)
            cw = (x1 - x0) / in_row
            pos[n["id"]] = (x0 + cw * (c + 0.5), r)
    max_rows = max(zone_rows.values())
    top = 110
    content_h = max_rows * CELL_H
    for z in present:  # centre verticalement les nœuds de chaque zone
        offset = (content_h - zone_rows[z] * CELL_H) / 2
        for n in nodes:
            if n.get("zone") == z:
                x, r = pos[n["id"]]
                pos[n["id"]] = (x, top + offset + r * CELL_H + 70)
    return present, cols, pos, top, content_h


def _exit(box, cx, cy, ux, uy):
    """Distance depuis (cx, cy) jusqu'au bord de la boîte, dans la direction (ux, uy)."""
    x0, y0, x1, y1 = box
    ts = []
    if ux > 1e-9:
        ts.append((x1 - cx) / ux)
    if ux < -1e-9:
        ts.append((x0 - cx) / ux)
    if uy > 1e-9:
        ts.append((y1 - cy) / uy)
    if uy < -1e-9:
        ts.append((y0 - cy) / uy)
    return min(ts) if ts else 0


def _arrow(d, p0, p1, box0, box1, offset=0.0):
    """Flèche de p0 vers p1, partant et arrivant au bord des boîtes des nœuds."""
    (x0, y0), (x1, y1) = p0, p1
    dx, dy = x1 - x0, y1 - y0
    L = math.hypot(dx, dy) or 1
    ux, uy = dx / L, dy / L
    px, py = -uy * offset, ux * offset
    r0 = _exit(box0, x0, y0, ux, uy) + 8
    r1 = _exit(box1, x1, y1, -ux, -uy) + 12
    if L - r0 - r1 < 30:  # flèche trop courte : on la fait partir et arriver au bord des tuiles
        tile = lambda x, y: (x - T / 2, y - T / 2, x + T / 2, y + T / 2)
        r0 = _exit(tile(x0, y0), x0, y0, ux, uy) + 8
        r1 = _exit(tile(x1, y1), x1, y1, -ux, -uy) + 12
    sx, sy = x0 + ux * r0 + px, y0 + uy * r0 + py
    ex, ey = x1 - ux * r1 + px, y1 - uy * r1 + py
    d.line([sx, sy, ex, ey], fill=ACCENT, width=6)
    a = 20
    d.polygon([(ex + ux * 6, ey + uy * 6),
               (ex - ux * a - uy * a * 0.6, ey - uy * a + ux * a * 0.6),
               (ex - ux * a + uy * a * 0.6, ey - uy * a - ux * a * 0.6)], fill=ACCENT)
    return (sx, sy), (ex, ey)


def make_diagram(story, out_dir):
    """Crée le schéma si besoin et renvoie son nom de fichier, ou None."""
    p = story.get("parcours")
    if not p or not p.get("noeuds"):
        return None
    name = f"{story['id']}-v{story['version']}.png"
    path = Path(out_dir) / name
    if path.exists():
        return name
    try:
        from PIL import Image, ImageDraw
        nodes, links = p["noeuds"], p.get("liens", [])
        present, cols, pos, top, content_h = _layout(nodes)

        f_zone = _font("Inter-Bold.otf", 22)
        f_name = _font("Inter-SemiBold.otf", 25)
        f_note = _font("Inter-Regular.otf", 21)
        f_num = _font("Inter-Bold.otf", 22)
        f_leg = _font("Inter-Medium.otf", 26)
        probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))

        legend = sorted(enumerate(links), key=lambda il: (il[1].get("etape", 0), il[0]))
        leg_lines = [(l.get("etape"), _wrap(probe, l.get("texte", ""), f_leg, W - 2 * 40 - 60))
                     for _, l in legend]
        leg_h = sum(len(ls) * 36 + 14 for _, ls in leg_lines)
        zone_bottom = top + content_h - 50
        H = zone_bottom + 40 + leg_h + 40

        img = Image.new("RGB", (W, int(H)), BG)
        d = ImageDraw.Draw(img)
        d.text((40, 32), "SCHÉMA DE L'ATTAQUE", font=_font("Inter-Bold.otf", 28), fill=ACCENT)

        for z, label in ZONES:  # zones
            if z not in cols:
                continue
            x0, x1 = cols[z]
            d.rounded_rectangle([x0, top - 20, x1, zone_bottom], radius=22, fill=ZONE_BG[z])
            d.text((x0 + 20, top - 6), label, font=f_zone, fill=ZONE_FG[z])

        # libellés et boîte (tuile + nom + note) de chaque nœud
        labels, boxes = {}, {}
        for n in nodes:
            cx, cy = pos[n["id"]]
            nl = _wrap(d, n.get("nom", ""), f_name, CELL_W - 20, 2)
            tl = _wrap(d, n.get("note", ""), f_note, CELL_W - 20, 2)
            lw = max([d.textlength(x, font=f_name) for x in nl] + [d.textlength(x, font=f_note) for x in tl] + [T])
            lh = len(nl) * 30 + len(tl) * 26
            labels[n["id"]] = (nl, tl, lw, lh)
            boxes[n["id"]] = (cx - max(T, lw) / 2 - 6, cy - T / 2 - 6, cx + max(T, lw) / 2 + 6, cy + T / 2 + 14 + lh)

        # liens (sous les nœuds), décalés si plusieurs liens relient les mêmes nœuds
        pairs, mids, seen = {}, [], {}
        for l in links:
            key = tuple(sorted((l["de"], l["vers"])))
            pairs[key] = pairs.get(key, 0) + 1
        for l in links:
            key = tuple(sorted((l["de"], l["vers"])))
            k = seen.get(key, 0)
            seen[key] = k + 1
            off = 0.0 if pairs[key] == 1 else (k - (pairs[key] - 1) / 2) * 30
            if (l["de"], l["vers"]) != key:
                off = -off
            mids.append((_arrow(d, pos[l["de"]], pos[l["vers"]], boxes[l["de"]], boxes[l["vers"]], off),
                         l.get("etape")))

        zone_of = {n["id"]: n.get("zone") for n in nodes}
        for n in nodes:  # nœuds
            cx, cy = pos[n["id"]]
            kind = n.get("type", "inconnu")
            nl, tl, lw, lh = labels[n["id"]]
            if lh:
                d.rounded_rectangle([cx - lw / 2 - 8, cy + T / 2 + 6, cx + lw / 2 + 8, cy + T / 2 + 14 + lh],
                                    radius=8, fill=ZONE_BG.get(zone_of[n["id"]], BG))
            d.rounded_rectangle([cx - T / 2, cy - T / 2, cx + T / 2, cy + T / 2], radius=22,
                                fill=TILE_ATT if kind == "attaquant" else TILE)
            _icon(d, kind if kind in TYPES else "inconnu", cx, cy)
            y = cy + T / 2 + 10
            for line in nl:
                d.text((cx - d.textlength(line, font=f_name) / 2, y), line, font=f_name, fill=TEXT)
                y += 30
            for line in tl:
                d.text((cx - d.textlength(line, font=f_note) / 2, y), line, font=f_note, fill=MUTED)
                y += 26

        def _free(x, y):
            return not any(b[0] - 22 <= x <= b[2] + 22 and b[1] - 22 <= y <= b[3] + 22 for b in boxes.values())

        placed = []
        for ((sx, sy), (ex, ey)), num in mids:  # numéros d'étape le long des flèches, hors des nœuds
            best = None
            for f in (0.5, 0.4, 0.6, 0.3, 0.7, 0.2, 0.8):
                x, y = sx + (ex - sx) * f, sy + (ey - sy) * f
                if _free(x, y) and all(math.hypot(x - a, y - b) > 46 for a, b in placed):
                    best = (x, y)
                    break
            best = best or ((sx + ex) / 2, (sy + ey) / 2)
            placed.append(best)
        mids = [(xy, num) for xy, (_, num) in zip(placed, mids)]
        for (mx, my), num in mids:
            d.ellipse([mx - 20, my - 20, mx + 20, my + 20], fill=WHITE, outline=ACCENT, width=4)
            s = str(num)
            d.text((mx - d.textlength(s, font=f_num) / 2, my - 14), s, font=f_num, fill=ACCENT)

        y = zone_bottom + 40  # légende
        for num, lines in leg_lines:
            d.ellipse([40, y, 76, y + 36], fill=ACCENT)
            s = str(num)
            d.text((58 - d.textlength(s, font=f_num) / 2, y + 5), s, font=f_num, fill=WHITE)
            for line in lines:
                d.text((92, y + 2), line, font=f_leg, fill=TEXT)
                y += 36
            y += 14

        Path(out_dir).mkdir(parents=True, exist_ok=True)
        img.save(path, optimize=True)
        return name
    except Exception as exc:  # un schéma raté ne doit jamais empêcher la publication
        print(f"AVERTISSEMENT: schéma non généré pour {story.get('id')}: {exc}")
        return None


def prune(out_dir, keep):
    q = Path(out_dir)
    if q.exists():
        for f in q.glob("*.png"):
            if f.name not in keep:
                f.unlink()
