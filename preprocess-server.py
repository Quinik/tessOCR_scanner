import os
import json
import math
import time

import zmq
import cv2 as cv
from skimage.filters import threshold_local
import numpy as np
import imutils
import pytesseract as tess

import preprocess_fn as pre

with open('./config.json') as f:
    config = json.load(f)

inbetween_writes = config['step_by_step_imwrite']
timing_verbosity = config['timing_verbosity']
req_nr = 0

context = zmq.Context()
socket = context.socket(zmq.REP)
zmq_port = config['zmqPort']
address = 'tcp://*:' + zmq_port

socket.bind(address)
print('Server started')
print('Binded to ' + address)

while True:
    # wait for next REQUEST from client
    message = socket.recv_json()
    t1_preprocess = cv.getTickCount()
    req_nr += 1
    print('=-----------------------Got request no.' + str(req_nr) + '---------------------------------------------------=')
    print('Recieved message: %s' % message)
    print('Recieved image: ', message['filename'])

    #path setup
    img_filename = message['filename']
    img_name = os.path.splitext(img_filename)[0]
    img_ext = os.path.splitext(img_filename)[1]
    img_input_path = config['path']['input_dir'] + img_name + img_ext
    img_output_path = config['path']['output_dir'] + os.path.splitext(message['filename'])[0] + '/' + os.path.splitext(message['filename'])[0] + '-done' + os.path.splitext(message['filename'])[1]

    #PREPROCESSING
    # step 0: reading the input image
    print('Reading image from', img_input_path)
    img = cv.imread(img_input_path, cv.IMREAD_COLOR)

    # step 1: resize
    height = config['preprocess']['resize']['height']
    img_resized = pre.resize(img, height)
    img_resized_copy = img_resized.copy()

    if(inbetween_writes):
        pre.write_image(img_resized, img_filename, '-resized-h' + str(height) + 'px')

    # step 2: grayscale
    img_gray = pre.grayscale(img_resized)

    if(inbetween_writes):
        pre.write_image(img_gray, img_filename, '-grayscaled')

    # step 3: gaussian blur
    kernel_size = config['preprocess']['gaussian_blur']['kernel_size']
    img_gaussian_blurred = pre.gaussian_blur(img_gray, kernel_size)

    if(inbetween_writes):
        pre.write_image(img_gaussian_blurred, img_filename, '-gaussBlur-ksize' + str(kernel_size))

    # step 4. canny edge detection
    lower = config['preprocess']['canny_edge']['lower']
    upper = config['preprocess']['canny_edge']['upper']
    img_edged = pre.canny_edge(img_gaussian_blurred, lower, upper)

    if(inbetween_writes):
        pre.write_image(img_edged, img_filename, '-edged-lower' + str(lower) + '-upper' + str(upper))

    # step 4.1: auto canny edge detection 
    #   write_image is called in auto_canny_edge function
    sigma = config['preprocess']['auto_canny_edge']['sigma']
    img_auto_edged = pre.auto_canny_edge(img_gaussian_blurred, img_filename, sigma)

    # step 5: contour grabbing
    img_contourapprox, final_contour = pre.contouring(img_auto_edged, img_resized)

    if(inbetween_writes):
        pre.write_image(img_contourapprox, img_filename, '-cnt')

    # step 6: perspective transformation
    img_perspective_warped = pre.warp_transform(img_resized_copy, final_contour)

    if(inbetween_writes):
        pre.write_image(img_perspective_warped, img_filename, '-warped')

    # step 7: thresholding/image binarization
    blocksize = config['preprocess']['threshold']['blocksize']
    method = config['preprocess']['threshold']['method']
    offset = config['preprocess']['threshold']['offset']
    _, img_thresholded = pre.thresholding(img_perspective_warped, blocksize, method, offset)

    descriptor_threshold = '-threshold' + '-bsize' + str(blocksize) + '-method_' + method + '-offset' + str(offset)
    if(inbetween_writes):
        pre.write_image(img_thresholded, img_filename, descriptor_threshold)
    
    # step 8: write final pre-processed image to disk
    pre.write_image(img_thresholded, img_filename, '-done')

    t2_preprocess = cv.getTickCount()
    preprocess_exec_time = (t2_preprocess - t1_preprocess) / cv.getTickFrequency()

    if timing_verbosity:
        print('\nPreprocess execution time ' + str(preprocess_exec_time) + ' seconds')

    # OPTICAL CHARACTER RECONGITION
    t1_ocr = cv.getTickCount()
    
    # step 1: convert image to RGB for Tesseract
    img_rgb = cv.cvtColor(img_thresholded, cv.COLOR_GRAY2RGB)

    # step 2: set OCR configuration parameters
    ocr_verbosity = config['ocr_verbosity']
    lang = config['ocr']['lang']
    oem = config['ocr']['ocr_engine_modes']
    psm = config['ocr']['page_segmentation_method']
    userwords = config['ocr']['user-words']
    configfile = config['ocr']['configfile']
    oem_psm_config = r'--oem ' + oem + ' --psm ' + psm + ' ' + configfile

    if ocr_verbosity :
        print('\tOCR config: ' + oem_psm_config)
    
    # step 3: OCR with Tesseract
    ocr_output_str = tess.image_to_string(img_rgb, lang=lang, config=oem_psm_config)
    
    # step 4: export OCR output to JSON
    print(ocr_output_str)
    ocr_output = {
        "res_str": ocr_output_str,
        "src_img_path": img_output_path
    }

    # step 5: writing JSON output to disk
    ocr_output_path = config['path']['output_dir'] + img_name + '/' + img_name + '.json'
    with open(ocr_output_path, 'w') as write_file:
        json.dump(ocr_output, write_file)

    t2_ocr = cv.getTickCount()
    ocr_exec_time = (t2_ocr - t1_ocr) / cv.getTickFrequency()

    if timing_verbosity:
        print('\OCR execution time ' + str(ocr_exec_time) + ' seconds')
    
    # step 6: sending reply back to client/requester
    socket.send_json({
        'img_output_path': img_output_path,
        'pid': os.getpid(),
        'preprocess_exec_time': preprocess_exec_time,
        'ocr_exec_time': ocr_exec_time,
        'ocr_output': ocr_output
    })

    print('img output: ', img_output_path)
    print('=------------------Finished processing request no.' + str(req_nr) + '----------------------------------------=')