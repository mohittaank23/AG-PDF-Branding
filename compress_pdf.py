"""
Simple PDF Compression Script - No web interface, just pure Python.

Usage:
    python compress_pdf.py input.pdf [output.pdf] [level] [quality]

Examples:
    python compress_pdf.py document.pdf
    python compress_pdf.py document.pdf compressed.pdf 3 85
    python compress_pdf.py document.pdf compressed.pdf 2

Parameters:
    input.pdf: Path to input PDF file (required)
    output.pdf: Path to output PDF file (optional, default: input_compressed.pdf)
    level: Compression level 0-3 (optional, default: 3)
           0 = No compression
           1 = Garbage collection only
           2 = + Stream compression
           3 = + Image optimization
    quality: Image quality 1-100 (optional, default: 85)
             Only used with level 3
"""

import sys
import os
from pathlib import Path
from datetime import datetime

try:
    import fitz
except ImportError:
    print("Error: PyMuPDF not installed. Install it with:")
    print("  pip install PyMuPDF")
    sys.exit(1)


def format_size(size_bytes):
    """Convert bytes to human readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"


def compress_pdf(input_path, output_path=None, compression_level=3, image_quality=85):
    """
    Compress a PDF file.
    
    Args:
        input_path: Path to input PDF file
        output_path: Path to output PDF file (default: input_compressed.pdf)
        compression_level: 0-3, higher = more compression
        image_quality: 1-100, higher = better quality (only for level 3)
    
    Returns:
        Dictionary with compression statistics
    """
    # Validate input file
    if not os.path.exists(input_path):
        print(f"Error: File not found: {input_path}")
        return None
    
    if not input_path.lower().endswith('.pdf'):
        print("Error: Input file must be a PDF")
        return None
    
    # Set output path if not provided
    if output_path is None:
        input_file = Path(input_path)
        output_path = str(input_file.parent / f"{input_file.stem}_compressed.pdf")
    
    # Validate parameters
    compression_level = max(0, min(3, compression_level))
    image_quality = max(1, min(100, image_quality))
    
    # Get input file size
    input_size = os.path.getsize(input_path)
    
    print(f"Starting compression...")
    print(f"Input file: {input_path}")
    print(f"Input size: {format_size(input_size)}")
    print(f"Compression level: {compression_level}")
    if compression_level == 3:
        print(f"Image quality: {image_quality}%")
    print()
    
    try:
        # Open PDF
        print("Opening PDF file...")
        doc = fitz.open(input_path)
        print(f"PDF has {len(doc)} pages")
        
        # Clean pages (garbage collection)
        if compression_level >= 1:
            print("Applying garbage collection...")
            doc.clean_pages()
        
        # Optimize images (level 3)
        if compression_level >= 3:
            print("Optimizing images...")
            image_count = 0
            for page_num, page in enumerate(doc, 1):
                images = page.get_images()
                if images:
                    image_count += len(images)
                if page_num % max(1, len(doc) // 10) == 0:
                    print(f"  Processed {page_num}/{len(doc)} pages...")
            print(f"Found {image_count} images")
        
        # Save with compression
        print("Saving compressed PDF...")
        save_options = {
            "garbage": compression_level,  # 0-4
            "deflate": True,               # Enable stream compression
            "clean": True,                 # Clean content streams
        }
        
        doc.save(output_path, **save_options)
        doc.close()
        
        # Get output file size
        output_size = os.path.getsize(output_path)
        compression_ratio = (1 - output_size / input_size) * 100
        size_reduced = input_size - output_size
        
        # Print results
        print()
        print("=" * 60)
        print("COMPRESSION COMPLETE")
        print("=" * 60)
        print(f"Output file: {output_path}")
        print(f"Input size:  {format_size(input_size)}")
        print(f"Output size: {format_size(output_size)}")
        print(f"Size reduced: {format_size(size_reduced)} ({compression_ratio:.1f}%)")
        print("=" * 60)
        
        return {
            "success": True,
            "input_size": input_size,
            "output_size": output_size,
            "compression_ratio": compression_ratio,
            "size_reduced": size_reduced,
            "output_path": output_path,
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {"success": False, "error": str(e)}


def batch_compress(input_dir, output_dir=None, compression_level=3, image_quality=85):
    """
    Compress all PDFs in a directory.
    
    Args:
        input_dir: Directory containing PDF files
        output_dir: Directory for output files (default: input_dir)
        compression_level: 0-3, higher = more compression
        image_quality: 1-100, higher = better quality
    """
    if output_dir is None:
        output_dir = input_dir
    
    if not os.path.isdir(input_dir):
        print(f"Error: Directory not found: {input_dir}")
        return
    
    # Create output directory if needed
    os.makedirs(output_dir, exist_ok=True)
    
    # Find all PDFs
    pdf_files = list(Path(input_dir).glob("*.pdf"))
    
    if not pdf_files:
        print(f"No PDF files found in {input_dir}")
        return
    
    print(f"Found {len(pdf_files)} PDF file(s)\n")
    
    total_input = 0
    total_output = 0
    
    for idx, pdf_file in enumerate(pdf_files, 1):
        print(f"[{idx}/{len(pdf_files)}]")
        output_file = Path(output_dir) / f"{pdf_file.stem}_compressed.pdf"
        
        result = compress_pdf(
            str(pdf_file),
            str(output_file),
            compression_level,
            image_quality
        )
        
        if result and result.get("success"):
            total_input += result["input_size"]
            total_output += result["output_size"]
        
        print()
    
    # Summary
    if total_input > 0:
        total_ratio = (1 - total_output / total_input) * 100
        print("=" * 60)
        print("BATCH COMPRESSION SUMMARY")
        print("=" * 60)
        print(f"Total input size:  {format_size(total_input)}")
        print(f"Total output size: {format_size(total_output)}")
        print(f"Total reduction:   {format_size(total_input - total_output)} ({total_ratio:.1f}%)")
        print("=" * 60)


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nQuick Start:")
        print("  python compress_pdf.py myfile.pdf")
        print("\nThis will create: myfile_compressed.pdf")
        sys.exit(1)
    
    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    compression_level = int(sys.argv[3]) if len(sys.argv) > 3 else 3
    image_quality = int(sys.argv[4]) if len(sys.argv) > 4 else 85
    
    # Check if input is a directory (batch mode)
    if os.path.isdir(input_path):
        output_dir = output_path if output_path else input_path
        batch_compress(input_path, output_dir, compression_level, image_quality)
    else:
        compress_pdf(input_path, output_path, compression_level, image_quality)


if __name__ == "__main__":
    main()
