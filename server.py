from flask import Flask, request, send_file, render_template
from werkzeug.utils import secure_filename
from inat_changes import main

app = Flask(__name__)


@app.route('/', methods=['POST'])
def upload_file():
    if request.method == 'POST':
        file = request.files['file']

        start_date = (
            request.form.get('start_date')
            if 'use_min_date' not in request.form
            else 'min'
        )
        finish_date = (
            request.form.get('finish_date')
            if 'use_max_date' not in request.form
            else 'max'
        )

        show_positions = (
            request.form.get('show_positions')
            if 'use_show_all' not in request.form
            else 'all'
        )

        project_id = request.form.get('project_id')
        filename = secure_filename(file.filename)
        file.save(filename)
        main(filename, start_date, finish_date, show_positions, project_id)
        return send_file('changes.html', as_attachment=True)


@app.route("/", methods=['GET'])
def home():
    return render_template('index.html')


if __name__ == '__main__':
    print('Server started')
    app.run(port=5000)
