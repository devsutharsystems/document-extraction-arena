import json
from PIL import Image, ImageDraw, ImageFont

FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"
FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"

with open("generator/sample_truth.json") as f:
    inv = json.load(f)

W, H = 1240, 1754  # an A4 page at about 150 dpi
img = Image.new("RGB", (W, H), "white")
draw = ImageDraw.Draw(img)

title = ImageFont.truetype(FONT_BOLD, 44)
bold = ImageFont.truetype(FONT_BOLD, 26)
body = ImageFont.truetype(FONT, 26)


def money(x):
    return f"{x:,.2f}"  # 2549.97 -> "2,549.97"


# header
draw.text((90, 80), inv["vendor"], font=title, fill="black")
draw.text((W - 90, 80), "INVOICE", font=title, fill="black", anchor="ra")
draw.text((90, 200), f"Invoice no: {inv['invoice_number']}", font=body, fill="black")
draw.text((90, 245), f"Date: {inv['invoice_date']}", font=body, fill="black")
draw.text((90, 290), f"Currency: {inv['currency']}", font=body, fill="black")

# table header
y = 380
draw.text((90, y), "Description", font=bold, fill="black")
draw.text((700, y), "Qty", font=bold, fill="black", anchor="ra")
draw.text((900, y), "Unit price", font=bold, fill="black", anchor="ra")
draw.text((W - 90, y), "Amount", font=bold, fill="black", anchor="ra")
draw.line((90, y + 40, W - 90, y + 40), fill="black", width=2)

# one row per line item
y += 65
for item in inv["line_items"]:
    draw.text((90, y), item["description"], font=body, fill="black")
    draw.text((700, y), str(item["quantity"]), font=body, fill="black", anchor="ra")
    draw.text((900, y), money(item["unit_price"]), font=body, fill="black", anchor="ra")
    draw.text((W - 90, y), money(item["amount"]), font=body, fill="black", anchor="ra")
    y += 50

# totals
y += 40
draw.text((900, y), "Subtotal", font=body, fill="black")
draw.text((W - 90, y), money(inv["subtotal"]), font=body, fill="black", anchor="ra")
y += 50
draw.text((900, y), "Tax", font=body, fill="black")
draw.text((W - 90, y), money(inv["tax"]), font=body, fill="black", anchor="ra")
y += 50
draw.text((900, y), "Total", font=bold, fill="black")
draw.text((W - 90, y), money(inv["total"]), font=bold, fill="black", anchor="ra")

img.save("data/sample_invoice.png")
print("saved data/sample_invoice.png")