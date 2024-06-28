# app.py
from flask import Blueprint, current_app, render_template, request, redirect, url_for, send_from_directory, flash
from werkzeug.utils import secure_filename
from .forms import UploadForm
from .utils import process_text_file, clean_ssml_tags, get_existing_files, get_cleaned_chunks, estimate_cost, process_ssml_chunks, estimate_total_cost
import os

bp = Blueprint('app', __name__)

@bp.route('/', methods=['GET', 'POST'])
def index():
    upload_form = UploadForm()
    if request.method == 'POST' and upload_form.validate_on_submit():
        files = request.files.getlist('files')
        title = upload_form.title.data
        author = upload_form.author.data
        language = upload_form.language.data
        
        # Save files and get their paths
        file_paths = []
        for file in files:
            filename = file.filename
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            file_paths.append(file_path)

        # Render confirmation template with cost estimates
        total_character_count, formatted_gpt_cost, formatted_polly_cost_generative, formatted_polly_cost_long_form = estimate_total_cost(file_paths)
        formatted_gpt_cost = f"${formatted_gpt_cost:.2f}"
        formatted_polly_cost_generative = f"${formatted_polly_cost_generative:.2f}"
        formatted_polly_cost_long_form = f"${formatted_polly_cost_long_form:.2f}"
        return render_template('confirm.html', 
                               character_count=total_character_count,
                               gpt_cost=formatted_gpt_cost,
                               polly_cost_generative=formatted_polly_cost_generative,
                               polly_cost_long_form=formatted_polly_cost_long_form,
                               files=file_paths,
                               title=title,
                               author=author,
                               language=language)
    
    processed_files = get_existing_files(current_app.config['PROCESSED_FOLDER'])
    chunk_files = get_existing_files(current_app.config['CHUNKS_FOLDER'])
    chunks_folder = current_app.config['CHUNKS_FOLDER']

    return render_template('index.html', 
                           upload_form=upload_form, 
                           processed_files=processed_files, 
                           chunk_files=chunk_files,
                           chunks_folder=chunks_folder,
                           get_cleaned_chunks=get_cleaned_chunks,
                           enumerate=enumerate)

@bp.route('/confirm', methods=['POST'])
def confirm():
    files = request.form.getlist('files')
    title = request.form['title']
    author = request.form['author']
    language = request.form['language']
    
    for file_path in files:
        output_file_name = f"processed_{os.path.basename(file_path)}"
        process_text_file(file_path, output_file_name, title, author, language)
    
    flash("All files have been processed successfully!")
    return redirect(url_for('app.index'))

@bp.app_template_filter('basename')
def basename_filter(path):
    return os.path.basename(path)

@bp.route('/clean/<filename>', methods=['POST'])
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
    folder = current_app.config['PROCESSED_FOLDER']
    return send_from_directory(folder, filename)

@bp.route('/delete_processed/<filename>', methods=['POST'])
def delete_processed(filename):
    file_path = os.path.join(current_app.config['PROCESSED_FOLDER'], filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    return redirect(url_for('app.index'))

@bp.route('/delete_chunk/<filename>', methods=['POST'])
def delete_chunk(filename):
    file_path = os.path.join(current_app.config['CHUNKS_FOLDER'], filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    return redirect(url_for('app.index'))
