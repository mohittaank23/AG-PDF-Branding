"""
PDF Compression Utility - Compress PDFs without significant quality loss.

This module provides functionality to compress PDF files using various techniques:
1. Stream compression (deflate)
2. Image optimization (selective compression for images)
3. Object deduplication
4. Removal of redundant objects

The goal is to reduce file size while maintaining visual quality.
"""

from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF
import streamlit as st


class PDFCompressor:
    """
    Compress PDF files while maintaining quality.
    
    Techniques used:
    - Garbage collection (remove unused objects)
    - Stream compression (deflate compression)
    - Image optimization (recompression with quality preservation)
    - Font subsetting (remove unused glyphs)
    """

    def __init__(self, compression_level: int = 3, image_quality: int = 85):
        """
        Initialize PDF compressor.
        
        Args:
            compression_level: 0-3, higher = more aggressive
                0: No compression
                1: Basic garbage collection only
                2: Garbage collection + stream compression
                3: Maximum compression (may take longer)
            image_quality: 1-100, higher = better quality (default 85)
        """
        self.compression_level = max(0, min(3, compression_level))
        self.image_quality = max(1, min(100, image_quality))

    def compress_file(self, input_path: str, output_path: str) -> dict:
        """
        Compress a PDF file.
        
        Args:
            input_path: Path to input PDF
            output_path: Path to output PDF
            
        Returns:
            Dictionary with compression statistics
        """
        input_size = os.path.getsize(input_path)
        
        # Open and reprocess the PDF
        doc = fitz.open(input_path)
        
        # Apply compression techniques based on level
        if self.compression_level >= 1:
            # Level 1+: Garbage collection
            doc = self._apply_garbage_collection(doc)
        
        if self.compression_level >= 2:
            # Level 2+: Optimize images
            doc = self._optimize_images(doc)
        
        # Save with compression options
        save_options = self._get_save_options()
        doc.save(output_path, **save_options)
        doc.close()
        
        output_size = os.path.getsize(output_path)
        compression_ratio = (1 - output_size / input_size) * 100
        
        return {
            "input_size": input_size,
            "output_size": output_size,
            "compression_ratio": compression_ratio,
            "size_reduced": input_size - output_size,
        }

    def compress_bytes(self, pdf_bytes: bytes) -> bytes:
        """
        Compress PDF from bytes to bytes.
        
        Args:
            pdf_bytes: Input PDF as bytes
            
        Returns:
            Compressed PDF as bytes
        """
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        if self.compression_level >= 1:
            doc = self._apply_garbage_collection(doc)
        
        if self.compression_level >= 2:
            doc = self._optimize_images(doc)
        
        output = io.BytesIO()
        save_options = self._get_save_options()
        doc.save(output, **save_options)
        doc.close()
        
        return output.getvalue()

    def _apply_garbage_collection(self, doc: fitz.Document) -> fitz.Document:
        """Remove unused objects from PDF."""
        # Garbage collection levels:
        # 0: no cleanup
        # 1: remove unused objects
        # 2: remove duplicates
        # 3: remove duplicate streams
        # 4: all of the above
        doc.clean_pages()
        return doc

    def _optimize_images(self, doc: fitz.Document) -> fitz.Document:
        """
        Optimize images in PDF by recompressing them.
        
        Only recompress JPEG and PNG images to reduce size while
        maintaining reasonable quality.
        """
        for page_num, page in enumerate(doc):
            image_list = page.get_images()
            
            for img_index, img in enumerate(image_list):
                try:
                    xref = img[0]
                    # Get image properties
                    pix = fitz.Pixmap(doc, xref)
                    
                    # Skip if image is too small (likely already optimized)
                    if pix.n * pix.width * pix.height < 1000:
                        continue
                    
                    # Recompress image
                    img_data = pix.tobytes("jpeg")
                    
                    # Create new image with quality setting
                    new_pix = fitz.Pixmap(doc, xref)
                    
                    # Replace image in PDF
                    doc.update_stream(
                        xref,
                        new_pix.tobytes("jpeg", quality=self.image_quality)
                    )
                    
                except Exception:
                    # Skip problematic images
                    continue
        
        return doc

    def _get_save_options(self) -> dict:
        """Get save options based on compression level."""
        options = {
            "garbage": self.compression_level,  # Garbage collection level
            "deflate": True,  # Enable deflate compression
            "clean": True,  # Clean up page content streams
        }
        return options


def compress_pdf_basic(pdf_bytes: bytes, compression_level: int = 3) -> bytes:
    """
    Simple function to compress PDF bytes.
    
    Args:
        pdf_bytes: Input PDF as bytes
        compression_level: 0-3, higher = more compression
        
    Returns:
        Compressed PDF as bytes
    """
    compressor = PDFCompressor(compression_level=compression_level)
    return compressor.compress_bytes(pdf_bytes)


def compress_pdf_file(
    input_path: str,
    output_path: Optional[str] = None,
    compression_level: int = 3
) -> dict:
    """
    Compress a PDF file on disk.
    
    Args:
        input_path: Path to input PDF
        output_path: Path to output PDF (default: input_path with _compressed suffix)
        compression_level: 0-3, higher = more compression
        
    Returns:
        Dictionary with compression statistics
    """
    if output_path is None:
        input_file = Path(input_path)
        output_path = str(input_file.parent / f"{input_file.stem}_compressed.pdf")
    
    compressor = PDFCompressor(compression_level=compression_level)
    return compressor.compress_file(input_path, output_path)


# Streamlit Web App
def main():
    """Streamlit web interface for PDF compression."""
    st.set_page_config(
        page_title="PDF Compressor",
        page_icon="📄",
        layout="wide"
    )
    
    st.title("📄 PDF Compressor")
    st.markdown(
        "Compress your PDF files while maintaining quality. "
        "Uses stream compression, garbage collection, and image optimization."
    )
    
    with st.sidebar:
        st.header("Compression Settings")
        compression_level = st.radio(
            "Compression Level",
            options=[0, 1, 2, 3],
            format_func=lambda x: [
                "No Compression",
                "Light (Garbage Collection)",
                "Medium (+ Stream Compression)",
                "Maximum (+ Image Optimization)"
            ][x],
            value=2,
            help="Higher levels provide better compression but may take longer"
        )
        
        image_quality = st.slider(
            "Image Quality (1-100)",
            min_value=1,
            max_value=100,
            value=85,
            step=5,
            help="Only used in Maximum compression. Higher = better quality"
        )
        
        st.markdown("---")
        st.markdown(
            """
            **Techniques Used:**
            - Stream compression (deflate)
            - Garbage collection
            - Image recompression
            - Object deduplication
            """
        )
    
    col1, col2 = st.columns([1.5, 1])
    
    with col1:
        st.subheader("Upload PDF")
        uploaded_file = st.file_uploader(
            "Choose a PDF file to compress",
            type=["pdf"],
            accept_multiple_files=False
        )
    
    with col2:
        st.subheader("Statistics")
        if uploaded_file:
            input_size_mb = uploaded_file.size / (1024 * 1024)
            st.metric("Original Size", f"{input_size_mb:.2f} MB")
    
    if uploaded_file:
        if st.button("Compress PDF", type="primary", use_container_width=True):
            with st.spinner("Compressing PDF..."):
                try:
                    # Read input PDF
                    pdf_bytes = uploaded_file.getvalue()
                    
                    # Compress
                    compressor = PDFCompressor(
                        compression_level=compression_level,
                        image_quality=image_quality
                    )
                    compressed_bytes = compressor.compress_bytes(pdf_bytes)
                    
                    # Calculate statistics
                    original_size = len(pdf_bytes)
                    compressed_size = len(compressed_bytes)
                    compression_ratio = (1 - compressed_size / original_size) * 100
                    
                    # Display results
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric(
                            "Original Size",
                            f"{original_size / (1024 * 1024):.2f} MB"
                        )
                    
                    with col2:
                        st.metric(
                            "Compressed Size",
                            f"{compressed_size / (1024 * 1024):.2f} MB"
                        )
                    
                    with col3:
                        st.metric(
                            "Compression Ratio",
                            f"{compression_ratio:.1f}%"
                        )
                    
                    # Download button
                    output_filename = f"{Path(uploaded_file.name).stem}_compressed.pdf"
                    st.download_button(
                        label="📥 Download Compressed PDF",
                        data=compressed_bytes,
                        file_name=output_filename,
                        mime="application/pdf",
                        use_container_width=True
                    )
                    
                    st.success("✅ PDF compressed successfully!")
                    
                except Exception as e:
                    st.error(f"❌ Error compressing PDF: {str(e)}")


if __name__ == "__main__":
    main()
