import io

import regex as re
import pymupdf
from docx import Document  # For Word files
from PIL import Image
import pytesseract  # Make sure you have Tesseract OCR installed and pytesseract installed

ALPHA_RE = r'\p{L}'
ALPHA3_RE = r'\p{L}{3,}'


def is_meaningful_text(text: str) -> bool:
    if len(text) < 400:
        return False

    words = text.split()
    if len(words) < 50:
        return False

    alpha_chars = re.findall(ALPHA_RE, text)
    alpha_ratio = len(alpha_chars) / max(len(text), 1)

    word_like = [w for w in words if re.search(ALPHA3_RE, w)]
    word_like_ratio = len(word_like) / len(words)

    gibberish_penalty = len(re.findall(r"[^\w\s\.,;:!?-]", text)) / len(text)

    return alpha_ratio > 0.65 and word_like_ratio > 0.50 and gibberish_penalty < 0.10


class TextExtractor:

    def __init__(self, file_content: bytes, file_ext: str):
        file_stream = io.BytesIO(file_content)
        self._file_stream = file_stream
        self._file_ext = file_ext

    # Unified function to extract text based on file type
    def extract_text_from_uploaded_file(self) -> str:
        self._file_stream.seek(0)  # Ensure the pointer is at the start
        if self._file_ext == 'pdf':
            return self._extract_text_from_pdf()
        elif self._file_ext == 'docx':
            return self._extract_text_from_word()
        elif self._file_ext == 'txt':
            return self._file_stream.read().decode('utf-8')  # Decode directly for text files
        else:
            raise ValueError("Unsupported file type!")

    def _extract_text_from_pdf(self) -> str:
        self._file_stream.seek(0)  # Ensure the pointer is at the start
        text = ""
        doc = pymupdf.open(stream=self._file_stream, filetype="pdf")
        previous_bottom = None  # To track the vertical position of the last line

        for page in doc:
            page_text = ""
            blocks = page.get_text("dict")["blocks"]
            fallback_failures = 0

            for block in blocks:
                has_done_image_ocr = False
                block_text = ""

                if block["type"] == 0 and "lines" in block:
                    for line in block["lines"]:
                        current_top = line['bbox'][1]
                        if previous_bottom is not None and current_top - previous_bottom > 10:
                            block_text += "\n\n"

                        line_text = " ".join([span["text"].strip() for span in line["spans"]])
                        block_text += line_text.strip() + " "
                        previous_bottom = line['bbox'][3]

                    page_text += block_text.strip() + "\n"

                elif block["type"] == 1 and 'image' in block:
                    try:
                        image_bytes = block["image"]
                        image = Image.open(io.BytesIO(image_bytes))
                        ocr_text = pytesseract.image_to_string(image, lang="ara+eng").strip()
                        block_text = ocr_text.strip()
                        page_text += block_text
                        has_done_image_ocr = True
                    except Exception as e:
                        print(f"OCR failed on image block (page {page.number}): {e}")

                # ➕ Add fallback OCR for gibberish block_text if not handled as image
                if not has_done_image_ocr and (not is_meaningful_text(block_text) or not block_text):
                    try:
                        bbox = block['bbox']
                        if len(bbox) != 4 or bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
                            raise ValueError(f"Invalid bbox: {bbox}")

                        rect = pymupdf.Rect(*bbox)
                        if rect.width < 2 or rect.height < 2:
                            raise ValueError(f"Skipping OCR fallback: degenerate bbox: {bbox}")

                        pix = page.get_pixmap(clip=rect)
                        image = Image.open(io.BytesIO(pix.tobytes("png")))
                        ocr_text = pytesseract.image_to_string(image, lang="ara+eng").strip()

                        if ocr_text:
                            page_text += ocr_text + "\n"
                            print(f"OCR fallback applied to gibberish block on page {page.number}")
                            print(ocr_text)
                    except Exception as e:
                        fallback_failures += 1
                        print(f"OCR fallback failed for block on page {page.number}: {e}")

            # 🛡️ If too many block-level OCRs failed, fallback to full-page OCR
            if fallback_failures > len(blocks) * 0.3:
                print(f"⚠ Too many OCR block failures on page {page.number} — applying full-page OCR")
                try:
                    pix = page.get_pixmap()
                    image = Image.open(io.BytesIO(pix.tobytes("png")))
                    page_text = pytesseract.image_to_string(image).strip() + "\n"
                except Exception as e:
                    print(f"Full-page OCR failed on page {page.number}: {e}")
                    page_text = ""

            text += page_text

        print(text)
        return text if is_meaningful_text(text) else ""

    # Function to extract text from Word
    def _extract_text_from_word(self) -> str:
        self._file_stream.seek(0)  # Reset pointer to the beginning
        doc = Document(self._file_stream)
        return "\n".join([para.text for para in doc.paragraphs])
