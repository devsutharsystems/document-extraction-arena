import time

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client()  # reads GEMINI_API_KEY from the environment

# Step A: list the models your key can use, then pick a Flash-Lite and a Flash.
for m in client.models.list():
    print(m.name)

# Step B: paste an exact name from the list above (for example "gemini-...-flash-lite"),
# then run the extraction below.
MODEL = "gemini-3.5-flash-lite"

with open("data/synthetic/level1_clean/level1_clean_001.png", "rb") as f:
    img = f.read()

PROMPT = (
    "Extract this invoice as JSON with keys: invoice_number, vendor, "
    "invoice_date (YYYY-MM-DD), currency (ISO code), "
    "line_items (description, quantity, unit_price, amount), subtotal, tax, total. "
    "Return only the JSON."
)

start = time.time()
resp = client.models.generate_content(
    model=MODEL,
    contents=[types.Part.from_bytes(data=img, mime_type="image/png"), PROMPT],
)
print(resp.text)
print("seconds:", round(time.time() - start, 2))
print("input tokens:", resp.usage_metadata.prompt_token_count,
      "| output tokens:", resp.usage_metadata.candidates_token_count)