---
title: Ogentic-Shield Demo
emoji: 🛡️
colorFrom: green
colorTo: blue
sdk: docker
app_port: 8501
pinned: false
license: apache-2.0
---

<!--
HF Spaces' create-API removed `streamlit` as an SDK option in 2026 — only
gradio/docker/static are accepted. This Space runs Streamlit inside a Docker
container; the app, samples, and behavior are identical to a native Streamlit
Space. See Dockerfile.
-->

# ogentic-shield — drag-and-drop redaction demo

A zero-install Streamlit app that demonstrates the document-redaction surface
of [`ogentic-shield`](https://github.com/OgenticAI/ogentic-shield) — regulatory
sensitivity detection for AI applications.

## Why

Lawyers, therapists, and finance teams are pasting privileged, clinical, and
MNPI content into public AI chats every day. `ogentic-shield` answers a simple
question *before* the text leaves a device: **does this contain something that
should never reach a third-party model?** It detects attorney-client privilege
markers, HIPAA PHI, financial MNPI, and 50+ PII types, then redacts them with
reversible deterministic tokens.

This demo is the 30-second proof. Drop a document, pick a profile, and see what
shield catches — without writing a line of Python. It runs the same detection
pipeline you'd get from `pip install ogentic-shield` and the upstream CLI.

For the engineering surface (CLI, Python API, MCP server, custom profiles),
see [github.com/OgenticAI/ogentic-shield](https://github.com/OgenticAI/ogentic-shield).

## Try it

**Hosted (no install):** click the HuggingFace Spaces tile at
[huggingface.co/spaces/sotto/shield-demo](https://huggingface.co/spaces/sotto/shield-demo)
(replace with the actual URL once David deploys).

**Locally** (preferred for the full pipeline, including Layer 3):

```bash
git clone https://github.com/OgenticAI/shield-streamlit-demo
cd shield-streamlit-demo
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Then open `http://localhost:8501` and drop one of the bundled samples (or your
own `.txt`/`.md`/`.log`). To see the full pipeline including LLM-backed
disambiguation, follow the upstream
[install guide](https://github.com/OgenticAI/ogentic-shield#install) and run
`shield analyze --llm path/to/file.txt` from the CLI.

## What just happened

Under the hood, every document you drop runs through `Shield.redact_document`,
which composes the same three-layer detection pipeline you'd get from the
upstream library:

- **Layer 1 — Regex.** ~50 deterministic patterns (SSNs, MRNs, deal codes,
  Bates numbers, case numbers, ICD-10 codes, …) anchored by context windows
  to keep false positives down. Fast, fully offline.
- **Layer 2 — NER.** A [Microsoft Presidio](https://github.com/microsoft/presidio)
  pipeline over [spaCy](https://spacy.io) `en_core_web_lg`, extended with 30+
  ogentic-shield-specific recognizers (`PRIVILEGE_MARKER`, `PSYCHIATRIC_MED`,
  `MNPI_MARKER`, …) that Presidio doesn't ship with.
- **Layer 3 — LLM (disabled in this hosted demo).** Localhost-only Ollama
  classifier that resolves the ~10% of cases Layers 1+2 leave ambiguous —
  things like "is *this* mention of 'merger' MNPI or background context?".
  Requires GPU/local-CPU compute, which HuggingFace's free Spaces tier doesn't
  give us, so we ship it off by default here. Install locally to flip it on.

The **profiles** (`shield-legal`, `shield-therapy`, `shield-finance`) bundle
domain-tuned recognizer sets and scoring weights — picking more than one
applies the union, so a document that triggers both privilege markers and
MNPI markers gets flagged by both. They're composable and YAML-extensible
(see upstream docs).

The **redaction mapping** is reversible by design. Every sensitive span gets
swapped for a deterministic token like `[Person_a3f9c1]`; pass the mapping
back through `Shield.unredact(text, mapping)` to restore originals. This is
why you can send the redacted text to a public LLM, then locally restore the
real values from the response — the "who" never leaves your machine.

## Privacy & limitations

- **In-memory only.** Uploaded files are written to a temp file (Streamlit's
  uploader needs a path for parsers), processed, then unlinked before the
  request returns. No persistence, no telemetry, no analytics SDKs.
- **No outbound calls.** Layer 1 and 2 run entirely in-process. Layer 3
  (Ollama) is off in this hosted demo and would only ever talk to
  `localhost:11434` in a local install — never a cloud LLM provider.
- **Hosted demo is plain-text only.** PDF/DOCX/EML extraction needs the
  upstream `[documents]` extra, which pulls in `pdfplumber`, `python-docx`,
  and `extract-msg`. The hosted tier sticks to `.txt`/`.md`/`.log` to keep
  the image lean; install locally for the others.
- **Synthetic samples.** The three bundled documents are entirely fictitious
  (Alex Synthetic, Robin Example, Acme Synthetic Inc, fake SSN `000-00-0000`,
  invented case number `26-CV-9999`, etc.). Provenance: hand-written for this
  demo, no real person or organization referenced. Don't paste real
  privileged/PHI/MNPI content into a hosted demo — install locally if you
  want to evaluate against real material.

## License

Apache-2.0 — same as upstream `ogentic-shield`. See [`LICENSE`](./LICENSE).

## Feedback

Open an issue at
[github.com/OgenticAI/shield-streamlit-demo/issues](https://github.com/OgenticAI/shield-streamlit-demo/issues/new)
or file against the upstream
[`ogentic-shield` repo](https://github.com/OgenticAI/ogentic-shield/issues)
for engine-level questions.
