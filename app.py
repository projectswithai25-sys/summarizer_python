import os
import re
import io
import time
from typing import List, Tuple, Optional

import streamlit as st

# --- Content fetching ---
import requests
import trafilatura
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound, VideoUnavailable

# --- PDF parsing ---
import fitz  # PyMuPDF

# --- Summarization (free / local) ---
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lex_rank import LexRankSummarizer

# -------------- Helpers --------------
YOUTUBE_PAT = re.compile(r"(?:youtube\.com/watch\?v=|youtu\.be/)([A-Za-z0-9_\-]{6,})")

def extract_youtube_id(url: str) -> Optional[str]:
    m = YOUTUBE_PAT.search(url)
    return m.group(1) if m else None

def fetch_web_text(url: str, timeout=20) -> str:
    # Use trafilatura for robust article extraction
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        return ""
    text = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
    return text or ""

def fetch_youtube_transcript(video_id: str, tried_en=False) -> str:
    # Try to fetch transcript, preferring English but fall back if needed
    try_order = ["en", "en-US", "en-GB"]
    # First, try generated transcript list
    try:
        transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
        # Prefer English if available
        for lang in try_order:
            if transcripts.find_transcript([lang]):
                t = transcripts.find_transcript([lang]).fetch()
                return " ".join([x["text"] for x in t])
    except Exception:
        pass

    # If not, try "manually" fetching any transcript and translate to English (YT API supports translation)
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        for transcript in transcript_list:
            try:
                t = transcript.translate("en").fetch()
                return " ".join([x["text"] for x in t])
            except Exception:
                continue
    except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable):
        return ""
    except Exception:
        return ""
    return ""

def read_pdf(file_bytes: bytes) -> str:
    text_parts = []
    with fitz.open(stream=io.BytesIO(file_bytes), filetype="pdf") as doc:
        for page in doc:
            text_parts.append(page.get_text())
    return "\n".join(text_parts)

def chunk_text(text: str, max_chars: int = 3000) -> List[str]:
    # Simple chunking by paragraphs/sentences to keep boundaries
    if len(text) <= max_chars:
        return [text]
    # Split by sentences
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks, buf = [], ""
    for s in sentences:
        if len(buf) + len(s) + 1 > max_chars:
            if buf.strip():
                chunks.append(buf.strip())
            buf = s
        else:
            buf += (" " if buf else "") + s
    if buf.strip():
        chunks.append(buf.strip())
    return chunks

def summarize_lexrank(text: str, sentences: int = 5) -> str:
    try:
        parser = PlaintextParser.from_string(text, Tokenizer("english"))
        summarizer = LexRankSummarizer()
        summary_sents = summarizer(parser.document, sentences)
        return " ".join(str(s) for s in summary_sents)
    except Exception:
        # Fallback: take first N sentences
        fallback = " ".join(re.split(r'(?<=[.!?])\s+', text)[:sentences])
        return fallback

def summarize_long_text(text: str, target_sentences: int = 6) -> str:
    # Chunk then summarize each chunk; finally summarize combined summaries
    chunks = chunk_text(text, max_chars=4000)
    per_chunk = max(3, min(7, target_sentences))
    chunk_summaries = [summarize_lexrank(c, sentences=per_chunk) for c in chunks]
    combined = "\n".join(chunk_summaries)
    final = summarize_lexrank(combined, sentences=target_sentences)
    return final

def clean_text(t: str) -> str:
    t = re.sub(r'\s+', ' ', t).strip()
    return t

# -------------- Streamlit UI --------------
st.set_page_config(page_title="Summarizer — Text, Video & PDF", page_icon="🧠", layout="wide")

st.title("🧠 Summarizer — Links (Text/YouTube) & PDFs")
st.caption("Paste one or more links (comma-separated), or upload PDFs/TXT files. Get a crisp, consolidated summary.")

with st.expander("➕ Inputs", expanded=True):
    urls_input = st.text_area(
        "Links (text pages or YouTube):",
        placeholder="https://example.com/article, https://youtu.be/VIDEOID",
        height=80,
    )
    uploads = st.file_uploader(
        "Upload files (PDF or .txt). Multiple allowed.",
        type=["pdf", "txt"],
        accept_multiple_files=True
    )
    max_sentences = st.slider("Summary length (sentences)", min_value=3, max_value=12, value=6, step=1)

go = st.button("🚀 Generate Summary", type="primary")

if go:
    with st.spinner("Fetching and summarizing..."):
        sources = []
        # Handle URLs
        if urls_input.strip():
            urls = [u.strip() for u in urls_input.split(",") if u.strip()]
            for u in urls:
                yid = extract_youtube_id(u)
                if yid:
                    txt = fetch_youtube_transcript(yid)
                    label = f"YouTube: {u}"
                else:
                    txt = fetch_web_text(u)
                    label = f"Web: {u}"
                if txt:
                    sources.append((label, clean_text(txt)))
                else:
                    sources.append((label, ""))

        # Handle uploads
        for f in uploads or []:
            data = f.read()
            if f.type == "application/pdf" or f.name.lower().endswith(".pdf"):
                txt = read_pdf(data)
                label = f"PDF: {f.name}"
            else:
                try:
                    txt = data.decode("utf-8", errors="ignore")
                except Exception:
                    txt = ""
                label = f"TXT: {f.name}"
            sources.append((label, clean_text(txt)))

        # Filter out empty
        non_empty = [(label, txt) for label, txt in sources if txt and txt.strip()]
        empty = [label for label, txt in sources if not txt or not txt.strip()]

        if not non_empty:
            st.error("Couldn't extract any text. Check links/permissions or try different sources.")
        else:
            # Per-source summaries
            st.subheader("Per‑source summaries")
            per_summaries = []
            for label, txt in non_empty:
                summary = summarize_long_text(txt, target_sentences=max_sentences)
                per_summaries.append((label, summary))
                with st.container(border=True):
                    st.markdown(f"**{label}**")
                    st.write(summary)

            # Consolidated overall summary
            st.subheader("Consolidated takeaways")
            combined_text = "\n\n".join(s for _, s in per_summaries)
            overall = summarize_long_text(combined_text, target_sentences=max_sentences)
            with st.container(border=True):
                st.markdown("**Overall Summary**")
                st.write(overall)

            # Optional: bulletized crisp points (extract top sentences from the overall summary)
            st.subheader("Crisp takeaways")
            bullets = re.split(r'(?<=[.!?])\s+', overall)
            bullets = [b.strip() for b in bullets if b.strip()]
            bullets = bullets[: max(5, max_sentences)]
            st.markdown("\n".join([f"- {b}" for b in bullets]))

        if empty:
            with st.expander("Sources with no extractable text (click to view)"):
                for label in empty:
                    st.write(f"• {label} — no text found or transcript disabled")

st.caption("Built with Streamlit, Trafilatura, PyMuPDF, Sumy LexRank, and YouTube Transcript API — all free libraries.")