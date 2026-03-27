from ultralytics import YOLO
import cv2
import numpy as np
import tensorflow as tf

from flask import Flask, render_template, request, session, redirect, send_from_directory
from flask_socketio import SocketIO, emit
import pandas as pd
import os
import shutil
import uuid
from datetime import datetime
import time
import matplotlib.pyplot as plt

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

# create data structure to store predictions
prediction_log = []

GRAPH_DIR = "graphs"
os.makedirs(GRAPH_DIR, exist_ok=True)

class_names = [
        "Convertible",
        "Coupe",
        "Hatchback",
        "Pick-Up",
        "Sedan",
        "SUV",
        "VAN"
        ]


###########
# Utility #
###########


def process(img_path : str, final_path : str):



    # Load YOLO car detector
    detector = YOLO("yolov8n.pt")

    # Load your Keras classifier
    model = tf.keras.models.load_model("pruned.keras")

    img = cv2.imread(img_path)
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # Detect objects
    results = detector(img)

    for result in results:
        for box in result.boxes:
            cls = int(box.cls[0])
            label = detector.names[cls]

            if label == "car":
                x1, y1, x2, y2 = map(int, box.xyxy[0])

                crop = img_rgb[y1:y2, x1:x2]
                crop = cv2.resize(crop, (244, 244))
                crop = crop / 255.0
                crop = np.expand_dims(crop, axis=0)

                prediction = model.predict(crop)
                class_id = np.argmax(prediction)
                confidence = np.max(prediction)
                predicted_label = class_names[class_id]
                print(prediction)

                # store predictions to data structure
                prediction_log.append({
                    "filename": os.path.basename(img_path),
                    "label": predicted_label,
                    "confidence": float(confidence)
                })

                cv2.rectangle(img_rgb, (x1, y1), (x2, y2), (0,255,0), 3)
                # Create display text
                display_text = f"{predicted_label}: {confidence * 100:.1f}%"

                # Put label above box
                cv2.putText(
                    img_rgb,
                    display_text,
                    (x1, y1-10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2,
                    cv2.LINE_AA
                )

    #cv2.imshow("Cars", cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR))
    #cv2.waitKey(0)
    #cv2.destroyAllWindows()

    cv2.imwrite(final_path,  cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR))


def checkDependancies(path: str):
    if not os.path.exists(path):
        return "File not found"

    df = pd.read_csv(path)

    if "filename" not in df.columns:
        return "File does not contain media references"

    return list(df["filename"].unique())


def runPatternRecognition(files: list, sid: str):
    """
    Background worker tied to socket session.
    Emits progress updates to the correct client.
    """

    for i, file in enumerate(files):
        process(
            os.path.join(file),
            os.path.join(file)
        )

        socketio.emit(
            "status",
            {
                "message": str(os.path.basename(file)),
                "progress": int((i + 1) / len(files) * 100)
            },
            room=sid
        )

    plot_prediction_timeline()
    plot_prediction_frequency()
    plot_confidence_distribution()
    plot_confidence_per_class()
    plot_cumulative_classes()
    plot_detections_per_image()

    socketio.emit("done", {}, room=sid)


def plot_prediction_timeline(save_path="graphs/timeline.png"):
    if not prediction_log:
        print("No data to plot.")
        return

    df = pd.DataFrame(prediction_log)

    # Create index (timeline)
    df["index"] = range(len(df))

    # Convert labels to numeric
    label_map = {label: i for i, label in enumerate(df["label"].unique())}
    df["label_id"] = df["label"].map(label_map)

    plt.figure()
    plt.scatter(df["index"], df["label_id"])

    plt.yticks(list(label_map.values()), list(label_map.keys()))
    plt.xlabel("Image Order")
    plt.ylabel("Predicted Class")
    plt.title("Prediction Timeline")

    plt.savefig(save_path)   # better for Flask
    plt.close()

def plot_prediction_frequency(save_path="graphs/frequency_per_class.png"):
    if not prediction_log:
        print("No data to plot.")
        return

    df = pd.DataFrame(prediction_log)

    car_counts = df['label'].value_counts()

    plt.figure()
    plt.bar(car_counts.index, car_counts.values)

    plt.xlabel('car type')
    plt.ylabel('car count')
    plt.title('# of each car type')
    plt.xticks(rotation=20)

    plt.savefig(save_path)
    plt.close()


def plot_confidence_distribution(save_path="graphs/confidence_hist.png"):
    if not prediction_log:
        return

    df = pd.DataFrame(prediction_log)

    plt.figure()
    plt.hist(df["confidence"], bins=20)

    plt.xlabel("Confidence")
    plt.ylabel("Frequency")
    plt.title("Confidence Distribution")

    plt.savefig(save_path)
    plt.close()

def plot_confidence_per_class(save_path="graphs/conf_per_class.png"):
    if not prediction_log:
        return

    df = pd.DataFrame(prediction_log)

    avg_conf = df.groupby("label")["confidence"].mean()

    plt.figure()
    plt.bar(avg_conf.index, avg_conf.values)

    plt.xlabel("Car Type")
    plt.ylabel("Avg Confidence")
    plt.title("Average Confidence per Class")
    plt.xticks(rotation=20)

    plt.savefig(save_path)
    plt.close()

def plot_cumulative_classes(save_path="graphs/cumulative.png"):
    if not prediction_log:
        return

    df = pd.DataFrame(prediction_log)

    df["index"] = range(len(df))

    for label in df["label"].unique():
        mask = (df["label"] == label).astype(int)
        cumulative = mask.cumsum()

        plt.plot(df["index"], cumulative, label=label)

    plt.xlabel("Image Index")
    plt.ylabel("Cumulative Count")
    plt.title("Cumulative Class Counts Over Time")
    plt.legend()

    plt.savefig(save_path)
    plt.close()

def plot_detections_per_image(save_path="graphs/detections_per_image.png"):
    if not prediction_log:
        return

    df = pd.DataFrame(prediction_log)

    counts = df.groupby("filename").size()

    plt.figure()
    plt.hist(counts, bins=10)

    plt.xlabel("Detections per Image")
    plt.ylabel("Frequency")
    plt.title("Cars Detected per Image")

    plt.savefig(save_path)
    plt.close()


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

@app.route("/files")
def files():
    return render_template("files.html")

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
        os.path.join(UPLOAD_DIR, session["fileDirectory"]),
        filename
    )

##############
# API Routes #
##############

@app.route("/api/upload", methods=["POST"])
def upload():
    """
        Upload endpoint for file management
        Can expect a single file in the "file" portion of request
    """

    #   Prevent user from accessing pages without regestering with server
    #       Also ensures the user has a local directory
    if "fileDirectory" not in session:
        return redirect("/")

    file = request.files.get("file")

    if not file.filename:
        return

    if not any([file.filename.endswith(fileType) for fileType in VALID_TYPES]):
        return

    if file.filename.endswith(".csv"):
        dependancies = checkDependancies()


    path = os.path.join(UPLOAD_DIR, session["fileDirectory"], file.filename)
    file.save(path)
    return


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

    """source_dir = os.path.join(UPLOAD_DIR, sid_directory_map[sid])
    destination_dir = os.path.join(RESULT_DIR, sid_directory_map[sid])
    try:
        # This will copy the 'source_folder' directory *into* the 'destination_folder' path
        shutil.copytree(source_dir, destination_dir, dirs_exist_ok=True)
        print(f"Directory '{source_dir}' copied to '{destination_dir}'")
    except FileExistsError:
        print(f"Error: Destination directory '{destination_dir}' already exists.")
    except Exception as e:
        print(f"An error occurred: {e}")"""

    socketio.start_background_task(runPatternRecognition, files, sid)

if __name__ == "__main__":
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)
