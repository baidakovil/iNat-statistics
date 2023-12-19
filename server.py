from flask import Flask, request, send_from_directory, render_template
from werkzeug.utils import secure_filename
import os
from inat_changes import main

app = Flask(__name__)


@app.route('/upload', methods=['POST'])
def upload_file():
    print('Go to upload_file()')
    file = request.files['file']
    filename = secure_filename(file.filename)
    file.save(os.path.join('.', filename))
    main(filename)  # Run your script here
    return 'changes.html'


@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    return send_from_directory('.', filename)
    # return send_from_directory('.', 'IB.pdf')


@app.route("/")
def home():
    return render_template('index.html')


if __name__ == '__main__':
    print('Server started')
    app.run(port=5000)
