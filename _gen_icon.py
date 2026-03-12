"""
Render the official FieldLgx SVG to PNGs using cairosvg for pixel-perfect output.
Reads the SVG directly and renders at each target size.
"""
import cairosvg
from PIL import Image
import os, io

BASE = "/Users/adencappelletti/landscape-saas"
SVG_PATH = os.path.join(BASE, "static/img/logo-icon.svg")
BG = (10, 10, 10)


def svg_to_png(svg_path, size):
    """Render SVG to a Pillow Image at the given size using cairosvg."""
    png_data = cairosvg.svg2png(
        url=svg_path,
        output_width=size,
        output_height=size,
    )
    return Image.open(io.BytesIO(png_data)).convert("RGBA")


if __name__ == "__main__":
    # Render at 1024 (master size)
    icon = svg_to_png(SVG_PATH, 1024)
    print(f"  Rendered SVG at 1024x1024")

    # Save all web icon sizes
    outputs = {
        1024: os.path.join(BASE, "static/img/icon-1024.png"),
        512:  os.path.join(BASE, "static/img/icon-512.png"),
        192:  os.path.join(BASE, "static/img/icon-192.png"),
        180:  os.path.join(BASE, "static/img/apple-touch-icon.png"),
    }

    for sz, path in outputs.items():
        if sz == 1024:
            img = icon
        else:
            # Re-render from SVG at exact size for best quality
            img = svg_to_png(SVG_PATH, sz)
        img.convert("RGB").save(path, "PNG", optimize=True)
        print(f"  {os.path.basename(path)} ({sz}x{sz})")

    # Xcode AppIcon (1024x1024)
    xcode_path = os.path.join(BASE, "native/ios/App/App/Assets.xcassets/AppIcon.appiconset/AppIcon-512@2x.png")
    icon.convert("RGB").save(xcode_path, "PNG", optimize=True)
    print(f"  AppIcon-512@2x.png (1024 Xcode)")

    # Splash screens
    SPLASH = 2732
    ICON_SZ = 400
    splash_dir = os.path.join(BASE, "native/ios/App/App/Assets.xcassets/Splash.imageset")
    small = svg_to_png(SVG_PATH, ICON_SZ)
    splash = Image.new("RGBA", (SPLASH, SPLASH), (*BG, 255))
    off = (SPLASH - ICON_SZ) // 2
    splash.paste(small, (off, off), small)  # use alpha channel as mask
    splash_rgb = splash.convert("RGB")
    for name in ["splash-2732x2732.png", "splash-2732x2732-1.png", "splash-2732x2732-2.png"]:
        splash_rgb.save(os.path.join(splash_dir, name), "PNG", optimize=True)
        print(f"  {name} (splash)")

    print("\nAll done!")
