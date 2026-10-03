"""Images de couverture des sujets (1200x630), utilisées comme vignette par les lecteurs RSS.

Feedly retient en priorité une image du contenu portant la classe `webfeedsFeaturedVisual`,
sinon la première image de plus de 450 px de large et de haut.

Ne bloque jamais la publication : si Pillow ou les polices manquent, `make_cover` renvoie None
et l'article est publié sans image.
"""
from pathlib import Path

W, H = 1200, 630
BG = (20, 24, 33)          # fond sombre
PANEL = (32, 38, 51)       # pastilles
ACCENT = (217, 119, 87)    # orange
TEXT = (240, 242, 246)
MUTED = (150, 158, 175)
FONT_DIRS = ["/usr/share/fonts/opentype/inter", "/usr/share/fonts/truetype/inter"]


def _font(name, size):
    from PIL import ImageFont
    for d in FONT_DIRS:
        p = Path(d) / name
        if p.exists():
            return ImageFont.truetype(str(p), size)
    for fallback in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                     "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if Path(fallback).exists():
            return ImageFont.truetype(fallback, size)
    return ImageFont.load_default(size=size)


def _wrap(draw, text, font, max_width, max_lines):
    words, lines, line = text.split(), [], ""
    for w in words:
        test = f"{line} {w}".strip()
        if draw.textlength(test, font=font) <= max_width:
            line = test
        else:
            if line:
                lines.append(line)
            line = w
    if line:
        lines.append(line)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while draw.textlength(last + " …", font=font) > max_width and " " in last:
            last = last.rsplit(" ", 1)[0]
        lines[-1] = last + " …"
    return lines


def make_cover(story, out_dir):
    """Crée l'image du sujet si besoin et renvoie son nom de fichier, ou None en cas d'échec."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None
    name = f"{story['id']}-v{story['version']}.png"
    path = Path(out_dir) / name
    if path.exists():
        return name
    try:
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        M = 64

        # bandeau supérieur
        d.rectangle([0, 0, W, 10], fill=ACCENT)
        d.text((M, 52), "VEILLE CYBER", font=_font("Inter-Bold.otf", 26), fill=ACCENT)
        date = story["updated"][:10]
        f_small = _font("Inter-Medium.otf", 26)
        d.text((W - M - d.textlength(date, font=f_small), 52), date, font=f_small, fill=MUTED)

        # titre
        f_title = _font("Inter-ExtraBold.otf", 52)
        y = 112
        for line in _wrap(d, story["title"], f_title, W - 2 * M, 4):
            d.text((M, y), line, font=f_title, fill=TEXT)
            y += 64

        # chaîne d'attaque : une pastille par phase, reliées par des flèches
        f_step = _font("Inter-SemiBold.otf", 24)
        x, y_chain = M, max(y + 34, 400)
        for i, e in enumerate(story.get("chaine", [])[:6]):
            label = e.get("etape", "")
            w = d.textlength(label, font=f_step) + 36
            arrow = 0 if i == 0 else 44
            if x + arrow + w > W - M:          # passe à la ligne suivante
                x, y_chain = M, y_chain + 66
                arrow = 0
                if y_chain > H - 130:
                    break
            if arrow:
                d.text((x + 8, y_chain + 6), "→", font=f_step, fill=ACCENT)
                x += arrow
            d.rounded_rectangle([x, y_chain, x + w, y_chain + 48], radius=24, fill=PANEL)
            d.text((x + 18, y_chain + 10), label, font=f_step, fill=TEXT)
            x += w

        # pied : CVE et nombre de sources
        cves = [c["id"] for c in story.get("cves", [])]
        n = len(story.get("sources", []))
        foot = (" · ".join(cves[:3]) + (f" +{len(cves) - 3}" if len(cves) > 3 else "") + "   ") if cves else ""
        foot += f"{n} source{'s' if n > 1 else ''}"
        d.text((M, H - 70), foot, font=_font("Inter-Medium.otf", 26), fill=MUTED)

        Path(out_dir).mkdir(parents=True, exist_ok=True)
        img.save(path, optimize=True)
        return name
    except Exception as exc:  # une image ratée ne doit jamais empêcher la publication
        print(f"AVERTISSEMENT: image non générée pour {story.get('id')}: {exc}")
        return None


def prune(out_dir, keep):
    """Supprime les images qui ne correspondent plus à aucun sujet publié."""
    p = Path(out_dir)
    if not p.exists():
        return
    for f in p.glob("*.png"):
        if f.name not in keep:
            f.unlink()
