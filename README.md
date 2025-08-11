# Summarizer (Free Python Version)

A lightweight, free-to-run Streamlit app that summarizes:
- **Web articles** (via `trafilatura`)
- **YouTube videos** (via transcripts using `youtube-transcript-api`)
- **PDFs** (via `pymupdf`)
- **TXT files**

It uses **extractive summarization** (Sumy LexRank), which is fast and free. You can later swap in LLM-based abstractive summarization if you add an API key.

## Run locally

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

Open the URL displayed by Streamlit in your browser.

## Deploy free

- **Streamlit Community Cloud**: one-click from a GitHub repo.
- **Hugging Face Spaces (Gradio/Streamlit)**: add these files to a new Space and select Streamlit.

## Notes

- YouTube transcripts must be enabled for the video; otherwise the app reports "no text found or transcript disabled".
- For very long documents, the app chunks text before summarizing, then merges the summaries.
- You can adjust the number of sentences in the summary with the slider.