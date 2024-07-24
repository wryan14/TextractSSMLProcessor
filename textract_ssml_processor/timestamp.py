from flask import Blueprint, render_template, request, send_file, current_app, flash
import os
import json
from mutagen.mp3 import MP3
from werkzeug.utils import secure_filename
from typing import List, Dict
import io

bp = Blueprint('timestamp', __name__)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'mp3'}

def generate_srt_content(all_chunks: List[Dict], language: str) -> str:
    srt_content = ""
    for i, chunk in enumerate(all_chunks, 1):
        start = format_time(chunk['start_time'])
        end = format_time(chunk['end_time'])
        text = chunk[f'cleaned_{language}_translation' if language == 'english' else 'original_latin']
        srt_content += f"{i}\n{start} --> {end}\n{text}\n\n"
    return srt_content

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
        
        # Get all JSON files in the processed folder
        json_files = sorted([f for f in os.listdir(processed_folder) if f.endswith('.json')])
        print(f"Found {len(json_files)} JSON files")
        
        # Get all audio files
        audio_files = sorted([f for f in os.listdir(audio_dir) if f.endswith('.mp3')])
        print(f"Found {len(audio_files)} audio files")
        
        all_chunks = []
        cumulative_time = 0.0
        
        audio_file_index = 0
        for json_file in json_files:
            json_file_path = os.path.join(processed_folder, json_file)
            print(f"Processing JSON file: {json_file}")
            
            # Process JSON file
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
                
                print(f"Processing {audio_file} for chunk {audio_file_index + 1}: Duration = {duration:.2f} seconds")
                
                chunk['start_time'] = cumulative_time
                cumulative_time += duration
                chunk['end_time'] = cumulative_time
                all_chunks.append(chunk)
                
                audio_file_index += 1
            
            # Update the JSON file with new timestamps
            with open(json_file_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)
        
        print(f"Total chunks processed: {len(all_chunks)}")
        print(f"Total duration: {cumulative_time:.2f} seconds")
        
        # Generate SRT content
        english_srt = generate_srt_content(all_chunks, 'english')
        latin_srt = generate_srt_content(all_chunks, 'latin')
        
        return render_template('timestamp_result.html', 
                               english_srt=english_srt, 
                               latin_srt=latin_srt,
                               total_duration=format_time(cumulative_time))
    
    return render_template('create_timestamps.html')

@bp.route('/download_srt/<language>')
def download_srt(language):
    if language not in ['english', 'latin']:
        return "Invalid language", 400
    
    srt_content = request.args.get(f'{language}_srt', '')
    buffer = io.BytesIO(srt_content.encode('utf-8'))
    buffer.seek(0)
    return send_file(buffer,
                     as_attachment=True,
                     download_name=f'{language}_subtitles.srt',
                     mimetype='text/plain')