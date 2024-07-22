# text_processing.py

import re
import os

def remove_square_brackets(text):
    return re.sub(r'\[.*?\]', '', text, flags=re.DOTALL)

def split_into_sections(text):
    sections = re.split(r'<h4><center>', text)
    return [section.strip() for section in sections if section.strip() and section.strip()!="<br>"]

def extract_and_print_all_caps_title(content, part):
    lines = content.split('\n')
    all_caps_lines = []
    for line in lines:
        line = line.strip()
        if line.isupper() and line:
            all_caps_lines.append(line)
        else:
            break
    
    if all_caps_lines:
        print("All-caps title found:")
        for line in all_caps_lines:
            print(f'Part {part}:\t', line)
    else:
        pass

def process_text(input_text, filename_base, output_dir):
    cleaned_text = remove_square_brackets(input_text)
    sections = split_into_sections(cleaned_text)
    
    for i, section in enumerate(sections, 1):
        content = re.sub(r'<h4><center>.*?</center></h4>', '', section, flags=re.DOTALL).strip()
        content = re.sub(r'<.*?>', '', content)
        
        extract_and_print_all_caps_title(content, i)
        
        filename = f"{filename_base}_part_{i}.txt"
        
        with open(os.path.join(output_dir, filename), 'w', encoding='utf-8') as f:
            f.write(content)
    return f"Processed files have been saved in: {output_dir}"

def process_files_in_directory(directory, output_dir):
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        if os.path.isfile(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            filename_base = os.path.splitext(filename)[0]
            try:
                result = process_text(content, filename_base, output_dir)
                print(result)
            except Exception as e:
                print(f"An error occurred while processing the file '{filename}': {e}")
