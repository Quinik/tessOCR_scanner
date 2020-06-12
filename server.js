'use strict';

//ZMQ is installed with: $ npm install zeromq@6.0.0-beta.5
//more info at: https://www.npmjs.com/package/zeromq
const zmq = require('zeromq/v5-compat');
const fs = require('fs');
const socketio = require('socket.io');
const SocketIOFileUpload = require('socketio-file-upload');
const express = require('express');
const path = require('path');

//loading local config JSON file
let raw_json = fs.readFileSync(__dirname + '/config.json');
let config = JSON.parse(raw_json);
const expressPort = config.expressPort

//creating express server and setting up middleware
const app = express();

app.use(SocketIOFileUpload.router);
app.use(express.static(__dirname + '/public'));
const server = app.listen(expressPort, function() {
    console.log('Express is listening on port ' + expressPort);
});

//Socket-IO setup
const io = socketio.listen(server);

io.sockets.on('connection', (socket) => {
    console.log('socket connection established, id: ' + socket.id);

    //make an instance of socketiofileupload and listen on this socket
    const uploader = new SocketIOFileUpload();
    uploader.dir = config.path.input_dir;   //the client's input files will be uploaded to this directory
    uploader.listen(socket);

    uploader.on('saved', (event) => {
        console.log(event.file.name + ' has been uploaded ---> ' + event.file.pathName);

        //sending signal to preprocess/ocr script with ZMQ
        console.log('Requester (pid ' + process.pid + ') is sending REQUEST on ' + address + ' [file pathName: ' + event.file.pathName + ']\n');

        //defining the message
        let data = JSON.stringify({
            pid: process.pid,
            filename: path.basename(event.file.pathName),
            filesize: event.file.size,
            socketio_socket_id: socket.id
        });

        //sending the message
        requester.send(data);
    });

    uploader.on('error', (event) => {
        console.log('Error from uploader', event);
    });

});


//zmq setup
const requester = zmq.socket('req');
const zmqPort = config.zmqPort;
const address = 'tcp://localhost:' + zmqPort;

let filename = process.argv[2] || config.default_input_filename;

//connect to predefined address
//CONNECT
requester.connect(address);

//make it verbose
console.log('Connected to ' + address);
console.log('Process id: ' + process.pid);
console.log('======================================');

//when getting a reply from preprocess+OCR script, run this code
requester.on('message', (data) => {
    let response = JSON.parse(data);

    console.log('Received response from ' + response.pid);
    console.log(response.img_output_path);
    console.log('Preprocess done in ' + response.preprocess_exec_time.toFixed(3) + 'sec');
    console.log('OCR done in ' + response.ocr_exec_time.toFixed(3) + 'sec');

    let totalExecTime = (parseFloat(response.preprocess_exec_time) + parseFloat(response.ocr_exec_time)).toFixed(3);

    let replyData = JSON.stringify({
        message: 'PREPROCESS + OCR done in ' + totalExecTime + ' seconds',
        ocr_output: response.ocr_output.res_str
    });

    //send message back to client-side, signaling that OCR is done
    console.log('Sending message back to clientside');
    io.emit('ocr_done', replyData);
});