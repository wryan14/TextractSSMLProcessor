from flask import Blueprint, current_app, render_template, request, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename
from .forms import UploadForm
from .utils import handle_uploaded_file, get_existing_files, estimate_total_cost# , process_ssml_chunks, preprocess_ssml_tags, clean_ssml_tags
import os
import json
import logging
from logging.handlers import RotatingFileHandler

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create a file handler that logs even debug messages
file_handler = RotatingFileHandler('app.log', maxBytes=10240, backupCount=10)
file_handler.setLevel(logging.DEBUG)

# Create a console handler with a higher log level
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Create a formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Add the handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

bp = Blueprint('app', __name__)

@bp.route('/', methods=['GET', 'POST'])
def index():
    upload_form = UploadForm()
    if request.method == 'POST' and upload_form.validate_on_submit():
        files = request.files.getlist('files')
        title = upload_form.title.data
        author = upload_form.author.data
        language = upload_form.language.data
        
        logger.info(f"Received upload request: Title: {title}, Author: {author}, Language: {language}")
        
        # Save files temporarily and get their paths
        file_paths = []
        for file in files:
            filename = secure_filename(file.filename)
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            file_paths.append(file_path)
            logger.debug(f"Saved file: {file_path}")

        # Calculate cost estimate
        total_character_count, gpt_cost, polly_cost_generative, polly_cost_long_form = estimate_total_cost(file_paths)
        
        logger.info(f"Cost estimate: Characters: {total_character_count}, GPT: ${gpt_cost:.2f}, Polly Gen: ${polly_cost_generative:.2f}, Polly LF: ${polly_cost_long_form:.2f}")
        
        # Render confirmation template with cost estimates
        return render_template('confirm.html', 
                               character_count=total_character_count,
                               gpt_cost=f"${gpt_cost:.2f}",
                               polly_cost_generative=f"${polly_cost_generative:.2f}",
                               polly_cost_long_form=f"${polly_cost_long_form:.2f}",
                               files=file_paths,
                               title=title,
                               author=author,
                               language=language)
    
    processed_files = get_existing_files(current_app.config['PROCESSED_FOLDER'])
    return render_template('index.html', 
                           upload_form=upload_form, 
                           processed_files=processed_files)

@bp.route('/confirm', methods=['POST'])
def confirm():
    logger.info("Confirm route accessed")
    try:
        files = request.form.getlist('files')
        title = request.form.get('title')
        author = request.form.get('author')
        language = request.form.get('language')
        
        logger.info(f"Received data: files={files}, title={title}, author={author}, language={language}")
        
        if not files:
            logger.error("No files received in the request")
            flash("No files were selected for processing.", 'error')
            return redirect(url_for('app.index'))

        processed_files = []
        for file_path in files:
            logger.info(f"Processing file: {file_path}")
            if os.path.exists(file_path):
                try:
                    output_json_path = handle_uploaded_file(file_path, title, author, language)
                    processed_files.append(os.path.basename(output_json_path))
                    logger.info(f"File processed successfully: {output_json_path}")
                    os.remove(file_path)  # Remove the temporary file
                except Exception as e:
                    logger.error(f"Error processing file {file_path}: {str(e)}", exc_info=True)
                    flash(f"Error processing file {os.path.basename(file_path)}: {str(e)}", 'error')
            else:
                logger.warning(f"File not found: {file_path}")
                flash(f"File {file_path} not found. It may have been deleted.", 'warning')
        
        if processed_files:
            flash("All files have been processed successfully!", 'success')
        else:
            flash("No files were processed. Please try uploading again.", 'warning')
        
        logger.info("Redirecting to index page")
        return redirect(url_for('app.index'))
    
    except Exception as e:
        logger.error(f"Unexpected error in confirm route: {str(e)}", exc_info=True)
        flash(f"An unexpected error occurred: {str(e)}", 'error')
        return redirect(url_for('app.index'))

@bp.route('/view_json/<filename>', methods=['GET', 'POST'])
def view_json(filename):
    processed_folder = current_app.config['PROCESSED_FOLDER']
    json_path = os.path.join(processed_folder, filename)
    
    # Get list of all JSON files and current file's position
    json_files = sorted([f for f in os.listdir(processed_folder) if f.endswith('.json')])
    current_index = json_files.index(filename)
    total_files = len(json_files)
    
    # Get previous and next file names (if they exist)
    prev_file = json_files[current_index - 1] if current_index > 0 else None
    next_file = json_files[current_index + 1] if current_index < total_files - 1 else None
    
    try:
        if request.method == 'POST':
            # Handle the save operation
            updated_data = request.json
            with open(json_path, 'w', encoding='utf-8') as json_file:
                json.dump(updated_data, json_file, ensure_ascii=False, indent=2)
            flash('Changes saved successfully!', 'success')
            return jsonify({"message": "Changes saved successfully"}), 200
        else:
            # GET request - load and display the JSON
            with open(json_path, 'r', encoding='utf-8') as json_file:
                data = json.load(json_file)
            logger.debug(f"JSON file viewed: {filename}")
            return render_template('view_json.html', 
                                data=data, 
                                filename=filename,
                                prev_file=prev_file,
                                next_file=next_file,
                                current_file_number=current_index + 1,
                                total_files=total_files)
    except Exception as e:
        logger.error(f"Error processing JSON file {filename}: {str(e)}", exc_info=True)
        flash(f"Error processing JSON file: {str(e)}", 'error')
        return redirect(url_for('app.index'))

@bp.route('/delete_processed/<filename>', methods=['POST'])
def delete_processed(filename):
    file_path = os.path.join(current_app.config['PROCESSED_FOLDER'], filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        logger.info(f"Deleted file: {filename}")
        flash(f"File {filename} has been deleted.")
    else:
        logger.warning(f"File not found for deletion: {filename}")
        flash(f"File {filename} not found.")
    return redirect(url_for('app.index'))

# @bp.route('/clean/<filename>', methods=['POST'])
# def clean(filename):
#     logger.info(f"Cleaning file: {filename}")
#     processed_folder = current_app.config['PROCESSED_FOLDER']
#     file_path = os.path.join(processed_folder, filename)
    
#     try:
#         with open(file_path, 'r', encoding='utf-8') as file:
#             content = json.load(file)
        
#         cleaned_chunks = []
#         for chunk in content['chunks']:
#             original_latin = chunk['original_latin']
#             translated_english = chunk['translated_english']
            
#             # Clean both original Latin and translated English
#             cleaned_latin = clean_ssml_tags(preprocess_ssml_tags(original_latin))
#             cleaned_english = clean_ssml_tags(preprocess_ssml_tags(translated_english))
            
#             cleaned_chunks.append({
#                 "chunk_number": chunk['chunk_number'],
#                 "original_latin": cleaned_latin,
#                 "translated_english": cleaned_english
#             })
        
#         content['chunks'] = cleaned_chunks
        
#         # Save the cleaned content back to the file
#         with open(file_path, 'w', encoding='utf-8') as file:
#             json.dump(content, file, ensure_ascii=False, indent=2)
        
#         logger.info(f"File cleaned successfully: {filename}")
#         flash(f"File {filename} has been cleaned successfully.")
#     except Exception as e:
#         logger.error(f"Error cleaning file {filename}: {str(e)}", exc_info=True)
#         flash(f"Error cleaning file {filename}: {str(e)}")
    
#     return redirect(url_for('app.index'))