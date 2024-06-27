import openai
import os
import re
import time
from xml.etree import ElementTree as ET
from xml.etree.ElementTree import ParseError
from lxml import etree
import html
from werkzeug.utils import secure_filename
from flask import current_app
from bs4 import BeautifulSoup

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

# Function to chunk the processed SSML
def chunk_ssml_text(ssml_text, chunk_size=4000):
    # Split the SSML content into manageable chunks
    ssml_chunks = chunk_text(ssml_text, chunk_size)
    return [f"<speak>{chunk}</speak>" for chunk in ssml_chunks]

# Function to generate SSML request
def generate_ssml_request(text_chunk, title, author):
    allowed_tags = "<break>, <lang>, <p>, <phoneme>, <s>, <speak>, <sub>, <w>"
    prompt_text = (f"Please review this messy text to format, correct any spelling mistakes, remove page numbers and page titles, and mark it up with SSML markup for a text-to-speech process. "
                   f"The only permitted tags are {allowed_tags}. Please only provide the marked up text in your response. "
                   f"Text to format: {text_chunk}")
    return prompt_text

# Function to generate translation request
def generate_translation_request(ssml_chunk, language):
    prompt_text = (f"Please translate the following {language} text into English. The translation should use modern, easy-to-understand English while staying true to the original meaning and context. "
                   f"Translate all Roman numerals to standard numbers and expand any abbreviations, especially Bible attributions. "
                   f"Do not alter the SSML tags in the text. Provide only the translated text. "
                   f"Text to translate: {ssml_chunk}")
    return prompt_text

# Function to clean and enhance SSML with GPT

def clean_and_enhance_ssml_with_gpt(ssml_chunk):
    allowed_tags = "<break>, <lang>, <p>, <phoneme>, <s>, <speak>, <sub>, <w>"
    prompt_text = (
        f"Please review and enhance the provided SSML content to correct any spelling mistakes and improve readability. "
        f"Ensure that all SSML tags are correctly formatted with no nested tags and all open tags are closed. "
        f"Honor the initial SSML markup and add any additional {allowed_tags} SSML tags for improved readability. "
        f"Ensure the content is engaging, easy to understand, and enjoyable to listen to, while preserving the original meaning. "
        f"Do not add any new SSML tags, but you may modify the existing SSML tags to improve readability. "
        f"Replace references to 'ibid.' with the appropriate text. "
        f"Read out full names of Bible books (e.g., 'First Corinthians' instead of '1 Corinthians'). "
        f"Address and reduce any noticeable repetition for better listenability. "
        f"Return only the cleaned and enhanced SSML content without any additional text or instructions. "
        f"SSML to clean: {ssml_chunk}"
    )
    
    for attempt in range(5):  # Retry up to 5 times
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt_text}],
                max_tokens=2048,
                temperature=0.7
            )
            if response.choices and response.choices[0].message:
                return response.choices[0].message.content.strip()
            else:
                print(f"No response generated. Attempt: {attempt + 1}, Response: {response}")
                time.sleep(2 ** attempt)  # Exponential backoff
        except Exception as e:
            print(f"Exception occurred: {e}. Attempt: {attempt + 1}")
            time.sleep(2 ** attempt)  # Exponential backoff
    
    raise Exception("Failed to process text after multiple attempts")


def validate_ssml_with_gpt(ssml_chunk):
    allowed_tags = "<break>, <lang>, <p>, <phoneme>, <s>, <speak>, <sub>, <w>"
    prompt_text = (
        f"Please review the provided SSML content to ensure it is valid and compatible with AWS Polly. "
        f"Ensure that all SSML tags are correctly formatted with no nested tags and all open tags are closed. "
        f"Honor the initial SSML markup and make sure it complies with AWS Polly requirements. "
        f"Return only the validated SSML content without any additional text or instructions. "
        f"SSML to validate: {ssml_chunk}"
    )
    
    for attempt in range(5):  # Retry up to 5 times
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt_text}],
                max_tokens=2048,
                temperature=0.7
            )
            if response.choices and response.choices[0].message:
                return response.choices[0].message.content.strip()
            else:
                print(f"No response generated. Attempt: {attempt + 1}, Response: {response}")
                time.sleep(2 ** attempt)  # Exponential backoff
        except Exception as e:
            print(f"Exception occurred: {e}. Attempt: {attempt + 1}")
            time.sleep(2 ** attempt)  # Exponential backoff
    
    raise Exception("Failed to validate text after multiple attempts")




def safe_format_text_with_gpt(text_chunk, language="Latin", title="", author=""):
    if language.lower() != 'english':
        formatted_prompt = generate_translation_request(text_chunk, language)
    else:
        formatted_prompt = generate_ssml_request(text_chunk, title, author)
 
    for attempt in range(5):  # Retry up to 5 times
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": formatted_prompt}],
                max_tokens=2048,
                temperature=0.7
            )
            if response.choices and response.choices[0].message:
                enhanced_ssml = clean_and_enhance_ssml_with_gpt(response.choices[0].message.content.strip())
                validated_ssml = validate_ssml_with_gpt(enhanced_ssml)
                return validated_ssml
            else:
                return "No response generated"
        except Exception as e:
            wait = 2 ** attempt
            print(f"Request failed, retrying in {wait} seconds... Exception: {e}")
            time.sleep(wait)
    raise Exception("Failed to process text after multiple attempts")


def convert_html_to_ssml(html_content):
    # Parse HTML content
    soup = BeautifulSoup(html_content, 'html.parser')

    # Define SSML wrappers
    ssml_open = '<speak>'
    ssml_close = '</speak>'

    # Process titles (h4 tags)
    for title in soup.find_all('h4'):
        title.string = f"<break time='500ms'/>{title.text}<break time='2s'/>"

    # Process quotations (em tags)
    for em in soup.find_all('em'):
        text = em.text
        next_sibling = em.find_next_sibling('strong')
        if len(text) > 100:  # Use break tags for longer passages
            em.string = f"<break time='500ms'/>{text}"
            # Leave the following strong tag if it exists
            if next_sibling:
                next_sibling.string = f"<break time='250ms'/>{next_sibling.text}<break time='500ms'/>"
        else:  # No break tags for shorter passages
            em.string = text
            # Remove the following strong tag if it exists
            if next_sibling:
                next_sibling.decompose()

    # Convert the soup object back to a string
    processed_html = str(soup)

    # Remove the HTML tags but keep the SSML tags
    processed_html = re.sub(r'<(/?)(h4|em|strong|p)>', '', processed_html)
    
    # Combine the processed HTML with SSML wrappers
    processed_content = ssml_open + processed_html + ssml_close

    return processed_content

# Function to process text file
def process_text_file(file_path, output_file_name, title, author, language):
    with open(file_path, 'r', encoding='utf-8') as file:
        text = file.read()

    if is_html(text):
        clean_text = convert_html_to_ssml(text)
    else:
        clean_text = remove_headers(text)

    chunks = chunk_text(clean_text)
    formatted_chunks = [safe_format_text_with_gpt(chunk, language, title, author) for chunk in chunks]
    formatted_text = '\n'.join(formatted_chunks)
    
    output_folder = current_app.config['PROCESSED_FOLDER']
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    output_file_path = os.path.join(output_folder, output_file_name)
    
    with open(output_file_path, 'w', encoding='utf-8') as file:
        file.write(formatted_text.replace('```xml', "").replace('```ssml', '').replace('```', ''))
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
    base_name = base_name.replace('processed_', '')
    for i, chunk in enumerate(chunks, start=1):
        if len(base_name.split('_part_'))==2:
            if len(chunks) >=2:
                part_num = base_name.split('_part_')[-1]+'_'+str(int(i))
            else:
                part_num = base_name.split('_part_')[-1]
            chunk_file_name = f"{base_name}_chunk_{part_num}.txt"
        else:
            chunk_file_name = f"{base_name}_chunk_{i}.txt"
        chunk_file_path = os.path.join(output_folder, chunk_file_name)
        with open(chunk_file_path, 'w', encoding='utf-8') as file:
            file.write(chunk)
        chunk_files.append(chunk_file_name)
    
    return chunk_files

# Function to detect HTML content
def is_html(text):
    html_tags = re.compile('<.*?>')
    return bool(html_tags.search(text))

# Main function for handling uploaded files
def handle_uploaded_file(uploaded_file):
    file_path = secure_filename(uploaded_file.filename)
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], file_path)
    with open(file_path, 'wb') as f:
        f.write(uploaded_file.read())
    return file_path

def get_existing_files(folder):
    files = [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]
    return files

def get_cleaned_chunks(folder, filename):
    print(f"get_cleaned_chunks called with folder: {folder}, filename: {filename}")
    pattern = re.compile(r'_chunk_(\d+)\.txt$')
    chunks = [f for f in os.listdir(folder) if f.startswith(filename)]
    chunks = [f for f in chunks if pattern.search(f)]
    chunks.sort(key=lambda x: int(pattern.search(x).group(1)))
    print(f"Cleaned chunks for {filename}: {chunks}")
    return chunks

# Function to clean SSML tags
def clean_ssml_tags(file_path):
    allowed_tags = "<break>, <lang>, <p>, <phoneme>, <s>, <speak>, <sub>, <w>"

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

        root = etree.fromstring(f"<root>{content}</root>")

        def remove_unwanted_tags(element, allowed_tags=allowed_tags):
            for child in list(element):
                if child.tag not in allowed_tags:
                    # Replace the tag with its children
                    parent = child.getparent()
                    for grandchild in list(child):
                        parent.insert(parent.index(child), grandchild)
                    parent.remove(child)
                else:
                    remove_unwanted_tags(child, allowed_tags)

        remove_unwanted_tags(root)
        cleaned_ssml = etree.tostring(root, encoding='unicode').replace('<root>', '').replace('</root>', '')

        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(cleaned_ssml)

        print(f"Cleaned SSML file saved at {file_path}")

    except ParseError as e:
        print(f"Error parsing the SSML text: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def estimate_cost(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        text = file.read()
    
    character_count = len(text)

    # OpenAI gpt-4oo cost
    gpt_cost = (character_count / 1000000) * 20  # $0.02 per 1k tokens (approx 750 characters)

    # Amazon Polly costs
    polly_cost_generative = (character_count / 1000000) * 30  # $30 per 1M characters
    polly_cost_long_form = (character_count / 1000000) * 100  # $100 per 1M characters

    return character_count, gpt_cost, polly_cost_generative, polly_cost_long_form

def estimate_total_cost(file_paths):
    total_character_count = 0
    total_gpt_cost = 0
    total_polly_cost_generative = 0
    total_polly_cost_long_form = 0
    
    for file_path in file_paths:
        with open(file_path, 'r', encoding='utf-8') as file:
            file_content = file.read()
        
        character_count = len(file_content)
        total_character_count += character_count
        
        # Calculate costs
        gpt_cost = (character_count / 1000000) * 20  # $0.02 per 1k tokens (approx 750 characters)
        polly_cost_generative = (character_count / 1000000) * 30  # $30 per 1M characters
        polly_cost_long_form = (character_count / 1000000) * 100  # $100 per 1M characters
        
        total_gpt_cost += gpt_cost
        total_polly_cost_generative += polly_cost_generative
        total_polly_cost_long_form += polly_cost_long_form
    
    return total_character_count, total_gpt_cost, total_polly_cost_generative, total_polly_cost_long_form

