import openai
import os
import re
import time
from xml.etree import ElementTree as ET
from xml.etree.ElementTree import ParseError
import html
from flask import current_app

# Retrieve the API key from the environment variable
api_key = os.getenv('OPENAI_API_KEY')

if not api_key:
    raise ValueError("API key for OpenAI is not set. Please set the OPENAI_API_KEY environment variable.")

# Initialize the client with the API key
client = openai.OpenAI(api_key=api_key)

# Function to remove page titles and headers
def remove_headers(text):
    lines = text.split('\n')
    processed_lines = []
    for line in lines:
        if not (line.isupper() and len(line.split()) < 5):
            processed_lines.append(line)
    return '\n'.join(processed_lines)

# Function to break text into chunks
def chunk_text(text, chunk_size=4000):
    return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

def generate_ssml_request(text_chunk):
    allowed_tags = "<break>, <lang>, <p>, <phoneme>, <s>, <speak>, <sub>, and <w>"
    prompt_text = (f"Please review this messy text to format, correct any spelling mistakes, remove page numbers and page titles, and mark it up with SSML markup for a text-to-speech process. "
                   f"The only permitted tags are {allowed_tags}. Please only provide the marked up text in your response. "
                   f"Text to format: {text_chunk}")
    return prompt_text

def generate_translation_and_ssml_request(text_chunk, language):
    allowed_tags = "<break>, <lang>, <p>, <phoneme>, <s>, <speak>, <sub>, and <w>"
    prompt_text = (f"Please translate the following {language} text into English. The translation should use modern, easy-to-understand English while staying true to the original meaning and context. "
                   f"After translating, format the translated text, correct any spelling mistakes in the translation, remove page numbers and page titles, and mark it up with SSML markup for a text-to-speech process. "
                   f"The only permitted tags are {allowed_tags}. Please only provide the translated and marked-up text in your response. "
                   f"Text to translate and format: {text_chunk}")
    return prompt_text

def safe_format_text_with_gpt(text_chunk, translate=True, language="Latin"):
    if translate:
        formatted_prompt = generate_translation_and_ssml_request(text_chunk, language)
    else:
        formatted_prompt = generate_ssml_request(text_chunk)
 
    for attempt in range(5):  # Retry up to 5 times
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": formatted_prompt}],
                max_tokens=2048,
                temperature=0.7
            )
            if response.choices and response.choices[0].message:
                return response.choices[0].message.content.strip()
            else:
                return "No response generated"
        except Exception as e:
            wait = 2 ** attempt
            print(f"Request failed, retrying in {wait} seconds...")
            time.sleep(wait)
    raise Exception("Failed to process text after multiple attempts")


def process_text_file(file_path, output_file_name):
    with open(file_path, 'r', encoding='utf-8') as file:
        text = file.read()
    clean_text = remove_headers(text)
    chunks = chunk_text(clean_text)
    formatted_chunks = [safe_format_text_with_gpt(chunk) for chunk in chunks]
    formatted_text = '\n'.join(formatted_chunks)
    
    output_folder = current_app.config['PROCESSED_FOLDER']
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    output_file_path = os.path.join(output_folder, output_file_name)
    
    with open(output_file_path, 'w', encoding='utf-8') as file:
        file.write(formatted_text)
    print(f"File processed and saved as {output_file_path}")
    return output_file_path

def process_ssml_chunks(file_path, output_folder):
    with open(file_path, 'r', encoding='utf-8') as file:
        text = file.read()
    
    # Remove any existing <speak> tags to avoid duplicates
    text = re.sub(r'</?speak>', '', text)

    text = html.unescape(text)
    paragraphs = re.split(r'(?<=</p>)', text)
    
    chunks = []
    current_chunk = ''
    chunk_size = 50000  # 50,000 characters

    for para in paragraphs:
        if len(current_chunk) + len(para) > chunk_size:
            chunks.append(f'<speak>{current_chunk}</speak>')
            current_chunk = para
        else:
            current_chunk += para
    
    # Add the last chunk if it's not empty
    if current_chunk:
        chunks.append(f'<speak>{current_chunk}</speak>')
    
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    chunk_files = []
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    for i, chunk in enumerate(chunks, start=1):
        chunk_file_name = f"{base_name}_chunk_{i}.txt"
        chunk_file_path = os.path.join(output_folder, chunk_file_name)
        with open(chunk_file_path, 'w', encoding='utf-8') as file:
            file.write(chunk)
        chunk_files.append(chunk_file_name)
    
    return chunk_files

def clean_ssml_tags(file_path):
    allowed_tags = {"break", "lang", "p", "phoneme", "s", "speak", "sub", "w"}

    def ensure_role_attribute(tag):
        if 'role=' not in tag:
            tag = tag.replace('<w', '<w role="amazon:NN"', 1)
        return tag

    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()

        content = html.unescape(content)

        def ensure_break_time(match):
            if 'time' not in match.group(0):
                return '<break time="1s"/>'
            return match.group(0)

        content = re.sub(r'<break\s*/?>', ensure_break_time, content)

        content = re.sub(r'<w([^>]*)>', lambda m: ensure_role_attribute(m.group(0)), content)

        root = ET.fromstring(f"<root>{content}</root>")

        def remove_unwanted_tags(element):
            for child in list(element):
                if child.tag not in allowed_tags:
                    element.remove(child)
                else:
                    remove_unwanted_tags(child)

        remove_unwanted_tags(root)
        cleaned_ssml = ET.tostring(root, encoding='unicode').replace('<root>', '').replace('</root>', '')

        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(cleaned_ssml)

        print(f"Cleaned SSML file saved at {file_path}")

    except ParseError as e:
        print(f"Error parsing the SSML text: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def get_existing_files(folder):
    files = [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]
    print(f"Existing files in {folder}: {files}")
    return files

def get_cleaned_chunks(folder, filename):
    pattern = re.compile(r'_chunk_(\d+)\.txt$')
    chunks = [f for f in os.listdir(folder) if f.startswith(filename)]
    chunks = [f for f in chunks if pattern.search(f)]
    chunks.sort(key=lambda x: int(pattern.search(x).group(1)))
    print(f"Cleaned chunks for {filename}: {chunks}")
    return chunks

def estimate_cost(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        text = file.read()
    
    character_count = len(text)

    # OpenAI GPT-4 cost
    gpt_cost = (character_count / 1000000) * 20  # $0.02 per 1k tokens (approx 750 characters)

    # Amazon Polly costs
    polly_cost_generative = (character_count / 1000000) * 30  # $30 per 1M characters
    polly_cost_long_form = (character_count / 1000000) * 100  # $100 per 1M characters

    return character_count, gpt_cost, polly_cost_generative, polly_cost_long_form
