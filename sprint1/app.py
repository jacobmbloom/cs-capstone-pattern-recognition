import cv2
import numpy as np
import tensorflow as tf
import pandas as pd
import os
import shutil
import uuid

from ultralytics import YOLO
from flask import Flask, render_template, request, session, redirect, send_from_directory
from flask_socketio import SocketIO, emit
from datetime import datetime
import time

# Setup
app = Flask(__name__)
app.secret_key = "your_very_secret_and_unique_key"

socketio = SocketIO(app, cors_allowed_origins="*")

UPLOAD_DIR = "uploads"
RESULT_DIR = "results"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)

VALID_TYPES = [".csv", ".mp4", ".jpg", ".png"]

# Map socket session ID to user directory
sid_directory_map = {}

#####################
# Backend Functions #
#####################

# Model setup and use
def process(img_path : str, final_path : str):
    class_names = [
        "Convertible",
        "Coupe",
        "Hatchback",
        "Pick-Up",
        "Sedan",
        "SUV",
        "VAN"
        ]


    # Load YOLO car detector
    detector = YOLO("yolov8n.pt")

    # Load your Keras classifier
    model = tf.keras.models.load_model("pruned.keras")

    # Load the image
    img = cv2.imread(img_path)

    # Parameter tune
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    new_size = (1280, 720)
    duplicated_image = img_rgb.copy()
    resized_duplicate = cv2.resize(duplicated_image, new_size, interpolation=cv2.INTER_LINEAR)

    orig_h, orig_w = img_rgb.shape[:2]

    scale_x = new_size[0] / orig_w
    scale_y = new_size[1] / orig_h

    # Detect objects
    results = detector(img)

    # Review results and give a classificaiton
    for result in results:
        for box in result.boxes:
            cls = int(box.cls[0])
            label = detector.names[cls]

            # If yolo has decided the object in box is a car
            if label == "car":
                # Map the box
                x1, y1, x2, y2 = map(int, box.xyxy[0])

                # Resize to avoid text size exploding on lower pixel images
                crop = img_rgb[y1:y2, x1:x2]
                crop = cv2.resize(crop, (244, 244))
                crop = crop / 255.0
                crop = np.expand_dims(crop, axis=0)

                # Predict and store the most likely
                prediction = model.predict(crop)
                class_id = np.argmax(prediction)
                confidence = np.max(prediction)

                # Setup and place box onto image
                new_x1 = int(x1 * scale_x)
                new_y1 = int(y1 * scale_y)
                new_x2 = int(x2 * scale_x)
                new_y2 = int(y2 * scale_y)

                cv2.rectangle(resized_duplicate, (new_x1, new_y1), (new_x2, new_y2), (0,255,0), 3)

                predicted_label = class_names[class_id]
                display_text = f"{predicted_label}: {confidence * 100:.1f}%"

                # Place classification onto box
                cv2.putText(
                    resized_duplicate,
                    display_text,
                    (new_x1, new_y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.9,
                    (0, 255, 0),
                    2,
                    cv2.LINE_AA
                )

            cv2.imwrite(final_path, cv2.cvtColor(resized_duplicate, cv2.COLOR_RGB2BGR))

# Check if file is found
def checkDependancies(path: str):
    if not os.path.exists(path):
        return "File not found"

    df = pd.read_csv(path)

    if "filename" not in df.columns:
        return "File does not contain media references"

    return list(df["filename"].unique())


def runPatternRecognition(files, sid: str):
    """
    Background worker tied to socket session.
    Emits progress updates to the correct client.
    """

    for i, file in enumerate(files):
        process(
            os.path.join(file),
            os.path.join(RESULT_DIR, sid_directory_map[sid], os.path.basename(file))
        )

        socketio.emit(
            "status",
            {
                "message": str(os.path.basename(file)),
                "progress": int((i + 1) / len(files) * 100)
            },
            room=sid
        )
    socketio.emit("done", {}, room=sid)


###############
# HTTP Routes #
###############

@app.route("/")
def index():
    if "fileDirectory" not in session:
        session["fileDirectory"] = str(uuid.uuid4())
        usr_upload_dir = os.path.join(UPLOAD_DIR, session["fileDirectory"])
        usr_result_dir = os.path.join(RESULT_DIR, session["fileDirectory"])
        os.makedirs(usr_upload_dir, exist_ok=True)
        os.makedirs(usr_result_dir, exist_ok=True)

    return render_template("index.html")

@app.route("/csv_post", methods=["POST"])
def csv_post():

    if "fileDirectory" not in session:
        return redirect("/")

    files = request.files.getlist("files")

    depencancies = {}

    for f in files:
        if not f.filename:
            continue

        path = os.path.join(UPLOAD_DIR, session["fileDirectory"], f.filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        f.save(path)

        depencancies[f.filename] = checkDependancies(path)

        if isinstance(depencancies[f.filename], str):
            os.remove(path)

    return depencancies

@app.route("/media_post", methods=["POST"])
def media_post():
    """
    Only saves files.
    Processing is triggered via socket event.
    """

    if "fileDirectory" not in session:
        return redirect("/")

    files = request.files.getlist("files")
    saved_files = []

    for f in files:
        print(f.filename)
        if not f.filename:
            continue

        path = os.path.join(UPLOAD_DIR, session["fileDirectory"], f.filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        f.save(path)
        saved_files.append(path)

    return {"saved": saved_files}

@app.route("/results/<path:filename>")
def get_file(filename):
    return send_from_directory(
        os.path.join(RESULT_DIR, session["fileDirectory"]),
        filename
    )

#################
# Socket Events #
#################

@socketio.on("connect")
def handle_connect():
    if "fileDirectory" in session:
        sid_directory_map[request.sid] = session["fileDirectory"]

@socketio.on("disconnect")
def handle_disconnect():
    sid_directory_map.pop(request.sid, None)

@socketio.on("start_processing")
def handle_processing(data):
    sid = request.sid
    files = data.get("files", [])

    if not files:
        emit("status", {"message": "No files provided"})
        return
        
    socketio.start_background_task(runPatternRecognition, files, sid)

if __name__ == "__main__":
    socketio.run(app, debug=True)
