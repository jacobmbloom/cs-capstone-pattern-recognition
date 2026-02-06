
import os
import cv2
import numpy as np
from flask import Flask, request, jsonify, render_template_string
from werkzeug.utils import secure_filename

# make a upload folder in the project and make allowed extensions
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}

# allow actually making the new upload folder
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


STATIC_OUTPUT = "static/outputs"
os.makedirs(STATIC_OUTPUT, exist_ok=True)




# helper functions
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# computer vision logic from last prototype
def compare_images(img_path1, img_path2, output_path):
    img1 = cv2.imread(img_path1)
    img2 = cv2.imread(img_path2)

    img1 = cv2.resize(img1, (450, 450))
    img2 = cv2.resize(img2, (450, 450))

    sift = cv2.SIFT_create()
    kp1, des1 = sift.detectAndCompute(img1, None)
    kp2, des2 = sift.detectAndCompute(img2, None)

    if des1 is None or des2 is None:
        return None, {"good_matches": 0}

    flann = cv2.FlannBasedMatcher(
        dict(algorithm=1, trees=5),
        dict(checks=50)
    )

    matches = flann.knnMatch(des1, des2, k=2)

    good_matches = [
        m for m, n in matches if m.distance < 0.7 * n.distance
    ]

    match_img = cv2.drawMatches(
        img1, kp1,
        img2, kp2,
        good_matches, None,
        matchColor=(0, 255, 0),
        singlePointColor=(255, 0, 0)
    )

    cv2.imwrite(output_path, match_img)

    return output_path, {
        "keypoints_1": len(kp1),
        "keypoints_2": len(kp2),
        "good_matches": len(good_matches)
    }



# home page
@app.route("/", methods=["GET"])
def index():
    # will change to regular html file late
    return render_template_string("""
    <!doctype html>
    <title>Image Comparison</title>
    <h1>Compare Two Images</h1>
    <form method="post" action="/compare" enctype="multipart/form-data">
        <input type="file" name="image1" required>
        <input type="file" name="image2" required>
        <button type="submit">Compare Images</button>
    </form>
    """)


# page once you click compare for images
@app.route("/compare", methods=["POST"])
def compare():
    # get images with flask function
    img1 = request.files.get("image1")
    img2 = request.files.get("image2")

    if not img1 or not img2:
        return "Two images required", 400

    # save images to upload folder we made at the start
    path1 = os.path.join(UPLOAD_FOLDER, secure_filename(img1.filename))
    path2 = os.path.join(UPLOAD_FOLDER, secure_filename(img2.filename))

    img1.save(path1)
    img2.save(path2)

    output_filename = "comparison.png"
    output_path = os.path.join(STATIC_OUTPUT, output_filename)

    image_url, stats = compare_images(path1, path2, output_path)

    return render_template_string("""
    <!doctype html>
    <title>Comparison Result</title>

    <h1>Image Comparison Result</h1>

    <p>Keypoints (Image 1): {{ stats.keypoints_1 }}</p>
    <p>Keypoints (Image 2): {{ stats.keypoints_2 }}</p>
    <p>Good Matches: {{ stats.good_matches }}</p>

    <img src="{{ image_url }}" style="max-width:100%;">

    <br><br>
    <a href="/">Compare another</a>
    """,
    image_url=f"/static/outputs/{output_filename}",
    stats=stats
    )



# run app
if __name__ == "__main__":
    app.run(debug=True)
