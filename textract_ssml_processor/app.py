from flask import Blueprint, current_app, render_template, request, redirect, url_for, send_from_directory, flash
from werkzeug.utils import secure_filename
from .forms import UploadForm
from .utils import process_text_file, clean_ssml_tags, get_existing_files, get_cleaned_chunks, estimate_cost, process_ssml_chunks
import os

bp = Blueprint('app', __name__)

@bp.route('/', methods=['GET', 'POST'])
def index():
    upload_form = UploadForm()
    if upload_form.validate_on_submit():
        file = upload_form.file.data
        output_file_name = upload_form.output_file_name.data
        title = upload_form.title.data
        author = upload_form.author.data
        language = upload_form.language.data
        upload_file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
        file.save(upload_file_path)

        # Estimate cost
        character_count, gpt_cost, polly_cost_generative, polly_cost_long_form = estimate_cost(upload_file_path)
        
        formatted_gpt_cost = f"${gpt_cost:.2f}"
        formatted_polly_cost_generative = f"${polly_cost_generative:.2f}"
        formatted_polly_cost_long_form = f"${polly_cost_long_form:.2f}"
        
        flash(f"Estimated cost: GPT-4: {formatted_gpt_cost}, Polly Generative: {formatted_polly_cost_generative}, Polly Long-Form: {formatted_polly_cost_long_form}")
        
        return render_template('confirm.html', 
                               character_count=character_count,
                               gpt_cost=formatted_gpt_cost,
                               polly_cost_generative=formatted_polly_cost_generative,
                               polly_cost_long_form=formatted_polly_cost_long_form,
                               upload_file_name=file.filename,
                               output_file_name=output_file_name,
                               title=title,
                               author=author,
                               language=language,
                               )
        
    processed_files = get_existing_files(current_app.config['PROCESSED_FOLDER'])
    chunk_files = get_existing_files(current_app.config['CHUNKS_FOLDER'])
    chunks_folder = current_app.config['CHUNKS_FOLDER']

    return render_template('index.html', 
                           upload_form=upload_form, 
                           processed_files=processed_files, 
                           chunk_files=chunk_files,
                           chunks_folder=chunks_folder,  # Ensure chunks_folder is passed to the template
                           get_cleaned_chunks=get_cleaned_chunks,
                           enumerate=enumerate)

@bp.route('/confirm', methods=['POST'])
def confirm():
    upload_file_name = request.form['upload_file_name']
    output_file_name = request.form['output_file_name']
    title = request.form.get('title', '')
    author = request.form.get('author', '')
    language = request.form.get('language', 'latin')
    upload_file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], upload_file_name)

    # Process the file and save the output with the specified name in the processed folder
    processed_file_paths = process_text_file(upload_file_path, output_file_name, title, author, language)

    # Remove the original uploaded file
    # if os.path.exists(upload_file_path):
    #     os.remove(upload_file_path)

    return redirect(url_for('app.index'))

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
