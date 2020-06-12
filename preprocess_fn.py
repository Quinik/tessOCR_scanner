import os
import math
import json

import cv2 as cv
import imutils
from skimage.filters import threshold_local
import numpy as np

with open('./config.json') as f:
    config = json.load(f)

preprocess_verbosity = config['preprocess_verbosity']
write_verbosity = config['write_verbosity']
inbetween_writes = config['step_by_step_imwrite']

def calc_distance(p1, p2):
    # dist = sqrt( (x2-x1)^2 + (y2-y1)^2 )
    distance = math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
    return distance

def write_image(img, filename, descriptor_str):
    if write_verbosity:
        print('\ninput_filename:', filename)
        print('descriptor_str:', descriptor_str)

    # getting extension and path+filename
    name = os.path.splitext(filename)[0]
    ext = os.path.splitext(filename)[1]

    # building output path
    id_dir = name + '/'
    path_out = config['path']['output_dir'] + id_dir + name + descriptor_str + ext

    #checking if directory exists, if not create it
    if os.path.exists(config['path']['output_dir'] + id_dir):
        if write_verbosity: 
            print('path ' + config['path']['output_dir'] + id_dir + ' exists')
    else:
        if write_verbosity:
            print('creating ' + config['path']['output_dir'] + id_dir)
        os.mkdir(config['path']['output_dir'] + id_dir)

    # writing image to output directory
    if write_verbosity:
        print('saving ' + filename + ' -->', path_out)
    success = cv.imwrite(path_out, img)
    
    # checking if imwrite succeded
    if write_verbosity:
        if success:
            print('image ' + filename + ' saved to ' + path_out + '\n')
        else:
            print('valami nem jo\n')

# resizing the image for faster execution and better OCR performance
def resize(img, height):
    if preprocess_verbosity:
        print('\trescaling image...')
        print('\toriginal size:', img.shape)

    img_resized = imutils.resize(img, height=height)
    
    if preprocess_verbosity:
        print('\tresized size:', img_resized.shape)
    
    return img_resized

# grayscaling the image
def grayscale(img):
    if preprocess_verbosity:
        print('\tconverting image to grayscale')
    
    img = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
    
    return img

# blurring the image (needed for contour grabbing)
def gaussian_blur(img, kernel_size):
    if preprocess_verbosity:
        print('\tblurring image using Gaussian Blur, kernel size = ' + str(kernel_size))
    
    img = cv.GaussianBlur(img, (kernel_size, kernel_size), 0)
    
    return img

# Canny edge detection using static lower and upper threshold values
def canny_edge(img, lower, upper):
    if preprocess_verbosity:
        print('\tCanny edge detection, lower=' + str(lower) + ' upper=' + str(upper))
    
    img = cv.Canny(img, lower, upper)
    
    return img

# Canny edge detection using lower and upper threshold values calculated based on the intensity of pixel color
def auto_canny_edge(img, filename, sigma=0.33):
    # computing the median of the single channel pixel intensities
    median = np.median(img)

    # applying automatic Canny edge detection using the computed median
    lower = int(max(0, (1.0 - sigma) * median))
    upper = int(min(255, (1.0 + sigma) * median))
    img = cv.Canny(img, lower, upper)

    if(inbetween_writes):
        write_image(img, filename, '-autoedged-low' + str(lower) + '-up' + str(upper) + '-sigma' + str(int(sigma*100)))
    
    if preprocess_verbosity:
        print('\tAutomatic Canny edge detection, sigma=' + str(sigma) + ' lower=' + str(lower) + ' upper=' + str(upper) + ' median=' + str(v))
    return img

# getting the contour of the shape
def contouring(img, img_original):

    if (config['preprocess']['contour']['contour_find_mode'] == 'cv.RETR_LIST'):
        mode = cv.RETR_LIST

    if (config['preprocess']['contour']['contour_find_method'] == 'cv.CHAIN_APPROX_NONE'):
        method = cv.CHAIN_APPROX_NONE

    # finding every contour on the image
    contours = cv.findContours(img, mode, method)[0]
    
    if preprocess_verbosity:
        print('\tnumber of contours=' + str(len(contours)))
        print('\tsorting contours...')
    
    # sorting the contours based on area, the first contour in this array has the biggest area
    contours_sorted = sorted(contours, key=cv.contourArea, reverse=True)[:5] 

    for contour in contours_sorted:
        # trying to get an approximated contour from the found contour
        epsilon_coeff = config['preprocess']['contour']['epsilon_coeff']
        closed_contour = config['preprocess']['contour']['closed_contour']
        perimeter = cv.arcLength(contour, closed_contour)

        epsilon = perimeter * epsilon_coeff # maximum distance from contour to approximated contour
        if preprocess_verbosity:
            print('\tapproximating 4 point contour...')
            print('\tepsilon_coeff=' + str(epsilon_coeff) +
                ' EPSILON=' + str(epsilon))

        approx_contour = cv.approxPolyDP(contour, epsilon, True)

        # if approximated contour is defined by 4 points, we found the final contour
        if(len(approx_contour) == 4):
            final_contour = approx_contour
            if preprocess_verbosity:
                print('\tfinal contour found, coords(x,y):')
                print('\t\ttop-left: \t(' +
                    str(final_contour[0][0][0]) + ',' + str(final_contour[0][0][1]) + ')')
                print('\t\ttop-right: \t(' +
                    str(final_contour[3][0][0]) + ',' + str(final_contour[3][0][1]) + ')')
                print('\t\tbottom-left: \t(' +
                    str(final_contour[1][0][0]) + ',' + str(final_contour[1][0][1]) + ')')
                print('\t\tbottom-right: \t(' +
                    str(final_contour[2][0][0]) + ',' + str(final_contour[2][0][1]) + ')')
            break

    line_thickness = config['preprocess']['contour']['line_thickness']
    r = config['preprocess']['contour']['conrour_color']['r']
    g = config['preprocess']['contour']['conrour_color']['g']
    b = config['preprocess']['contour']['conrour_color']['b']
    img_contoured = cv.drawContours(img_original, [final_contour], -1, (r, g, b), line_thickness)
    # the contour is placed on the original picture, if we want to use img_scaled later we need a copy of it

    return img_contoured, final_contour

# warp transforming the image to get a topdown view of the shape
# using absolute distance between 2 points
def warp_transform(img, coords4point):

    img = cv.cvtColor(img, cv.COLOR_BGR2GRAY)

    # assign the 4 points defining the rectangle
    top_left = coords4point[0][0]
    top_right = coords4point[3][0]
    bottom_left = coords4point[1][0]
    bottom_right = coords4point[2][0]

    # nezzuk meg, mennyire sikerult teglalap alaku contour-t rajzolni
    # if coeff > 1 then: top-left corner TO bottom-right corner distance is the longer, else: vice-versa

    # calculate the deformity of the contour
    # if deform_coeff = 0, then the shape on the input image is a rectangle (photographed from perfect bird view)
    deform_coeff = calc_distance(
        top_left, bottom_right) / calc_distance(top_right, bottom_left)
    if preprocess_verbosity:
        print('\tdeform coeff of contour rectangle: ' + str(deform_coeff))

    # new width = maximum distance between bottom-right and bottom-left x-coords or the top-right and top-left x-coords
    width_bottom = calc_distance(bottom_left, bottom_right)
    width_top = calc_distance(top_left, top_right)
    if preprocess_verbosity:
        print('\twidth_top=' + str(width_top))
        print('\twidth_bottom=' + str(width_bottom))
        print('\t')
    max_width = max(int(width_top), int(width_bottom))

    # new height = maximum distance between the top-right and bottom-right y-coords or the top-left and bottom-left y-coords
    height_left = calc_distance(bottom_left, top_left)
    height_right = calc_distance(bottom_right, top_right)
    if preprocess_verbosity:
        print('\theight_left=' + str(height_left))
        print('\theight_right=' + str(height_right))
        print('')
    max_height = max(int(height_left), int(height_right))

    # create source rectangle(deformed)
    src_rect = np.array([
        top_left,
        top_right,
        bottom_left,
        bottom_right 
    ], dtype='float32')

    # create destination rectangle
    dest_rect = np.array([
        [0, 0],                     # top-left
        [max_width-1, 0],           # top-right
        [0, max_height - 1],        # bottom-left
        [max_width-1, max_height-1] # bottom-right
    ], dtype='float32')

    # compute perspective transform matrix and apply it to the image
    if preprocess_verbosity:
        print('\tcomputing perspective transform matrix...')
    perspective_transform_matrix = cv.getPerspectiveTransform(src_rect, dest_rect)

    if preprocess_verbosity:
        print('\tapplying perspective transform matrix...')
    img_warped = cv.warpPerspective(img, perspective_transform_matrix, (max_width, max_height))

    return img_warped

# thresholding/binarizing the image using skimage's threshold local
def thresholding(img, blocksize, method, offset):
    if preprocess_verbosity:
        print('\tthresholding image, block_size=' + str(blocksize) + ' method=' + method + ' offset=' + str(offset))
    img_thresholded = threshold_local(img, blocksize, method=method, offset=offset)

    img_cpy = img.copy()
    img_cpy = (img_cpy > img_thresholded).astype("uint8") * 255

    return img_thresholded, img_cpy