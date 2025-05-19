# forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, FileField, SubmitField
from wtforms.validators import DataRequired

class UploadForm(FlaskForm):
    language = StringField('Language', validators=[DataRequired()])
    files = FileField('Files', validators=[DataRequired()], render_kw={'multiple': True})
    submit = SubmitField('Upload')