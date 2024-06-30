# file_processing.py

import os
import re
import shutil
import glob
from bs4 import BeautifulSoup

def process_files(volume, author, title, base_path, ssml_source_dir):
    # Create directory name
    dir_name = f"{author} - {title}"
    
    # Create output directory
    output_dir = os.path.join(base_path, f"vol_{volume}", dir_name)
    os.makedirs(output_dir, exist_ok=True)

    # Create SSML subdirectory
    ssml_dir = os.path.join(output_dir, "SSML")
    os.makedirs(ssml_dir, exist_ok=True)

    # Get list of files
    files = sorted(glob.glob(os.path.join(ssml_source_dir, "*chunk*.txt")), key=lambda x: int(re.search(r"chunk_(\d+)", x).group(1)))

    # Process files
    for file_path in files:
        filename = os.path.basename(file_path)
        print(f"Reading file: {filename}")  # Debugging: file being read
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if content:  # Verify that content is not empty
                    shutil.copy(file_path, ssml_dir)
                    print(f"File {filename} copied to {ssml_dir}.")  # Debugging: confirm file copy

                    # Remove SSML tags and format
                    soup = BeautifulSoup(content, 'xml')
                    clean_text = soup.get_text(separator='\n')

                    # Additional formatting
                    clean_text = re.sub(r'\n\s*\n', '\n\n', clean_text)  # Remove excessive blank lines
                    clean_text = re.sub(r'(\n\s*){2,}', '\n\n', clean_text)  # Ensure no multiple blank lines
                    clean_text = clean_text.strip()  # Remove leading/trailing whitespace
                    print(f"Clean text length: {len(clean_text)}")  # Debugging: show length of clean text

                    # Write clean text to file with the combined output naming convention
                    output_file = os.path.join(output_dir, f"{author} - {title}_{filename.split('_')[-1].split('.')[0]} (English).txt")
                    with open(output_file, 'w', encoding='utf-8') as out_f:
                        out_f.write(clean_text)
                        print(f"Clean text written to {output_file}.")  # Debugging: confirm file write

                else:
                    print(f"File {filename} is empty.")  # Debugging: alert if content is empty
        except Exception as e:
            print(f"Failed to read file {file_path} with error: {e}")  # Debugging: file read error

    return output_dir
