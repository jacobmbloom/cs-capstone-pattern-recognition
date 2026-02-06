import cv2
import numpy as np

# https://learnopencv.com/histogram-of-oriented-gradients/

# Opening  the models
# For people - working good so far
hog = cv2.HOGDescriptor()

# For cars dector working yolo is not
hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
net = cv2.dnn.readNetFromONNX("yolov8n.onnx")


# Getting image
image = cv2.imread('peds.png')

# Using the model to find people
pedestrians, confidence = hog.detectMultiScale(image, winStride=(8, 8), padding=(4, 4), scale=1.01)

# Putting the boxes around each person
for (x, y, w, h) in pedestrians:
    # Create new image
    roi = image[y:y + h, x:x + w]

    # Giving label (Will make more useful later (giving colors and stuff, getting cars done first)
    label = "Person"

    # Show ROI
    cv2.rectangle(image, (x, y), (x + w, y + h), (0, 255, 0), 2)

    # put text onto the rectangle for a label of what the item was classified as
    cv2.putText(image, label,(x, y - 10),cv2.FONT_HERSHEY_SIMPLEX,0.6,(0, 255, 0),2)

# Resizing
resized_image = cv2.resize(image, (800, 800))

# Show
cv2.imshow("HOG Pedestrians", resized_image)
cv2.waitKey(0)

# https://learnopencv.com/moving-object-detection-with-opencv/

# Opening video
cap = cv2.VideoCapture("moving.mp4")

backSub = cv2.createBackgroundSubtractorMOG2()
kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
min_contour_area = 1000

CAR_CLASS_ID = 2  # COCO car class index

while True:
    ret, frame = cap.read()
    if not ret:
        break

    fg_mask = backSub.apply(frame)
    _, mask_thresh = cv2.threshold(fg_mask, 180, 255, cv2.THRESH_BINARY)
    mask_clean = cv2.morphologyEx(mask_thresh, cv2.MORPH_OPEN, kernel)

    contours, _ = cv2.findContours(mask_clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    frame_out = frame.copy()

    i = 0
    for cont in contours:
        i = i + 1

        if i > 20:
            break

        # Need to normalize the area before checking otherwise it finds closer objects in the 90k range and further objects < 500
        # Also the classifier found online sucks, probably should just make it 
        if cv2.contourArea(cont) > min_contour_area:
            print(cv2.contourArea(cont))
            
            # Get box
            x, y, w, h = cv2.boundingRect(cont)
            roi = frame[y:y+h, x:x+w]
            if roi.size == 0:
                continue

            # classifier needs it changed to a blob
            blob = cv2.dnn.blobFromImage(roi, 1/255.0, (640, 640), swapRB=True, crop=False)
            net.setInput(blob)
            outputs = net.forward()[0]
            
            # Determine if areas found are a car
            for det in outputs:
                conf = det[4]
                if conf < 0.04:
                    continue

                class_scores = det[5:]
                class_id = np.argmax(class_scores)
                score = class_scores[class_id]

                # If its actually a car
                if score > .4:
                    roi_h, roi_w = roi.shape[:2]
                    cx, cy, bw, bh = det[0], det[1], det[2], det[3]
                    x1 = int((cx - bw / 2) * roi_w) + x
                    y1 = int((cy - bh / 2) * roi_h) + y
                    x2 = int((cx + bw / 2) * roi_w) + x
                    y2 = int((cy + bh / 2) * roi_h) + y

                    cv2.rectangle(frame_out, (x1, y1), (x2, y2), (0, 0, 200), 2)
                    cv2.putText(frame_out, "Car", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 200), 2)

    resized_frame_out = cv2.resize(frame_out, (800, 800))
    cv2.imshow("Motion Detection", resized_frame_out)

    if cv2.waitKey(20) & 0xFF == 27:
        break


cap.release()
cap = cv2.VideoCapture("moving.mp4")

# https://dev.to/jarvissan22/blog-cv2-video-and-motion-detection-and-tracking-j4c

feature_params = dict(maxCorners=100, qualityLevel=0.3, minDistance=7, blockSize=7)
lk_params = dict(winSize=(15, 15), maxLevel=2, criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03))

# Read the first frame and initialize tracking points
ret, old_frame = cap.read()
old_gray = cv2.cvtColor(old_frame, cv2.COLOR_BGR2GRAY)
p0 = cv2.goodFeaturesToTrack(old_gray, mask=None, **feature_params)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Convert the current frame to grayscale
    frame_gray = cv2.cvtColor(frame.copy(), cv2.COLOR_BGR2GRAY)

    # Calculate optical flow
    p1, st, err = cv2.calcOpticalFlowPyrLK(old_gray, frame_gray, p0, None, **lk_params)

    # Select points successfully tracked
    good_new = p1[st == 1]
    good_old = p0[st == 1]

    # Draw the tracked points
    for i, (new, old) in enumerate(zip(good_new, good_old)):
        a, b = map(int, new.ravel())
        c, d = map(int, old.ravel())
        cv2.circle(frame, (a, b), 5, (0, 0, 255), -1)
        cv2.line(frame, (a, b), (c, d), (0, 255, 0), 2)

    # Update the previous frame and points
    old_gray = frame_gray.copy()
    p0 = good_new.reshape(-1, 1, 2)

    # Write and display the frame
    resized_frame = cv2.resize(frame, (800, 800))
    cv2.imshow("Tracked Motion", resized_frame)

    if cv2.waitKey(10) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()
