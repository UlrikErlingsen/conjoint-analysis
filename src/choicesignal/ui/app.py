"""Choice Signal Streamlit UI.

Everything that draws the app runs inside ``render()`` (or the functions it calls), so it runs on every rerun,
both in the standalone ``app.py`` and inside Signal Hub. Module-level code here only defines constants and
functions. ``render()`` never calls ``st.set_page_config`` or ``st.navigation``.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import platform
import traceback
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from choicesignal import __version__
from choicesignal.concept_test import (
    DEFAULT_TRIAL_WEIGHTS,
    box_summary,
    intent_table,
    prepare_concept,
    rejection_summary,
    segment_table,
    trial_estimate,
    trial_intention_export,
)
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
from choicesignal.ui import signal_theme as sig


NS = "choice"


def k(name: str) -> str:
    """Namespace a session-state or widget key with the app slug, so apps can share one Hub session."""
    return f"{NS}:{name}"


# The fictional demo studies ship inside the package (copies of examples/), so the demo buttons also work when
# the app is installed from a wheel, as in Signal Hub.
DEMOS = Path(__file__).resolve().parent / "assets" / "examples"

PAGES = [
    "Welcome",
    "1 · Data & design",
    "2 · Utilities & importance",
    "3 · Simulate & export",
    "4 · Concept test",
    "Methods & limits",
]

SIDEBAR_TAGLINE = "Know what customers actually value."
MASTHEAD_KICKER = "OPEN CONJOINT ANALYSIS"
MASTHEAD_PROMISES = ["Local-first", "Explainable", "Open source"]
FOOTER_LINE = "Stated preference, not market share"

CAUTION = (
    "**Treat these results as decision support, not predicted market shares.** Ratings describe stated "
    "preferences for hypothetical profiles. Real choices also depend on awareness, availability, budgets, "
    "habits, and competitors outside the study."
)

ANALYSIS_KEYS = ("study", "result", "products", "shares", "optimal", "adjusted_shares", "concept")
# Column-mapping widgets re-guess their defaults whenever a different table becomes active.
STUDY_WIDGETS = ("study_respondent", "study_rating", "study_attributes")

_USES_STRETCH_WIDTH = "width" in inspect.signature(st.button).parameters


def full_width(widget, *args, **kwargs):
    """Use Streamlit's full-width API across both older and newer releases."""
    if _USES_STRETCH_WIDTH:
        kwargs["width"] = "stretch"
    else:
        kwargs["use_container_width"] = True
    return widget(*args, **kwargs)


def show_error(exc: Exception) -> None:
    st.error(friendly_message(exc))
    if not isinstance(exc, DataProblem) and os.getenv("CHOICESIGNAL_DEBUG") == "1":
        with st.expander("Technical details"):
            st.code("".join(traceback.format_exception(exc)))


def _drop(*names: str) -> None:
    for name in names:
        st.session_state.pop(k(name), None)


def _ensure_state() -> None:
    for name, default in (
        ("tables", None), ("source_name", None), ("active_table", None),
        ("upload_epoch", 0), ("_uploader_had_file", False),
        ("nav_target", PAGES[0]),
    ):
        st.session_state.setdefault(k(name), default)


def set_loaded(loaded: LoadedData) -> None:
    st.session_state[k("tables")] = loaded.tables
    st.session_state[k("source_name")] = loaded.source_name
    st.session_state[k("active_table")] = next(iter(loaded.tables))
    _drop(*ANALYSIS_KEYS, *STUDY_WIDGETS, "table_select")


def load_demo(filename: str) -> None:
    set_loaded(load_data(DEMOS / filename))


def current_frame() -> pd.DataFrame | None:
    tables = st.session_state.get(k("tables"))
    if not tables:
        return None
    name = st.session_state.get(k("active_table"), next(iter(tables)))
    return tables[name]


def require_data() -> pd.DataFrame | None:
    frame = current_frame()
    if frame is None:
        st.info("Bring a CSV, Excel, or JSON ratings file in the sidebar—or use a fictional demo study.")
    return frame


def go_to(page_name: str) -> None:
    """Navigate programmatically: the sidebar radio adopts ``nav_target`` before it is drawn on the next run."""
    st.session_state[k("nav_target")] = page_name
    st.session_state[k("nav_jump")] = True


def _sidebar() -> str:
    """Draw the sidebar lockup, data controls and page selector; return the selected page."""
    sig.sidebar_brand(NS, SIDEBAR_TAGLINE)
    with st.sidebar:
        st.markdown("### 1. Bring your ratings")
        epoch = int(st.session_state[k("upload_epoch")])
        uploaded = st.file_uploader(
            "CSV, Excel, or JSON",
            type=["csv", "xlsx", "xls", "xlsm", "json"],
            key=k(f"ratings_upload_{epoch}"),
        )
        if uploaded is not None:
            upload_identity = (
                str(getattr(uploaded, "file_id", "") or f"widget-{epoch}"),
                uploaded.name,
                int(getattr(uploaded, "size", 0)),
            )
            st.session_state[k("_uploader_had_file")] = True
            if st.session_state.get(k("upload_identity")) != upload_identity:
                try:
                    raw = uploaded.getvalue()
                    set_loaded(load_data(raw, name=uploaded.name))
                    st.session_state[k("upload_identity")] = upload_identity
                    st.session_state[k("_uploader_had_file")] = False
                    st.session_state[k("upload_epoch")] = epoch + 1
                    go_to("1 · Data & design")
                    st.rerun()
                except Exception as exc:
                    show_error(exc)
        elif st.session_state.get(k("_uploader_had_file")):
            st.session_state[k("_uploader_had_file")] = False
        if full_width(st.button, "Demo · coffee subscriptions", key=k("demo_coffee")):
            load_demo("demo_coffee_ratings.csv")
            go_to("1 · Data & design")
            st.rerun()
        if full_width(st.button, "Demo · car buyers", key=k("demo_cars")):
            load_demo("demo_car_ratings.csv")
            go_to("1 · Data & design")
            st.rerun()
        if full_width(st.button, "Demo · streaming plans", key=k("demo_streaming")):
            load_demo("demo_streaming_ratings.csv")
            go_to("1 · Data & design")
            st.rerun()
        if full_width(st.button, "Demo · concept test", key=k("demo_concept")):
            load_demo("demo_concept_test.csv")
            go_to("4 · Concept test")
            st.rerun()
        with st.expander("What are the demos?"):
            st.caption(
                "**Coffee subscriptions:** 300 fictional respondents rated 14 subscription profiles each "
                "(brand, price, beans, delivery).\n\n"
                "**Car buyers:** 350 fictional respondents rated 16 car profiles each (brand origin, body, "
                "engine, price). This one hides two different taste groups — try exporting the part-worths "
                "into Segment Signal to find them.\n\n"
                "**Streaming plans:** 150 fictional respondents rated 12 plan profiles each "
                "(price, quality, ads, screens).\n\n"
                "**Concept test:** 260 fictional respondents answered the five-point purchase-intent "
                "question about a single cold-brew subscription concept — for page 4, not conjoint.\n\n"
                "Every record is synthetic. `examples/ratings_template.csv` and "
                "`examples/concept_template.csv` show the expected shapes."
            )
        if st.session_state.get(k("tables")) and full_width(st.button, "Clear session data", key=k("clear_data")):
            _drop("tables", "source_name", "active_table", "upload_identity", "_uploader_had_file", *ANALYSIS_KEYS)
            _drop(*STUDY_WIDGETS, "table_select")
            st.session_state[k("upload_epoch")] = epoch + 1
            go_to("Welcome")
            st.rerun()
        if st.session_state.get(k("tables")):
            table_names = list(st.session_state[k("tables")])
            active_table = st.session_state.get(k("active_table"))
            selected_table = st.selectbox(
                "Table / sheet",
                table_names,
                index=table_names.index(active_table) if active_table in table_names else 0,
                key=k("table_select"),
            )
            if selected_table != active_table:
                st.session_state[k("active_table")] = selected_table
                _drop(*ANALYSIS_KEYS, *STUDY_WIDGETS)
            active = st.session_state[k("tables")][selected_table]
            st.caption(f"{st.session_state.get(k('source_name'))} · {len(active):,} rows × {len(active.columns)} columns")
        st.markdown("### 2. Follow the workflow")
        # Set the radio's state before it is drawn: after a programmatic jump, or when Streamlit dropped the
        # widget state because the radio was not drawn (for example while another Hub page was open).
        if st.session_state.pop(k("nav_jump"), False) or k("page") not in st.session_state:
            st.session_state[k("page")] = st.session_state.get(k("nav_target"), PAGES[0])
        page = st.radio("Page", PAGES, key=k("page"), label_visibility="collapsed")
        st.session_state[k("nav_target")] = page
    return page


def welcome_page() -> None:
    sig.hero(
        NS,
        eyebrow="CONJOINT ANALYSIS, WITHOUT THE BLACK BOX",
        title="From simple ratings to",
        em="what customers value.",
        body=(
            "Upload ratings of product profiles. Choice Signal estimates how much every feature level is worth to "
            "your respondents, which attributes drive preference, and how candidate products would split "
            "preference between them."
        ),
        pills=["No account", "No telemetry", "Per-respondent estimates", "Honest design warnings"],
    )
    sig.note("warn", CAUTION)
    sig.cards(
        [
            ("STEP 01", "Map the study", "Tell the app which columns hold the respondent, the rating, and the product attributes. The design is health-checked first."),
            ("STEP 02", "Estimate utilities", "Each respondent's ratings become part-worth utilities per feature level, with attribute importance and fit quality."),
            ("STEP 03", "Simulate and export", "Define candidate products, compare preference shares, and export every estimate with a full audit trail."),
        ]
    )
    metric_columns = st.columns(4)
    metric_columns[0].metric("Input formats", "5", "CSV · Excel · JSON")
    metric_columns[1].metric("Estimation", "OLS", "per respondent + pooled")
    metric_columns[2].metric("Attributes", "up to 10", "12 levels each")
    metric_columns[3].metric("Data stored", "None", "by the app")
    with st.expander("Where this tool fits"):
        st.write(
            "Choice Signal covers ratings-based (full-profile) conjoint: respondents rate complete product profiles, "
            "and regression turns the ratings into feature values. Its siblings answer the other questions: "
            "Worth Signal covers customer value and retention, Segment Signal covers segmentation, Adopt Signal "
            "forecasts adoption timing, and Position Signal maps brand perception. Choice-based conjoint with "
            "hierarchical Bayes estimation is a different, more complex method and is outside this release."
        )


def data_page() -> None:
    sig.header(
        "Step 1",
        "Map the study design",
        "One row = one respondent rating one product profile. The columns describe the profile.",
    )
    st.caption(
        "Testing a **single concept** (would people buy this one idea?) instead of trading off "
        "attributes? Use **4 · Concept test** — it expects one row per respondent."
    )
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
    respondent_column = st.selectbox("Respondent ID column", columns, index=respondent_guess, key=k("study_respondent"))
    rating_hints = [index for index, column in enumerate(columns) if any(
        token in column.lower() for token in ("rating", "score", "liking", "preference", "eval")
    )]
    rating_column = st.selectbox(
        "Rating column (higher = better)",
        columns,
        index=rating_hints[0] if rating_hints else len(columns) - 1,
        key=k("study_rating"),
    )
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
        key=k("study_attributes"),
    )

    if st.button("Check the design and save the setup", type="primary", key=k("save_design")):
        try:
            design = build_design(frame, respondent_column, rating_column, attribute_columns)
            report, warnings = design_report(frame, design)
            st.session_state[k("study")] = {
                "frame": frame.copy(), "design": design, "source": st.session_state.get(k("source_name")),
            }
            _drop("result", "products", "shares", "optimal", "adjusted_shares")
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
    if st.session_state.get(k("study")):
        st.write("")
        if full_width(st.button, "Continue to 2 · Utilities & importance →", key=k("continue_utilities")):
            go_to("2 · Utilities & importance")
            st.rerun()


def utilities_page() -> None:
    sig.header("Step 2", "Estimate what each feature level is worth")
    study = st.session_state.get(k("study"))
    if not study:
        st.info("Save a study design on page 1 first.")
        return
    frame, design = study["frame"], study["design"]
    context = st.columns(4)
    context[0].metric("Respondents", f"{frame[design.respondent_column].nunique():,}")
    context[1].metric("Ratings", f"{len(frame):,}")
    context[2].metric("Attributes", len(design.attribute_columns))
    context[3].metric("Model parameters", design.parameter_count)

    if st.button("Estimate part-worth utilities", type="primary", key=k("estimate")):
        try:
            with st.spinner("Fitting one regression per respondent…"):
                st.session_state[k("result")] = estimate_conjoint(frame, design)
            _drop("shares", "optimal")
        except Exception as exc:
            show_error(exc)

    result = st.session_state.get(k("result"))
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
        st.info(
            f"Pooled model with respondent fixed effects (within-respondent R² = {result.pooled_r_squared:.2f}); "
            "rating-style differences between respondents are absorbed and cannot pose as attribute effects."
        )

    st.subheader("Part-worth utilities — the value of each feature level")
    st.caption(
        "Zero is the average appeal within each attribute. Positive levels add appeal, negative levels cost appeal, "
        "measured in rating-scale points. Compare levels within and across attributes freely."
    )
    partworths = result.partworths.copy()
    chart = px.bar(
        partworths, x="partworth", y="level", color="attribute", facet_row="attribute", orientation="h",
        labels={"partworth": "Part-worth (rating points)", "level": "", "attribute": ""},
        template=sig.template(NS),
    )
    chart.update_yaxes(matches=None, showticklabels=True, type="category")
    chart.for_each_annotation(lambda a: a.update(text=""))
    chart.update_layout(
        height=max(360, 120 * len(design.attribute_columns)), showlegend=True,
        legend_title_text="", margin={"l": 10, "r": 10, "t": 20, "b": 10},
    )
    sig.chart(NS, chart, key=k("partworth_chart"))

    st.subheader("Attribute importance — what drives preference")
    importance = result.importance.copy()
    importance_chart = px.bar(
        importance.sort_values("importance_%"), x="importance_%", y="attribute", orientation="h",
        labels={"importance_%": "Importance (% of total preference range)", "attribute": ""},
        template=sig.template(NS),
    )
    importance_chart.update_layout(height=320, margin={"l": 10, "r": 10, "t": 20, "b": 10})
    sig.chart(NS, importance_chart, key=k("importance_chart"))
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
        if full_width(st.button, "Continue to 3 · Simulate & export →", key=k("continue_simulate")):
            go_to("3 · Simulate & export")
            st.rerun()


def simulate_page() -> None:
    sig.header("Step 3", "Compare candidate products and export the evidence")
    study = st.session_state.get(k("study"))
    result = st.session_state.get(k("result"))
    if not study or result is None:
        st.info("Estimate utilities on page 2 first.")
        return
    design: ConjointDesign = study["design"]
    sig.note("warn", CAUTION)

    if result.method != "individual":
        st.info(
            "The simulator needs individual estimates, and this analysis fell back to one pooled model. "
            "The exports below still contain the pooled part-worths and importance."
        )
    else:
        st.subheader("Define the products to compare")
        st.caption("Each product is one level per attribute. Two to four products keep the comparison readable.")
        product_count = st.slider("Products to compare", 2, 4, 2, key=k("product_count"))
        products: dict[str, dict[str, str]] = {}
        product_columns = st.columns(product_count)
        for index in range(product_count):
            with product_columns[index], st.container(border=True):
                default_name = f"Product {chr(65 + index)}"
                name = st.text_input("Name", value=default_name, key=k(f"product_name_{index}")) or default_name
                profile = {}
                for attribute in design.attribute_columns:
                    profile[attribute] = st.selectbox(
                        attribute.replace("_", " "),
                        design.levels[attribute],
                        index=min(index, len(design.levels[attribute]) - 1),
                        key=k(f"product_{index}_{attribute}"),
                    )
                products[name] = profile
        if len(set(products)) < product_count:
            st.warning("Give every product a different name.")
        elif st.button("Simulate preference shares", type="primary", key=k("simulate")):
            try:
                st.session_state[k("shares")] = simulate_shares(result, products, design)
                st.session_state[k("products")] = products
            except Exception as exc:
                show_error(exc)

        shares = st.session_state.get(k("shares"))
        saved_products = st.session_state.get(k("products"), {})
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
                template=sig.template(NS),
            )
            share_chart.update_layout(height=380, margin={"l": 10, "r": 10, "t": 20, "b": 10})
            sig.chart(NS, share_chart, key=k("share_chart"))
            full_width(st.dataframe, shares, hide_index=True)
            st.caption(
                "**First choice:** every respondent picks their single highest-value product; decisive, fits big "
                "considered purchases. **Share of preference:** splits each respondent in proportion to how far each "
                "product's predicted rating sits above the study's lowest observed rating (anchored so that shifting "
                "the whole rating scale cannot change the shares); fits habitual categories where people sample "
                "around. **Logit:** an in-between rule whose softness depends on the rating-scale units — treat it as "
                "a sensitivity check. All three are preference shares among these exact products, not market-share "
                "forecasts. If the rules disagree strongly, say so in your recommendation."
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
                        awareness = st.number_input("Awareness %", 0.0, 100.0, 100.0, 5.0, key=k(f"aware_{index}"))
                        availability = st.number_input("Availability %", 0.0, 100.0, 100.0, 5.0, key=k(f"avail_{index}"))
                        factors[name] = (awareness, availability)
                if any(value != (100.0, 100.0) for value in factors.values()):
                    try:
                        adjusted = adjust_shares(shares, factors)
                        st.session_state[k("adjusted_shares")] = adjusted
                        full_width(st.dataframe, adjusted, hide_index=True)
                        st.caption("Adjusted shares are only as good as the awareness and availability estimates behind them. They are included in the exports below.")
                    except Exception as exc:
                        show_error(exc)
                else:
                    _drop("adjusted_shares")

            if len(saved_products) >= 3:
                with st.expander("Cannibalization — where would a new product’s share come from?"):
                    st.caption(
                        "Pick which of the defined products is the new entrant. The table compares the other products’ "
                        "first-choice shares without and with it; share taken from your own products is cannibalization."
                    )
                    entrant = st.selectbox("The new entrant", list(saved_products), key=k("cannibal_entrant"))
                    try:
                        full_width(
                            st.dataframe,
                            cannibalization_report(result, saved_products, entrant, design),
                            hide_index=True,
                        )
                    except Exception as exc:
                        show_error(exc)

        st.subheader("Search for the highest stated-preference design")
        st.caption(
            "Instead of testing designs one by one, search every combination of the tested levels. With simulated "
            "products above, candidates are ranked by first-choice share against them; otherwise by predicted "
            "rating. This ranks stated preference only — costs, margins, and feasibility are not in the search."
        )
        if st.button("Find the top stated-preference designs", key=k("search_designs")):
            try:
                competitors = saved_products if st.session_state.get(k("shares")) is not None else None
                st.session_state[k("optimal")] = optimal_products(result, design, competitors, top_n=5)
            except Exception as exc:
                show_error(exc)
        optimal = st.session_state.get(k("optimal"))
        if optimal is not None:
            full_width(st.dataframe, optimal, hide_index=True)
            st.caption(
                "The highest **stated-preference** designs among the levels you tested — untested levels, production "
                "costs, feasibility, and brand fit are outside the search. A design that wins on preference can "
                "still lose on margin."
            )

    st.subheader("Export the evidence")
    frame = study["frame"]
    fingerprint = hashlib.sha256(
        pd.util.hash_pandas_object(
            frame[[design.respondent_column, *design.attribute_columns]].astype(str), index=True
        ).values.tobytes()
    ).hexdigest()
    metadata = {
        "product": "Choice Signal", "version": __version__, "source": study.get("source"),
        "method": "ratings-based conjoint, effects-coded OLS, "
                  + ("per-respondent with fixed-effects pooled reference" if result.method == "individual" else "respondent-fixed-effects pooled only"),
        "respondents": int(frame[design.respondent_column].nunique()),
        "ratings": len(frame),
        "attributes": {attribute: design.levels[attribute] for attribute in design.attribute_columns},
        "pooled_r_squared": round(result.pooled_r_squared, 4),
        "mean_rating": round(result.mean_rating, 4),
        "dataset_fingerprint_sha256": fingerprint,
        "simulated_products": st.session_state.get(k("products"), {}),
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
    shares = st.session_state.get(k("shares"))
    if shares is not None:
        export_tables["Simulated shares"] = shares
    adjusted = st.session_state.get(k("adjusted_shares"))
    if adjusted is not None:
        export_tables["Adjusted shares"] = adjusted
    optimal = st.session_state.get(k("optimal"))
    if optimal is not None:
        export_tables["Top preference designs"] = optimal
    downloads = st.columns(3)
    full_width(
        downloads[0].download_button,
        "Download full Excel pack", results_to_excel(export_tables), "choicesignal_results.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=k("download_excel"),
    )
    full_width(
        downloads[1].download_button,
        "Download part-worths CSV",
        safe_for_spreadsheet(result.partworths).to_csv(index=False).encode("utf-8"),
        "choicesignal_partworths.csv", "text/csv",
        key=k("download_partworths"),
    )
    full_width(
        downloads[2].download_button,
        "Download JSON + audit trail",
        results_to_json(
            {name.lower().replace(" ", "_"): table for name, table in export_tables.items() if name != "Analysis manifest"},
            metadata,
        ),
        "choicesignal_results.json", "application/json",
        key=k("download_json"),
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
            key=k("download_by_respondent"),
        )
        st.caption(
            "One row per respondent, one column per feature level. Different customers often want different "
            "things: upload this file to **Segment Signal** (our segmentation sibling) to discover preference-based "
            "segments, then design one product per segment here."
        )


def concept_page() -> None:
    sig.header(
        "Step 4",
        "Test one concept: who says they would buy?",
        "One row = one respondent answering the classic five-point purchase-intent question about a single "
        "described concept. This complements conjoint: conjoint trades off attributes across many profiles; the "
        "concept test asks for a verdict on one idea.",
    )
    frame = require_data()
    if frame is None:
        return

    columns = [str(column) for column in frame.columns]
    respondent_guess = next(
        (index for index, column in enumerate(columns) if "respondent" in column.lower() or column.lower().endswith("id")),
        0,
    )
    respondent_column = st.selectbox("Respondent ID column", columns, index=respondent_guess, key=k("concept_respondent"))
    intent_hints = [index for index, column in enumerate(columns) if any(
        token in column.lower() for token in ("intent", "buy", "purchase", "likel")
    )]
    intent_column = st.selectbox(
        "Purchase-intent column",
        columns,
        index=intent_hints[0] if intent_hints else len(columns) - 1,
        key=k("concept_intent"),
        help="The five standard answers (‘Definitely would buy’ … ‘Definitely would not buy’) or the numbers 1–5.",
    )
    option_columns = ["(none)"] + [column for column in columns if column not in (respondent_column, intent_column)]
    reason_guess = next((index for index, column in enumerate(option_columns) if "reason" in column.lower()), 0)
    reason_column = st.selectbox(
        "Rejection-reason column (optional)", option_columns, index=reason_guess, key=k("concept_reason"),
        help="Why non-buyers said no. Several reasons in one cell can be separated with ‘;’ or ‘|’.",
    )
    segment_guess = next((index for index, column in enumerate(option_columns) if any(
        token in column.lower() for token in ("segment", "group", "cluster")
    )), 0)
    segment_column = st.selectbox(
        "Segment column (optional)", option_columns, index=segment_guess, key=k("concept_segment"),
        help="Compare intent between customer groups — for example segments exported from Segment Signal.",
    )
    concept_name = st.text_input("Concept name (used in the export)", value="New concept", key=k("concept_name"))
    reversed_numeric = st.checkbox(
        "My numeric scale is reversed (1 = definitely would buy)",
        value=False,
        key=k("concept_reversed"),
        help="Only affects numeric answers. Text labels are always read by their meaning.",
    )

    if st.button("Run the concept test", type="primary", key=k("run_concept")):
        try:
            data = prepare_concept(
                frame,
                respondent_column,
                intent_column,
                None if reason_column == "(none)" else reason_column,
                None if segment_column == "(none)" else segment_column,
                reversed_numeric,
            )
            st.session_state[k("concept")] = {
                "data": data, "name": concept_name, "source": st.session_state.get(k("source_name")),
            }
        except Exception as exc:
            show_error(exc)

    saved = st.session_state.get(k("concept"))
    if not saved:
        return
    data = saved["data"]
    for warning in data.warnings:
        st.warning(warning)

    summary = box_summary(data)
    top = summary["top_box"]
    top_two = summary["top_two_box"]
    metric_columns = st.columns(3)
    metric_columns[0].metric("Respondents", f"{summary['respondents']:,}")
    metric_columns[1].metric("Top box", f"{top['share_%']:.1f}%", "definitely would buy")
    metric_columns[2].metric("Top two boxes", f"{top_two['share_%']:.1f}%", "definitely + probably")
    st.caption(
        f"With 95% confidence, the top-box share lies between {top['wilson95_%'][0]:.1f}% and "
        f"{top['wilson95_%'][1]:.1f}%, and the top-two-box share between {top_two['wilson95_%'][0]:.1f}% "
        f"and {top_two['wilson95_%'][1]:.1f}% (Wilson intervals). **Stated intent overstates real buying** — "
        "read these as enthusiasm for the idea, not as a sales forecast."
    )

    boxes = intent_table(data)
    chart_frame = boxes.copy()
    chart_frame["error_high"] = chart_frame["wilson95_high_%"] - chart_frame["share_%"]
    chart_frame["error_low"] = chart_frame["share_%"] - chart_frame["wilson95_low_%"]
    chart = px.bar(
        chart_frame, x="share_%", y="intent", orientation="h",
        error_x="error_high", error_x_minus="error_low",
        labels={"share_%": "Share of respondents (%)", "intent": ""},
        template=sig.template(NS),
    )
    chart.update_yaxes(type="category", categoryorder="array", categoryarray=list(chart_frame["intent"])[::-1])
    chart.update_layout(height=320, margin={"l": 10, "r": 10, "t": 20, "b": 10})
    sig.chart(NS, chart, key=k("intent_chart"))
    with st.expander("Detailed intent table"):
        full_width(
            st.dataframe,
            boxes.style.format({"share_%": "{:.1f}", "wilson95_low_%": "{:.1f}", "wilson95_high_%": "{:.1f}"}),
            hide_index=True,
        )

    st.subheader("From stated intent to an assumed trial rate")
    st.caption(
        "People overstate. A common practice is to count only a fraction of each box as real trial. "
        "The defaults below are an illustrative starting point — **calibrate them to past launches in "
        "your category**, and carry the top-two-box share alongside as the optimistic ceiling."
    )
    weight_columns = st.columns(3)
    weights = dict(DEFAULT_TRIAL_WEIGHTS)
    weights[5] = weight_columns[0].number_input("Weight · definitely", 0.0, 1.0, DEFAULT_TRIAL_WEIGHTS[5], 0.05, key=k("w5"))
    weights[4] = weight_columns[1].number_input("Weight · probably", 0.0, 1.0, DEFAULT_TRIAL_WEIGHTS[4], 0.05, key=k("w4"))
    weights[3] = weight_columns[2].number_input("Weight · might", 0.0, 1.0, DEFAULT_TRIAL_WEIGHTS[3], 0.05, key=k("w3"))
    trial = trial_estimate(data, weights)
    trial_columns = st.columns(2)
    trial_columns[0].metric("Assumed trial rate", f"{trial['weighted_trial_%']:.1f}%", "weighted intent")
    trial_columns[1].metric("Optimistic ceiling", f"{trial['ceiling_top_two_box_%']:.1f}%", "raw top two boxes")
    st.caption(
        "Trial is only one factor of volume: market size × awareness × **trial** × availability × repeat "
        "× frequency. The export below carries this estimate, its assumptions, and its ceiling into that "
        "calculation."
    )

    if "reason" in data.frame.columns:
        st.subheader("Why the others said no")
        reasons, reason_meta = rejection_summary(data)
        if reasons.empty:
            st.info("No rejection reasons were recorded for respondents below the top two boxes.")
        else:
            reason_chart = px.bar(
                reasons.sort_values("mentions"), x="mentions", y="reason", orientation="h",
                labels={"mentions": "Mentions", "reason": ""},
                template=sig.template(NS),
            )
            reason_chart.update_yaxes(type="category")
            reason_chart.update_layout(height=max(220, 44 * len(reasons)), margin={"l": 10, "r": 10, "t": 20, "b": 10})
            sig.chart(NS, reason_chart, key=k("reason_chart"))
            full_width(st.dataframe, reasons, hide_index=True)
            st.caption(
                f"{reason_meta['rejecters_with_reason']} of {reason_meta['rejecters']} respondents below the "
                "top two boxes gave a reason; one respondent can mention several, so percentages can sum "
                "past 100%. Reasons are what people say — fixable objections (price, packaging) and "
                "polite refusals read differently."
            )

    if "segment" in data.frame.columns:
        st.subheader("Intent by segment")
        segments, segment_warnings = segment_table(data)
        for warning in segment_warnings:
            st.warning(warning)
        full_width(
            st.dataframe,
            segments[["segment", "respondents", "top_box_%", "top_two_box_%", "top_two_wilson95_low_%", "top_two_wilson95_high_%"]]
            .style.format({column: "{:.1f}" for column in segments.columns if column.endswith("%")}),
            hide_index=True,
        )
        st.caption(
            "Descriptive comparison: where the Wilson intervals overlap heavily, the data cannot "
            "separate the segments. No significance test is run — small groups simply have wide intervals."
        )

    st.subheader("Export the evidence")
    export_payload = trial_intention_export(
        data, saved.get("name", "New concept"),
        weights, __version__, saved.get("source"),
    )
    download_columns = st.columns(2)
    full_width(
        download_columns[0].download_button,
        "Download intent table CSV",
        safe_for_spreadsheet(boxes).to_csv(index=False).encode("utf-8"),
        "choicesignal_concept_test.csv", "text/csv",
        key=k("download_concept_csv"),
    )
    full_width(
        download_columns[1].download_button,
        "Download trial intention JSON — ready for an ATR volume plan",
        json.dumps(export_payload, indent=2, allow_nan=False).encode("utf-8"),
        "choicesignal_trial_intention.json", "application/json",
        key=k("download_trial_json"),
    )
    st.caption(
        "The JSON records the boxes, intervals, weights, and caveats — designed as the **trial** input "
        "of an awareness × trial × availability × repeat volume plan (for example in **Gate Signal**, the "
        "Signal decision-gate sibling), so the assumption trail travels with the number."
    )


def methods_page() -> None:
    sig.header("Methods & limits", "Methods, assumptions, and honest limits")
    sig.note("warn", CAUTION)
    st.subheader("What the app estimates")
    st.write(
        "Choice Signal implements classic ratings-based (full-profile) conjoint analysis. Attribute levels are "
        "effects-coded, so each attribute's part-worths sum to zero and describe value relative to that attribute's "
        "average. A separate ordinary-least-squares regression is fitted per respondent; the app reports the "
        "average part-worths, the spread across respondents, per-respondent fit (R²), and attribute importance "
        "(each attribute's share of the total preference range, averaged over respondents)."
    )
    method_columns = st.columns(2)
    with method_columns[0], st.container(border=True):
        st.markdown("#### Per-respondent estimation")
        st.write(
            "Preserves differences between people and powers the simulator. A respondent needs at least as many "
            "rated profiles as model parameters; others fall back to the pooled model."
        )
    with method_columns[1], st.container(border=True):
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
        - Willingness-to-pay conversions are deliberately excluded: dividing part-worths by a price coefficient is fragile with categorical prices and is easy to over-read. For the actual pricing decision, use **Tag Signal**, the pricing sibling — it works from price experiments, sales history, or willingness-to-pay surveys.
        """
    )
    st.subheader("The single-concept test")
    st.write(
        "Page 4 covers the other classic pre-launch question: one described concept, the five-point "
        "purchase-intent scale, top-box and top-two-box shares with Wilson 95% intervals, reasons for "
        "rejection, and an optional segment comparison. Stated intent overstates real buying, so the "
        "trial estimate applies user-editable discount weights and always carries its unadjusted ceiling "
        "and its assumptions in the export. It is a screening read on one idea — not a demand forecast, "
        "and not a substitute for conjoint when the question is which features to build."
    )
    with st.expander("References and implementation notes"):
        st.write(
            "See `docs/methods.md` for the estimation details, formulas, warnings, and citations "
            "(Green & Srinivasan 1978; Green & Rao 1971; Orme 2020). Every computational module is separate "
            "from Streamlit and covered by automated tests."
        )


PAGE_FUNCTIONS = {
    "Welcome": welcome_page,
    "1 · Data & design": data_page,
    "2 · Utilities & importance": utilities_page,
    "3 · Simulate & export": simulate_page,
    "4 · Concept test": concept_page,
    "Methods & limits": methods_page,
}


def render() -> None:
    """Draw the whole Choice Signal app on the current page. Never calls st.set_page_config or st.navigation."""
    sig.apply(NS)
    _ensure_state()
    page = _sidebar()
    sig.masthead(NS, MASTHEAD_PROMISES, MASTHEAD_KICKER)
    try:
        PAGE_FUNCTIONS[page]()
    except Exception as exc:
        show_error(exc)
    sig.footer(NS, __version__, FOOTER_LINE)
