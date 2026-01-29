# -*- coding: utf-8 -*-
"""
Created on Mon Feb 24 11:10:54 2025

@author: jacob
"""

import cv2
import numpy as np

img1 = cv2.imread('wmnt3.png')
img2 = cv2.imread('wmnt2.png')
img3 = cv2.imread('wmnt1.png')

# init sift detector
sift = cv2.SIFT_create()

# both immages give keypoints(features) for 128 descriptor
# find key points and descriptors with sift
kp1, des1 = sift.detectAndCompute(img1,None)
kp2, des2 = sift.detectAndCompute(img2,None)
kp3, des3 = sift.detectAndCompute(img3,None)


# sanity check stuff that doesnt really matter
'''
cv2.imshow("img1", img1)
cv2.imshow('img2', img2)
cv2.imshow('img3', img3)
print(len(kp1))
print(des1.shape)
print(len(kp2))
print(des2.shape)
print(len(kp3))
print(des3.shape)
'''


# getting code from geeksforgeeks https://www.geeksforgeeks.org/feature-matching-in-opencv/
# and also openCV documantation :p https://docs.opencv.org/4.x/dc/dc3/tutorial_py_matcher.html

# making paramters for flann
# flan is alternate matcher, got better results than from brute force

FLANN_INDEX_KDTREE = 1
index_params = dict(algorithm = FLANN_INDEX_KDTREE, trees = 5)
search_params = dict(checks=50)   # or pass empty dictionary
 
flann = cv2.FlannBasedMatcher(index_params,search_params)
 
matches = flann.knnMatch(des1,des2,k=2)

 
# ratio test as per Lowe's paper
good = []
for m,n in matches:
    if m.distance < 0.7*n.distance:
        good.append(m)
        
# Need to draw only good matches, so create a mask
matchesMask = [[0,0] for i in range(len(matches))]
 
# ratio test as per Lowe's paper
for i,(m,n) in enumerate(matches):
    if m.distance < 0.6*n.distance:
        matchesMask[i]=[1,0]
 
draw_params = dict(matchColor = (0,255,0),
                   singlePointColor = (255,0,0),
                   matchesMask = matchesMask,
                   flags = cv2.DrawMatchesFlags_DEFAULT)
 
matchIMG = cv2.drawMatchesKnn(img1,kp1,img2,kp2,matches,None,**draw_params)
 
cv2.imshow("matches", matchIMG)


src_pts = np.float32([ kp1[m.queryIdx].pt for m in good ]).reshape(-1,1,2)
dst_pts = np.float32([ kp2[m.trainIdx].pt for m in good ]).reshape(-1,1,2)
 
matrix, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC,5.0)

dst = cv2.warpPerspective(img1, matrix, ((img1.shape[1] + img1.shape[1] + 200), img2.shape[0]))

cv2.imshow("warped perspective", dst)


dst[0:img2.shape[0], 0:img2.shape[1]] = img2
cv2.imshow("first merged img", dst)

######################################################################
# repeat but with new image

kp4, des4 = sift.detectAndCompute(dst,None)

matches = flann.knnMatch(des4,des3,k=2)
1
good = []
for m,n in matches:
    if m.distance < 0.7*n.distance:
        good.append(m)
        
matchesMask = [[0,0] for i in range(len(matches))]
 
# ratio test as per Lowe's paper
for i,(m,n) in enumerate(matches):
    if m.distance < 0.6*n.distance:
        matchesMask[i]=[1,0]
 
draw_params = dict(matchColor = (0,255,0),
                   singlePointColor = (255,0,0),
                   matchesMask = matchesMask,
                   flags = cv2.DrawMatchesFlags_DEFAULT)
 
matchIMG2 = cv2.drawMatchesKnn(dst,kp4,img3,kp3,matches,None,**draw_params)
 
cv2.imshow("second pic matches", matchIMG2)


src_pts = np.float32([ kp4[m.queryIdx].pt for m in good ]).reshape(-1,1,2)
dst_pts = np.float32([ kp3[m.trainIdx].pt for m in good ]).reshape(-1,1,2)
 
matrix, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC,5.0)

dst2 = cv2.warpPerspective(dst, matrix, ((dst.shape[1] + img3.shape[1] + 200), img3.shape[0]))

cv2.imshow("warped perspective", dst2)


dst2[0:img3.shape[0], 0:img3.shape[1]] = img3
cv2.imshow("final merged img", dst2)

cv2.waitKey(0)
