import json
import random
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import numpy as np
from faker import Faker
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"
FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"

LEVELS = ["level1_clean", "level2_mixed", "level3_noisy", "level4_hard"]  # append only: index feeds the Faker seed
HARD = "level4_hard"

# style "eu" prints 1.234,56 ; style "us" prints 1,234.56
CURRENCIES = {
    "INR": {"style": "us", "decimals": 2, "country": "India", "locale": "en_IN"},
    "USD": {"style": "us", "decimals": 2, "country": "USA", "locale": "en_US"},
    "GBP": {"style": "us", "decimals": 2, "country": "United Kingdom", "locale": "en_GB"},
    "EUR": {"style": "eu", "decimals": 2, "country": "Germany", "locale": "de_DE"},
    "JPY": {"style": "us", "decimals": 0, "country": "Japan", "locale": "en_US"},
}
JP_CITIES = ["Tokyo", "Osaka", "Nagoya", "Yokohama"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]

ITEMS = [
    "Wireless Keyboard", "Wireless Mouse", "USB-C Hub", "Office Chair", "Printer Toner",
    "Laptop Stand", "Network Switch", "LED Desk Lamp", "Webcam", "External SSD",
    "Packaging Materials", "Courier Delivery", "Whiteboard Markers", "Ethernet Cable",
    "Security Audit", "Cloud Hosting", "Software Licence", "Training Workshop",
]


def q(x, decimals):
    return x.quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)


def money(x, cur):
    s = f"{x:,.{cur['decimals']}f}"
    if cur["style"] == "eu":
        s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return s


def date_text(d, country, rng, mixed):
    if not mixed:
        return d.isoformat()
    kind = rng.choice(["numeric", "long_dmy", "long_mdy", "short_month"])
    if kind == "numeric":
        if country == "USA":
            return f"{d.month:02d}/{d.day:02d}/{d.year}"
        if country == "Japan":
            return f"{d.year}/{d.month:02d}/{d.day:02d}"
        sep = rng.choice(["/", ".", "-"])
        return f"{d.day:02d}{sep}{d.month:02d}{sep}{d.year}"
    if kind == "long_dmy":
        return f"{d.day} {MONTHS[d.month - 1]} {d.year}"
    if kind == "long_mdy":
        return f"{MONTHS[d.month - 1]} {d.day}, {d.year}"
    return f"{d.day:02d}-{MONTHS[d.month - 1][:3]}-{d.year}"


def hard_date_text(d, country, rng):
    """Numeric only, day <= 12 and day != month, so the order is genuinely ambiguous."""
    if country == "USA":
        return f"{d.month:02d}/{d.day:02d}/{d.year}"
    sep = rng.choice(["/", ".", "-"])
    return f"{d.day:02d}{sep}{d.month:02d}{sep}{d.year}"


def make_invoice(level, n, seed):
    """Returns (truth, display). Same (level, n, seed) -> same invoice."""
    mixed = level != "level1_clean"
    rng = random.Random(f"{seed}-{level}-{n}")
    hard = level == HARD
    if hard:  # no JPY: its YYYY/MM/DD dates would not be ambiguous
        code = rng.choice([c for c in CURRENCIES if c != "JPY"])
    else:
        code = rng.choice(list(CURRENCIES)) if mixed else "INR"
    cur = CURRENCIES[code]

    fake = Faker(cur["locale"])
    fake.seed_instance(seed * 1000 + n + 100000 * LEVELS.index(level))
    city = rng.choice(JP_CITIES) if code == "JPY" else fake.city()
    address = f"{fake.street_address()}, {city}, {cur['country']}"

    items = []
    for desc in rng.sample(ITEMS, rng.randint(8, 15) if hard else rng.randint(2, 6)):
        qty = rng.randint(1, 20)
        if code == "JPY":
            unit = Decimal(rng.randint(5, 400) * 100)
        else:
            unit = Decimal(rng.randint(50, 5000)) + Decimal(rng.randint(0, 99)) / 100
        items.append({"description": desc, "quantity": qty,
                      "unit_price": q(unit, cur["decimals"]),
                      "amount": q(unit * qty, cur["decimals"])})

    subtotal = sum((i["amount"] for i in items), Decimal("0"))
    tax_pct = Decimal(rng.choice([0, 5, 10, 18, 20])) if mixed else Decimal(18)
    tax = q(subtotal * tax_pct / 100, cur["decimals"])
    total = subtotal + tax
    if hard:
        month = rng.randint(1, 12)
        inv_date = date(2026, month, rng.choice([x for x in range(1, 13) if x != month]))
    else:
        inv_date = date(2026, 1, 1) + timedelta(days=rng.randint(0, 270))

    truth = {
        "id": f"{level}_{n:03d}",
        "level": level,
        "invoice_number": f"INV-2026-{rng.randint(10000, 99999)}",
        "vendor": fake.company(),
        "invoice_date": inv_date.isoformat(),
        "currency": code,
        "line_items": [{"description": i["description"], "quantity": i["quantity"],
                        "unit_price": float(i["unit_price"]), "amount": float(i["amount"])}
                       for i in items],
        "subtotal": float(subtotal),
        "tax": float(tax),
        "total": float(total),
    }
    display = {
        "address": address,
        "date_text": (hard_date_text(inv_date, cur["country"], rng) if hard
                      else date_text(inv_date, cur["country"], rng, mixed)),
        "tax_pct": int(tax_pct),
        "cur": cur,
    }
    return truth, display


def render(inv, disp, compact=False):
    W, H = 1240, 1754
    cur = disp["cur"]
    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)
    t, b, sm, row = (36, 20, 17, 38) if compact else (44, 26, 22, 50)  # compact = smaller text
    title = ImageFont.truetype(FONT_BOLD, t)
    bold = ImageFont.truetype(FONT_BOLD, b)
    body = ImageFont.truetype(FONT, b)
    small = ImageFont.truetype(FONT, sm)

    draw.text((90, 80), inv["vendor"], font=title, fill="black")
    draw.text((90, 140), disp["address"], font=small, fill="black")
    draw.text((W - 90, 80), "INVOICE", font=title, fill="black", anchor="ra")
    draw.text((90, 220), f"Invoice no: {inv['invoice_number']}", font=body, fill="black")
    draw.text((90, 265), f"Date: {disp['date_text']}", font=body, fill="black")
    draw.text((90, 310), f"Currency: {inv['currency']}", font=body, fill="black")

    y = 400
    draw.text((90, y), "Description", font=bold, fill="black")
    draw.text((700, y), "Qty", font=bold, fill="black", anchor="ra")
    draw.text((900, y), "Unit price", font=bold, fill="black", anchor="ra")
    draw.text((W - 90, y), "Amount", font=bold, fill="black", anchor="ra")
    draw.line((90, y + 40, W - 90, y + 40), fill="black", width=2)

    y += 65
    for item in inv["line_items"]:
        draw.text((90, y), item["description"], font=body, fill="black")
        draw.text((700, y), str(item["quantity"]), font=body, fill="black", anchor="ra")
        draw.text((900, y), money(item["unit_price"], cur), font=body, fill="black", anchor="ra")
        draw.text((W - 90, y), money(item["amount"], cur), font=body, fill="black", anchor="ra")
        y += row

    y += 40
    draw.text((900, y), "Subtotal", font=body, fill="black")
    draw.text((W - 90, y), money(inv["subtotal"], cur), font=body, fill="black", anchor="ra")
    y += row
    draw.text((900, y), f"Tax ({disp['tax_pct']}%)", font=body, fill="black")
    draw.text((W - 90, y), money(inv["tax"], cur), font=body, fill="black", anchor="ra")
    y += row
    draw.text((900, y), "Total", font=bold, fill="black")
    draw.text((W - 90, y), money(inv["total"], cur), font=bold, fill="black", anchor="ra")
    return img


def degrade(img, rng):
    """Make a clean render look like a mediocre phone scan."""
    np_rng = np.random.default_rng(rng.randint(0, 2**31 - 1))
    img = img.rotate(rng.uniform(-2.5, 2.5), resample=Image.BICUBIC, fillcolor=(235, 235, 232))
    img = img.filter(ImageFilter.GaussianBlur(radius=rng.uniform(0.8, 1.6)))
    arr = np.asarray(img).astype(np.float32)
    h, w, _ = arr.shape
    gx = np.linspace(rng.uniform(0.80, 0.95), rng.uniform(0.95, 1.05), w)[None, :, None]
    gy = np.linspace(rng.uniform(0.85, 1.0), rng.uniform(0.90, 1.05), h)[:, None, None]
    arr = arr * gx * gy                                   # uneven lighting
    arr = (arr - 128) * rng.uniform(0.75, 0.9) + 128      # lower contrast
    arr += np_rng.normal(0, rng.uniform(9, 16), arr.shape)  # sensor noise
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def degrade_hard(img, rng):
    """Worse than degrade(): more rotation, blur, noise, lighting and contrast loss."""
    np_rng = np.random.default_rng(rng.randint(0, 2**31 - 1))
    img = img.rotate(rng.uniform(-5, 5), resample=Image.BICUBIC, fillcolor=(228, 228, 224))
    img = img.filter(ImageFilter.GaussianBlur(radius=rng.uniform(1.0, 1.8)))
    arr = np.asarray(img).astype(np.float32)
    h, w, _ = arr.shape
    gx = np.linspace(rng.uniform(0.65, 0.9), rng.uniform(0.9, 1.05), w)[None, :, None]
    gy = np.linspace(rng.uniform(0.7, 0.95), rng.uniform(0.85, 1.05), h)[:, None, None]
    arr = arr * gx * gy                                   # strong uneven lighting
    arr = (arr - 128) * rng.uniform(0.6, 0.8) + 128       # low contrast
    arr += np_rng.normal(0, rng.uniform(14, 24), arr.shape)  # heavy sensor noise
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def main(out_root="data/synthetic", count=30, seed=42, levels=LEVELS):
    for level in levels:
        out_dir = Path(out_root) / level
        out_dir.mkdir(parents=True, exist_ok=True)
        for n in range(1, count + 1):
            truth, disp = make_invoice(level, n, seed)
            img = render(truth, disp, compact=level == HARD)
            if level == HARD:
                rng = random.Random(f"{seed}-{level}-{n}-noise")
                degrade_hard(img, rng).save(out_dir / f"{truth['id']}.jpg", quality=rng.randint(15, 30))
            elif level == "level3_noisy":
                rng = random.Random(f"{seed}-{level}-{n}-noise")
                degrade(img, rng).save(out_dir / f"{truth['id']}.jpg", quality=rng.randint(35, 55))
            else:
                img.save(out_dir / f"{truth['id']}.png")
            (out_dir / f"{truth['id']}.json").write_text(json.dumps(truth, indent=2))
        print(f"{level}: {count} invoices in {out_dir}")


if __name__ == "__main__":
    main()