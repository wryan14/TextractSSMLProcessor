from flask import Blueprint, render_template, request, send_file, current_app, flash, Response
import os
import json
from mutagen.mp3 import MP3
from werkzeug.utils import secure_filename
from typing import List, Dict
import io
import re

bp = Blueprint('timestamp', __name__)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'mp3'}

def clean_text(text: str) -> str:
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Replace multiple spaces with a single space
    text = re.sub(r' +', ' ', text)
    # Split the text into lines, remove leading/trailing spaces, and filter out empty lines
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    # Join the non-empty lines back together
    return '\n'.join(lines)

def split_into_subtitles(text: str, start_time: float, end_time: float, max_chars: int = 80, target_duration: float = 5.0) -> List[Dict]:
    def split_sentences(text):
        result = []
        current_sentence = ""
        in_special_block = False
        special_block_char = None

        for char in text:
            current_sentence += char
            if char in "([\"":
                in_special_block = True
                special_block_char = char
            elif (char == ")" and special_block_char == "(") or \
                 (char == "]" and special_block_char == "[") or \
                 (char == "\"" and special_block_char == "\""):
                in_special_block = False
                special_block_char = None
            elif char in ".!?" and not in_special_block and len(current_sentence.strip()) > 0:
                result.append(current_sentence.strip())
                current_sentence = ""

        if current_sentence.strip():
            result.append(current_sentence.strip())

        return result

    sentences = split_sentences(text)
    total_duration = end_time - start_time
    time_per_char = total_duration / len(text)
    
    subtitles = []
    current_subtitle = ""
    current_start = start_time
    
    for sentence in sentences:
        if len(current_subtitle) + len(sentence) <= max_chars:
            current_subtitle += (" " if current_subtitle else "") + sentence
        else:
            if current_subtitle:
                subtitle_duration = len(current_subtitle) * time_per_char
                subtitles.append({
                    "text": current_subtitle,
                    "start": current_start,
                    "end": min(current_start + subtitle_duration, end_time)
                })
                current_start += subtitle_duration
            current_subtitle = sentence
        
        if (current_start - start_time) >= target_duration:
            subtitle_duration = len(current_subtitle) * time_per_char
            subtitles.append({
                "text": current_subtitle,
                "start": current_start,
                "end": min(current_start + subtitle_duration, end_time)
            })
            current_start += subtitle_duration
            current_subtitle = ""
    
    if current_subtitle:
        subtitles.append({
            "text": current_subtitle,
            "start": current_start,
            "end": end_time
        })
    
    return subtitles

def split_latin_subtitles(text: str, start_time: float, end_time: float, max_chars: int = 300) -> List[Dict]:
    def split_sentences(text):
        sentences = []
        current_sentence = ""
        parenthesis_level = 0
        
        for char in text:
            current_sentence += char
            if char == '(':
                parenthesis_level += 1
            elif char == ')':
                parenthesis_level -= 1
            elif char == '.' and parenthesis_level == 0 and len(current_sentence.strip()) > 0:
                sentences.append(current_sentence.strip())
                current_sentence = ""
        
        if current_sentence.strip():
            sentences.append(current_sentence.strip())
        
        return sentences

    def split_long_sentence(sentence, max_chars):
        words = sentence.split()
        chunks = []
        current_chunk = ""
        for word in words:
            if len(current_chunk) + len(word) + 1 <= max_chars:
                current_chunk += (" " if current_chunk else "") + word
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = word
        if current_chunk:
            chunks.append(current_chunk)
        return chunks

    sentences = split_sentences(text)
    total_duration = end_time - start_time
    time_per_char = total_duration / len(text)
    
    subtitles = []
    current_subtitle = ""
    current_start = start_time

    for sentence in sentences:
        if len(sentence) > max_chars:
            # If the current subtitle is not empty, add it to subtitles
            if current_subtitle:
                subtitle_duration = len(current_subtitle) * time_per_char
                subtitles.append({
                    "text": current_subtitle,
                    "start": current_start,
                    "end": min(current_start + subtitle_duration, end_time)
                })
                current_start += subtitle_duration
                current_subtitle = ""
            
            # Split the long sentence
            chunks = split_long_sentence(sentence, max_chars)
            for chunk in chunks:
                chunk_duration = len(chunk) * time_per_char
                subtitles.append({
                    "text": chunk,
                    "start": current_start,
                    "end": min(current_start + chunk_duration, end_time)
                })
                current_start += chunk_duration
        elif len(current_subtitle) + len(sentence) <= max_chars:
            current_subtitle += (" " if current_subtitle else "") + sentence
        else:
            # Add the current subtitle to subtitles
            subtitle_duration = len(current_subtitle) * time_per_char
            subtitles.append({
                "text": current_subtitle,
                "start": current_start,
                "end": min(current_start + subtitle_duration, end_time)
            })
            current_start += subtitle_duration
            current_subtitle = sentence

    # Add any remaining content
    if current_subtitle:
        subtitles.append({
            "text": current_subtitle,
            "start": current_start,
            "end": end_time
        })

    return subtitles

def generate_srt_content(all_chunks: List[Dict], language: str, use_shorter_subtitles: bool = False) -> str:
    srt_content = ""
    subtitle_index = 1
    
    for chunk in all_chunks:
        if language == 'english':
            text = clean_text(chunk['cleaned_english_translation'])
            if use_shorter_subtitles:
                subtitles = split_into_subtitles(text, chunk['start_time'], chunk['end_time'])
            else:
                subtitles = [{"text": text, "start": chunk['start_time'], "end": chunk['end_time']}]
        else:  # Latin
            text = clean_text(chunk['original_latin'])
            if use_shorter_subtitles:
                subtitles = split_latin_subtitles(text, chunk['start_time'], chunk['end_time'])
            else:
                subtitles = [{"text": text, "start": chunk['start_time'], "end": chunk['end_time']}]
        
        for subtitle in subtitles:
            start = format_time(subtitle['start'])
            end = format_time(subtitle['end'])
            srt_content += f"{subtitle_index}\n{start} --> {end}\n{subtitle['text']}\n\n"
            subtitle_index += 1
    
    return srt_content


def save_srt_files(english_original, english_shorter, latin_original, latin_shorter, output_dir=None):
    if output_dir is None:
        output_dir = current_app.config['SUBTITLE_OUTPUT']
    
    os.makedirs(output_dir, exist_ok=True)
    
    files = {
        'english_original.srt': english_original,
        'english_shorter.srt': english_shorter,
        'latin_original.srt': latin_original,
        'latin_shorter.srt': latin_shorter
    }
    
    for filename, content in files.items():
        with open(os.path.join(output_dir, filename), 'w', encoding='utf-8') as f:
            f.write(content)


def format_time(seconds: float) -> str:
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    milliseconds = int((seconds % 1) * 1000)
    return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d},{milliseconds:03d}"

def natural_sort_key(s):
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', s)]


@bp.route('/create_timestamps', methods=['GET', 'POST'])
def create_timestamps():
    if request.method == 'POST':
        processed_folder = current_app.config['PROCESSED_FOLDER']
        audio_dir = current_app.config['AUDIO_OUTPUT_FOLDER']
        
        print(f"Processed folder: {processed_folder}")
        print(f"Audio directory: {audio_dir}")
        
        json_files = sorted([f for f in os.listdir(processed_folder) if f.endswith('.json')], key=natural_sort_key)
        audio_files = sorted([f for f in os.listdir(audio_dir) if f.endswith('.mp3')], key=natural_sort_key)
        
        print(f"Number of JSON files: {len(json_files)}")
        print(f"Number of audio files: {len(audio_files)}")
        
        all_chunks = []
        cumulative_time = 0.0
        
        audio_file_index = 0
        for json_file in json_files:
            json_file_path = os.path.join(processed_folder, json_file)
            print(f"Processing JSON file: {json_file}")
            
            with open(json_file_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            chunks = json_data['chunks']
            print(f"Number of chunks in {json_file}: {len(chunks)}")
            
            for chunk in chunks:
                if audio_file_index >= len(audio_files):
                    print("Warning: More chunks than audio files. Stopping processing.")
                    break
                
                audio_file = audio_files[audio_file_index]
                file_path = os.path.join(audio_dir, audio_file)
                print(f"Processing audio file: {audio_file}")
                audio = MP3(file_path)
                duration = audio.info.length
                
                chunk['start_time'] = cumulative_time
                cumulative_time += duration
                chunk['end_time'] = cumulative_time
                all_chunks.append(chunk)
                
                audio_file_index += 1
        
        print(f"Total number of chunks processed: {len(all_chunks)}")
        print(f"Total duration: {cumulative_time} seconds")
        
        english_srt_original = generate_srt_content(all_chunks, 'english', use_shorter_subtitles=False)
        english_srt_shorter = generate_srt_content(all_chunks, 'english', use_shorter_subtitles=True)
        latin_srt_original = generate_srt_content(all_chunks, 'latin', use_shorter_subtitles=False)
        latin_srt_shorter = generate_srt_content(all_chunks, 'latin', use_shorter_subtitles=True)
        
        print(f"Length of english_srt_original: {len(english_srt_original)}")
        print(f"Length of english_srt_shorter: {len(english_srt_shorter)}")
        print(f"Length of latin_srt_original: {len(latin_srt_original)}")
        print(f"Length of latin_srt_shorter: {len(latin_srt_shorter)}")
        
        save_srt_files(english_srt_original, english_srt_shorter, latin_srt_original, latin_srt_shorter)
        return render_template('timestamp_result.html', 
                               english_srt_original=english_srt_original,
                               english_srt_shorter=english_srt_shorter,
                               latin_srt_original=latin_srt_original,
                               latin_srt_shorter=latin_srt_shorter,
                               total_duration=format_time(cumulative_time))
    
    return render_template('create_timestamps.html')

@bp.route('/download_srt/<language>/<version>')
def download_srt(language, version):
    filename = f"{language}_{version}.srt"
    file_path = os.path.join(current_app.config['SUBTITLE_OUTPUT'], filename)
    
    if not os.path.exists(file_path):
        return f"File not found: {file_path}", 404

    return send_file(file_path,
                     as_attachment=True,
                     download_name=filename,
                     mimetype='text/plain')

@bp.route('/batch_create_timestamps', methods=['POST'])
def batch_create_timestamps():
    projects_directory = request.form['projects_directory']
    
    if not os.path.exists(projects_directory):
        flash('Projects directory does not exist.', 'danger')
        return render_template('create_timestamps.html')
    
    project_dirs = [d for d in os.listdir(projects_directory) if os.path.isdir(os.path.join(projects_directory, d))]
    
    all_results = []
    
    for project in project_dirs:
        processed_folder = os.path.join(projects_directory, project, 'SSML')
        audio_dir = os.path.join(projects_directory, project, 'Audio')
        subtitle_output_dir = os.path.join(projects_directory, project, 'subtitles')
        
        if not os.path.exists(processed_folder) or not os.path.exists(audio_dir):
            flash(f'Missing directories for project: {project}', 'warning')
            continue
        
        json_files = sorted([f for f in os.listdir(processed_folder) if f.endswith('.json')], key=natural_sort_key)
        audio_files = sorted([f for f in os.listdir(audio_dir) if f.endswith('.mp3')], key=natural_sort_key)
        
        all_chunks = []
        cumulative_time = 0.0
        audio_file_index = 0
        
        for json_file in json_files:
            json_file_path = os.path.join(processed_folder, json_file)
            with open(json_file_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            chunks = json_data['chunks']
            
            for chunk in chunks:
                if audio_file_index >= len(audio_files):
                    break
                
                audio_file = audio_files[audio_file_index]
                file_path = os.path.join(audio_dir, audio_file)
                audio = MP3(file_path)
                duration = audio.info.length
                
                chunk['start_time'] = cumulative_time
                cumulative_time += duration
                chunk['end_time'] = cumulative_time
                all_chunks.append(chunk)
                
                audio_file_index += 1
        
        english_srt_original = generate_srt_content(all_chunks, 'english', use_shorter_subtitles=False)
        english_srt_shorter = generate_srt_content(all_chunks, 'english', use_shorter_subtitles=True)
        latin_srt_original = generate_srt_content(all_chunks, 'latin', use_shorter_subtitles=False)
        latin_srt_shorter = generate_srt_content(all_chunks, 'latin', use_shorter_subtitles=True)
        
        save_srt_files(english_srt_original, english_srt_shorter, latin_srt_original, latin_srt_shorter, output_dir=subtitle_output_dir)
        
        all_results.append({
            'project': project,
            'english_srt_original': english_srt_original,
            'english_srt_shorter': english_srt_shorter,
            'latin_srt_original': latin_srt_original,
            'latin_srt_shorter': latin_srt_shorter,
            'total_duration': format_time(cumulative_time)
        })
    
    return render_template('batch_timestamp_result.html', results=all_results)