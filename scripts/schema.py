"""Schéma vertical de la chaîne d'attaque d'un sujet (PNG, lisible sur téléphone).

Une carte par étape : numéro, phase, action, puis le résultat (texte après la flèche « → »).
Ne bloque jamais la publication : en cas d'échec (Pillow absent, police manquante...),
`make_schema` renvoie None et l'article est publié sans schéma.
"""
import re
from pathlib import Path

W = 1080
M = 48                      # marge extérieure
BG = (246, 247, 249)
CARD = (255, 255, 255)
BORDER = (222, 226, 232)
TEXT = (28, 32, 40)
MUTED = (96, 104, 118)
ACCENT = (201, 100, 66)     # orange
RESULT = (34, 120, 84)      # vert : ce que l'étape a apporté
FONT_DIRS = ["/usr/share/fonts/opentype/inter", "/usr/share/fonts/truetype/inter"]
REF_RE = re.compile(r"\s*\[\d+(?:\s*,\s*\d+)*\]")


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


def _split(texte):
    """Sépare « action → résultat » ; retire les références [n] (elles restent dans le texte)."""
    t = REF_RE.sub("", texte).strip().rstrip(".")
    if "→" in t:
        action, result = t.split("→", 1)
        result = re.sub(r"\s*→\s*", ", ", result).strip()
        return action.strip(), result[:1].upper() + result[1:]
    return t, ""


def make_schema(story, out_dir):
    """Crée le schéma si besoin et renvoie son nom de fichier, ou None."""
    steps = story.get("chaine") or []
    if not steps:
        return None
    name = f"{story['id']}-v{story['version']}.png"
    path = Path(out_dir) / name
    if path.exists():
        return name
    try:
        from PIL import Image, ImageDraw
        f_head = _font("Inter-Bold.otf", 30)
        f_num = _font("Inter-Bold.otf", 30)
        f_phase = _font("Inter-Bold.otf", 34)
        f_body = _font("Inter-Regular.otf", 30)
        f_res = _font("Inter-SemiBold.otf", 30)
        probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))

        PAD, NUM_D, GAP = 32, 56, 72          # marge interne, diamètre du numéro, espace entre cartes
        text_x = M + PAD + NUM_D + 24
        text_w = W - M - PAD - text_x
        LH = 42

        cards = []
        for e in steps:
            action, result = _split(e.get("texte", ""))
            a_lines = _wrap(probe, action, f_body, text_w)
            r_lines = _wrap(probe, "→ " + result, f_res, text_w) if result else []
            h = PAD + 46 + len(a_lines) * LH + (10 + len(r_lines) * LH if r_lines else 0) + PAD
            cards.append((e.get("etape", ""), a_lines, r_lines, max(h, PAD * 2 + NUM_D)))

        H = M + 50 + sum(c[3] for c in cards) + GAP * (len(cards) - 1) + M
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        d.text((M, M - 6), "CHAÎNE D'ATTAQUE", font=f_head, fill=ACCENT)

        y = M + 50
        for i, (phase, a_lines, r_lines, h) in enumerate(cards):
            if i:  # flèche entre deux cartes
                cx = M + PAD + NUM_D // 2
                d.line([cx, y - GAP + 8, cx, y - 16], fill=ACCENT, width=5)
                d.polygon([(cx - 13, y - 22), (cx + 13, y - 22), (cx, y - 6)], fill=ACCENT)
            d.rounded_rectangle([M, y, W - M, y + h], radius=22, fill=CARD, outline=BORDER, width=2)
            nx, ny = M + PAD, y + PAD
            d.ellipse([nx, ny, nx + NUM_D, ny + NUM_D], fill=ACCENT)
            num = str(i + 1)
            d.text((nx + (NUM_D - d.textlength(num, font=f_num)) / 2, ny + 10), num, font=f_num, fill=(255, 255, 255))
            ty = y + PAD + 4
            d.text((text_x, ty), phase, font=f_phase, fill=TEXT)
            ty += 46
            for line in a_lines:
                d.text((text_x, ty), line, font=f_body, fill=MUTED)
                ty += LH
            if r_lines:
                ty += 10
                for line in r_lines:
                    d.text((text_x, ty), line, font=f_res, fill=RESULT)
                    ty += LH
            y += h + GAP

        Path(out_dir).mkdir(parents=True, exist_ok=True)
        img.save(path, optimize=True)
        return name
    except Exception as exc:  # un schéma raté ne doit jamais empêcher la publication
        print(f"AVERTISSEMENT: schéma non généré pour {story.get('id')}: {exc}")
        return None


def prune(out_dir, keep):
    """Supprime les schémas qui ne correspondent plus à aucun sujet publié."""
    p = Path(out_dir)
    if p.exists():
        for f in p.glob("*.png"):
            if f.name not in keep:
                f.unlink()
