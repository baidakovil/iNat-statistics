document.querySelector('input[type="file"]').addEventListener('change', function() {
    var formData = new FormData();
    formData.append('file', this.files[0]);

    axios.post('/upload', formData, {
        headers: {
            'Content-Type': 'multipart/form-data'
        }
    }).then(function(response) {
        var link = document.createElement('a');
        link.href = '/download/' + response.data;
        link.click();
    }).catch(function(error) {
        console.log(error);
    });
});
