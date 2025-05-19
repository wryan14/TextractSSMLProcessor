import os
import re
import time
import html
import logging
import json
from datetime import datetime
from typing import Dict, List, Tuple

import openai
import nltk
from lxml import etree
from bs4 import BeautifulSoup
from werkzeug.utils import secure_filename
from flask import current_app
from xml.etree import ElementTree as ET
from xml.etree.ElementTree import ParseError

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create a custom logger for translations
translation_logger = logging.getLogger('translation_mapping')
translation_logger.setLevel(logging.INFO)

# Create a file handler for the translation logger
log_directory = 'translation_logs'
os.makedirs(log_directory, exist_ok=True)
log_file = os.path.join(log_directory, f'translation_log_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
file_handler = logging.FileHandler(log_file, mode='w')
translation_logger.addHandler(file_handler)

def log_translation(latin_text, english_text):
    log_directory = 'translation_logs'
    os.makedirs(log_directory, exist_ok=True)
    log_file = os.path.join(log_directory, f'translation_log_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
    with open(log_file, 'a') as file:
        json.dump({'latin': latin_text, 'english': english_text}, file)
        file.write('\n')

# Retrieve the API key from the environment variable
api_key = os.getenv('OPENAI_API_KEY')

if not api_key:
    raise ValueError("API key for OpenAI is not set. Please set the OPENAI_API_KEY environment variable.")

# Initialize the client with the API key
client = openai.OpenAI(api_key=api_key)

# def log_translation(original, translated):
#     translation_logger.info(json.dumps({'original': original, 'translated': translated}))

# Function to remove page titles and headers
def remove_headers(text):
    lines = text.split('\n')
    processed_lines = []
    for line in lines:
        if not (line.isupper() and len(line.split()) < 5):
            processed_lines.append(line)
    return '\n'.join(processed_lines)

def chunk_text(text: str, max_chunk_size: int = 2000) -> List[str]:
    # Split the text into sentences using NLTK
    sentences = nltk.sent_tokenize(text)
    
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        # If adding this sentence would exceed the max chunk size, start a new chunk
        if len(current_chunk) + len(sentence) > max_chunk_size and current_chunk:
            chunks.append(current_chunk.strip())
            current_chunk = ""
        
        current_chunk += sentence + " "
        
        # If the current chunk is already at or over the max size, add it to chunks
        if len(current_chunk) >= max_chunk_size:
            chunks.append(current_chunk.strip())
            current_chunk = ""
    
    # Add any remaining text as the last chunk
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks

# # Function to chunk the processed SSML
# def chunk_ssml_text(ssml_text, chunk_size=4000):
#     # Split the SSML content into manageable chunks
#     ssml_chunks = chunk_text(ssml_text, chunk_size)
#     return [f"<speak>{chunk}</speak>" for chunk in ssml_chunks]

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




def safe_format_text_with_gpt(text_chunk: str, language: str) -> Tuple[str, str]:
    """Format ``text_chunk`` using GPT and return validated SSML.

    The function returns a tuple ``(validated_ssml, smooth_text)`` where
    ``validated_ssml`` is the SSML content ready for further processing and
    ``smooth_text`` is a human friendly version used only for logging.
    """
    logger.debug(f"Formatting text with GPT, language: {language}")
    if language.lower() != 'english':
        formatted_prompt = generate_translation_request(text_chunk, language)
    else:
        formatted_prompt = generate_ssml_request(text_chunk, "", "")

    for attempt in range(5):  # Retry up to 5 times
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": formatted_prompt}],
                max_tokens=2048,
                temperature=0.7
            )
            if response.choices and response.choices[0].message:
                translated_text = response.choices[0].message.content.strip()

                # Clean SSML and get the smoothed text
                enhanced_ssml = clean_and_enhance_ssml_with_gpt(translated_text)
                validated_ssml = validate_ssml_with_gpt(enhanced_ssml)

                # Get the smoothed text for logging
                smooth_text = smooth_text_for_youtube(validated_ssml)

                # Return the validated SSML for further processing and the
                # smoothed text for optional logging.
                return validated_ssml, smooth_text
            else:
                logger.warning(f"No response generated on attempt {attempt + 1}")
        except Exception as e:
            wait = 2 ** attempt
            logger.error(f"Request failed on attempt {attempt + 1}, retrying in {wait} seconds... Exception: {e}")
            time.sleep(wait)
    raise Exception("Failed to process text after multiple attempts")

def handle_uploaded_file(file_path: str, title: str, author: str, language: str) -> str:
    filename = os.path.basename(file_path)
    output_file_name = f"processed_{filename}"
    
    # Process the file
    output_dict = process_text_file(file_path, output_file_name, title, author, language)
    
    # Save the output dictionary as a JSON file
    output_json_path = os.path.join(current_app.config['PROCESSED_FOLDER'], f"{output_file_name}.json")
    with open(output_json_path, 'w', encoding='utf-8') as json_file:
        json.dump(output_dict, json_file, ensure_ascii=False, indent=2)
    
    return output_json_path

# Add this function to retrieve synchronized texts from the log file
def get_synchronized_texts(log_file_path):
    original_texts = []
    translated_texts = []
    with open(log_file_path, 'r') as log_file:
        for line in log_file:
            entry = json.loads(line)
            original_texts.append(entry['original'])
            translated_texts.append(entry['translated'])
    return "\n\n".join(original_texts), "\n\n".join(translated_texts)


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

import time
from typing import Dict, List
from functools import partial

def process_text_file(file_path: str, output_file_name: str, title: str, author: str, language: str) -> Dict[str, List[Dict[str, str]]]:
    logger.info(f"Starting to process file: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as file:
        text = file.read()

    if is_html(text):
        clean_text = convert_html_to_ssml(text)
    else:
        clean_text = text

    latin_correlate_path = os.path.join(current_app.config['LATIN_FOLDER'], f"latin_{output_file_name}")
    with open(latin_correlate_path, 'w', encoding='utf-8') as latin_file:
        latin_file.write(clean_text)

    chunks = chunk_text(clean_text)
    output_dict = {"chunks": []}
    
    def translate_with_retry(chunk: str, max_retries: int = 5, delay: float = 1.0):
        for attempt in range(max_retries):
            try:
                translated_chunk, _ = safe_format_text_with_gpt(chunk, language)
                return clean_ssml_tags(preprocess_ssml_tags(translated_chunk))
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(delay)
                else:
                    logger.error(f"All {max_retries} attempts failed for chunk")
                    return "Translation failed after multiple attempts"

    for i, chunk in enumerate(chunks, 1):
        cleaned_chunk = translate_with_retry(chunk)
        
        chunk_dict = {
            "chunk_number": i,
            "original_latin": chunk,
            "cleaned_english_translation": cleaned_chunk
        }
        output_dict["chunks"].append(chunk_dict)
    
    return output_dict

def generate_title_file(title, output_folder, base_name, part_num, chunk_num):
    title_content = f"""<speak>
<break time="1s"/>[TITLE </speak>]
<break time="2s"/>
</speak>"""
    
    title_file_name = f"{base_name}_Title_voice_Ruth_chunk_{chunk_num}.txt"
    title_file_path = os.path.join(output_folder, title_file_name)
    with open(title_file_path, 'w', encoding='utf-8') as file:
        file.write(title_content)
    return title_file_name

# def process_ssml_chunks(file_path: str, latin_correlate_path: str) -> Dict[str, List[Dict[str, str]]]:
#     logger.debug(f"Processing SSML chunks for file: {file_path}")
#     logger.debug(f"Latin correlate path: {latin_correlate_path}")
    
#     latin_text = ""
#     try:
#         with open(latin_correlate_path, 'r', encoding='utf-8') as latin_file:
#             latin_text = latin_file.read()
#         logger.debug(f"Latin text length: {len(latin_text)}")
#     except Exception as e:
#         logger.error(f'Error loading Latin path - {e}')
    
#     if not latin_text:
#         logger.warning("Latin text is empty or could not be loaded.")

#     text = ""
#     try:
#         with open(file_path, 'r', encoding='utf-8') as file:
#             text = file.read()
#         logger.debug(f"Original text length: {len(text)}")
#     except Exception as e:
#         logger.error(f'Error loading original file - {e}')
    
#     if not text:
#         logger.error("Original text is empty or could not be loaded.")
#         return {"chunks": []}

#     text = re.sub(r'</?speak>', '', text)
#     text = html.unescape(text)
#     paragraphs = re.split(r'(?<=</p>)', text)
    
#     chunks = []
#     current_chunk = ''
#     chunk_size = 50000

#     for para in paragraphs:
#         if len(current_chunk) + len(para) > chunk_size:
#             chunks.append(f'<speak>{current_chunk}</speak>')
#             current_chunk = para
#         else:
#             current_chunk += para
    
#     if current_chunk:
#         chunks.append(f'<speak>{current_chunk}</speak>')
    
#     logger.debug(f"Number of chunks: {len(chunks)}")
    
#     output_dict = {"chunks": []}
    
#     for i, chunk in enumerate(chunks, 1):
#         logger.debug(f"Processing chunk {i}")
#         # Preprocess and clean SSML tags
#         chunk = preprocess_ssml_tags(chunk)
#         chunk = clean_ssml_tags(chunk)
        
#         # Translate the chunk and clean SSML
#         try:
#             translated_chunk, _ = safe_format_text_with_gpt(chunk, language="Latin")
#             logger.debug(f"Translated chunk length: {len(translated_chunk)}")
            
#             # Clean the translated chunk
#             translated_chunk = preprocess_ssml_tags(translated_chunk)
#             translated_chunk = clean_ssml_tags(translated_chunk)
#         except Exception as e:
#             logger.error(f"Error in translation for chunk {i}: {e}")
#             translated_chunk = None
        
#         # Find corresponding Latin text
#         original_latin = "Latin text not found"
#         if latin_text:
#             start_index = latin_text.find(chunk)
#             if start_index != -1:
#                 end_index = start_index + len(chunk)
#                 original_latin = latin_text[start_index:end_index]
#             else:
#                 logger.warning(f"Latin text not found for chunk {i}")
#         else:
#             logger.warning(f"No Latin text available for chunk {i}")
        
#         chunk_dict = {
#             "chunk_number": i,
#             "original_latin": original_latin,
#             "translated_english": translated_chunk if translated_chunk else "Translation failed"
#         }
#         output_dict["chunks"].append(chunk_dict)
    
#     return output_dict

# Function to detect HTML content
def is_html(text):
    html_tags = re.compile('<.*?>')
    return bool(html_tags.search(text))

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

def preprocess_ssml_tags(content: str) -> str:
    """Preprocess SSML tags in the given content string."""
    allowed_tags = ["break", "lang", "p", "phoneme", "s", "speak", "sub", "w"]
    allowed_pattern = re.compile(r'</?({})(\s[^>]*)?/?>'.format('|'.join(allowed_tags)), re.IGNORECASE)

    # Unescape HTML entities
    content = html.unescape(content)

    # Function to remove disallowed tags
    def remove_disallowed_tags(match):
        tag = match.group(0)
        return tag if allowed_pattern.match(tag) else ''

    # Remove disallowed tags while preserving allowed tags
    cleaned_content = re.sub(r'</?[^>]+>', remove_disallowed_tags, content)

    return cleaned_content

def clean_ssml_tags(content: str) -> str:
    """Clean and process SSML tags in the given content string."""
    allowed_tags = ["break", "lang", "p", "phoneme", "s", "speak", "sub", "w"]

    def ensure_role_attribute(tag):
        return tag.replace('<w', '<w role="amazon:NN"', 1) if 'role=' not in tag else tag

    def clean_tags(content):
        try:
            root = etree.fromstring(f"<root>{content}</root>")
        except etree.ParseError as e:
            print(f"Error parsing SSML: {e}")
            return content  # Return original content if parsing fails

        def remove_unwanted_tags(element):
            for child in list(element):
                if child.tag not in allowed_tags:
                    # Keep the text content and tail
                    text = (child.text or '') + (child.tail or '')
                    previous = child.getprevious()
                    parent = child.getparent()
                    if previous is not None:
                        previous.tail = (previous.tail or '') + text
                    else:
                        parent.text = (parent.text or '') + text
                    # Remove the unwanted tag
                    parent.remove(child)
                else:
                    remove_unwanted_tags(child)

        remove_unwanted_tags(root)
        return etree.tostring(root, encoding='unicode').replace('<root>', '').replace('</root>', '')

    # Initial cleaning
    content = re.sub(r'<break\s*/?>', lambda m: '<break time="1s"/>' if 'time' not in m.group(0) else m.group(0), content)
    content = re.sub(r'<w([^>]*)>', ensure_role_attribute, content)
    content = clean_tags(content)

    # Final cleaning
    final_cleaned_ssml = clean_tags(content)

    # Ensure the content is wrapped in <speak> tags
    if not final_cleaned_ssml.strip().startswith('<speak>'):
        final_cleaned_ssml = f'<speak>{final_cleaned_ssml}</speak>'

    return final_cleaned_ssml

def smooth_text_for_youtube(ssml_content):
    prompt = ("Please review and smooth over the following text to make it more readable and coherent for a YouTube video script. "
              "Ensure that the meaning and tone are preserved, and make the language flow naturally for spoken presentation. "
              "Do not alter any SSML tags or introduce new ones. Provide only the smoothed-over text without adding any new content.")

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an AI assistant that smooths text for YouTube scripts while preserving SSML tags."},
                {"role": "user", "content": f"{prompt}\n\nText to smooth: {ssml_content}"}
            ],
            max_tokens=2048,
            temperature=0.7
        )
        if response.choices and response.choices[0].message:
            return response.choices[0].message.content.strip()
        else:
            return ssml_content  # Return original content if no response
    except Exception as e:
        print(f"Error in smoothing text: {e}")
        return ssml_content  # Return original content in case of error

def estimate_cost(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        text = file.read()
    
    character_count = len(text)

    # OpenAI gpt-4o cost
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

