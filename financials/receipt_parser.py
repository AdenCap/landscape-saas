"""
Extract receipt date, vendor, and total amount from a receipt image using OCR.
Uses pytesseract (Tesseract) when available; falls back to no-op if not installed.
"""
import re
from datetime import date
from decimal import Decimal
from typing import Optional


def _get_text_from_image(file) -> str:
    """Run OCR on an image file. Returns raw text or empty string."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return ""

    try:
        if hasattr(file, "read"):
            file.seek(0)
            img = Image.open(file)
        else:
            img = Image.open(file)
        img = img.convert("L")  # grayscale often works better
        text = pytesseract.image_to_string(img)
        return text or ""
    except Exception:
        return ""


def _parse_date_from_text(text: str) -> Optional[date]:
    """Try to find a date in common formats (MM/DD/YYYY, MM-DD-YYYY, etc.)."""
    today = date.today()
    # Common patterns: 01/15/2025, 01-15-2025, 2025-01-15, Jan 15 2025
    patterns = [
        r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b",
        r"\b(\d{1,2})-(\d{1,2})-(\d{4})\b",
        r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b",
        r"\b(\d{1,2})/(\d{1,2})/(\d{2})\b",  # 01/15/25
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            g = m.groups()
            try:
                if len(g) == 3 and len(g[0]) == 4:  # YYYY-MM-DD
                    y, mo, d = int(g[0]), int(g[1]), int(g[2])
                elif len(g[2]) == 2:  # 2-digit year
                    mo, d, y = int(g[0]), int(g[1]), int(g[2])
                    y = 2000 + y if y < 100 else y
                else:
                    mo, d, y = int(g[0]), int(g[1]), int(g[2])
                return date(y, mo, d)
            except (ValueError, TypeError):
                continue
    return None


def _parse_amount_from_text(text: str) -> Optional[Decimal]:
    """Find total / grand total amount. Prefer last or largest $ amount."""
    # Match $123.45 or $ 123.45 or 123.45
    amount_pattern = re.compile(r"\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?|\d+\.\d{2})\b")
    matches = amount_pattern.findall(text)
    if not matches:
        # Try without $: number with 2 decimal places at end of line (often total)
        alt = re.findall(r"\b(\d+\.\d{2})\b", text)
        matches = alt[-3:] if alt else []  # last few numbers might include total
    amounts = []
    for m in matches:
        try:
            cleaned = m.replace(",", "")
            v = Decimal(cleaned)
            if 0 < v < 100000:
                amounts.append(v)
        except Exception:
            continue
    if not amounts:
        return None
    # Often the total is the last or the largest
    return max(amounts)


def _parse_vendor_from_text(text: str) -> str:
    """First non-empty line is often the store name."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for line in lines[:5]:
        if len(line) > 2 and len(line) < 80:
            if not re.match(r"^[\d\s\$\.\,\-\/]+$", line):
                return line[:255]
    return ""


def parse_receipt_image(file) -> dict:
    """
    Parse a receipt image (or file-like) and return extracted fields.
    Returns dict with keys: receipt_date (date or None), vendor (str), amount (Decimal or None).
    """
    text = _get_text_from_image(file)
    if not text:
        return {"receipt_date": None, "vendor": "", "amount": None}

    return {
        "receipt_date": _parse_date_from_text(text),
        "vendor": _parse_vendor_from_text(text),
        "amount": _parse_amount_from_text(text),
    }
