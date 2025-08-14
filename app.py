import streamlit as st
import re
from helpers import (
    extract_youtube_id,
    fetch_web_text,
    fetch_youtube_transcript,
    read_pdf,
    summarize_long_text,
    clean_text,
)

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
    max_words = st.slider("Maximum summary words", min_value=50, max_value=500, value=150, step=10)

go = st.button("🚀 Generate Summary", type="primary")

if go:
    with st.spinner("Fetching and summarizing..."):
        sources = []
        errors = []

        # Handle URLs
        if urls_input.strip():
            urls = [u.strip() for u in urls_input.split(",") if u.strip()]
            for u in urls:
                yid = extract_youtube_id(u)
                if yid:
                    txt, err = fetch_youtube_transcript(yid)
                    label = f"YouTube: {u}"
                else:
                    txt, err = fetch_web_text(u)
                    label = f"Web: {u}"

                if err:
                    errors.append((label, err))
                if txt:
                    sources.append((label, clean_text(txt)))

        # Handle uploads
        for f in uploads or []:
            data = f.read()
            if f.type == "application/pdf" or f.name.lower().endswith(".pdf"):
                txt, err = read_pdf(data)
                label = f"PDF: {f.name}"
            else:
                try:
                    txt = data.decode("utf-8", errors="ignore")
                    err = None
                except Exception as e:
                    txt = None
                    err = f"Error reading text file: {e}"
                label = f"TXT: {f.name}"

            if err:
                errors.append((label, err))
            if txt:
                sources.append((label, clean_text(txt)))

        # Filter out empty
        non_empty = [(label, txt) for label, txt in sources if txt and txt.strip()]

        if not non_empty:
            st.error("Couldn't extract any text. Check links/permissions or try different sources.")
        else:
            # Per-source summaries
            st.subheader("Per‑source summaries")
            per_summaries = []
            for label, txt in non_empty:
                summary = summarize_long_text(txt, target_words=max_words)
                per_summaries.append((label, summary))
                with st.container(border=True):
                    st.markdown(f"**{label}**")
                    st.write(summary)

            # Consolidated overall summary
            st.subheader("Consolidated takeaways")
            combined_text = "\n\n".join(s for _, s in per_summaries)
            overall = summarize_long_text(combined_text, target_words=max_words)
            with st.container(border=True):
                st.markdown("**Overall Summary**")
                st.write(overall)

            # Optional: bulletized crisp points (extract top sentences from the overall summary)
            st.subheader("Crisp takeaways")
            bullets = re.split(r'(?<=[.!?])\s+', overall)
            bullets = [b.strip() for b in bullets if b.strip()]
            bullets = bullets[:5]
            st.markdown("\n".join([f"- {b}" for b in bullets]))

        if errors:
            with st.expander("Sources with errors (click to view)"):
                for label, err in errors:
                    st.write(f"• {label} — {err}")

st.caption("Built with Streamlit, Trafilatura, PyMuPDF, Sumy LexRank, and YouTube Transcript API — all free libraries.")