# TextractSSMLProcessor

TextractSSMLProcessor is a Flask-based web application that processes text files using OpenAI's gpt-4o and Amazon Polly. The application performs OCR text processing, formats the text with SSML tags, and cleans up the resulting SSML for text-to-speech conversion.

## Features

1. **Upload OCR Text Files**: Upload text files for processing.
2. **Send Text to OpenAI**: Process the uploaded text using OpenAI gpt-4o to format it with SSML tags.
3. **Clean and Chunk SSML**: Clean the SSML tags and chunk the text for efficient processing.
4. **Estimate Costs**: Estimate the processing costs for OpenAI gpt-4o and Amazon Polly.
5. **Manage Processed Files**: View and manage processed files, including the ability to download or delete them.

## Prerequisites

- Python 3.8+
- Anaconda (recommended for managing dependencies)
- OpenAI API key
- Flask

## Installation

1. **Clone the repository**:
    ```bash
    git clone https://github.com/yourusername/TextractSSMLProcessor.git
    cd TextractSSMLProcessor
    ```

2. **Create a Conda environment**:
    ```bash
    conda create -n textract_ssml_processor python=3.8
    conda activate textract_ssml_processor
    ```

3. **Install the required packages**:
    ```bash
    pip install -r requirements.txt
    ```

4. **Set up environment variables**:
    Create a `.env` file in the root directory and add your OpenAI API key:
    ```env
    OPENAI_API_KEY=your_openai_api_key
    ```

5. **Run the application**:
    ```bash
    flask run
    ```

## Usage

1. **Upload File**: Click on "Choose File" to upload a text file. Provide an output file name and submit to process the text with OpenAI gpt-4o.
2. **View Processed Files**: Once the text is processed, it will appear in the "Processed Files" table. Click "Clean" to clean the SSML tags and chunk the text.
3. **Manage Chunks**: The cleaned and chunked files will appear in the "Chunked Files" table. You can download or delete these files as needed.
4. **Estimate Costs**: After uploading a file, the estimated costs for processing with OpenAI gpt-4o and Amazon Polly will be displayed. Confirm if you want to proceed with the processing.

## Folder Structure

```plaintext
TextractSSMLProcessor/
│
├── textract_ssml_processor/
│   ├── __init__.py
│   ├── app.py
│   ├── utils.py
│   └── templates/
│       ├── base.html
│       ├── index.html
│       ├── confirm.html
│       ├── view_json.html
│       ├── create_timestamps.html
│       └── timestamp_result.html
│
├── uploads/
├── processed/
├── chunks/
├── .env
├── requirements.txt
└── README.md

## Workflow Overview

1. **Upload text through the web interface**
   - Start the application:
     ```bash
     python run.py
     ```
   - Use the browser to upload your text files. Each upload is sent to GPT-4o for cleanup and SSML tagging. The resulting JSON files are saved in `processed/`.

2. **Generate audio with Amazon Polly**
   - Edit `pipeline_support/ssml_processing.py` to point `input_directory` to `processed/` and `output_directory` to the folder where MP3 files should be created.
   - Run the script:
     ```bash
     python pipeline_support/ssml_processing.py
     ```
   - The script synthesizes each SSML chunk to an MP3 file.

3. **Create subtitle files**
   - Once audio files are available, create SRT subtitles using the timestamp blueprint:
     ```bash
     python -m textract_ssml_processor.timestamp
     ```
   - Subtitles are written to the `subtitles/` directory.

4. **Optional video generation**
   - `pipeline_support/audio_processing.py` can combine audio and subtitles into a simple video:
     ```bash
     python pipeline_support/audio_processing.py
     ```
   - Edit the script variables to reference your MP3 and SRT files. The output MP4 is saved to the location specified in the script.

## pipeline_support scripts

- **audio_processing.py** – utilities for merging MP3 files, adding metadata, and creating videos with subtitles.
- **file_processing.py** – strips SSML tags and copies cleaned text files.
- **ssml_processing.py** – converts SSML chunks in JSON files into MP3 using Amazon Polly.
- **ssml_validator.py** – runs a suite of checks for SSML formatting problems.
- **text_processing.py** – removes notes and splits input text into manageable sections.
