#!/usr/bin/env python3
"""Genera il tema muOS 'MBR Terminal' (640x480) con il font Topaz e i colori del sito di MBR.

Serve: Pillow, Node.js (comando npx, per convertire il font nel formato di muOS con
lv_font_conv) e il file topaz.ttf, che non e' nel repository.
La struttura del tema e le chiavi dei file .ini seguono il tema 'GB Dark' di muOS 2606.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PALETTE = ROOT / "theme" / "palette.json"
W, H = 640, 480
FONT_PX = 32  # 2x: ogni pixel 8x8 di Topaz diventa 2x2
RANGES = ["0x20-0x7E", "0xA0-0xFF"]
LIST_WIDTH = 360  # larghezza della lista giochi; il resto dello schermo e' per la copertina


def colors():
    p = json.loads(PALETTE.read_text(encoding="utf-8"))
    return {k: p[k].lstrip("#").lower()
            for k in ("background", "text", "secondary", "selected_background", "selected_text")}


def ini(sections):
    out = []
    for name, items in sections.items():
        out.append("[%s]" % name)
        out += ["%s=%s" % (k, v) for k, v in items.items()]
        out.append("")
    return "\n".join(out)


def default_scheme(c):
    bg, fg, dim, sel_bg, sel_fg = (c[k] for k in (
        "background", "text", "secondary", "selected_background", "selected_text"))
    glyph = {}
    for key in ("A", "B", "C", "X", "Y", "Z", "MENU"):
        glyph.update({"NAV_%s_GLYPH" % key: bg, "NAV_%s_GLYPH_ALPHA" % key: 255,
                      "NAV_%s_TEXT" % key: "000000", "NAV_%s_TEXT_ALPHA" % key: 255})
    return {
        "background": {"BACKGROUND": bg, "BACKGROUND_ALPHA": 255},
        "font": {"FONT_HEADER_PAD_TOP": 0, "FONT_HEADER_PAD_BOTTOM": 0, "FONT_HEADER_ICON_PAD_TOP": 0,
                 "FONT_HEADER_ICON_PAD_BOTTOM": 0, "FONT_FOOTER_PAD_TOP": 0, "FONT_FOOTER_PAD_BOTTOM": 0,
                 "FONT_FOOTER_ICON_PAD_TOP": 0, "FONT_FOOTER_ICON_PAD_BOTTOM": 0, "FONT_MESSAGE_PAD_TOP": 0,
                 "FONT_MESSAGE_PAD_BOTTOM": 0, "FONT_MESSAGE_ICON_PAD_TOP": 0, "FONT_MESSAGE_ICON_PAD_BOTTOM": 0,
                 "FONT_LIST_PAD_TOP": 1, "FONT_LIST_PAD_BOTTOM": 0, "FONT_LIST_ICON_PAD_TOP": 0,
                 "FONT_LIST_ICON_PAD_BOTTOM": 0},
        "status": {"PADDING_RIGHT": 10},
        "battery": {"BATTERY_NORMAL": fg, "BATTERY_ACTIVE": dim, "BATTERY_LOW": "ffb000",
                    "BATTERY_NORMAL_ALPHA": 255, "BATTERY_ACTIVE_ALPHA": 255, "BATTERY_LOW_ALPHA": 255},
        "network": {"NETWORK_NORMAL": fg, "NETWORK_ACTIVE": dim, "NETWORK_NORMAL_ALPHA": 255,
                    "NETWORK_ACTIVE_ALPHA": 255},
        "bluetooth": {"BLUETOOTH_NORMAL": fg, "BLUETOOTH_ACTIVE": dim, "BLUETOOTH_NORMAL_ALPHA": 255,
                      "BLUETOOTH_ACTIVE_ALPHA": 255},
        "date": {"DATETIME_TEXT": fg, "DATETIME_ALPHA": 255, "PADDING_LEFT": 10},
        "footer": {"FOOTER_BACKGROUND": dim, "FOOTER_BACKGROUND_ALPHA": 255, "FOOTER_TEXT": "000000",
                   "FOOTER_TEXT_ALPHA": 255},
        "header": {"HEADER_BACKGROUND": bg, "HEADER_BACKGROUND_ALPHA": 255, "HEADER_TEXT": fg,
                   "HEADER_TEXT_ALPHA": 255},
        "help": {"HELP_BACKGROUND": bg, "HELP_BACKGROUND_ALPHA": 255, "HELP_BORDER": fg, "HELP_BORDER_ALPHA": 255,
                 "HELP_CONTENT": fg, "HELP_TITLE": dim, "HELP_RADIUS": 0},
        "navigation": dict({"ALIGNMENT": 0}, **glyph),
        "list": {"LIST_DEFAULT_BACKGROUND": bg, "LIST_DEFAULT_BACKGROUND_ALPHA": 0,
                 "LIST_DEFAULT_GRADIENT_START": 0, "LIST_DEFAULT_GRADIENT_STOP": bg,
                 "LIST_DEFAULT_INDICATOR": bg, "LIST_DEFAULT_INDICATOR_ALPHA": 0,
                 "LIST_DEFAULT_TEXT": fg, "LIST_DEFAULT_TEXT_ALPHA": 255,
                 "LIST_DEFAULT_GLYPH_PAD_LEFT": 5, "LIST_DEFAULT_GLYPH_PAD_RIGHT": 6,
                 "LIST_DEFAULT_GLYPH_ALPHA": 255, "LIST_DEFAULT_GLYPH_RECOLOUR": dim,
                 "LIST_DEFAULT_GLYPH_RECOLOUR_ALPHA": 255,
                 "LIST_DISABLED_TEXT": dim, "LIST_DISABLED_TEXT_ALPHA": 255,
                 "LIST_FOCUS_BACKGROUND": sel_bg, "LIST_FOCUS_BACKGROUND_ALPHA": 255,
                 "LIST_FOCUS_GRADIENT_START": 0, "LIST_FOCUS_GRADIENT_STOP": sel_bg,
                 "LIST_FOCUS_INDICATOR": sel_bg, "LIST_FOCUS_INDICATOR_ALPHA": 0,
                 "LIST_FOCUS_TEXT": sel_fg, "LIST_FOCUS_TEXT_ALPHA": 255,
                 "LIST_FOCUS_GLYPH_ALPHA": 255, "LIST_FOCUS_GLYPH_RECOLOUR": sel_fg,
                 "LIST_FOCUS_GLYPH_RECOLOUR_ALPHA": 255},
        "image_list": {"IMAGE_LIST_RADIUS": 0, "IMAGE_LIST_RECOLOUR": bg, "IMAGE_LIST_RECOLOUR_ALPHA": 0,
                       "IMAGE_PREVIEW_RADIUS": 0, "IMAGE_PREVIEW_RECOLOUR": bg, "IMAGE_PREVIEW_RECOLOUR_ALPHA": 0},
        "charging": {"CHARGER_BACKGROUND": bg, "CHARGER_BACKGROUND_ALPHA": 255, "CHARGER_TEXT": fg,
                     "CHARGER_TEXT_ALPHA": 255, "CHARGER_Y_POS": 160},
        "verbose": {"VERBOSE_BOOT_BACKGROUND": bg, "VERBOSE_BOOT_BACKGROUND_ALPHA": 255,
                    "VERBOSE_BOOT_TEXT": fg, "VERBOSE_BOOT_TEXT_ALPHA": 255, "VERBOSE_BOOT_Y_POS": 160},
        "keyboard": {"OSK_BACKGROUND": bg, "OSK_BACKGROUND_ALPHA": 255, "OSK_BORDER": fg, "OSK_BORDER_ALPHA": 255,
                     "OSK_RADIUS": 0, "OSK_TEXT": fg, "OSK_TEXT_ALPHA": 255, "OSK_TEXT_FOCUS": sel_fg,
                     "OSK_TEXT_FOCUS_ALPHA": 255, "OSK_ITEM_BACKGROUND": bg, "OSK_ITEM_BACKGROUND_ALPHA": 255,
                     "OSK_ITEM_BACKGROUND_FOCUS": sel_bg, "OSK_ITEM_BACKGROUND_FOCUS_ALPHA": 255,
                     "OSK_ITEM_BORDER": dim, "OSK_ITEM_BORDER_ALPHA": 255, "OSK_ITEM_BORDER_FOCUS": fg,
                     "OSK_ITEM_BORDER_FOCUS_ALPHA": 255, "OSK_ITEM_RADIUS": 0},
        "notification": {"MSG_BACKGROUND": bg, "MSG_BACKGROUND_ALPHA": 255, "MSG_BORDER": fg,
                         "MSG_BORDER_ALPHA": 255, "MSG_RADIUS": 0, "MSG_TEXT": fg, "MSG_TEXT_ALPHA": 255},
        "roll": {"ROLL_TEXT": fg, "ROLL_TEXT_ALPHA": 255, "ROLL_BACKGROUND": bg, "ROLL_BACKGROUND_ALPHA": 0,
                 "ROLL_RADIUS": 0, "ROLL_SELECT_TEXT": sel_fg, "ROLL_SELECT_TEXT_ALPHA": 255,
                 "ROLL_SELECT_BACKGROUND": sel_bg, "ROLL_SELECT_BACKGROUND_ALPHA": 255, "ROLL_SELECT_RADIUS": 0,
                 "ROLL_BORDER_COLOUR": fg, "ROLL_BORDER_ALPHA": 255, "ROLL_BORDER_RADIUS": 0},
        "meta": {"META_CUT": 40},
        "bar": {"BAR_BACKGROUND": bg, "BAR_BACKGROUND_ALPHA": 255, "BAR_BORDER": fg, "BAR_BORDER_ALPHA": 255,
                "BAR_RADIUS": 0, "BAR_PROGRESS_BACKGROUND": "17452a", "BAR_PROGRESS_BACKGROUND_ALPHA": 255,
                "BAR_PROGRESS_ACTIVE_BACKGROUND": fg, "BAR_PROGRESS_ACTIVE_BACKGROUND_ALPHA": 255,
                "BAR_PROGRESS_RADIUS": 0, "BAR_ICON": fg, "BAR_ICON_ALPHA": 255},
        "misc": {"STATIC_ALIGNMENT": 0, "ANIMATED_BACKGROUND": 0, "NAVIGATION_TYPE": 0,
                 "CONTENT_PADDING_LEFT": 0, "CONTENT_WIDTH": W, "OVERLAY_IMAGE": 0},
        "counter": {"COUNTER_ENABLED": 1, "COUNTER_ALIGNMENT": 2, "COUNTER_PADDING_AROUND": 10,
                    "COUNTER_PADDING_SIDE": 5, "COUNTER_PADDING_TOP": 50, "COUNTER_BORDER_COLOUR": dim,
                    "COUNTER_BORDER_ALPHA": 255, "COUNTER_BORDER_WIDTH": 2, "COUNTER_RADIUS": 0,
                    "COUNTER_BACKGROUND": bg, "COUNTER_BACKGROUND_ALPHA": 255, "COUNTER_TEXT": fg,
                    "COUNTER_TEXT_ALPHA": 255, "COUNTER_TEXT_FADE_TIME": 50, "COUNTER_TEXT_SEPARATOR": " /"},
    }


def global_scheme(c):
    return {"dialogue": {"DIALOGUE_BACKGROUND": c["background"], "DIALOGUE_BACKGROUND_ALPHA": 255,
                         "DIALOGUE_BORDER": c["text"], "DIALOGUE_BORDER_ALPHA": 255,
                         "DIALOGUE_TITLE": c["secondary"], "DIALOGUE_CONTENT": c["text"],
                         "DIALOGUE_OPTION": "000000", "DIALOGUE_SELECTION": c["text"],
                         "DIALOGUE_SELECTION_ALPHA": 255}}


def convert_font(ttf, dest):
    npx = shutil.which("npx")
    if not npx:
        sys.exit("Serve Node.js (comando npx) per convertire il font nel formato di muOS.")
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [npx, "--yes", "lv_font_conv", "--font", str(ttf)]
    for r in RANGES:
        cmd += ["-r", r]
    cmd += ["--size", str(FONT_PX), "--bpp", "4", "--no-compress", "--format", "bin", "-o", str(dest)]
    subprocess.run(cmd, check=True)


def pil():
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        sys.exit("Serve Pillow: pip install --user pillow")
    return Image, ImageDraw, ImageFont


def text_screen(ttf, c, lines, center=False):
    """Immagine 640x480 con righe di testo Topaz; lines = [(testo, colore)]."""
    Image, ImageDraw, ImageFont = pil()
    img = Image.new("RGB", (W, H), "#" + c["background"])
    d = ImageDraw.Draw(img)
    d.fontmode = "1"
    f = ImageFont.truetype(str(ttf), FONT_PX)
    step = FONT_PX + 8
    y = (H - step * len(lines)) // 2
    for text, color in lines:
        x = (W - int(d.textlength(text, font=f))) // 2 if center else 40
        d.text((x, y), text, font=f, fill="#" + color)
        y += step
    return img


def logo_screen(src, background="000000"):
    """Logo dell'utente adattato a 640x480: intero, centrato, su sfondo pieno."""
    Image = pil()[0]
    img = Image.open(src).convert("RGB")
    img.thumbnail((W, H), Image.LANCZOS)
    out = Image.new("RGB", (W, H), "#" + background)
    out.paste(img, ((W - img.width) // 2, (H - img.height) // 2))
    return out


def preview(ttf, c):
    Image, ImageDraw, ImageFont = pil()
    img = Image.new("RGB", (W, H), "#" + c["background"])
    d = ImageDraw.Draw(img)
    d.fontmode = "1"
    f = ImageFont.truetype(str(ttf), FONT_PX)
    fg, dim = "#" + c["text"], "#" + c["secondary"]
    d.text((10, 6), "C:\\MUOS\\ROMS>_", font=f, fill=fg)
    rows = ["DOOM", "GOLDEN AXE", "DUKE NUKEM", "ROBOCOP", "CONTRA", "NINJA GAIDEN", "BATTLETOADS", "DOUBLE DRAGON"]
    y = 52
    for i, name in enumerate(rows):
        if i == 3:
            d.rectangle([0, y, LIST_WIDTH, y + 35], fill="#" + c["selected_background"])
            d.text((10, y + 2), name, font=f, fill="#" + c["selected_text"])
        else:
            d.text((10, y + 2), name, font=f, fill=fg)
        y += 36
    d.rectangle([LIST_WIDTH + 18, 70, LIST_WIDTH + 18 + 241, 70 + 216], outline=fg, width=2)
    d.rectangle([0, H - 40, W, H], fill=dim)
    d.text((10, H - 38), "A:OPEN  B:BACK", font=f, fill="#000000")
    return img


def build(ttf, out, name, base_theme=None, logo=None):
    """Crea out/<name>/ con il tema completo. Ritorna il percorso."""
    c = colors()
    theme = Path(out) / name
    if theme.exists():
        shutil.rmtree(theme)
    res = theme / ("%dx%d" % (W, H))
    for d in (theme / "scheme", theme / "image", res / "scheme", res / "image" / "wall"):
        d.mkdir(parents=True, exist_ok=True)

    (theme / "name.txt").write_text(name + "\n", encoding="utf-8")
    (theme / "version.txt").write_text("2606.0\n", encoding="utf-8")
    (theme / "credits.txt").write_text(
        "tema fan-made; font Topaz (Amiga), colori dal sito di MBR\n", encoding="utf-8")
    (theme / "scheme" / "global.ini").write_text(ini(global_scheme(c)), encoding="utf-8")
    (res / "scheme" / "default.ini").write_text(ini(default_scheme(c)), encoding="utf-8")
    narrow = ini({"misc": {"CONTENT_WIDTH": LIST_WIDTH}})
    for screen in ("muxplore", "muxcollect", "muxhistory"):  # le liste di giochi, con la copertina a destra
        (res / "scheme" / (screen + ".ini")).write_text(narrow, encoding="utf-8")

    convert_font(ttf, theme / "font" / "default.bin")

    Image = pil()[0]
    Image.new("RGBA", (1, 1), (0, 0, 0, 0)).save(theme / "image" / "none_box.png")
    Image.new("RGBA", (1, 1), (0, 0, 0, 0)).save(theme / "image" / "none_preview.png")
    fg, dim = c["text"], c["secondary"]
    Image.new("RGB", (W, H), "#" + c["background"]).save(res / "image" / "wall" / "default.png")
    if logo and Path(logo).is_file():
        logo_screen(logo).save(res / "image" / "bootlogo.bmp")
    else:
        text_screen(ttf, c, [("C:\\>BOOT MUOS", fg), ("LOADING...", dim), ("_", fg)]).save(res / "image" / "bootlogo.bmp")
    text_screen(ttf, c, [("STARTING...", fg)], center=True).save(res / "image" / "wall" / "muxstart.png")
    text_screen(ttf, c, [("CHARGING...", fg)], center=True).save(res / "image" / "wall" / "muxcharge.png")
    prev = preview(ttf, c)
    prev.save(res / "preview.png")
    prev.save(res / "preview.0.png")

    if base_theme and (Path(base_theme) / "sound").is_dir():
        shutil.copytree(Path(base_theme) / "sound", theme / "sound")
    return theme


if __name__ == "__main__":
    ap_font = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("topaz.ttf")
    print(build(ap_font, ROOT / "build" / "theme", "MBR Terminal"))
