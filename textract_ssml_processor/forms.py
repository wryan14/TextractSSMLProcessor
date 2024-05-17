# textract_ssml_processor/forms.py

from flask_wtf import FlaskForm
from wtforms import FileField, StringField, SubmitField
from wtforms.validators import DataRequired

class UploadForm(FlaskForm):
    file = FileField('Upload OCR File', validators=[DataRequired()])
    output_file_name = StringField('Output File Name', validators=[DataRequired()])
    submit = SubmitField('Process')
