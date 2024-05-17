# textract_ssml_processor/app.py

from flask import Blueprint, current_app, render_template, request, redirect, url_for, send_from_directory
from .forms import UploadForm
from .utils import process_text_file, process_ssml_chunks, clean_ssml_tags, get_existing_files, get_cleaned_chunks
import os

bp = Blueprint('app', __name__)

@bp.route('/', methods=['GET', 'POST'])
def index():
    upload_form = UploadForm()
    if upload_form.validate_on_submit():
        file = upload_form.file.data
        output_file_name = upload_form.output_file_name.data
        upload_file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], file.filename)
        file.save(upload_file_path)
        
        # Process the file and save the output with the specified name in the processed folder
        processed_file_path = process_text_file(upload_file_path, output_file_name)
        
        # Remove the original uploaded file
        if os.path.exists(upload_file_path):
            os.remove(upload_file_path)
        
        # Redirect to refresh the page with updated files
        return redirect(url_for('app.index'))

    processed_files = get_existing_files(current_app.config['PROCESSED_FOLDER'])
    chunk_files = get_existing_files(current_app.config['CHUNKS_FOLDER'])
    processed_folder = current_app.config['PROCESSED_FOLDER']
    chunks_folder = current_app.config['CHUNKS_FOLDER']

    return render_template('index.html', 
                           upload_form=upload_form, 
                           processed_files=processed_files, 
                           chunk_files=chunk_files,
                           processed_folder=processed_folder,
                           chunks_folder=chunks_folder,
                           get_cleaned_chunks=get_cleaned_chunks,
                           enumerate=enumerate)

@bp.route('/clean/<filename>', methods=['GET', 'POST'])
def clean(filename):
    processed_folder = current_app.config['PROCESSED_FOLDER']
    chunks_folder = current_app.config['CHUNKS_FOLDER']
    file_path = os.path.join(processed_folder, filename)
    chunked_files = process_ssml_chunks(file_path, chunks_folder)
    for chunk_file in chunked_files:
        clean_ssml_tags(os.path.join(chunks_folder, chunk_file))

    return redirect(url_for('app.index'))

@bp.route('/download/<filename>', methods=['GET'])
def download(filename):
    folder = current_app.config['CHUNKS_FOLDER']
    print(f"Downloading {filename} from {folder}")  # Debug statement
    return send_from_directory(folder, filename)
