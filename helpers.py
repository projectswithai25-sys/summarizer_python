import re
import io
from typing import List, Optional, Tuple

import streamlit as st
import trafilatura
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound, VideoUnavailable
import fitz  # PyMuPDF
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lex_rank import LexRankSummarizer

YOUTUBE_PAT = re.compile(r"(?:youtube\.com/watch\?v=|youtu\.be/)([A-Za-z0-9_\-]{6,})")

def extract_youtube_id(url: str) -> Optional[str]:
    m = YOUTUBE_PAT.search(url)
    return m.group(1) if m else None

@st.cache_data
def fetch_web_text(url: str, timeout=20) -> Tuple[Optional[str], Optional[str]]:
    try:
        downloaded = trafilatura.fetch_url(url, timeout=timeout)
        if not downloaded:
            return None, "Failed to download content."
        text = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
        if not text:
            return None, "Could not extract main text from the page."
        return text, None
    except Exception as e:
        return None, f"An error occurred: {e}"

@st.cache_data
def fetch_youtube_transcript(video_id: str) -> Tuple[Optional[str], Optional[str]]:
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        try_order = ["en", "en-US", "en-GB"]
        for lang in try_order:
            try:
                transcript = transcript_list.find_transcript([lang])
                t = transcript.fetch()
                return " ".join([x["text"] for x in t]), None
            except NoTranscriptFound:
                continue

        for transcript in transcript_list:
            try:
                t = transcript.translate("en").fetch()
                return " ".join([x["text"] for x in t]), None
            except Exception:
                continue

        return None, "No English transcript found and translation failed."

    except TranscriptsDisabled:
        return None, "Transcripts are disabled for this video."
    except VideoUnavailable:
         return None, "This video is unavailable."
    except NoTranscriptFound:
        return None, "No transcript could be found for this video."
    except Exception as e:
        return None, f"Could not fetch transcript: {e}"

@st.cache_data
def read_pdf(file_bytes: bytes) -> Tuple[Optional[str], Optional[str]]:
    try:
        text_parts = []
        with fitz.open(stream=io.BytesIO(file_bytes), filetype="pdf") as doc:
            for page in doc:
                text_parts.append(page.get_text())
        text = "\n".join(text_parts)
        if not text.strip():
            return None, "PDF contains no text."
        return text, None
    except Exception as e:
        return None, f"Failed to read PDF: {e}"

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

def summarize_lexrank(text: str, max_words: int = 150) -> str:
    try:
        parser = PlaintextParser.from_string(text, Tokenizer("english"))
        summarizer = LexRankSummarizer()
        # Request a large number of sentences
        summary_sents_all = summarizer(parser.document, len(parser.document.sentences))

        summary_sents = []
        word_count = 0
        for s in summary_sents_all:
            sentence_word_count = len(str(s).split())
            if word_count + sentence_word_count > max_words:
                break
            summary_sents.append(str(s))
            word_count += sentence_word_count

        return " ".join(summary_sents)
    except Exception:
        # Fallback: take first sentences up to word limit
        sentences = re.split(r'(?<=[.!?])\s+', text)
        summary_words = []
        word_count = 0
        for sentence in sentences:
            sentence_word_count = len(sentence.split())
            if word_count + sentence_word_count > max_words:
                break
            summary_words.append(sentence)
            word_count += sentence_word_count
        fallback = " ".join(summary_words)
        return fallback

@st.cache_data
def summarize_long_text(text: str, target_words: int = 150) -> str:
    # Chunk then summarize each chunk; finally summarize combined summaries
    chunks = chunk_text(text, max_chars=4000)
    # Summarize each chunk to a fixed size to extract key sentences
    chunk_summaries = [summarize_lexrank(c, max_words=100) for c in chunks]
    combined = "\n".join(chunk_summaries)
    # Summarize the combined summaries to the final target word count
    final = summarize_lexrank(combined, max_words=target_words)
    return final

def clean_text(t: str) -> str:
    t = re.sub(r'\s+', ' ', t).strip()
    return t
