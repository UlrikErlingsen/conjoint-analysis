from __future__ import annotations

import os

# pyarrow's bundled mimalloc allocator can segfault on macOS when Streamlit
# serializes tables from a worker thread; the system allocator is stable.
# Must be set before Arrow creates its default memory pool.
os.environ.setdefault("ARROW_DEFAULT_MEMORY_POOL", "system")

import base64
import hashlib
import inspect
import json
import platform
import sys
import traceback
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from choicesignal import __version__
from choicesignal.conjoint import (
    ConjointDesign,
    adjust_shares,
    build_design,
    cannibalization_report,
    design_report,
    estimate_conjoint,
    ideal_products,
    optimal_products,
    simulate_shares,
)
from choicesignal.errors import DataProblem, friendly_message
from choicesignal.io import LoadedData, load_data, results_to_excel, results_to_json, safe_for_spreadsheet


MARK_URI = "data:image/svg+xml;base64," + base64.b64encode(
    (ROOT / "assets" / "choicesignal-mark.svg").read_bytes()
).decode("ascii")

PAGES = [
    "Welcome",
    "1 · Data & design",
    "2 · Utilities & importance",
    "3 · Simulate & export",
    "Methods & limits",
]

CAUTION = (
    "**Treat these results as decision support, not predicted market shares.** Ratings describe stated "
    "preferences for hypothetical profiles. Real choices also depend on awareness, availability, budgets, "
    "habits, and competitors outside the study."
)

_USES_STRETCH_WIDTH = "width" in inspect.signature(st.button).parameters


def full_width(widget, *args, **kwargs):
    """Use Streamlit's full-width API across both older and newer releases."""
    if _USES_STRETCH_WIDTH:
        kwargs["width"] = "stretch"
    else:
        kwargs["use_container_width"] = True
    return widget(*args, **kwargs)


st.set_page_config(page_title="ChoiceSignal | Open conjoint analysis", page_icon="◈", layout="wide")
st.markdown(
    """
    <style>
    :root {
        --cs-ink: #17322e; --cs-deep: #102c2a; --cs-teal: #173c3a;
        --cs-coral: #d95b40; --cs-mint: #83d2b4; --cs-gold: #f2c66d;
        --cs-paper: #f8f5ed; --cs-line: rgba(23, 50, 46, 0.14);
    }
    [data-testid="stAppViewContainer"] {
        background: radial-gradient(circle at 93% 2%, rgba(242,198,109,.20), transparent 27rem),
                    linear-gradient(180deg,#fbf9f3 0%,var(--cs-paper) 100%);
    }
    [data-testid="stHeader"] { background: rgba(248,245,237,.78); }
    [data-testid="stSidebar"] { background: linear-gradient(165deg,#173c3a 0%,#102c2a 65%,#0c2422 100%); }
    [data-testid="stSidebar"] h1,[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] p,[data-testid="stSidebar"] label,[data-testid="stSidebar"] span { color:#f8f5ed; }
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p { color:#b9cbc5; }
    [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] { background:rgba(255,255,255,.06); border-color:rgba(242,198,109,.32); }
    [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] small,
    [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] small span { color:#b9cbc5 !important; }
    [data-testid="stSidebar"] button { border-color:rgba(255,255,255,.23); }
    [data-testid="stSidebar"] [data-testid="stButton"] button { background:rgba(255,255,255,.08); color:#f8f5ed !important; }
    [data-testid="stSidebar"] [data-testid="stButton"] button:hover { background:rgba(242,198,109,.16); border-color:rgba(242,198,109,.48); }
    [data-testid="stSidebar"] [data-testid="stButton"] button p,
    [data-testid="stSidebar"] [data-testid="stButton"] button span { color:#f8f5ed !important; }
    [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] button { background:#f8f5ed; color:#17322e !important; }
    [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] button * { color:#17322e !important; }
    .block-container { max-width:1240px; padding-top:4.4rem; padding-bottom:4rem; }
    h1,h2,h3 { color:var(--cs-ink); letter-spacing:-.025em; }
    a { color:#9b3e2b; }
    [data-testid="stMetric"] { background:rgba(255,255,255,.75); border:1px solid var(--cs-line); border-radius:16px; padding:1rem 1.05rem; box-shadow:0 8px 28px rgba(23,50,46,.045); }
    [data-testid="stMetricValue"] { color:var(--cs-ink); }
    .stButton > button[kind="primary"] { background:linear-gradient(135deg,#e26748,#c94c34); color:white; border:0; box-shadow:0 8px 20px rgba(217,91,64,.22); font-weight:750; }
    .stButton > button[kind="primary"]:hover { background:linear-gradient(135deg,#c94c34,#b63f2b); color:white; }
    [data-testid="stExpander"],[data-testid="stAlert"],[data-testid="stVerticalBlockBorderWrapper"] { border-radius:14px; }
    .cs-brand { padding:.25rem 0 1.1rem; }
    .cs-lockup { display:flex; align-items:center; gap:.65rem; }
    .cs-mark { width:38px; height:38px; }
    .cs-name { color:white; font-size:1.28rem; line-height:1; font-weight:850; letter-spacing:-.04em; }
    .cs-name span { color:#f2c66d !important; }
    .cs-tag { margin:.55rem 0 0 !important; color:#b9cbc5 !important; font-size:.77rem; line-height:1.4; }
    .cs-masthead { display:flex; justify-content:space-between; align-items:center; gap:1rem; padding:.72rem 1rem .72rem .78rem; margin-bottom:1.35rem; background:rgba(255,255,255,.65); border:1px solid var(--cs-line); border-radius:18px; box-shadow:0 10px 36px rgba(23,50,46,.05); }
    .cs-masthead .cs-mark { width:48px; height:48px; }
    .cs-wordmark { color:var(--cs-ink); font-weight:850; letter-spacing:-.045em; font-size:1.55rem; line-height:1; }
    .cs-wordmark span { color:var(--cs-coral); }
    .cs-kicker { margin-top:.32rem; color:#59716c; font-size:.67rem; font-weight:800; letter-spacing:.13em; }
    .cs-promise { color:#47645e; font-size:.78rem; font-weight:700; white-space:nowrap; }
    .cs-promise span { color:var(--cs-coral); padding:0 .3rem; }
    .cs-hero { position:relative; overflow:hidden; padding:clamp(1.7rem,4vw,3.4rem); margin-bottom:1.3rem; background:linear-gradient(135deg,#173c3a 0%,#102c2a 75%); border-radius:26px; box-shadow:0 18px 50px rgba(23,50,46,.17); }
    .cs-hero:after { content:""; position:absolute; width:310px; height:310px; right:-100px; top:-135px; border-radius:50%; border:58px solid rgba(242,198,109,.14); }
    .cs-eyebrow { color:#f2c66d; font-size:.72rem; font-weight:850; letter-spacing:.16em; }
    .cs-hero h1 { color:white; font-size:clamp(2.25rem,5vw,4.7rem); line-height:.97; margin:.75rem 0 1rem; max-width:900px; }
    .cs-hero h1 em { color:#83d2b4; font-style:normal; }
    .cs-hero p { color:#d7e3df; font-size:1.06rem; line-height:1.6; max-width:780px; }
    .cs-pills { display:flex; flex-wrap:wrap; gap:.55rem; margin-top:1.15rem; }
    .cs-pill { padding:.4rem .72rem; border:1px solid rgba(255,255,255,.16); border-radius:999px; color:#f8f5ed; font-size:.78rem; font-weight:700; background:rgba(255,255,255,.055); }
    .cs-step { height:100%; padding:1.2rem 1.2rem 1rem; background:rgba(255,255,255,.66); border:1px solid var(--cs-line); border-radius:18px; }
    .cs-step b { color:var(--cs-coral); font-size:.72rem; letter-spacing:.12em; }
    .cs-step h3 { margin:.4rem 0 .5rem; }
    .cs-step p { color:#59716c; font-size:.9rem; line-height:1.55; }
    .cs-footer { margin-top:3.2rem; padding-top:1rem; border-top:1px solid var(--cs-line); color:#617670; font-size:.76rem; text-align:center; }
    .cs-footer span { color:var(--cs-coral); padding:0 .38rem; }
    @media (max-width:760px) { .cs-promise{display:none}.cs-hero{border-radius:20px} }
    </style>
    """,
    unsafe_allow_html=True,
)


def show_error(exc: Exception) -> None:
    st.error(friendly_message(exc))
    if not isinstance(exc, DataProblem) and os.getenv("CHOICESIGNAL_DEBUG") == "1":
        with st.expander("Technical details"):
            st.code("".join(traceback.format_exception(exc)))


def set_loaded(loaded: LoadedData) -> None:
    st.session_state["tables"] = loaded.tables
    st.session_state["source_name"] = loaded.source_name
    st.session_state["active_table"] = next(iter(loaded.tables))
    for key in ("study", "result", "products", "shares", "optimal"):
        st.session_state.pop(key, None)


def load_demo(filename: str) -> None:
    set_loaded(load_data(ROOT / "examples" / filename))


def current_frame() -> pd.DataFrame | None:
    tables = st.session_state.get("tables")
    if not tables:
        return None
    name = st.session_state.get("active_table", next(iter(tables)))
    return tables[name]


def require_data() -> pd.DataFrame | None:
    frame = current_frame()
    if frame is None:
        st.info("Bring a CSV, Excel, or JSON ratings file in the sidebar—or use a fictional demo study.")
    return frame


def masthead() -> None:
    st.markdown(
        f"""
        <div class="cs-masthead"><div class="cs-lockup"><img class="cs-mark" src="{MARK_URI}"/>
        <div><div class="cs-wordmark">Choice<span>Signal</span></div><div class="cs-kicker">OPEN CONJOINT ANALYSIS</div></div></div>
        <div class="cs-promise">Local-first <span>•</span> Explainable <span>•</span> Open source</div></div>
        """,
        unsafe_allow_html=True,
    )


for key, default in (
    ("tables", None), ("source_name", None), ("active_table", None),
    ("upload_epoch", 0), ("_uploader_had_file", False),
    ("nav_target", PAGES[0]), ("nav_epoch", 0),
):
    st.session_state.setdefault(key, default)


def go_to(page_name: str) -> None:
    """Navigate programmatically.

    The sidebar radio is re-created with a fresh key so it adopts ``nav_target``
    even when a rerun interrupted the script before the radio was drawn.
    """
    st.session_state["nav_target"] = page_name
    st.session_state["nav_epoch"] = int(st.session_state["nav_epoch"]) + 1


with st.sidebar:
    st.markdown(
        f"<div class='cs-brand'><div class='cs-lockup'><img class='cs-mark' src='{MARK_URI}'/><div class='cs-name'>Choice<span>Signal</span></div></div><p class='cs-tag'>Know what customers actually value.</p></div>",
        unsafe_allow_html=True,
    )
    st.markdown("### 1. Bring your ratings")
    uploaded = st.file_uploader(
        "CSV, Excel, or JSON",
        type=["csv", "xlsx", "xls", "xlsm", "json"],
        key=f"ratings_upload_{st.session_state['upload_epoch']}",
    )
    if uploaded is not None:
        upload_identity = (
            str(getattr(uploaded, "file_id", "") or f"widget-{st.session_state['upload_epoch']}"),
            uploaded.name,
            int(getattr(uploaded, "size", 0)),
        )
        st.session_state["_uploader_had_file"] = True
        if st.session_state.get("upload_identity") != upload_identity:
            try:
                raw = uploaded.getvalue()
                set_loaded(load_data(raw, name=uploaded.name))
                st.session_state["upload_identity"] = upload_identity
                st.session_state["_uploader_had_file"] = False
                st.session_state["upload_epoch"] = int(st.session_state.get("upload_epoch", 0)) + 1
                go_to("1 · Data & design")
                st.rerun()
            except Exception as exc:
                show_error(exc)
    elif st.session_state.get("_uploader_had_file"):
        st.session_state["_uploader_had_file"] = False
    if full_width(st.button, "Demo · coffee subscriptions"):
        load_demo("demo_coffee_ratings.csv")
        go_to("1 · Data & design")
        st.rerun()
    if full_width(st.button, "Demo · car buyers"):
        load_demo("demo_car_ratings.csv")
        go_to("1 · Data & design")
        st.rerun()
    if full_width(st.button, "Demo · streaming plans"):
        load_demo("demo_streaming_ratings.csv")
        go_to("1 · Data & design")
        st.rerun()
    with st.expander("What are the demos?"):
        st.caption(
            "**Coffee subscriptions:** 300 fictional respondents rated 14 subscription profiles each "
            "(brand, price, beans, delivery).\n\n"
            "**Car buyers:** 350 fictional respondents rated 16 car profiles each (brand origin, body, "
            "engine, price). This one hides two different taste groups — try exporting the part-worths "
            "into SegmentSignal to find them.\n\n"
            "**Streaming plans:** 150 fictional respondents rated 12 plan profiles each "
            "(price, quality, ads, screens).\n\n"
            "Every record is synthetic. `examples/ratings_template.csv` shows the expected shape."
        )
    if st.session_state.get("tables") and full_width(st.button, "Clear session data"):
        for key in (
            "tables", "source_name", "active_table", "upload_identity", "_uploader_had_file",
            "study", "result", "products", "shares", "optimal",
        ):
            st.session_state.pop(key, None)
        st.session_state["upload_epoch"] = int(st.session_state.get("upload_epoch", 0)) + 1
        go_to("Welcome")
        st.rerun()
    if st.session_state.get("tables"):
        table_names = list(st.session_state["tables"])
        selected_table = st.selectbox(
            "Table / sheet",
            table_names,
            index=table_names.index(st.session_state.get("active_table"))
            if st.session_state.get("active_table") in table_names
            else 0,
        )
        if selected_table != st.session_state.get("active_table"):
            st.session_state["active_table"] = selected_table
            for key in ("study", "result", "products", "shares", "optimal"):
                st.session_state.pop(key, None)
        active = st.session_state["tables"][selected_table]
        st.caption(f"{st.session_state.get('source_name')} · {len(active):,} rows × {len(active.columns)} columns")
    st.markdown("### 2. Follow the workflow")
    page = st.radio(
        "Page",
        PAGES,
        index=PAGES.index(st.session_state["nav_target"]),
        key=f"nav_radio_{st.session_state['nav_epoch']}",
        label_visibility="collapsed",
    )
    st.session_state["nav_target"] = page

masthead()


def welcome_page() -> None:
    st.markdown(
        """
        <section class="cs-hero"><div class="cs-eyebrow">CONJOINT ANALYSIS, WITHOUT THE BLACK BOX</div>
        <h1>From simple ratings to <em>what customers value.</em></h1>
        <p>Upload ratings of product profiles. ChoiceSignal estimates how much every feature level is worth to your respondents, which attributes drive preference, and how candidate products would split preference between them.</p>
        <div class="cs-pills"><span class="cs-pill">No account</span><span class="cs-pill">No telemetry</span><span class="cs-pill">Per-respondent estimates</span><span class="cs-pill">Honest design warnings</span></div></section>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(CAUTION)
    st.write("")
    columns = st.columns(3)
    steps = [
        ("STEP 01", "Map the study", "Tell the app which columns hold the respondent, the rating, and the product attributes. The design is health-checked first."),
        ("STEP 02", "Estimate utilities", "Each respondent's ratings become part-worth utilities per feature level, with attribute importance and fit quality."),
        ("STEP 03", "Simulate and export", "Define candidate products, compare preference shares, and export every estimate with a full audit trail."),
    ]
    for column, (number, title, body) in zip(columns, steps):
        column.markdown(f"<div class='cs-step'><b>{number}</b><h3>{title}</h3><p>{body}</p></div>", unsafe_allow_html=True)
    st.write("")
    metric_columns = st.columns(4)
    metric_columns[0].metric("Input formats", "5", "CSV · Excel · JSON")
    metric_columns[1].metric("Estimation", "OLS", "per respondent + pooled")
    metric_columns[2].metric("Attributes", "up to 10", "12 levels each")
    metric_columns[3].metric("Data stored", "None", "by the app")
    with st.expander("Where this tool fits"):
        st.write(
            "ChoiceSignal covers ratings-based (full-profile) conjoint: respondents rate complete product profiles, "
            "and regression turns the ratings into feature values. WorthSignal covers customer value and retention; "
            "SegmentSignal covers customer segmentation. Choice-based conjoint with hierarchical Bayes estimation "
            "is a different, more complex method and is outside this first release."
        )


def data_page() -> None:
    st.title("Map the study design")
    st.write("One row = one respondent rating one product profile. The columns describe the profile.")
    frame = require_data()
    if frame is None:
        return

    top = st.columns(4)
    top[0].metric("Rows (ratings)", f"{len(frame):,}")
    top[1].metric("Columns", len(frame.columns))
    top[2].metric("Missing cells", f"{int(frame.isna().sum().sum()):,}")
    top[3].metric("Duplicate rows", f"{int(frame.duplicated().sum()):,}")
    full_width(st.dataframe, frame.head(12), hide_index=True)

    columns = [str(column) for column in frame.columns]
    respondent_guess = next(
        (index for index, column in enumerate(columns) if "respondent" in column.lower() or column.lower().endswith("id")),
        0,
    )
    respondent_column = st.selectbox("Respondent ID column", columns, index=respondent_guess)
    rating_hints = [index for index, column in enumerate(columns) if any(
        token in column.lower() for token in ("rating", "score", "liking", "preference", "eval")
    )]
    rating_column = st.selectbox("Rating column (higher = better)", columns, index=rating_hints[0] if rating_hints else len(columns) - 1)
    attribute_options = [column for column in columns if column not in (respondent_column, rating_column)]
    attribute_defaults = [
        column for column in attribute_options
        if frame[column].astype(str).nunique() <= 12 and not pd.api.types.is_float_dtype(frame[column])
    ]
    attribute_columns = st.multiselect(
        "Attribute columns — the product features that were varied",
        attribute_options,
        default=attribute_defaults,
        help="Each attribute needs 2–12 levels. Numeric measurements (like exact prices) should be grouped into a few levels.",
    )

    if st.button("Check the design and save the setup", type="primary"):
        try:
            design = build_design(frame, respondent_column, rating_column, attribute_columns)
            report, warnings = design_report(frame, design)
            st.session_state["study"] = {"frame": frame.copy(), "design": design, "source": st.session_state.get("source_name")}
            for key in ("result", "products", "shares", "optimal"):
                st.session_state.pop(key, None)
            st.success(
                f"Design saved: {frame[respondent_column].nunique():,} respondents, "
                f"{len(attribute_columns)} attributes, {design.parameter_count} model parameters."
            )
            for warning in warnings:
                st.warning(warning)
            with st.expander("Design health: how often was each level shown?", expanded=False):
                full_width(st.dataframe, report, hide_index=True)
                st.caption("Levels shown rarely or very unevenly produce unstable part-worth estimates.")
        except Exception as exc:
            show_error(exc)
    if st.session_state.get("study"):
        st.write("")
        if full_width(st.button, "Continue to 2 · Utilities & importance →"):
            go_to("2 · Utilities & importance")
            st.rerun()


def utilities_page() -> None:
    st.title("Estimate what each feature level is worth")
    study = st.session_state.get("study")
    if not study:
        st.info("Save a study design on page 1 first.")
        return
    frame, design = study["frame"], study["design"]
    context = st.columns(4)
    context[0].metric("Respondents", f"{frame[design.respondent_column].nunique():,}")
    context[1].metric("Ratings", f"{len(frame):,}")
    context[2].metric("Attributes", len(design.attribute_columns))
    context[3].metric("Model parameters", design.parameter_count)

    if st.button("Estimate part-worth utilities", type="primary"):
        try:
            with st.spinner("Fitting one regression per respondent…"):
                st.session_state["result"] = estimate_conjoint(frame, design)
            st.session_state.pop("shares", None)
            st.session_state.pop("optimal", None)
        except Exception as exc:
            show_error(exc)

    result = st.session_state.get("result")
    if result is None:
        return
    for warning in result.warnings:
        st.warning(warning)
    if result.method == "individual":
        estimable = int(result.fit["estimable"].sum())
        median_fit = float(result.fit["r_squared"].median())
        st.success(
            f"Estimated individual preferences for {estimable:,} respondents "
            f"(median fit R² = {median_fit:.2f}). Averages below; the spread column shows disagreement."
        )
    else:
        st.info(f"Pooled model across all ratings (R² = {result.pooled_r_squared:.2f}).")

    st.subheader("Part-worth utilities — the value of each feature level")
    st.caption(
        "Zero is the average appeal within each attribute. Positive levels add appeal, negative levels cost appeal, "
        "measured in rating-scale points. Compare levels within and across attributes freely."
    )
    partworths = result.partworths.copy()
    chart = px.bar(
        partworths, x="partworth", y="level", color="attribute", facet_row="attribute", orientation="h",
        labels={"partworth": "Part-worth (rating points)", "level": "", "attribute": ""},
    )
    chart.update_yaxes(matches=None, showticklabels=True, type="category")
    chart.for_each_annotation(lambda a: a.update(text=""))
    chart.update_layout(
        height=max(360, 120 * len(design.attribute_columns)), showlegend=True,
        legend_title_text="", margin=dict(l=10, r=10, t=20, b=10),
    )
    full_width(st.plotly_chart, chart)

    st.subheader("Attribute importance — what drives preference")
    importance = result.importance.copy()
    importance_chart = px.bar(
        importance.sort_values("importance_%"), x="importance_%", y="attribute", orientation="h",
        labels={"importance_%": "Importance (% of total preference range)", "attribute": ""},
    )
    importance_chart.update_layout(height=320, margin=dict(l=10, r=10, t=20, b=10))
    full_width(st.plotly_chart, importance_chart)
    st.caption(
        "Importance is how much of the total preference range each attribute controls, averaged over respondents. "
        "It depends on the levels you tested: a price attribute spanning a wider price range would look more important."
    )

    if result.method == "individual":
        with st.expander("Most wanted combinations — each respondent’s personal favorite"):
            try:
                favorites = ideal_products(result, design, top_n=3)
                full_width(st.dataframe, favorites, hide_index=True)
                st.caption(
                    "The level each respondent values most on every attribute, counted across respondents. "
                    "A popular favorite is not automatically the best product to launch — costs, competitors, "
                    "and feasibility still matter, and the simulator on page 3 tests designs against real alternatives."
                )
            except Exception as exc:
                show_error(exc)

    with st.expander("Detailed tables: part-worths, importance, and per-respondent fit"):
        full_width(st.dataframe, partworths.style.format({"partworth": "{:.2f}", "spread_std": "{:.2f}"}), hide_index=True)
        full_width(st.dataframe, importance.style.format({"importance_%": "{:.1f}", "spread_std": "{:.1f}"}), hide_index=True)
        fit = result.fit.copy()
        full_width(st.dataframe, fit.style.format({"r_squared": "{:.2f}"}), hide_index=True)
        st.caption(
            "Respondents with low R² rated inconsistently (or their preferences do not follow the additive model); "
            "their utilities deserve less weight."
        )
    if result.method == "individual":
        st.write("")
        if full_width(st.button, "Continue to 3 · Simulate & export →"):
            go_to("3 · Simulate & export")
            st.rerun()


def simulate_page() -> None:
    st.title("Compare candidate products and export the evidence")
    study = st.session_state.get("study")
    result = st.session_state.get("result")
    if not study or result is None:
        st.info("Estimate utilities on page 2 first.")
        return
    design: ConjointDesign = study["design"]
    st.markdown(CAUTION)

    if result.method != "individual":
        st.info(
            "The simulator needs individual estimates, and this analysis fell back to one pooled model. "
            "The exports below still contain the pooled part-worths and importance."
        )
    else:
        st.subheader("Define the products to compare")
        st.caption("Each product is one level per attribute. Two to four products keep the comparison readable.")
        product_count = st.slider("Products to compare", 2, 4, 2)
        products: dict[str, dict[str, str]] = {}
        product_columns = st.columns(product_count)
        for index in range(product_count):
            with product_columns[index]:
                with st.container(border=True):
                    default_name = f"Product {chr(65 + index)}"
                    name = st.text_input("Name", value=default_name, key=f"product_name_{index}") or default_name
                    profile = {}
                    for attribute in design.attribute_columns:
                        profile[attribute] = st.selectbox(
                            attribute.replace("_", " "),
                            design.levels[attribute],
                            index=min(index, len(design.levels[attribute]) - 1),
                            key=f"product_{index}_{attribute}",
                        )
                    products[name] = profile
        if len(set(products)) < product_count:
            st.warning("Give every product a different name.")
        elif st.button("Simulate preference shares", type="primary"):
            try:
                st.session_state["shares"] = simulate_shares(result, products, design)
                st.session_state["products"] = products
            except Exception as exc:
                show_error(exc)

        shares = st.session_state.get("shares")
        saved_products = st.session_state.get("products", {})
        if shares is not None:
            melted = shares.melt(
                id_vars="product",
                value_vars=["first_choice_share_%", "share_of_preference_%", "logit_share_%"],
                var_name="rule", value_name="share",
            )
            melted["rule"] = melted["rule"].map(
                {
                    "first_choice_share_%": "First choice",
                    "share_of_preference_%": "Share of preference",
                    "logit_share_%": "Logit",
                }
            )
            share_chart = px.bar(
                melted, x="product", y="share", color="rule", barmode="group",
                labels={"share": "Preference share (%)", "product": "", "rule": ""},
            )
            share_chart.update_layout(height=380, margin=dict(l=10, r=10, t=20, b=10))
            full_width(st.plotly_chart, share_chart)
            full_width(st.dataframe, shares, hide_index=True)
            st.caption(
                "**First choice:** every respondent picks their single highest-value product; decisive, fits big "
                "considered purchases. **Share of preference:** splits each respondent in proportion to product value; "
                "fits habitual categories where people sample around. **Logit:** an in-between rule whose softness "
                "depends on the rating scale — treat it as a sensitivity check. All three are preference shares among "
                "these exact products, not market-share forecasts. If the rules disagree strongly, say so in your "
                "recommendation. **Tip:** a preference share × a defensible target population is one disciplined way "
                "to set the market potential in **AdoptSignal**, our adoption-forecasting sibling."
            )

            with st.expander("Adjust for awareness and availability"):
                st.caption(
                    "A customer cannot choose a product they have never heard of or cannot find. Enter managerial "
                    "estimates per product; shares are weighted by awareness × availability and rebalanced to 100%."
                )
                factor_columns = st.columns(max(len(saved_products), 1))
                factors: dict[str, tuple[float, float]] = {}
                for index, name in enumerate(saved_products):
                    with factor_columns[index]:
                        st.markdown(f"**{name}**")
                        awareness = st.number_input("Awareness %", 0.0, 100.0, 100.0, 5.0, key=f"aware_{index}")
                        availability = st.number_input("Availability %", 0.0, 100.0, 100.0, 5.0, key=f"avail_{index}")
                        factors[name] = (awareness, availability)
                if any(value != (100.0, 100.0) for value in factors.values()):
                    try:
                        full_width(st.dataframe, adjust_shares(shares, factors), hide_index=True)
                        st.caption("Adjusted shares are only as good as the awareness and availability estimates behind them.")
                    except Exception as exc:
                        show_error(exc)

            if len(saved_products) >= 3:
                with st.expander("Cannibalization — where would a new product’s share come from?"):
                    st.caption(
                        "Pick which of the defined products is the new entrant. The table compares the other products’ "
                        "first-choice shares without and with it; share taken from your own products is cannibalization."
                    )
                    entrant = st.selectbox("The new entrant", list(saved_products), key="cannibal_entrant")
                    try:
                        full_width(
                            st.dataframe,
                            cannibalization_report(result, saved_products, entrant, design),
                            hide_index=True,
                        )
                    except Exception as exc:
                        show_error(exc)

        st.subheader("Search for the optimal product")
        st.caption(
            "Instead of testing designs one by one, search every combination of the tested levels. With simulated "
            "products above, candidates are ranked by first-choice share against them; otherwise by predicted rating."
        )
        if st.button("Find the best possible designs"):
            try:
                competitors = saved_products if st.session_state.get("shares") is not None else None
                st.session_state["optimal"] = optimal_products(result, design, competitors, top_n=5)
            except Exception as exc:
                show_error(exc)
        optimal = st.session_state.get("optimal")
        if optimal is not None:
            full_width(st.dataframe, optimal, hide_index=True)
            st.caption(
                "The best designs **among the levels you tested** — untested levels, production costs, feasibility, "
                "and brand fit are outside the search. A design that wins on preference can still lose on margin."
            )

    st.subheader("Export the evidence")
    frame = study["frame"]
    fingerprint = hashlib.sha256(
        pd.util.hash_pandas_object(
            frame[[design.respondent_column, *design.attribute_columns]].astype(str), index=True
        ).values.tobytes()
    ).hexdigest()
    metadata = {
        "product": "ChoiceSignal", "version": __version__, "source": study.get("source"),
        "method": "ratings-based conjoint, effects-coded OLS, "
                  + ("per-respondent with pooled reference" if result.method == "individual" else "pooled only"),
        "respondents": int(frame[design.respondent_column].nunique()),
        "ratings": len(frame),
        "attributes": {attribute: design.levels[attribute] for attribute in design.attribute_columns},
        "pooled_r_squared": round(result.pooled_r_squared, 4),
        "mean_rating": round(result.mean_rating, 4),
        "dataset_fingerprint_sha256": fingerprint,
        "simulated_products": st.session_state.get("products", {}),
        "library_versions": {
            "python": platform.python_version(), "numpy": np.__version__,
            "pandas": pd.__version__, "streamlit": st.__version__,
        },
        "caution": "Stated-preference estimates from rated hypothetical profiles; not market-share forecasts.",
    }
    manifest = pd.DataFrame(
        {
            "field": list(metadata),
            "value": [json.dumps(value, default=str, sort_keys=True) if isinstance(value, (dict, list)) else str(value) for value in metadata.values()],
        }
    )
    export_tables = {
        "Analysis manifest": manifest,
        "Partworth utilities": result.partworths,
        "Attribute importance": result.importance,
        "Individual partworths": result.individual,
        "Respondent fit": result.fit,
        "Pooled partworths": result.pooled_partworths,
    }
    shares = st.session_state.get("shares")
    if shares is not None:
        export_tables["Simulated shares"] = shares
    optimal = st.session_state.get("optimal")
    if optimal is not None:
        export_tables["Optimal designs"] = optimal
    downloads = st.columns(3)
    full_width(
        downloads[0].download_button,
        "Download full Excel pack", results_to_excel(export_tables), "choicesignal_results.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    full_width(
        downloads[1].download_button,
        "Download part-worths CSV",
        safe_for_spreadsheet(result.partworths).to_csv(index=False).encode("utf-8"),
        "choicesignal_partworths.csv", "text/csv",
    )
    full_width(
        downloads[2].download_button,
        "Download JSON + audit trail",
        results_to_json(
            {name.lower().replace(" ", "_"): table for name, table in export_tables.items() if name != "Analysis manifest"},
            metadata,
        ),
        "choicesignal_results.json", "application/json",
    )
    if result.method == "individual" and not result.individual.empty:
        wide = result.individual.pivot_table(
            index="respondent", columns=["attribute", "level"], values="partworth"
        )
        wide.columns = [f"{attribute} · {level}" for attribute, level in wide.columns]
        wide = wide.reset_index().merge(
            result.fit[["respondent", "r_squared"]], on="respondent", how="left"
        )
        full_width(
            st.download_button,
            "Download part-worths per respondent — ready for segmentation",
            safe_for_spreadsheet(wide).to_csv(index=False).encode("utf-8"),
            "choicesignal_partworths_by_respondent.csv", "text/csv",
        )
        st.caption(
            "One row per respondent, one column per feature level. Different customers often want different "
            "things: upload this file to **SegmentSignal** (our segmentation sibling) to discover preference-based "
            "segments, then design one product per segment here."
        )


def methods_page() -> None:
    st.title("Methods, assumptions, and honest limits")
    st.markdown(CAUTION)
    st.subheader("What the app estimates")
    st.write(
        "ChoiceSignal implements classic ratings-based (full-profile) conjoint analysis. Attribute levels are "
        "effects-coded, so each attribute's part-worths sum to zero and describe value relative to that attribute's "
        "average. A separate ordinary-least-squares regression is fitted per respondent; the app reports the "
        "average part-worths, the spread across respondents, per-respondent fit (R²), and attribute importance "
        "(each attribute's share of the total preference range, averaged over respondents)."
    )
    method_columns = st.columns(2)
    with method_columns[0]:
        with st.container(border=True):
            st.markdown("#### Per-respondent estimation")
            st.write(
                "Preserves differences between people and powers the simulator. A respondent needs at least as many "
                "rated profiles as model parameters; others fall back to the pooled model."
            )
    with method_columns[1]:
        with st.container(border=True):
            st.markdown("#### Preference-share simulation")
            st.write(
                "Three classic choice rules — first choice, utility-proportional share of preference, and logit — "
                "plus awareness/availability adjustment, a cannibalization view, and an exhaustive search for the "
                "best design among the tested levels. Rules can disagree; that disagreement is information."
            )
    st.subheader("Important boundaries")
    st.markdown(
        """
        - Ratings are **stated** preferences for hypothetical profiles; real markets add awareness, availability, budgets, and competition.
        - The model is additive: no interactions between attributes (for example, brand-specific price sensitivity) in this release.
        - Importance depends on the levels tested — widening a price range makes price look more important.
        - Numeric attributes are treated as discrete levels; the app does not interpolate between tested prices.
        - Choice-based conjoint (CBC) with hierarchical Bayes estimation is the modern survey standard and is out of scope for this first release; it needs choice tasks, not ratings.
        - A perfectly confounded design (two attributes always changing together) is rejected rather than silently mis-estimated.
        - Willingness-to-pay conversions are deliberately excluded: dividing part-worths by a price coefficient is fragile with categorical prices and is easy to over-read.
        """
    )
    with st.expander("References and implementation notes"):
        st.write(
            "See `docs/methods.md` for the estimation details, formulas, warnings, and citations "
            "(Green & Srinivasan 1978; Green & Rao 1971; Orme 2020). Every computational module is separate "
            "from Streamlit and covered by automated tests."
        )


if page == "Welcome":
    welcome_page()
elif page == "1 · Data & design":
    data_page()
elif page == "2 · Utilities & importance":
    utilities_page()
elif page == "3 · Simulate & export":
    simulate_page()
else:
    methods_page()

st.markdown(
    f"<div class='cs-footer'>ChoiceSignal v{__version__} <span>•</span> Built for transparent conjoint analysis <span>•</span> Your uploaded file is not persisted by the app</div>",
    unsafe_allow_html=True,
)
