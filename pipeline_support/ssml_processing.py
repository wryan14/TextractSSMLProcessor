# ssml_processing.py

import boto3
import os
import re
from botocore.exceptions import BotoCoreError, ClientError

def split_ssml(ssml_text, max_chunk_size=3000):
    parts = re.split(r'(<[^>]+>)', ssml_text)

    chunks = []
    current_chunk = ""
    current_length = 0
    open_tags = []

    def add_closing_tags(open_tags):
        return "".join([f"</{tag[1:]}" for tag in reversed(open_tags)])

    def add_opening_tags(open_tags):
        return "".join(open_tags)

    for part in parts:
        part_length = len(part)

        if current_length + part_length <= max_chunk_size:
            current_chunk += part
            current_length += part_length

            if re.match(r'<[^/]+>', part) and not part.startswith('<speak'):
                open_tags.append(part)
            elif re.match(r'</[^>]+>', part):
                if open_tags and open_tags[-1][1:] == part[2:]:
                    open_tags.pop()
        else:
            current_chunk += add_closing_tags(open_tags)
            current_chunk = f"<speak>{current_chunk}</speak>"
            chunks.append(current_chunk)

            current_chunk = add_opening_tags(open_tags) + part
            current_length = len(current_chunk)

            open_tags = []
            if re.match(r'<[^/]+>', part) and not part.startswith('<speak'):
                open_tags.append(part)
            elif re.match(r'</[^>]+>', part):
                if open_tags and open_tags[-1][1:] == part[2:]:
                    open_tags.pop()

    if current_chunk:
        current_chunk += add_closing_tags(open_tags)
        current_chunk = f"<speak>{current_chunk}</speak>"
        chunks.append(current_chunk)

    return [x.replace('<p></p>', '').replace("<speak><speak>", '<speak>').replace('</speak></speak>', '</speak>') for x in chunks]

def get_voice_from_filename(filename, default_voice):
    voice_match = re.search(r'_voice_(Ruth|Matthew|Gregory)_', filename)
    return voice_match.group(1) if voice_match else default_voice

def process_ssml_files(input_directory, output_directory, output_filename, default_voice_id):
    polly_client = boto3.client('polly')

    voice_engine_map = {
        'Ruth': 'generative',
        'Matthew': 'generative',
        'Gregory': 'long-form'
    }

    if default_voice_id not in voice_engine_map:
        raise ValueError(f"Unsupported default_voice_id: {default_voice_id}. Please use 'Ruth', 'Matthew', or 'Gregory'.")

    os.makedirs(output_directory, exist_ok=True)
    output_files = []
    input_files = sorted([f for f in os.listdir(input_directory) if f.endswith('.txt')])

    global_part_number = 1

    for input_file in input_files:
        voice_id = get_voice_from_filename(input_file, default_voice_id)
        engine = voice_engine_map[voice_id]
        max_chars = 3000 if engine == 'generative' else 6000

        with open(os.path.join(input_directory, input_file), 'r') as file:
            ssml_text = file.read()

        ssml_chunks = split_ssml(ssml_text, max_chars)

        for chunk in ssml_chunks:
            try:
                response = polly_client.synthesize_speech(
                    Engine=engine,
                    Text=chunk,
                    TextType='ssml',
                    OutputFormat='mp3',
                    VoiceId=voice_id
                )

                output_file = f"{output_filename}_part{global_part_number}.mp3"
                output_path = os.path.join(output_directory, output_file)
                
                with open(output_path, 'wb') as file:
                    file.write(response['AudioStream'].read())
                
                output_files.append(output_path)
                print(f"Generated: {output_file} using {voice_id} voice with {engine} engine")

                global_part_number += 1

            except (BotoCoreError, ClientError) as error:
                print(f"Error processing {input_file} (part {global_part_number}): {error}")
                break

    return output_files

def rename_files(directory):
    files = os.listdir(directory)
    filtered_files = [f for f in files if f.endswith('.txt') and f.split('_')[-1][0].isdigit()]
    sorted_files = sorted(filtered_files, key=lambda x: int(x.split('_')[-1].split('.')[0]))

    for index, file_name in enumerate(sorted_files):
        new_name = f"{file_name.rsplit('_', 1)[0]}_{index + 1}.txt"
        os.rename(os.path.join(directory, file_name), os.path.join(directory, new_name))
        print(f"Renamed: {file_name} -> {new_name}")
