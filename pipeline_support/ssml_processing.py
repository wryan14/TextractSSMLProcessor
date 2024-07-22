import boto3
import os
import re
from botocore.exceptions import BotoCoreError, ClientError

def split_ssml(ssml_text, max_chunk_size=2500):
    parts = re.split(r'(<[^>]+>)', ssml_text)
    chunks = []
    current_chunk = ""
    current_length = 0
    open_tags = []

    def add_closing_tags(tags):
        closing_tags = ""
        for tag in reversed(tags):
            if tag.startswith('</'):
                continue
            tag_name = tag[1:-1].split()[0]  # Get the tag name without attributes
            closing_tags += f"</{tag_name}>"
        return closing_tags

    def add_opening_tags(tags):
        opening_tags = ""
        for tag in tags:
            if tag.startswith('</'):
                continue
            opening_tags += tag
        return opening_tags

    for part in parts:
        part_length = len(part)

        if current_length + part_length <= max_chunk_size:
            current_chunk += part
            current_length += part_length

            if re.match(r'<[^/]+>', part) and not part.startswith('<speak'):
                open_tags.append(part)
            elif re.match(r'</[^>]+>', part):
                tag_name = part[2:-1]
                if open_tags and open_tags[-1][1:-1].split()[0] == tag_name:
                    open_tags.pop()
        else:
            current_chunk += add_closing_tags(open_tags)
            current_chunk = f"<speak>{current_chunk.strip()}</speak>"
            chunks.append(current_chunk)

            current_chunk = add_opening_tags(open_tags) + part
            current_length = len(current_chunk)

            open_tags = [tag for tag in open_tags if not tag.startswith('</')]
            if re.match(r'<[^/]+>', part) and not part.startswith('<speak'):
                open_tags.append(part)
            elif re.match(r'</[^>]+>', part):
                tag_name = part[2:-1]
                if open_tags and open_tags[-1][1:-1].split()[0] == tag_name:
                    open_tags.pop()

    if current_chunk:
        current_chunk += add_closing_tags(open_tags)
        current_chunk = f"<speak>{current_chunk}</speak>"
        chunks.append(current_chunk)

    return [x.replace('<p></p>', '').replace("<speak><speak>", '<speak>').replace('</speak></speak>', '</speak>') for x in chunks]

def get_voice_from_filename(filename, default_voice):
    voice_match = re.search(r'_voice_(Ruth|Matthew|Gregory)_', filename)
    return voice_match.group(1) if voice_match else default_voice

class SSMLProcessingError(Exception):
    """Custom exception for SSML processing errors"""
    pass

def process_ssml_files(input_directory, output_directory, output_filename, default_voice_id, start_part=1):
    print(f"Starting process_ssml_files with start_part={start_part}")
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

    pattern = re.compile(r'_(part_\d+)_.*_(chunk_\d+)\.txt$')
    input_files = [f for f in os.listdir(input_directory) if f.endswith('.txt') and pattern.search(f)]
    
    if not input_files:
        raise SSMLProcessingError(f"No input files found in directory: {input_directory}")

    sorted_files = sorted(input_files, key=lambda x: (
        int(pattern.search(x).group(1).split('_')[1]), 
        int(pattern.search(x).group(2).split('_')[1])
    ))

    print(f"Found {len(sorted_files)} input files")

    global_part_number = 1

    for input_file in sorted_files:
        print(f"Processing file: {input_file}")

        voice_id = get_voice_from_filename(input_file, default_voice_id)
        engine = voice_engine_map[voice_id]

        if engine == 'generative':
            max_chars = 2750
        elif engine == 'long-form':
            max_chars = 2500
        else:
            max_chars = 6000

        try:
            with open(os.path.join(input_directory, input_file), 'r', encoding='utf-8') as file:
                ssml_text = file.read()
        except Exception as e:
            raise SSMLProcessingError(f"Error reading file {input_file}: {str(e)}")

        ssml_chunks = split_ssml(ssml_text, max_chars)
        print(f"Split {input_file} into {len(ssml_chunks)} chunks")

        for chunk_index, chunk in enumerate(ssml_chunks):
            print(f"Processing part {global_part_number} (File: {input_file}, Chunk: {chunk_index + 1})")
            
            if global_part_number < start_part:
                print(f"Skipping part {global_part_number} < start_part {start_part}")
                global_part_number += 1
                continue

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
                raise SSMLProcessingError(f"Error processing {input_file} (part {global_part_number}, chunk {chunk_index + 1}): {error}\nProblematic chunk: {chunk}")
            except Exception as error:
                raise SSMLProcessingError(f"Unexpected error processing {input_file} (part {global_part_number}, chunk {chunk_index + 1}): {error}\nProblematic chunk: {chunk}")

    print(f"Finished processing. Generated {len(output_files)} output files.")
    return output_files

def rename_files(directory):
    files = os.listdir(directory)
    
    pattern = re.compile(r'_(part_\d+)_.*_(chunk_\d+)\.txt$')
    filtered_files = [f for f in files if f.endswith('.txt') and pattern.search(f)]
    sorted_files = sorted(filtered_files, key=lambda x: (
        int(pattern.search(x).group(1).split('_')[1]), 
        int(pattern.search(x).group(2).split('_')[1])
    ))

    for index, file_name in enumerate(sorted_files):
        new_name = re.sub(r'chunk_\d+', f'chunk_{index + 1}', file_name)
        os.rename(os.path.join(directory, file_name), os.path.join(directory, new_name))
        if index < 4:
            print(f"Renamed: {file_name} -> {new_name}")

# Example usage:
# output_files = process_ssml_files(
#     input_directory='/path/to/ssml/files',
#     output_directory='/path/to/output',
#     output_filename='my_audiobook',
#     default_voice_id='Matthew'
# )
