"""Streamlit drag-and-drop redaction demo for `ogentic-shield`.

Hosted on HuggingFace Spaces (free tier — CPU-only). Layer 3 (LLM) is
disabled here because the free tier has no GPU; install locally and run
`shield analyze --llm` for the full pipeline.

Privacy invariant: uploads are processed in-memory only. No persistence,
no telemetry, no third-party SDKs. The temp file the parser needs lives
in `tempfile.mkstemp(...)` and is unlinked before this function returns.
"""

from __future__ import annotations

import dataclasses
import json
import os
import tempfile
from pathlib import Path

import streamlit as st

from ogentic_shield import Shield
from ogentic_shield.models import DetectionLayer

# ─── Constants ──────────────────────────────────────────────────────────────

SAMPLES_DIR = Path(__file__).parent / "samples"

SAMPLE_FILES = {
    "Legal memo (privileged)": SAMPLES_DIR / "legal-sample.txt",
    "Clinical SOAP note (PHI)": SAMPLES_DIR / "clinical-sample.txt",
    "Finance M&A memo (MNPI)": SAMPLES_DIR / "finance-sample.txt",
}

# Note: brief asked for `shield-healthcare` but the actual shield profile id
# is `shield-therapy` (HIPAA-PHI profile). Same scope, different label.
PROFILE_OPTIONS = ["shield-legal", "shield-therapy", "shield-finance"]

# Map UI strength → min_confidence. Higher confidence = stricter = fewer
# false positives but more misses. Pre-LLM these are the levers users have.
STRENGTH_TO_CONFIDENCE = {
    "Low (more recall, more false positives)": 0.5,
    "Medium (balanced)": 0.7,
    "High (fewer false positives, may miss low-confidence hits)": 0.9,
}

# Layer 3 (LLM) is intentionally excluded — HF free tier has no GPU and we
# never want a hosted demo to phone home. Local users get LLM via the
# unrestricted CLI / Python API.
HOSTED_LAYERS = [DetectionLayer.REGEX, DetectionLayer.NER, DetectionLayer.RULES]

ACCEPTED_EXTENSIONS = ["txt", "md", "log"]
# .txt/.md/.log are Phase-1 supported end-to-end. PDF/DOCX/EML need the
# `[documents]` extra (Phase 2); we don't list them in the uploader until
# the upstream extractors land — listing here would let users upload a
# PDF and only learn at run-time that it raises UnsupportedDocumentFormatError.

# ─── Helpers ────────────────────────────────────────────────────────────────


def _materialize_upload(uploaded) -> Path:
    """Stage an uploaded file on disk so Shield's path-based API can read it.

    Streamlit gives us an in-memory buffer; Shield.redact_document wants
    a path. We write to a private temp file, return the path, and the
    caller is responsible for unlinking after use.
    """
    suffix = "." + uploaded.name.rsplit(".", 1)[-1].lower()
    fd, tmp_path = tempfile.mkstemp(suffix=suffix, prefix="shield_demo_")
    with os.fdopen(fd, "wb") as fh:
        fh.write(uploaded.getvalue())
    return Path(tmp_path)


def _entity_rows(entities) -> list[dict]:
    """Flatten DetectedEntity dataclasses into a streamlit-dataframe-friendly list."""
    return [
        {
            "start": e.start,
            "end": e.end,
            "category": e.category,
            "category_group": e.category_group.value
            if hasattr(e.category_group, "value")
            else str(e.category_group),
            "text": e.text,
            "confidence": round(e.confidence, 3),
            "layer": e.detection_layer.value
            if hasattr(e.detection_layer, "value")
            else str(e.detection_layer),
        }
        for e in entities
    ]


def _mapping_to_json(mapping) -> str:
    """Mapping dataclass → pretty JSON (for the download button)."""
    payload = dataclasses.asdict(mapping)
    return json.dumps(payload, indent=2, default=str)


# ─── Page setup ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="ogentic-shield — drag-and-drop redaction demo",
    page_icon="🛡️",
    layout="wide",
)

st.title("🛡️ ogentic-shield: drag-and-drop redaction demo")
st.markdown(
    "Drop a document, pick one or more **shield profiles**, hit **Run**. "
    "See the redacted output alongside the entity table — no install needed."
)

st.info(
    "**Layer 3 (LLM) is disabled in this hosted demo** — HF Spaces free tier "
    "has no GPU. You're seeing Layers 1 (regex), 2 (NER), and the rules engine. "
    "For the full pipeline with localhost-Ollama Layer 3, "
    "`pip install ogentic-shield[llm]` and run the CLI locally.",
    icon="ℹ️",
)

# ─── Input column / output column ───────────────────────────────────────────

left, right = st.columns([1, 2], gap="large")

with left:
    st.subheader("1. Input")

    input_mode = st.radio(
        "Source",
        options=["Use a sample", "Upload your own"],
        index=0,
        help="Samples are bundled synthetic documents. "
        "Uploaded files stay in-memory and are unlinked after processing.",
    )

    if input_mode == "Use a sample":
        sample_label = st.radio("Sample document", list(SAMPLE_FILES.keys()), index=0)
        uploaded = None
    else:
        uploaded = st.file_uploader(
            "Drop a .txt / .md / .log file (≤10 MB)",
            type=ACCEPTED_EXTENSIONS,
            accept_multiple_files=False,
            help="Plain text only in the hosted demo. "
            "Local install supports PDF/DOCX/EML via the [documents] extra.",
        )
        sample_label = None

    st.subheader("2. Profile(s)")
    selected_profiles = st.multiselect(
        "Shield profiles to apply",
        options=PROFILE_OPTIONS,
        default=PROFILE_OPTIONS,
        help="shield-legal = attorney-client privilege; shield-therapy = HIPAA PHI; "
        "shield-finance = MNPI / insider info. Pick more than one to see how "
        "category groups stack.",
    )

    st.subheader("3. Redaction strength")
    strength_label = st.select_slider(
        "Minimum confidence threshold",
        options=list(STRENGTH_TO_CONFIDENCE.keys()),
        value="Medium (balanced)",
    )
    min_confidence = STRENGTH_TO_CONFIDENCE[strength_label]

    run = st.button("Run shield ▶", type="primary", use_container_width=True)

with right:
    st.subheader("Output")

    if not run:
        st.markdown(
            "👈 Pick a sample (or upload), choose profiles, hit **Run**.  \n"
            "*Detection runs entirely in-memory in this Space — no upload is persisted "
            "and Layer 3 is off.*"
        )
    else:
        if not selected_profiles:
            st.error("Pick at least one shield profile.")
            st.stop()

        # Resolve the path. Either a bundled sample (already on disk and safe to read)
        # or a temp file we materialize from the upload buffer.
        tmp_to_cleanup: Path | None = None
        if input_mode == "Use a sample":
            doc_path = SAMPLE_FILES[sample_label]
        else:
            if uploaded is None:
                st.error("Please upload a file first, or switch back to a sample.")
                st.stop()
            doc_path = _materialize_upload(uploaded)
            tmp_to_cleanup = doc_path

        try:
            with st.spinner("Analyzing + redacting…"):
                shield = Shield(profiles=selected_profiles)
                result = shield.redact_document(
                    doc_path,
                    profiles=selected_profiles,
                    layers=HOSTED_LAYERS,
                    min_confidence=min_confidence,
                )

            entities = result.analysis.aggregate.entities

            top_a, top_b, top_c, top_d = st.columns(4)
            top_a.metric("Sensitivity score", f"{result.analysis.aggregate.score}/100")
            top_b.metric(
                "Sensitivity level",
                result.analysis.aggregate.sensitivity_level.value,
            )
            top_c.metric("Entities found", len(entities))
            top_d.metric(
                "Routing",
                result.analysis.aggregate.routing_suggestion.upper(),
            )

            st.markdown("---")
            orig_col, red_col = st.columns(2)
            with orig_col:
                st.markdown("**Original**")
                st.text_area(
                    "original_text",
                    value=result.original_text,
                    height=320,
                    label_visibility="collapsed",
                )
            with red_col:
                st.markdown("**Redacted**")
                st.text_area(
                    "redacted_text",
                    value=result.redacted_text,
                    height=320,
                    label_visibility="collapsed",
                )

            st.markdown("### Entities detected")
            rows = _entity_rows(entities)
            if rows:
                st.dataframe(rows, use_container_width=True, hide_index=True)
            else:
                st.success(
                    "No entities matched the selected profile(s) at this confidence. "
                    "Try lowering the redaction strength."
                )

            mapping_json = _mapping_to_json(result.mapping)
            st.download_button(
                "Download mapping JSON (for unredact)",
                data=mapping_json,
                file_name="redaction-mapping.json",
                mime="application/json",
                help="Pass this back through `Shield.unredact(text, mapping)` "
                "to restore the original tokens.",
            )

        finally:
            # Strict invariant: uploaded files never persist past the request.
            if tmp_to_cleanup is not None:
                try:
                    tmp_to_cleanup.unlink()
                except OSError:
                    pass

# ─── Footer ─────────────────────────────────────────────────────────────────

st.markdown("---")
st.markdown(
    "Built with [`ogentic-shield`](https://pypi.org/project/ogentic-shield/) · "
    "[GitHub repo](https://github.com/OgenticAI/shield-streamlit-demo) · "
    "[Upstream shield repo](https://github.com/OgenticAI/ogentic-shield) · "
    "[File an issue](https://github.com/OgenticAI/shield-streamlit-demo/issues/new)"
)
