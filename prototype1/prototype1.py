

import cv2
import numpy as np
import os


# Load images from user
img_path1 = input("Enter path to first image: ").strip()
img_path2 = input("Enter path to second image: ").strip()

if not os.path.exists(img_path1) or not os.path.exists(img_path2):
    raise FileNotFoundError("One or both image paths are invalid.")

img1 = cv2.imread(img_path1)
img2 = cv2.imread(img_path2)

if img1 is None or img2 is None:
    raise ValueError("Failed to load one or both images.")

# resizing for visability and testing but realistically dont need to
img1 = cv2.resize(img1, (500, 500), interpolation=cv2.INTER_LINEAR)
img2 = cv2.resize(img2, (500, 500), interpolation=cv2.INTER_LINEAR)


# SIFT feature detection

sift = cv2.SIFT_create()

kp1, des1 = sift.detectAndCompute(img1, None)
kp2, des2 = sift.detectAndCompute(img2, None)

if des1 is None or des2 is None:
    raise ValueError("Could not compute descriptors for one or both images.")


# FLANN-based matching

FLANN_INDEX_KDTREE = 1
index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
search_params = dict(checks=50)

flann = cv2.FlannBasedMatcher(index_params, search_params)

matches = flann.knnMatch(des1, des2, k=2)


# Lowe's ratio test

good_matches = []
for m, n in matches:
    if m.distance < 0.7 * n.distance:
        good_matches.append(m)

print(f"Total keypoints in image 1: {len(kp1)}")
print(f"Total keypoints in image 2: {len(kp2)}")
print(f"Good matches found: {len(good_matches)}")


# Draw matches

match_img = cv2.drawMatches(
    img1, kp1,
    img2, kp2,
    good_matches, None,
    matchColor=(0, 255, 0),
    singlePointColor=(255, 0, 0),
    flags=cv2.DrawMatchesFlags_DEFAULT
)

cv2.imshow("Image Similarities", match_img)
cv2.waitKey(0)
cv2.destroyAllWindows()
