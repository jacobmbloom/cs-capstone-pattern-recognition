# -*- coding: utf-8 -*-
"""
Created on Mon Mar  3 12:00:32 2025

@author: jacob
"""

import numpy as np
import cv2



def mouse_click(event, x, y, flags, param):
    global points
    global clicked
    if event == cv2.EVENT_LBUTTONDOWN:
        print("coords: " + str(x) + ", " + str(y))
        points = list(points)
        points.append([x,y])
        clicked = True
        
# global vars for stuff
# changed p0 -> points
points = []
clicked = False
paused = False

cap = cv2.VideoCapture('cars.mp4')

# need to google params for future use
# params for ShiTomasi corner detection
# probably dont need this idk
feature_params = dict( maxCorners = 100,
                       qualityLevel = 0.3,
                       minDistance = 7,
                       blockSize = 7 )

# params: max window size of feature tracking (wont track if pixel moves out of window)
#         max level is how many gaussian img levels you track across for iterative LK flow
#         criteria, leave as is or google to improve
# Parameters for lucas kanade optical flow
lk_params = dict( winSize  = (15,15),
                  maxLevel = 2,
                  criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03))

# Create some random colors
color = np.random.randint(0,255,(100,3))

# Take first frame and find corners in it

# uses capture object, reads a frame
ret, old_frame = cap.read()

# for simplicity convert to grayscale
old_gray = cv2.cvtColor(old_frame, cv2.COLOR_BGR2GRAY)

# feature detector, could have used SIFT or FLAN idc
# all we want is x, y of feature we want to track
# NOTE: dont do feature detection inside of loop
# make this user dfined points in loop add them to list?


#print(p0.shape)
#print(p0)

# Create a mask image for drawing purposes
mask = np.zeros_like(old_frame)


while(1):
    # get the next frame, covert to gray again
    ret,frame = cap.read()
    frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    

    # calculate optical flow'
    # input params are two frames we are comparing and the feature points from the first frame
    # return val is x, y locations in second param image
    
    if(len(points) >= 1):
        pointsArray = np.array(points, dtype=np.float32)
        
        p1, st, err = cv2.calcOpticalFlowPyrLK(old_gray, frame_gray, pointsArray, None, **lk_params)
        # had to ravel to make it a 1d array

        # draw the tracks
        # i dont think i need this anymore but i dont want to break it so im keeping it
        for i,(new,old) in enumerate(zip(p1, pointsArray)):
            a,b = new.ravel()
            c,d = old.ravel()
            
            # need to fix for our video, points need to be ints on img
            a = int(a)
            b = int(b)
            c = int(c)
            d = int(d)
            
            mask = cv2.line(mask, (a,b),(c,d), color[i].tolist(), 2)
            frame = cv2.circle(frame,(a,b),5,color[i].tolist(),-1)
        
        old_gray = frame_gray.copy()
        
        points = p1.copy()
        
    # if we dont want lines :p
    img = frame

    cv2.imshow('frame',img)
    cv2.setMouseCallback("frame", mouse_click, points)
    
    
    # user actions
    myWaitKey = cv2.waitKey(40) & 0xff
    
    if myWaitKey == ord('q'):
        break
    
    if myWaitKey == ord('c'):
        points = []
        
    if myWaitKey == ord('p'):
        print('paused')
        cv2.imshow('frame', img)
        paused = True
        
        while paused:
            
            if clicked:
                print(points)
                for point in points:
                   
                    # had to covert a bunch also just doing the x coord of the point mod 100 for the color to get a practically random one
                    frame = cv2.circle(frame,(int(point[0]),int(point[1])), 5, color[(int(point[0])%100)].tolist(),4)
                    cv2.imshow('frame', frame)
                clicked = False
            
            if cv2.waitKey(10) & 0xff == ord('p'):
                paused = False
            
        print('unpaused')

cv2.destroyAllWindows()
cap.release()