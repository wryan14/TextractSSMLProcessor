from flask import Blueprint, current_app, render_template, request, redirect, url_for
from .forms import UploadForm, SSMLForm
from .utils import process_text_file, process_ssml_chunks, clean_ssml_tags
import os

bp = Blueprint('app', __name__)

@bp.route('/', methods=['GET', 'POST'])
def index():
    form = UploadForm()
    if form.validate_on_submit():
        file = form.file.data
        output_file_name = form.output_file_name.data
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], file.filename)
        file.save(file_path)
        processed_file_path = process_text_file(file_path, output_file_name)
        return redirect(url_for('app.process', filename=processed_file_path))
    return render_template('index.html', form=form)

@bp.route('/process/<filename>', methods=['GET', 'POST'])
def process(filename):
    form = SSMLForm()
    if request.method == 'POST':
        output_folder = request.form['output_folder']
        process_ssml_chunks(filename, output_folder)
        return redirect(url_for('app.clean', folder=output_folder))
    return render_template('process.html', filename=filename, form=form)

@bp.route('/clean/<folder>', methods=['GET', 'POST'])
def clean(folder):
    if request.method == 'POST':
        for filename in os.listdir(folder):
            file_path = os.path.join(folder, filename)
            clean_ssml_tags(file_path)
        return render_template('result.html', output_folder=folder)
    return render_template('clean.html', folder=folder)
