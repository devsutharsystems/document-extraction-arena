"""Document Extraction Arena: a small web app. Run with: streamlit run app.py

Reuses runner/run_models.py (the model call and PROMPT) and runner/score.py (the scoring).
The API key comes from GEMINI_API_KEY or the key field in the Try tab; it is never shown, logged or saved.
"""
import html
import json
import os
import sys
import tempfile
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "runner"))

import run_models  # noqa: E402
import score  # noqa: E402

DATA = ROOT / "data" / "synthetic"
RESULTS = ROOT / "results"
SAMPLE_DIRS = [ROOT / "examples" / "samples", ROOT / "examples" / "my_invoice"]
MODELS = ["gemini-3.1-flash-lite", "gemini-3.6-flash", "gemini-3.8-flash"]
BIG, SMALL = "gemini-3.6-flash", "gemini-3.1-flash-lite"
REPO_URL = "https://github.com/devsutharsystems/document-extraction-arena"
TERMS_URL = "https://ai.google.dev/gemini-api/terms"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}

FIELD_LABELS = {
    "invoice_number": "Invoice number", "vendor": "Vendor", "invoice_date": "Date",
    "currency": "Currency", "subtotal": "Subtotal", "tax": "Tax", "total": "Total",
    "line_items": "Line items",
}

CSS = """
<style>
:root {color-scheme: light;}
.card, .big, .step {color: #111111;}
#MainMenu, footer, [data-testid="stDecoration"] {visibility: hidden; height: 0;}
[data-testid="stToolbar"], [data-testid="stMainMenu"], [data-testid="stAppDeployButton"], .stDeployButton {display: none;}
[data-testid="stHeader"] {background: transparent;}
.block-container {padding-top: 4rem; padding-bottom: 3rem; max-width: 1200px;}
.eyebrow {font-size: .78rem; letter-spacing: .12em; font-weight: 700; color: #B9770E; margin-bottom: .5rem;}
.headline {font-size: 3rem; line-height: 1.05; font-weight: 800; margin: 0 0 .8rem 0;}
.sub {font-size: 1.1rem; color: #444; margin-bottom: 1.2rem;}
.steps {display: flex; flex-wrap: wrap; gap: .75rem; margin-bottom: 1.5rem;}
.step {background: #fff; border: 1px solid #ECE6D8; border-radius: 12px; padding: .6rem 1rem; font-weight: 600;}
.step b {color: #E8A33D; margin-right: .5rem;}
.card {background: #fff; border: 1px solid #ECE6D8; border-radius: 14px; padding: .9rem 1.1rem; margin-bottom: .7rem;}
.card .top {display: flex; justify-content: space-between; align-items: center; margin-bottom: .4rem;}
.card .lbl {font-weight: 700;}
.card .kv {font-size: .92rem; color: #333; word-break: break-word;}
.card .kv span {color: #777; display: inline-block; min-width: 7.5rem;}
.badge {border-radius: 999px; padding: .15rem .7rem; font-size: .78rem; font-weight: 700;}
.ok {background: #DDF3E1; color: #17692B;}
.bad {background: #FBDADA; color: #A32020;}
.na {background: #E8E6E1; color: #555;}
.big {background: #fff; border: 1px solid #ECE6D8; border-radius: 16px; padding: 1.2rem 1.4rem; height: 100%;}
.big .who {font-size: .85rem; font-weight: 700; color: #666;}
.big .num {font-size: 2.4rem; font-weight: 800; line-height: 1.15;}
.big .small {font-size: .9rem; color: #555;}
.big.accent {border: 2px solid #E8A33D;}
.tag {display: inline-block; background: #FCEBCB; color: #7A4B00; border-radius: 999px; padding: .2rem .8rem; font-size: .8rem; font-weight: 700; margin-bottom: .8rem;}
.score {display: inline-block; font-size: 1.5rem; font-weight: 800; border-radius: 14px; padding: .4rem 1rem; margin-bottom: .8rem;}
.note {background: #FFF6E3; border: 1px solid #F1D79B; border-radius: 12px; padding: .7rem 1rem; font-size: .9rem;}
.foot {text-align: center; color: #777; font-size: .85rem; margin-top: 3rem;}
</style>
"""


def esc(x):
    return html.escape("" if x is None else str(x))


def badge(status):
    cls, text = {"ok": ("ok", "Correct"), "bad": ("bad", "Wrong"), "na": ("na", "No answer key")}[status]
    return f'<span class="badge {cls}">{text}</span>'


def show(x):
    if isinstance(x, float) and x == int(x):
        return f"{x:.2f}"
    return "—" if x is None else str(x)


def line_item_rows(truth_items, pred_items):
    """Per AI-returned line: does it match a key line (same description, quantity, price, amount)?
    Uses the scorer's own helpers so the ticks agree with the score."""
    by_desc = {score.norm_text(t["description"]): t for t in (truth_items or [])}
    rows = []
    for p in pred_items if isinstance(pred_items, list) else []:
        if not isinstance(p, dict):
            continue
        t = by_desc.get(score.norm_text(p.get("description", "")))
        if truth_items is None:
            mark = "?"
        else:
            ok = t is not None and all(score.money_equal(p.get(k), t[k]) for k in ("quantity", "unit_price", "amount"))
            mark = "✓" if ok else "✗"
        rows.append({"": mark, "Description": p.get("description"), "Qty": p.get("quantity"),
                     "Unit price": p.get("unit_price"), "Amount": p.get("amount")})
    return rows


def evaluate(truth, pred):
    """({field: 'ok'|'bad'|'na'}, fields_correct) for one invoice."""
    if truth is None:
        return {f: "na" for f in FIELD_LABELS}, None
    scores, _ = score.score_invoice(truth, pred)
    status = {f: ("ok" if v == 1.0 else "bad") for f, v in scores.items()}
    return status, sum(v == "ok" for v in status.values())


def render_fields(truth, pred, status, n_correct):
    if n_correct is not None:
        good = n_correct == len(FIELD_LABELS)
        st.markdown(f'<div class="score {"ok" if good else "bad"}">{n_correct} / {len(FIELD_LABELS)} fields correct</div>',
                    unsafe_allow_html=True)
    else:
        st.markdown('<div class="score na">No answer key to check against</div>', unsafe_allow_html=True)
    pred = pred or {}
    for f, label in FIELD_LABELS.items():
        if f == "line_items":
            continue
        correct = f'<div class="kv"><span>Correct answer</span>{esc(show(truth[f]))}</div>' if truth else ""
        st.markdown(f'<div class="card"><div class="top"><div class="lbl">{label}</div>{badge(status[f])}</div>'
                    f'<div class="kv"><span>AI read</span>{esc(show(pred.get(f)))}</div>{correct}</div>',
                    unsafe_allow_html=True)
    rows = line_item_rows(truth["line_items"] if truth else None, pred.get("line_items"))
    n_truth = f" (answer key has {len(truth['line_items'])})" if truth else ""
    st.markdown(f'<div class="card"><div class="top"><div class="lbl">Line items{esc(n_truth)}</div>'
                f'{badge(status["line_items"])}</div></div>', unsafe_allow_html=True)
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    else:
        st.caption("The AI returned no line items.")


def friendly_error(err):
    if "429" in err or "RESOURCE_EXHAUSTED" in err:
        return "Today's free quota for this model is used up. Try again tomorrow or pick another model."
    if "503" in err or "UNAVAILABLE" in err:
        return "Google is busy right now. Try again in a few minutes."
    if "API key" in err or "401" in err or "403" in err or "API_KEY" in err:
        return "Google did not accept the API key. Check it and try again."
    return "The model call failed. Try again in a few minutes."


SAMPLE_NAMES = {  # file name (no extension) -> name shown in the picker
    "sample_01": "US software invoice (USD)",
    "sample_02": "UK print shop (GBP)",
    "sample_03": "Indian GST bill, phone photo (INR)",
    "level1_clean_001": "Test set, level 1: clean (INR)",
    "level2_mixed_003": "Test set, level 2: US date 05/10/2026 (USD)",
    "level3_noisy_005": "Test set, level 3: scan noise",
    "level4_hard_014": "Test set, level 4: hard, ambiguous date",
    "my_001": "Worked example (fictional invoice)",
}


def list_samples():
    """{picker name: image path}, readable names first, in the order of SAMPLE_NAMES."""
    found = {}
    for d in SAMPLE_DIRS:
        if d.is_dir():
            for p in sorted(d.iterdir()):
                if p.suffix.lower() in IMAGE_SUFFIXES:
                    found[p.stem] = p
    order = [s for s in SAMPLE_NAMES if s in found] + [s for s in found if s not in SAMPLE_NAMES]
    return {SAMPLE_NAMES.get(s, s): found[s] for s in order}


def run_once(model, image_bytes, suffix, api_key):
    """One request, no retries. The image goes to a temp folder outside the repo."""
    suffix = ".jpg" if suffix.lower() in (".jpg", ".jpeg") else ".png"
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / f"upload{suffix}"
        path.write_bytes(image_bytes)
        return run_models.extract(model, path, no_retry=True, client=run_models.make_client(api_key))


def header():
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown('<div class="eyebrow">DOCUMENT EXTRACTION ARENA · AN LDS PROJECT</div>'
                '<div class="headline">Read the invoice.<br>Check every field.</div>'
                '<div class="sub">See how well AI models read invoices, field by field, against a known answer.</div>'
                '<div class="steps"><div class="step"><b>01</b>Pick an invoice</div>'
                '<div class="step"><b>02</b>Let the AI read it</div>'
                '<div class="step"><b>03</b>See what it got right</div></div>', unsafe_allow_html=True)


def tab_try():
    env_key = os.environ.get("GEMINI_API_KEY", "")
    samples = list_samples()
    source = st.radio("Where is the invoice?", ["Use a sample", "Upload your own"], horizontal=True)
    image_bytes = suffix = truth = name = None
    if source == "Use a sample":
        choice = st.selectbox("Use a sample", list(samples))
        if choice:
            p = samples[choice]
            image_bytes, suffix, name = p.read_bytes(), p.suffix, choice
            key_path = p.with_suffix(".json")
            truth = json.loads(key_path.read_text()) if key_path.exists() else None
    else:
        st.markdown(f'<div class="note">On the free tier, Google may use uploaded content to improve its products '
                    f'(<a href="{TERMS_URL}" target="_blank">terms</a>). Use samples, not real invoices with '
                    f'personal or business data.</div>', unsafe_allow_html=True)
        up = st.file_uploader("Invoice image", type=["png", "jpg", "jpeg"])
        key_up = st.file_uploader("Answer key (optional JSON)", type=["json"])
        if up:
            image_bytes, suffix, name = up.getvalue(), Path(up.name).suffix, up.name
        if key_up:
            try:
                truth = json.loads(key_up.getvalue())
                for f in list(score.SCALAR_FIELDS) + ["line_items"]:
                    truth[f]
            except (ValueError, KeyError, TypeError):
                truth = None
                st.warning("That answer key is missing fields or is not valid JSON, so it will be ignored. "
                           "It needs: " + ", ".join(list(score.SCALAR_FIELDS) + ["line_items"]) + ".")

    model = st.selectbox("Model", MODELS, index=0, key="try_model")
    typed = st.text_input("Your Gemini API key (free from Google AI Studio)", type="password", key="api_key_input",
                          disabled=bool(env_key),
                          placeholder="Using the GEMINI_API_KEY environment variable" if env_key else "")
    st.caption("Your key is used only for this session and is never saved.")
    api_key = env_key or typed
    if st.button("Run", type="primary", disabled=image_bytes is None):
        if not api_key:
            st.session_state["result"] = {"message": "Please add your Gemini API key above the Run button first."}
        else:
            with st.spinner("The AI is reading the invoice…"):
                res = run_once(model, image_bytes, suffix, api_key)
            st.session_state["result"] = {"res": res, "truth": truth, "image": image_bytes, "model": model, "name": name}

    out = st.session_state.get("result")
    if not out:
        return
    if "message" in out:
        st.info(out["message"])
        return
    res = out["res"]
    if res["error"]:
        st.error(friendly_error(res["error"]))
        return
    pred = score.parse_response(res["response_text"])
    if pred is None:
        st.error("The AI answered, but not in a form we could read. Try again.")
        return
    status, n_correct = evaluate(out["truth"], pred)
    left, right = st.columns([1, 1.1], gap="large")
    with left:
        st.image(out["image"], caption=out["name"], width="stretch")
    with right:
        render_fields(out["truth"], pred, status, n_correct)
    tokens = res["input_tokens"] + res["output_tokens"] + res["thinking_tokens"]
    p_in, p_out = score.PRICES.get(out["model"], (0, 0))
    cost = (res["input_tokens"] * p_in + (res["output_tokens"] + res["thinking_tokens"]) * p_out) / 1e6
    st.caption(f"Time: {res['seconds']} s · Tokens: {tokens:,} · Paid-tier equivalent cost: ${cost:.5f} "
               "(you are on the free tier, so nothing is charged).")


def read_csv(name):
    p = RESULTS / name
    return pd.read_csv(p) if p.exists() else None


def big_card(title, row, accent=False):
    n = int(row.n)
    exact = round(row.exact_invoice_pct / 100 * n)
    st.markdown(f'<div class="big {"accent" if accent else ""}"><div class="who">{esc(title)}</div>'
                f'<div class="num">{exact} of {n} fully correct</div>'
                f'<div class="small">Accuracy {row.accuracy_pct}% · Average {row.avg_seconds} s per invoice · '
                f'Cost ${row.cost_per_invoice_usd:.5f} per invoice (paid-tier equivalent)</div></div>',
                unsafe_allow_html=True)


def shared_level4_ids(per_invoice, n):
    ok = per_invoice[(per_invoice.level == "level4_hard") & ~per_invoice.api_error]
    ids = set(ok[ok.model == BIG].id) & set(ok[ok.model == SMALL].id)
    return sorted(ids)[:n]


def field_error_counts(per_inv, ids):
    """Long table (Field, Model, Wrong): invoices among `ids` where the field scored below 1."""
    rows = []
    for model in (SMALL, BIG):
        sub = per_inv[per_inv.id.isin(ids) & (per_inv.model == model) & ~per_inv.api_error]
        for f, label in FIELD_LABELS.items():
            rows.append({"Field": label, "Model": model, "Wrong": int((sub[f"f_{f}"] < 1).sum())})
    return pd.DataFrame(rows)


def error_chart(counts, n):
    """Grouped (side-by-side) horizontal bars with value labels."""
    enc = dict(
        y=alt.Y("Field:N", sort=list(FIELD_LABELS.values()), title=None, axis=alt.Axis(labelLimit=200)),
        yOffset=alt.YOffset("Model:N", sort=[SMALL, BIG]),
    )
    x = alt.X("Wrong:Q", title=f"Invoices with this field wrong (out of {n})",
              scale=alt.Scale(domain=[0, int(counts.Wrong.max()) + 1], nice=False),
              axis=alt.Axis(tickMinStep=1, format="d"))
    color = alt.Color("Model:N", scale=alt.Scale(domain=[SMALL, BIG], range=["#555555", "#E8A33D"]),
                      legend=alt.Legend(orient="top", title=None))
    bars = alt.Chart(counts).mark_bar(size=20).encode(x=x, color=color, **enc)
    labels = alt.Chart(counts).transform_filter(alt.datum.Wrong > 0).mark_text(align="left", dx=4, color="#111111").encode(
        x="Wrong:Q", text=alt.Text("Wrong:Q", format="d"), **enc)
    return (bars + labels).properties(height=420, background="transparent").configure_view(strokeWidth=0)


def tab_results():
    same, summary, per_inv = read_csv("summary_same_invoices.csv"), read_csv("summary.csv"), read_csv("per_invoice.csv")
    if same is None or summary is None or per_inv is None:
        st.info("The results files are not here yet. Run the scorer first: python runner/score.py")
        return
    l4 = same[same.level == "level4_hard"].set_index("model")
    if BIG in l4.index and SMALL in l4.index:
        n = int(l4.loc[BIG, "n"])
        st.markdown(f'<span class="tag">Preliminary · {n} hard invoices</span>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            big_card(f"Bigger model ({BIG})", l4.loc[BIG], accent=True)
        with c2:
            big_card(f"Small model ({SMALL})", l4.loc[SMALL])
        st.caption("Same invoices for both models. Small sample: this says nothing about the other hard invoices "
                   "or the easier levels, where only the small model was run.")
        st.subheader("Which fields went wrong?")
        counts = field_error_counts(per_inv, shared_level4_ids(per_inv, n))
        st.altair_chart(error_chart(counts, n), width="stretch")
    else:
        st.info("The comparison file does not contain both models yet.")

    st.subheader(f"The small model ({SMALL}) on all four levels")
    t = summary[summary.model == SMALL][["level", "n", "accuracy_pct", "exact_invoice_pct", "avg_seconds", "cost_per_invoice_usd"]]
    t.columns = ["Level", "Invoices", "Accuracy %", "Fully correct %", "Avg seconds", "Cost per invoice ($)"]
    st.dataframe(t, hide_index=True, width="stretch")

    st.subheader("Inspect an invoice")
    levels = sorted(p.name for p in DATA.iterdir() if p.is_dir()) if DATA.is_dir() else []
    if not levels:
        return
    c1, c2 = st.columns(2)
    level = c1.selectbox("Level", levels, index=levels.index("level4_hard") if "level4_hard" in levels else 0,
                         key="inspect_level")
    inv_ids = sorted(p.stem for p in (DATA / level).glob("*.json"))
    default_inv = inv_ids.index("level4_hard_014") if "level4_hard_014" in inv_ids else 0  # a known date mistake
    inv = c2.selectbox("Invoice", inv_ids, index=default_inv, key=f"inspect_inv_{level}")
    answered = []
    for d in sorted((RESULTS / "raw").iterdir()) if (RESULTS / "raw").is_dir() else []:
        f = d / f"{inv}.json"
        if f.exists() and json.loads(f.read_text()).get("error") is None:
            answered.append(d.name)
    if not answered:
        st.info("No model has a saved answer for this invoice.")
        return
    model = st.selectbox("Model", answered, index=answered.index(SMALL) if SMALL in answered else 0,
                         key=f"inspect_model_{inv}")
    truth = json.loads((DATA / level / f"{inv}.json").read_text())
    res = json.loads((RESULTS / "raw" / model / f"{inv}.json").read_text())
    pred = score.parse_response(res["response_text"])
    img = next(p for p in (DATA / level).glob(inv + ".*") if p.suffix.lower() in IMAGE_SUFFIXES)
    status, n_correct = evaluate(truth, pred)
    left, right = st.columns([1, 1.1], gap="large")
    with left:
        st.image(str(img), caption=inv, width="stretch")
    with right:
        render_fields(truth, pred, status, n_correct)


def tab_how():
    st.markdown(f"""
This project tests how well AI models read invoices. The invoices are **synthetic**: a program makes them up, so it
already knows the right answer for every field (the *answer key*). Each model gets only the picture and has to
return the invoice number, vendor, date, currency, subtotal, tax, total and line items.

Marking is done by **plain code, field by field, with no AI judge**. Money must match to the cent, text must match
after ignoring spaces and capitals, and dates must match exactly. An invoice counts as "fully correct" only when all
8 fields are right.

There are four levels. **Level 1** is a clean image. **Level 2** mixes currencies, date styles and number formats.
**Level 3** adds phone-scan noise and blur. **Level 4** has many more line items, smaller text, dates like 05/10/2026
that can be read two ways, and heavier degradation.

What the results can't tell you: the invoices are synthetic and all use one layout, the model comparison covers only a
small sample of 16 hard invoices, and some hard invoices turned out to be unfairly hard even for a person. Don't treat
these numbers as how a model will do on your real documents.

Code, data and full write-up: [{REPO_URL}]({REPO_URL})
""")


def main():
    st.set_page_config(page_title="Document Extraction Arena", layout="wide", initial_sidebar_state="collapsed")
    header()
    t1, t2, t3 = st.tabs(["Try an invoice", "Results", "How it works"])
    with t1:
        tab_try()
    with t2:
        tab_results()
    with t3:
        tab_how()
    st.markdown('<div class="foot">Synthetic invoices · Free-tier runs · Your API key is used only for this session and is never saved.</div>',
                unsafe_allow_html=True)


if __name__ == "__main__":
    main()
