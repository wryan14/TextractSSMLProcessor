import json
import os
import re
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from typing import List, Dict

def split_ssml(ssml_text, max_chunk_size=2500):
    parts = re.split(r'(<[^>]+>)', ssml_text)
    chunks = []
    current_chunk = ""
    current_length = 0
    open_tags = []

    def add_closing_tags(tags):
        return "".join(f"</{tag[1:-1].split()[0]}>" for tag in reversed(tags) if not tag.startswith('</'))

    def add_opening_tags(tags):
        return "".join(tag for tag in tags if not tag.startswith('</'))

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

class SSMLProcessingError(Exception):
    """Custom exception for SSML processing errors"""
    pass

def process_ssml_from_json_files(input_directory: str,
                                 output_directory: str, 
                                 output_filename: str, 
                                 default_voice_id: str,
                                 start_part: int = 1) -> List[str]:
    print(f"Starting process_ssml_from_json_files with start_part={start_part}")
    polly_client = boto3.client('polly')

    voice_engine_map = {
        'Ruth': 'generative',
        'Matthew': 'generative',
        'Gregory': 'long-form'
    }

    os.makedirs(output_directory, exist_ok=True)
    output_files = []

    # Modified sorting logic
    def sort_key(filename):
        # Extract the number at the end of the filename
        match = re.search(r'_part_(\d+)\.txt\.json$', filename)
        if match:
            return int(match.group(1))
        return 0  # Default value for files that don't match the pattern

    json_files = sorted([f for f in os.listdir(input_directory) if f.endswith('.json')], key=sort_key)
    
    if not json_files:
        raise ValueError(f"No JSON files found in directory: {input_directory}")

    print(f"Found {len(json_files)} input JSON files")

    global_part_number = start_part

    for json_file in json_files:
        print(f"Processing file: {json_file}")

        try:
            with open(os.path.join(input_directory, json_file), 'r', encoding='utf-8') as file:
                data = json.load(file)
        except Exception as e:
            raise ValueError(f"Error reading JSON file {json_file}: {str(e)}")

        for chunk_index, chunk in enumerate(data['chunks'], start=1):
            ssml_text = chunk['cleaned_english_translation']
            
            # Use the voice from the JSON if available, otherwise use the default
            voice_id = chunk.get('voice')
            if voice_id is None:
                voice_id = default_voice_id
                print(f"Chunk {chunk_index} - No voice specified in JSON, using default: {voice_id}")
            else:
                print(f"Chunk {chunk_index} - Voice specified in JSON: {voice_id}")
            
            if voice_id not in voice_engine_map:
                print(f"Warning: Unsupported voice '{voice_id}' for chunk {chunk_index} in {json_file}. Using default voice.")
                voice_id = default_voice_id

            engine = voice_engine_map[voice_id]
            print(f"Using voice: {voice_id} with engine: {engine}")

            try:
                print(f"Attempting to synthesize speech for chunk {chunk_index} with voice {voice_id}")
                response = polly_client.synthesize_speech(
                    Engine=engine,
                    Text=ssml_text,
                    TextType='ssml',
                    OutputFormat='mp3',
                    VoiceId=voice_id
                )

                output_file = f"{output_filename}_part{global_part_number:03d}_{voice_id}.mp3"
                output_path = os.path.join(output_directory, output_file)
                
                with open(output_path, 'wb') as file:
                    file.write(response['AudioStream'].read())
                
                output_files.append(output_path)
                print(f"Generated: {output_file} using {voice_id} voice with {engine} engine")

                global_part_number += 1

            except (BotoCoreError, ClientError) as error:
                print(f"Error synthesizing speech: {error}")
                raise ValueError(f"Error processing {json_file} (part {global_part_number}, chunk {chunk_index}): {error}\nProblematic SSML: {ssml_text}")
            except Exception as error:
                print(f"Unexpected error: {error}")
                raise ValueError(f"Unexpected error processing {json_file} (part {global_part_number}, chunk {chunk_index}): {error}\nProblematic SSML: {ssml_text}")

    print(f"Finished processing. Generated {len(output_files)} output files.")
    return output_files

# Example usage
if __name__ == "__main__":
    input_directory = 'C:/Users/rdw71/Documents/Python/TextractSSMLProcessor/processed'
    audio_dir = 'C:/Users/rdw71/Documents/Python/TextractSSMLProcessor/audio_output'
    title = "Your Book Title"  # Set this to your book title
    output_filename = title.replace(' ', '_')
    default_voice_id = 'Matthew'
    start_part = 1  # Start from Polly audio file part 1, adjust as needed

    # Check if the input directory exists
    if not os.path.exists(input_directory):
        print(f"Error: Input directory '{input_directory}' does not exist.")
    else:
        print(f"Processing SSML chunks from JSON files, starting from Polly audio file part {start_part}...")
        try:
            outfiles = process_ssml_from_json_files(
                input_directory=input_directory,
                output_directory=audio_dir, 
                output_filename=output_filename, 
                default_voice_id=default_voice_id,
                start_part=start_part
            )

            print(f"Processed {len(outfiles)} files.")
            if outfiles:
                print("First few output files:")
                for file in outfiles[:5]:
                    print(file)
        except SSMLProcessingError as e:
            print(f"Error processing SSML: {str(e)}")
        except Exception as e:
            print(f"Unexpected error: {str(e)}")