import os
import shutil
import re
import glob
import subprocess
import time
import logging
from pydub import AudioSegment
from mutagen.mp4 import MP4, MP4Cover
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, TCON, COMM, APIC, error
from mutagen.mp3 import MP3
from moviepy.editor import AudioFileClip, ColorClip, CompositeVideoClip, TextClip, ImageClip
from moviepy.config import change_settings

from moviepy.video.tools.subtitles import SubtitlesClip

# Configuration
image_magick_binary = os.environ.get("IMAGEMAGICK_BINARY")
if image_magick_binary:
    change_settings({"IMAGEMAGICK_BINARY": image_magick_binary})

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# Constants
FONT_DIR = os.path.join('../static', os.path.dirname(os.path.abspath(__file__)))
LUXURIOUS_ROMAN = os.path.join(FONT_DIR, "LuxuriousRoman-Regular.ttf")
OPEN_SANS = os.path.join(FONT_DIR, "OpenSans-VariableFont_wdth,wght.ttf")
PT_SERIF = os.path.join(FONT_DIR, "PTSerif-Regular.ttf")

BACKGROUND_COLOR = (237, 224, 202)  # #EDE0CA (light beige)
TEXT_COLOR = (62, 44, 27)  # #3E2C1B (dark brown)
HIGHLIGHT_COLOR = (184, 134, 11)  # #B8860B (Dark Goldenrod)


# Utility Functions
def check_ffmpeg_installed():
    try:
        subprocess.run(["ffmpeg", "-version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except FileNotFoundError:
        return False
    except subprocess.CalledProcessError:
        return False

def natural_sort_key(s):
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', s)]

def rgb_to_string(rgb_tuple):
    return f"rgb{rgb_tuple}"

def remove_ssml_tags(text):
    return re.sub(r'<[^>]+>', '', text).strip()

def parse_srt(srt_file):
    with open(srt_file, 'r', encoding='utf-8') as file:
        content = file.read()

    # Split the content into individual subtitle blocks
    subtitle_blocks = re.split(r'\n\s*\n', content.strip())
    
    subtitles = []
    for block in subtitle_blocks:
        parts = block.split('\n', 2)
        if len(parts) < 3:
            continue  # Skip invalid blocks
        
        index = parts[0]
        time_range = parts[1]
        text = parts[2].strip()
        
        # Extract start and end times
        time_pattern = r'(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})'
        time_match = re.match(time_pattern, time_range)
        if not time_match:
            continue  # Skip if time format is invalid
        
        start_time, end_time = time_match.groups()
        
        subtitles.append({
            'index': int(index),
            'start': time_to_seconds(start_time),
            'end': time_to_seconds(end_time),
            'text': text
        })
    
    return subtitles

def time_to_seconds(time_str):
    h, m, s = time_str.replace(',', '.').split(':')
    return int(h) * 3600 + int(m) * 60 + float(s)

# Audio Processing Functions
def combine_mp3_files(files, output_file):
    combined = AudioSegment.empty()
    for file in sorted(files, key=natural_sort_key):
        combined += AudioSegment.from_mp3(file)
    combined.export(output_file, format="mp3")
    return output_file

def convert_to_audiobook(mp3_file, audiobook_file):
    AudioSegment.from_mp3(mp3_file).export(audiobook_file, format="mp4")
    return audiobook_file

def add_metadata_to_m4b(m4b_file_path, cover_image_path, title, author, year, genre, description):
    audio = MP4(m4b_file_path)
    audio['\xa9nam'] = title
    audio['\xa9ART'] = author
    audio['\xa9alb'] = title
    audio['\xa9day'] = year
    audio['\xa9gen'] = genre
    audio['desc'] = description

    with open(cover_image_path, 'rb') as f:
        cover = MP4Cover(f.read(), imageformat=MP4Cover.FORMAT_PNG)
    audio['covr'] = [cover]

    audio.save()
    logging.info("Metadata added successfully to M4B.")

def add_metadata_to_mp3(mp3_file_path, cover_image_path, title, author, year, genre, description):
    audio = MP3(mp3_file_path, ID3=ID3)

    try:
        audio.add_tags()
    except error:
        pass

    audio.tags.add(APIC(encoding=3, mime='image/png', type=3, desc=u'Cover', data=open(cover_image_path, 'rb').read()))
    audio.tags.add(TIT2(encoding=3, text=title))
    audio.tags.add(TPE1(encoding=3, text=author))
    audio.tags.add(TALB(encoding=3, text=title))
    audio.tags.add(TDRC(encoding=3, text=year))
    audio.tags.add(TCON(encoding=3, text=genre))
    audio.tags.add(COMM(encoding=3, desc=u'Comment', text=description))

    audio.save()
    logging.info("Metadata added successfully to MP3.")

def create_optimized_video(audio, subtitles, book_title, logo_path, main_font):
    bg_clip = ColorClip(size=(1920, 1080), color=BACKGROUND_COLOR).set_duration(audio.duration)

    # Logo creation is commented out, but let's keep it as an option
    # remove this if you want the logo back -
    logo_path = None
    if logo_path:
        logo = (ImageClip(logo_path)
                .resize(height=120)
                .set_opacity(0.3)
                .set_position(('right', 'bottom'))
                .set_duration(audio.duration))
    else:
        logo = None

    title_clip = (TextClip(book_title, fontsize=60, color=rgb_to_string(TEXT_COLOR), 
                           font=LUXURIOUS_ROMAN, size=(1920, 100))
                  .set_position(('center', 50))
                  .set_duration(audio.duration))

    # Sort subtitles by start time
    subtitles.sort(key=lambda x: x['start'])

    # Prepare subtitles in the format expected by SubtitlesClip
    subtitle_clips = [((sub['start'], sub['end']), sub['text']) for sub in subtitles]

    # Create a SubtitlesClip with a custom text clip generator
    def make_textclip(txt):
        return TextClip(txt, fontsize=40, color=rgb_to_string(TEXT_COLOR), 
                        font=main_font, size=(1720, None), method='caption')

    subtitles_clip = SubtitlesClip(subtitle_clips, make_textclip)
    subtitles_clip = subtitles_clip.set_position(('center', 'center'))

    # Create the composite video clip
    video_elements = [bg_clip, title_clip, subtitles_clip]
    if logo:
        video_elements.append(logo)
    
    video = CompositeVideoClip(video_elements)
    video = video.set_audio(audio)
    
    return video

def write_optimized_video(video, output_path):
    start_time = time.time()
    logging.info(f"Starting video write at {time.strftime('%H:%M:%S')}")
    
    video.write_videofile(output_path, 
                          codec='libx264', 
                          preset='ultrafast',
                          fps=24, 
                          threads=4,
                          logger=None)
    
    end_time = time.time()
    logging.info(f"Video write completed at {time.strftime('%H:%M:%S')}")
    logging.info(f"Total time taken: {end_time - start_time:.2f} seconds")

def enhanced_mp3_to_mp4_with_subtitles(mp3_path, srt_path, logo_path, output_path, book_title, main_font='open_sans'):
    start_time = time.time()
    logging.info(f"Starting enhanced MP3 to MP4 conversion at {time.strftime('%H:%M:%S')}")

    audio = AudioFileClip(mp3_path)
    logging.info(f"Audio duration: {audio.duration} seconds")

    subtitles = parse_srt(srt_path)
    logging.info(f"Number of subtitles: {len(subtitles)}")

    main_font_file = OPEN_SANS if main_font.lower() == 'open_sans' else PT_SERIF

    video = create_optimized_video(audio, subtitles, book_title, logo_path, main_font_file)
    write_optimized_video(video, output_path)

    end_time = time.time()
    logging.info(f"Enhanced MP4 with subtitles created successfully using {os.path.basename(main_font_file)} for main text.")
    logging.info(f"Total processing time: {end_time - start_time:.2f} seconds")

# File Management Functions
def copy_files(source_dir, destination_dir):
    for file_name in os.listdir(source_dir):
        full_file_name = os.path.join(source_dir, file_name)
        if os.path.isfile(full_file_name):
            shutil.copy(full_file_name, destination_dir)
            logging.info(f"Copied: {file_name}")

def prompt_user_to_load_files(directory):
    print(f"Please load your audio files into the directory: {directory}")
    subprocess.run(f'explorer {os.path.realpath(directory)}')
    # input("Press Enter to continue once the files are loaded...")

# Store mp4 parts for later batch mp4 creation
import json
def store_mp4_components(combined_mp3_file_path, srt_path, logo_path, output_path, book_title, main_font):
    # Create a subdirectory for MP4 components
    mp4_components_dir = os.path.join(os.path.dirname(combined_mp3_file_path), "mp4_components")
    os.makedirs(mp4_components_dir, exist_ok=True)

    # Copy necessary files
    shutil.copy(combined_mp3_file_path, mp4_components_dir)
    shutil.copy(srt_path, mp4_components_dir)
    shutil.copy(logo_path, mp4_components_dir)

    # Create a JSON file with component information
    component_info = {
        "mp3_file": os.path.basename(combined_mp3_file_path),
        "srt_file": os.path.basename(srt_path),
        "logo_file": os.path.basename(logo_path),
        "output_path": output_path,
        "book_title": book_title,
        "main_font": main_font
    }

    with open(os.path.join(mp4_components_dir, "mp4_info.json"), "w") as f:
        json.dump(component_info, f, indent=4)

    print(f"MP4 components stored in: {mp4_components_dir}")

if __name__ == "__main__":
    # Usage example
    enhanced_mp3_to_mp4_with_subtitles(
        mp3_path='path/to/your/audio.mp3',
        srt_path='path/to/your/latin_subtitles.srt',
        logo_path='path/to/your/logo.png',
        output_path='path/to/output/video.mp4',
        book_title='Your Book Title',
        main_font='open_sans'  # or 'pt_serif'
    )