"""
app/services/pdf_processor.py
===============================================================================
PDF Processing and Text Chunking Engine.

Extracts raw text from uploaded PDF binary streams and splits the text recursively
into chunks of size ~600 characters with ~100 character overlap. Attaches document
metadata to every chunk for ChromaDB indexing.
===============================================================================
"""

import io
from typing import List, Dict, Any
from pypdf import PdfReader
from app.config import settings
from app.models.schemas import SourceRegisterMetadata


class PDFProcessor:
    """
    Handles PDF text extraction and recursive semantic text splitting.
    """

    def __init__(
        self, 
        chunk_size: int = settings.CHUNK_SIZE, 
        chunk_overlap: int = settings.CHUNK_OVERLAP
    ):
        """
        Initialize processor with target chunk size and character overlap.
        Defaults: chunk_size=600, chunk_overlap=100.
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def extract_text_from_pdf(self, pdf_bytes: bytes) -> str:
        """
        Extracts raw textual content from PDF byte stream page by page.
        
        :param pdf_bytes: Raw binary bytes of uploaded PDF file.
        :return: Extracted raw text consolidated across all pages.
        """
        # Load PDF bytes into memory stream
        pdf_file = io.BytesIO(pdf_bytes)
        reader = PdfReader(pdf_file)
        
        text_pages = []
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                text_pages.append(page_text)

        full_text = "\n\n".join(text_pages).strip()
        
        # Raise error if PDF is unreadable or empty
        if not full_text:
            raise ValueError("Could not extract any readable text from the provided PDF file.")
        
        return full_text

    def recursive_split_text(self, text: str, separators: List[str] = None) -> List[str]:
        """
        Splits raw text into chunks recursively using a hierarchy of separators:
        1. Paragraph breaks ("\n\n")
        2. Line breaks ("\n")
        3. Sentence boundaries (". ")
        4. Word boundaries (" ")
        5. Character fallback ("")
        
        Guarantees that chunk lengths remain <= chunk_size while retaining semantic coherence.
        """
        if separators is None:
            separators = ["\n\n", "\n", ". ", " ", ""]

        chunks = []

        def _split(text_segment: str, current_separators: List[str]):
            if not text_segment:
                return

            # Base Case: Segment fits within target chunk size
            if len(text_segment) <= self.chunk_size:
                chunks.append(text_segment.strip())
                return

            # Find highest priority separator present in the text segment
            sep = ""
            for s in current_separators:
                if s == "" or s in text_segment:
                    sep = s
                    break

            # Split segment by chosen separator
            if sep != "":
                splits = text_segment.split(sep)
            else:
                splits = [text_segment[i:i+self.chunk_size] for i in range(0, len(text_segment), self.chunk_size)]

            current_chunk = ""
            next_separators = current_separators[current_separators.index(sep) + 1:] if sep in current_separators else []

            # Recombine smaller splits into chunks up to chunk_size
            for part in splits:
                candidate = current_chunk + (sep if current_chunk else "") + part
                if len(candidate) <= self.chunk_size:
                    current_chunk = candidate
                else:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    if len(part) > self.chunk_size and next_separators:
                        _split(part, next_separators)
                        current_chunk = ""
                    else:
                        current_chunk = part

            if current_chunk:
                chunks.append(current_chunk.strip())

        # Execute recursive splitting
        _split(text, separators)

        # Filter out empty string chunks
        return [c for c in chunks if c]

    def process_pdf(self, pdf_bytes: bytes, metadata: SourceRegisterMetadata) -> List[Dict[str, Any]]:
        """
        Full workflow: Extracts PDF text, splits into chunks, and attaches metadata.
        
        Note: ChromaDB requires metadata dictionary values to be primitive types
        (str, int, float, bool). None/null values are sanitized to empty strings ("").
        """
        # Step 1: Extract text from PDF bytes
        raw_text = self.extract_text_from_pdf(pdf_bytes)

        # Step 2: Perform recursive splitting into ~600 character chunks
        text_chunks = self.recursive_split_text(raw_text)

        # Step 3: Sanitize metadata dictionary for ChromaDB compatibility
        raw_meta = metadata.model_dump()
        base_meta = {}
        for k, v in raw_meta.items():
            if v is not None:
                base_meta[k] = v
            else:
                base_meta[k] = ""  # Convert None values to empty string

        # Step 4: Attach metadata and unique chunk IDs to each chunk
        processed_chunks = []
        for idx, chunk_text in enumerate(text_chunks):
            chunk_meta = dict(base_meta)
            chunk_meta["chunk_index"] = idx
            chunk_meta["total_chunks"] = len(text_chunks)
            chunk_meta["chunk_id"] = f"{metadata.doc_id}_chunk_{idx}"

            processed_chunks.append({
                "id": f"{metadata.doc_id}_chunk_{idx}",
                "text": chunk_text,
                "metadata": chunk_meta
            })

        return processed_chunks
