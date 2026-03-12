"""Generate dark splash screens using cairosvg to render the SVG icon directly."""
import cairosvg
from PIL import Image
import os, io

base = "/Users/adencappelletti/landscape-saas"
svg_path = os.path.join(base, "static/img/logo-icon.svg")
splash_dir = os.path.join(base, "native/ios/App/App/Assets.xcassets/Splash.imageset")

SPLASH_SIZE = 2732
BG = (10, 10, 10)
ICON_SIZE = 400  # icon size on splash

# Render SVG at exact icon size
png_data = cairosvg.svg2png(url=svg_path, output_width=ICON_SIZE, output_height=ICON_SIZE)
icon = Image.open(io.BytesIO(png_data)).convert("RGBA")

splash = Image.new("RGBA", (SPLASH_SIZE, SPLASH_SIZE), (*BG, 255))
offset = (SPLASH_SIZE - ICON_SIZE) // 2
splash.paste(icon, (offset, offset), icon)
splash_rgb = splash.convert("RGB")

for name in ["splash-2732x2732.png", "splash-2732x2732-1.png", "splash-2732x2732-2.png"]:
    out = os.path.join(splash_dir, name)
    splash_rgb.save(out, "PNG", optimize=True)
    print(f"  {out}")

print("\nSplash screens done!")
