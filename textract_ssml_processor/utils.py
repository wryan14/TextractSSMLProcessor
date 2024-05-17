import openai
import os
import re
import time
from xml.etree import ElementTree as ET
from xml.etree.ElementTree import ParseError
import html

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
def chunk_text(text, chunk_size=1500):
    return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

def generate_ssml_request(text_chunk):
    allowed_tags = "<break>, <lang>, <p>, <phoneme>, <s>, <speak>, <sub>, and <w>"
    prompt_text = (f"Please review this messy text to format, correct any spelling mistakes, remove page numbers and page titles, and mark it up with SSML markup for a text to speech process. "
                   f"The only permitted tags are {allowed_tags}. Please only provide the marked up text in your response. "
                   f"Text to format: {text_chunk}")
    return prompt_text

def safe_format_text_with_gpt(text_chunk):
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
                return response.choices[0].message.content
            else:
                return "No response generated"
        except Exception as e:
            wait = 2 ** attempt
            print(f"Request failed, retrying in {wait} seconds...")
            time.sleep(wait)
    raise Exception("Failed to process text after multiple attempts")

# Function to process the text
def process_text_file(file_path, output_file_name):
    with open(file_path, 'r', encoding='utf-8') as file:
        text = file.read()
    clean_text = remove_headers(text)
    chunks = chunk_text(clean_text)
    formatted_chunks = [safe_format_text_with_gpt(chunk) for chunk in chunks]
    formatted_text = '\n'.join(formatted_chunks)
    output_file_path = os.path.join(os.path.dirname(file_path), output_file_name)
    with open(output_file_path, 'w', encoding='utf-8') as file:
        file.write(formatted_text)
    return output_file_path

def process_ssml_chunks(file_path, output_folder):
    with open(file_path, 'r', encoding='utf-8') as file:
        text = file.read()

    def save_chunks(chunks):
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
        for i, chunk in enumerate(chunks):
            with open(os.path.join(output_folder, f'chunk_{i+1}.txt'), 'w', encoding='utf-8') as file:
                file.write(chunk)

    cleaned_text = re.sub(r'</?speak>', '', text)
    chunks = []
    last_pos = 0
    speak_open_tag = '<speak>'
    speak_close_tag = '</speak>'
    chunk_size = 50000
    paragraphs = re.split(r'(?<=</p>)', cleaned_text)
    current_chunk = speak_open_tag
    for para in paragraphs:
        if len(current_chunk) + len(para) > chunk_size:
            current_chunk += speak_close_tag
            chunks.append(current_chunk)
            current_chunk = speak_open_tag + para
        else:
            current_chunk += para
    current_chunk += speak_close_tag
    chunks.append(current_chunk)
    save_chunks(chunks)

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

    except ParseError as e:
        print(f"Error parsing the SSML text: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
