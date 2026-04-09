from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from pathlib import Path

import fitz
import numpy as np
import streamlit as st
from PIL import Image


SAMPLE_SCALE = 0.35
CORNER_PRIORITY = ("bottom-right", "bottom-left", "top-right", "top-left")
DARK_PIXEL_THRESHOLD = 210
MAX_DARK_RATIO = 0.16
MAX_STD_DEV = 22


@dataclass(frozen=True)
class PlacementResult:
    corner: str
    width: float
    height: float
    rect: fitz.Rect
    mode: str


def normalize_image(uploaded_file) -> bytes:
    image = Image.open(io.BytesIO(uploaded_file.getvalue())).convert("RGBA")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def scaled_logo_dimensions(page: fitz.Page, logo_size: tuple[int, int], preferred_width: float) -> tuple[float, float]:
    logo_width_px, logo_height_px = logo_size
    aspect = logo_height_px / max(logo_width_px, 1)
    width = min(preferred_width, page.rect.width * 0.22)
    height = width * aspect
    return width, height


def candidate_rect(page: fitz.Page, corner: str, width: float, height: float, margin: float) -> fitz.Rect:
    page_rect = page.rect
    if corner == "bottom-right":
        return fitz.Rect(
            page_rect.width - margin - width,
            page_rect.height - margin - height,
            page_rect.width - margin,
            page_rect.height - margin,
        )
    if corner == "bottom-left":
        return fitz.Rect(
            margin,
            page_rect.height - margin - height,
            margin + width,
            page_rect.height - margin,
        )
    if corner == "top-right":
        return fitz.Rect(
            page_rect.width - margin - width,
            margin,
            page_rect.width - margin,
            margin + height,
        )
    return fitz.Rect(margin, margin, margin + width, margin + height)


def has_enough_whitespace(page: fitz.Page, rect: fitz.Rect) -> bool:
    matrix = fitz.Matrix(SAMPLE_SCALE, SAMPLE_SCALE)
    pix = page.get_pixmap(matrix=matrix, alpha=False, clip=rect)
    if pix.width == 0 or pix.height == 0:
        return False

    gray_image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples).convert("L")
    gray_array = np.array(gray_image)
    dark_ratio = float(np.mean(gray_array < DARK_PIXEL_THRESHOLD))
    std_dev = float(np.std(gray_array))

    # Accept a corner when it is either mostly light/empty or visually uniform,
    # which helps with scanned PDFs and image-heavy pages.
    return dark_ratio <= MAX_DARK_RATIO or std_dev <= MAX_STD_DEV


def find_logo_placement(
    page: fitz.Page,
    logo_size: tuple[int, int],
    preferred_width: float,
    min_width: float,
    margin: float,
) -> PlacementResult:
    base_width, base_height = scaled_logo_dimensions(page, logo_size, preferred_width)

    for corner in CORNER_PRIORITY:
        rect = candidate_rect(page, corner, base_width, base_height, margin)
        if has_enough_whitespace(page, rect):
            return PlacementResult(corner, base_width, base_height, rect, "preferred-size")

    current_width = base_width
    while current_width >= min_width:
        current_height = base_height * (current_width / base_width)
        lower_right = candidate_rect(page, "bottom-right", current_width, current_height, margin)
        if has_enough_whitespace(page, lower_right):
            return PlacementResult("bottom-right", current_width, current_height, lower_right, "reduced-lower-right")
        for corner in CORNER_PRIORITY[1:]:
            rect = candidate_rect(page, corner, current_width, current_height, margin)
            if has_enough_whitespace(page, rect):
                return PlacementResult(corner, current_width, current_height, rect, "reduced-other-corner")
        current_width -= max(4, preferred_width * 0.08)

    fallback_height = base_height * (min_width / max(base_width, 1))
    fallback_rect = candidate_rect(page, "bottom-right", min_width, fallback_height, margin)
    return PlacementResult("bottom-right", min_width, fallback_height, fallback_rect, "fallback")


def draw_full_bleed_image(page: fitz.Page, image_bytes: bytes) -> None:
    image = Image.open(io.BytesIO(image_bytes))
    image_width, image_height = image.size
    image_aspect = image_width / max(image_height, 1)
    page_aspect = page.rect.width / max(page.rect.height, 1)

    # Fill the whole cover page area after sizing the page to the image aspect.
    if image_aspect > page_aspect:
        draw_height = page.rect.height
        draw_width = draw_height * image_aspect
    else:
        draw_width = page.rect.width
        draw_height = draw_width / image_aspect

    x0 = (page.rect.width - draw_width) / 2
    y0 = (page.rect.height - draw_height) / 2
    page.insert_image(
        fitz.Rect(x0, y0, x0 + draw_width, y0 + draw_height),
        stream=image_bytes,
        keep_proportion=True,
        overlay=True,
    )


def insert_cover_page(target_doc: fitz.Document, image_bytes: bytes, position: str, reference_rect: fitz.Rect) -> None:
    image = Image.open(io.BytesIO(image_bytes))
    image_width, image_height = image.size
    image_aspect = image_width / max(image_height, 1)

    cover_width = float(reference_rect.width)
    cover_height = cover_width / image_aspect

    page = target_doc.new_page(
        width=cover_width,
        height=float(cover_height),
        pno=0 if position == "start" else len(target_doc),
    )
    draw_full_bleed_image(page, image_bytes)


def process_pdf(
    pdf_bytes: bytes,
    logo_bytes: bytes,
    institute_bytes: bytes,
    preferred_width: float,
    min_width: float,
    margin: float,
) -> bytes:
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    first_page_rect = fitz.Rect(document[0].rect)
    logo_image = Image.open(io.BytesIO(logo_bytes))
    logo_size = logo_image.size

    for page in document:
        placement = find_logo_placement(page, logo_size, preferred_width, min_width, margin)
        page.insert_image(placement.rect, stream=logo_bytes, keep_proportion=True, overlay=True)

    insert_cover_page(document, institute_bytes, "start", first_page_rect)
    insert_cover_page(document, institute_bytes, "end", first_page_rect)

    output = io.BytesIO()
    document.save(output, garbage=3, deflate=True)
    document.close()
    return output.getvalue()


def build_zip(processed_files: list[tuple[str, bytes]]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for filename, file_bytes in processed_files:
            archive.writestr(filename, file_bytes)
    return buffer.getvalue()


def main() -> None:
    st.set_page_config(page_title="PDF Logo Corner App", page_icon="PDF", layout="wide")

    st.title("PDF Logo Corner App")
    st.caption(
        "Upload one or many PDFs, add your logo to the best corner on every page, and place your institute image at the beginning and end."
    )

    with st.sidebar:
        st.header("Branding Rules")
        preferred_width = st.slider("Preferred logo width", min_value=30, max_value=140, value=56, step=2)
        min_width = st.slider("Minimum logo width", min_value=20, max_value=100, value=36, step=2)
        margin = st.slider("Corner margin", min_value=8, max_value=40, value=18, step=1)
        st.markdown(
            """
            Priority order:
            1. Lower-right at preferred size
            2. Other corners at preferred size
            3. Lower-right at reduced size
            4. Other corners at reduced size
            """
        )

    left, right = st.columns([1.2, 1])
    with left:
        pdf_files = st.file_uploader(
            "Upload one or multiple PDF files",
            type=["pdf"],
            accept_multiple_files=True,
        )
        logo_file = st.file_uploader("Upload logo image", type=["png", "jpg", "jpeg"], accept_multiple_files=False)
        institute_file = st.file_uploader(
            "Upload institute image for first and last page",
            type=["png", "jpg", "jpeg"],
            accept_multiple_files=False,
        )

        process = st.button("Process PDFs", type="primary", use_container_width=True)

    with right:
        st.subheader("How it works")
        st.write(
            "Each page is checked near the corners to find the cleanest available space. "
            "The app prefers the lower-right corner first. If that corner contains text or graphics, "
            "it tries the other three corners. If the logo still does not fit, it shrinks the logo until a corner works."
        )
        st.write(
            "A full-page institute image is added as a cover page at the start and the same image is added again at the end."
        )

    if process:
        if not pdf_files or not logo_file or not institute_file:
            st.error("Please upload at least one PDF, one logo image, and one institute image.")
            return

        logo_bytes = normalize_image(logo_file)
        institute_bytes = normalize_image(institute_file)
        processed_files: list[tuple[str, bytes]] = []
        progress = st.progress(0.0, text="Starting PDF processing...")

        for index, uploaded_pdf in enumerate(pdf_files, start=1):
            processed_pdf = process_pdf(
                uploaded_pdf.getvalue(),
                logo_bytes,
                institute_bytes,
                preferred_width=float(preferred_width),
                min_width=float(min_width),
                margin=float(margin),
            )
            output_name = f"{Path(uploaded_pdf.name).stem}_branded.pdf"
            processed_files.append((output_name, processed_pdf))
            progress.progress(index / len(pdf_files), text=f"Processed {uploaded_pdf.name}")

        st.success(f"Finished processing {len(processed_files)} PDF file(s).")

        if len(processed_files) == 1:
            output_name, output_bytes = processed_files[0]
            st.download_button(
                "Download processed PDF",
                data=output_bytes,
                file_name=output_name,
                mime="application/pdf",
                use_container_width=True,
            )
        else:
            zip_bytes = build_zip(processed_files)
            st.download_button(
                "Download all processed PDFs as ZIP",
                data=zip_bytes,
                file_name="processed_pdfs.zip",
                mime="application/zip",
                use_container_width=True,
            )

        with st.expander("Processed files"):
            for file_name, _ in processed_files:
                st.write(file_name)


if __name__ == "__main__":
    main()
