# audio_processing.py

import os
import shutil
import re
import glob
import subprocess
from pydub import AudioSegment
from mutagen.mp4 import MP4, MP4Cover
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, TCON, COMM, APIC, error
from mutagen.mp3 import MP3
from moviepy.editor import AudioFileClip, ImageClip

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
    audio['\xa9nam'] = title  # Title
    audio['\xa9ART'] = author  # Artist
    audio['\xa9alb'] = title  # Album
    audio['\xa9day'] = year  # Year
    audio['\xa9gen'] = genre  # Genre
    audio['desc'] = description

    with open(cover_image_path, 'rb') as f:
        cover = MP4Cover(f.read(), imageformat=MP4Cover.FORMAT_PNG)
    audio['covr'] = [cover]

    audio.save()
    print("Metadata added successfully to M4B.")

def add_metadata_to_mp3(mp3_file_path, cover_image_path, title, author, year, genre, description):
    audio = MP3(mp3_file_path, ID3=ID3)

    try:
        audio.add_tags()
    except error:
        pass

    audio.tags.add(
        APIC(
            encoding=3,  # 3 is for utf-8
            mime='image/png',  # image type
            type=3,  # 3 is for the cover(front) image
            desc=u'Cover',
            data=open(cover_image_path, 'rb').read()
        )
    )

    audio.tags.add(TIT2(encoding=3, text=title))  # Title
    audio.tags.add(TPE1(encoding=3, text=author))  # Artist
    audio.tags.add(TALB(encoding=3, text=title))  # Album
    audio.tags.add(TDRC(encoding=3, text=year))  # Year
    audio.tags.add(TCON(encoding=3, text=genre))  # Genre
    audio.tags.add(COMM(encoding=3, desc=u'Comment', text=description))  # Comment

    audio.save()
    print("Metadata added successfully to MP3.")

def remove_ssml_tags(text):
    return re.sub(r'<[^>]+>', '', text).strip()

def mp3_to_mp4(mp3_path, image_path, output_path):
    audio = AudioFileClip(mp3_path)
    image = ImageClip(image_path).set_duration(audio.duration).resize(height=1080).on_color(size=(1920, 1080), color=(0, 0, 0), pos=('center', 'center'))
    video = image.set_audio(audio)
    video.write_videofile(output_path, codec='libx264', fps=24)
    print("MP3 converted to MP4 successfully.")

def copy_files(source_dir, destination_dir):
    for file_name in os.listdir(source_dir):
        full_file_name = os.path.join(source_dir, file_name)
        if os.path.isfile(full_file_name):
            shutil.copy(full_file_name, destination_dir)
            print(f"Copied: {file_name}")

def prompt_user_to_load_files(directory):
    print(f"Please load your audio files into the directory: {directory}")
    subprocess.run(f'explorer {os.path.realpath(directory)}')
    input("Press Enter to continue once the files are loaded...")
