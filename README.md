# tessOCR_scanner
OCR Scanner webapp, using the Tesseract OCR engine.

1. Install required packages and libraries. <br>
`$ pip install pytesseract` <br>
`$ pip install pyzmq` <br>
`$ npm install` <br>
(libzmq is required, check https://github.com/zeromq/libzmq for details)

2. Open a terminal window and start the NodeJS server with `$ node server.js` 

3. Open another terminal window and start the image preprocessing process with `$ python3 preprocess-server.py` 

4. Navigate your browser to 
http://localhost:4630/

5. Upload an image.
