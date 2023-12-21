"""This module creates Flask app instanse -  WSGI application. Connect HTML to python"""
import logging
from typing import Union

from flask import Flask, Response, render_template, request, send_file
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from inat_changes import main
from services.logger import logger

app = Flask(__name__)


@app.route('/', methods=['POST'])
def upload_file() -> Union[Response, str]:
    """Takes POST requests."""
    logger.info('Receive POST request')
    file = request.files['file']
    start_date = (
        request.form.get('start_date') if 'use_min_date' not in request.form else 'min'
    )
    finish_date = (
        request.form.get('finish_date') if 'use_max_date' not in request.form else 'max'
    )
    show_positions = (
        request.form.get('show_positions')
        if 'use_show_all' not in request.form
        else 'all'
    )
    project_id = request.form.get('project_id')
    if (
        isinstance(file, FileStorage)
        and isinstance(file.filename, str)
        and isinstance(start_date, str)
        and isinstance(finish_date, str)
        and isinstance(show_positions, str)
    ):
        project_id = '' if not project_id else project_id
        filename = secure_filename(file.filename)
        file.save(filename)
        main(filename, start_date, finish_date, show_positions, project_id)
        return send_file('changes.html', as_attachment=True)
    return "<p>Sorry, some input data are wrong!</p>"


@app.route("/", methods=['GET'])
def home() -> str:
    """Takes GET requests."""
    logger.info('Receive GET request')
    return render_template('index.html')


logger = logging.getLogger('A.ina')
logger.setLevel(logging.DEBUG)

if __name__ == '__main__':
    logger.info('Server started')
    app.run()
