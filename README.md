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

## AWS Credentials for Amazon Polly

The application uses Amazon Polly to generate audio. Boto3 looks for AWS
credentials in your environment or the AWS configuration files. You can
provide them in one of two ways:

1. Export the following environment variables:
   ```bash
   export AWS_ACCESS_KEY_ID=your_access_key
   export AWS_SECRET_ACCESS_KEY=your_secret_key
   # export AWS_SESSION_TOKEN=your_session_token  # if using temporary credentials
   ```
2. Or configure the AWS CLI which creates `~/.aws/credentials`:
   ```bash
   aws configure
   ```

Ensure the credentials have permission to use the Polly `SynthesizeSpeech` API.

## ImageMagick and ffmpeg

The audio and video utilities depend on ImageMagick and `ffmpeg`. Install them
with your system package manager:

- **Ubuntu/Debian**
  ```bash
  sudo apt-get install imagemagick ffmpeg
  ```
- **macOS (Homebrew)**
  ```bash
  brew install imagemagick ffmpeg
  ```

MoviePy needs the path to the `magick` executable. Instead of editing
`pipeline_support/audio_processing.py` to set a hard-coded path, define the
`IMAGEMAGICK_BINARY` environment variable:

```bash
export IMAGEMAGICK_BINARY=/path/to/magick
```

This variable will be picked up at runtime and used by MoviePy.

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
