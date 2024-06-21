# textract_ssml_processor/forms.py

from flask_wtf import FlaskForm
from wtforms import StringField, FileField, SubmitField, SelectField, BooleanField
from wtforms.validators import DataRequired

class UploadForm(FlaskForm):
    file = FileField('OCR File', validators=[DataRequired()])
    output_file_name = StringField('Output File Name', validators=[DataRequired()])
    title = StringField('Title', validators=[DataRequired()])
    author = StringField('Author', validators=[DataRequired()])
    language = SelectField('Language', choices=[('english', 'English'),('latin', 'Latin'), ('greek', 'Greek'), ('middle_english', 'Middle English')])
    submit = SubmitField('Upload')
