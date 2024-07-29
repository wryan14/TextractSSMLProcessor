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
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\n{2,}', '\n', text)
    return text.strip()

def split_into_subtitles(text: str, start_time: float, end_time: float, max_chars: int = 80, target_duration: float = 5.0) -> List[Dict]:
    sentences = re.split(r'(?<=[.!?])\s+', text)
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

def generate_srt_content(all_chunks: List[Dict], language: str, use_shorter_subtitles: bool = False) -> str:
    srt_content = ""
    subtitle_index = 1
    
    for chunk in all_chunks:
        if language == 'english':
            text = clean_text(chunk['cleaned_english_translation'])
        else:
            text = chunk['original_latin']
        
        if use_shorter_subtitles:
            subtitles = split_into_subtitles(text, chunk['start_time'], chunk['end_time'])
            for subtitle in subtitles:
                start = format_time(subtitle['start'])
                end = format_time(subtitle['end'])
                srt_content += f"{subtitle_index}\n{start} --> {end}\n{subtitle['text']}\n\n"
                subtitle_index += 1
        else:
            start = format_time(chunk['start_time'])
            end = format_time(chunk['end_time'])
            srt_content += f"{subtitle_index}\n{start} --> {end}\n{text}\n\n"
            subtitle_index += 1
    
    return srt_content

def save_srt_files(english_original, english_shorter, latin_original, latin_shorter):
    subtitle_folder = current_app.config['SUBTITLE_OUTPUT']
    os.makedirs(subtitle_folder, exist_ok=True)
    
    files = {
        'english_original.srt': english_original,
        'english_shorter.srt': english_shorter,
        'latin_original.srt': latin_original,
        'latin_shorter.srt': latin_shorter
    }
    
    for filename, content in files.items():
        with open(os.path.join(subtitle_folder, filename), 'w', encoding='utf-8') as f:
            f.write(content)

def format_time(seconds: float) -> str:
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    milliseconds = int((seconds % 1) * 1000)
    return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d},{milliseconds:03d}"

@bp.route('/create_timestamps', methods=['GET', 'POST'])
def create_timestamps():
    if request.method == 'POST':
        processed_folder = current_app.config['PROCESSED_FOLDER']
        audio_dir = current_app.config['AUDIO_OUTPUT_FOLDER']
        
        json_files = sorted([f for f in os.listdir(processed_folder) if f.endswith('.json')])
        audio_files = sorted([f for f in os.listdir(audio_dir) if f.endswith('.mp3')])
        
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
                    print("Warning: More chunks than audio files. Stopping processing.")
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
            
            with open(json_file_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)
        
        english_srt_original = generate_srt_content(all_chunks, 'english', use_shorter_subtitles=False)
        english_srt_shorter = generate_srt_content(all_chunks, 'english', use_shorter_subtitles=True)
        latin_srt_original = generate_srt_content(all_chunks, 'latin', use_shorter_subtitles=False)
        latin_srt_shorter = generate_srt_content(all_chunks, 'latin', use_shorter_subtitles=True)
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