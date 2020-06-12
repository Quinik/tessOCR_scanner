const port = '4630';
const address = 'http://localhost:' + port;

const socket = io.connect(address);
const uploader = new SocketIOFileUpload(socket);

//querying the DOM
let progressBar = document.getElementById('upload_progress_bar');
let progressBarContainer = document.getElementById('upload_progress_bar_container');
let resultArea = document.getElementById('ocr_output')

//setting the initial width of the progressBar
progressBar.style.width = 0 + '%';
let chunkCount = 0;

//configuring the ways of file upload
// 1. upload button
document.getElementById("upload_btn").addEventListener("click", uploader.prompt, false);

// 2. file drop area
uploader.listenOnDrop(document.getElementById("file_drop"));

//tracking upload progress
uploader.addEventListener('progress', function(event){
    let percent = event.bytesLoaded / event.file.size * 100;
    console.log("File is", percent.toFixed(2), "percent uploaded");

    progressBar.style.width = percent + '%';
    progressBar.innerHTML = 'Progress:' + percent.toFixed(2) + '%';
    chunkCount += 1;

    if(percent == 100){
        progressBar.innerHTML = 'upload complete; transferred in ' + chunkCount + ' chunks.';
    }
});

// logging to the console that the file is successfully uploaded
uploader.addEventListener('complete', function(event) {
    console.log("Success: ", event.success);
    console.log("file: ", event.file);
});

// displaying the OCR result and total processing time 
socket.on('ocr_done', (data) => {
    response = JSON.parse(data);
    progressBarContainer.innerHTML += '<h3>' + response.message + '</h3>';

    //building HTML list from OCR output
    lines = response.ocr_output.split('\n');
    HTML_list = '<ol>';
    lines.forEach(element => {
        HTML_list+= '<li>' + element + '</li>';
    });
    HTML_list += '</ol>'

    //displaying the list
    resultArea.innerHTML = HTML_list;
});