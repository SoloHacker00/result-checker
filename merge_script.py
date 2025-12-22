import os
from pypdf import PdfWriter

def merge_pdfs_in_current_folder(output_filename):
    merger = PdfWriter()
    
    # '.' represents the current directory
    current_folder = '.'
    
    # Get all PDF files in the current directory
    files = [f for f in os.listdir(current_folder) if f.endswith('.pdf')]
    files.sort()

    # Prevent the output file from trying to merge itself if it already exists
    if output_filename in files:
        files.remove(output_filename)

    if not files:
        print("No PDF files found in this folder.")
        return

    print(f"Found {len(files)} PDFs. Merging...")

    for filename in files:
        merger.append(filename)
        print(f"Appended: {filename}")

    merger.write(output_filename)
    merger.close()
    print(f"Success! Created: {output_filename}")

# --- RUN ---
output_name = 'merged_all.pdf'
merge_pdfs_in_current_folder(output_name)