
from flask import Flask, Response, render_template, request, session, redirect, send_from_directory, jsonify
from flask_sock import Sock
from io import BytesIO
import pandas as pd
import os
import shutil
import uuid
import json
import time
import threading

from imageRecognition import *

app = Flask(__name__)
app.secret_key = "your_very_secret_and_unique_key"

sock = Sock(app)

UPLOAD_DIR = "uploads"
RESULT_DIR = "results"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)

VALID_TYPES = [".csv", ".mp4", ".jpg", ".png"]

CLEANUP_AFTER_SECONDS  = int(os.environ.get("CLEANUP_AFTER_SECONDS",  60 *60))  # 60 mins
CLEANUP_CHECK_INTERVAL = int(os.environ.get("CLEANUP_CHECK_INTERVAL", 30 *60))  # 30 mins

fileManager = {}
settingManager = {}
lastSeen = {}                     #dict[str, float]
lastSeenLock = threading.Lock()


###########
# Utility #
###########

def checkDependancies(path: str):
    if not os.path.exists(path):
        return "File not found"

    df = pd.read_csv(path)

    if "filename" not in df.columns:
        return "File does not contain media references"

    return list(df["filename"].unique())

def runImageProcessing(files, ws, file_directory):
    
    valid = None
    if file_directory in settingManager:
        valid = []
        for setting, state in settingManager[file_directory].items():
            if state == "on":
                valid.append(setting)
    
    for i, file in enumerate(files):
        try:
            if valid:
                result = image_processing(
                    file_directory,
                    os.path.join(UPLOAD_DIR, file_directory, os.path.basename(file)),
                    os.path.join(RESULT_DIR, file_directory, os.path.basename(file)),
                    valid
                )
            else:
                result = image_processing(
                    file_directory,
                    os.path.join(UPLOAD_DIR, file_directory, os.path.basename(file)),
                    os.path.join(RESULT_DIR, file_directory, os.path.basename(file))
                )

            ws.send(json.dumps({
                "type": "status",
                "file": os.path.basename(file),
                "progress": int((i + 1) / len(files) * 100),
                "result": result
            }))
            print("Clean")

        except Exception as e:
            ws.send(json.dumps({
                "type": "error",
                "file": os.path.basename(file),
                "message": str(e)
            }))

    ws.send(json.dumps({
        "type": "done"
    }))

################
# User Cleanup #
################

def touch(file_directory: str) -> None:
    """Record that a user just interacted with the server."""
    with lastSeenLock:
        lastSeen[file_directory] = time.time()

def _purge_user(file_directory: str) -> None:
    """Delete all uploaded/result files for one user and remove them from memory."""
    for base_dir in (UPLOAD_DIR, RESULT_DIR):
        target = os.path.join(base_dir, file_directory)
        if os.path.isdir(target):
            shutil.rmtree(target, ignore_errors=True)
 
    fileManager.pop(file_directory, None)
    settingManager.pop(file_directory, None)
    purgePrediction(file_directory)
 
    with lastSeenLock:
        lastSeen.pop(file_directory, None)
 
    print(f"[cleanup] Purged data for session directory: {file_directory}")

def _cleanup_loop() -> None:
    """Background thread: periodically evict stale user data."""
    while True:
        time.sleep(CLEANUP_CHECK_INTERVAL)
        cutoff = time.time() - CLEANUP_AFTER_SECONDS
        with lastSeenLock:
            stale = [fd for fd, ts in lastSeen.items() if ts < cutoff]
 
        for file_directory in stale:
            _purge_user(file_directory)

cleanupThread = threading.Thread(target=_cleanup_loop, daemon=True, name="file-cleanup")
cleanupThread.start()

###############
# HTTP Routes #
###############

@app.route("/")
@app.route("/files")
def files():
    if "fileDirectory" not in session:
        session["fileDirectory"] = str(uuid.uuid4())
    usr_upload_dir = os.path.join(UPLOAD_DIR, session["fileDirectory"])
    usr_result_dir = os.path.join(RESULT_DIR, session["fileDirectory"])
    os.makedirs(usr_upload_dir, exist_ok=True)
    os.makedirs(usr_result_dir, exist_ok=True)

    return render_template("files.html")    

@app.route("/visualizations")
def visualizations():
    if "fileDirectory" not in session:
        redirect("/files")
    return render_template("results.html")

@app.route("/patterns")
def patterns():
    if "fileDirectory" not in session:
        redirect("/files")
    raw_patterns = get_page_format_patterns(session["fileDirectory"])

    return render_template("patterns.html", patterns=raw_patterns)  

##################
# Dynamic Routes #
##################

PLOT_FUNCTION_MAP = {
    "plot_prediction_timeline"     : plot_prediction_timeline,
    "plot_prediction_frequency"    : plot_prediction_frequency,
    "plot_confidence_distribution" : plot_confidence_distribution,
    "plot_confidence_per_class"    : plot_confidence_per_class,
    "plot_cumulative_classes"      : plot_cumulative_classes,
    "plot_detections_per_image"    : plot_detections_per_image,

    "plot_repetition_patterns"     : plot_repetition_patterns,
    "plot_occurrence_patterns"     : plot_occurrence_patterns,
    "plot_occurrence_timeline"     : plot_occurrence_timeline,
    "plot_sequential_patterns"     : plot_sequential_patterns,
    "plot_sequential_timeline"     : plot_sequential_timeline,  
    "plot_multiple_prediction_timeline" : plot_multiple_prediction_timeline,
}

"""
    Returns a given plot as an object in memory so the file doesnt need to be saved to disk.
    Only in memory for a short period of time.
"""
@app.route("/plots/<string:plotname>")
def get_plot(plotname: str):
    #   Use fileDirectory to seperate users, even though this isnt technically a file
    if "fileDirectory" not in session:
        return redirect("/")
    
    #   To keep things flexible for future plots,
    #       The argument passed is used as the function name
    #       BUT to keep it safe it must be a function from the table above
    fig = PLOT_FUNCTION_MAP[plotname](session["fileDirectory"])
    
    if not fig:
        raise Exception("Figure Error")

    if (isinstance(fig, tuple)):
        fig = fig[0]

    #   write figure image to buffer
    buf = BytesIO()
    print(type(fig))
    fig.savefig(buf, format="png")
    buf.seek(0)

    # Return image response
    return Response(buf.getvalue(), mimetype="image/png")

@app.route("/results/<path:filename>")
def get_file(filename):
    return send_from_directory(
        os.path.join(RESULT_DIR, session["fileDirectory"]),
        filename
    )

@app.route("/csvDownload")
def download_csv():
    return Response(
        export_predictions(session["fileDirectory"]),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=data.csv"}
    )

##############
# API Routes #
##############

@app.route("/api/getUploads", methods=["GET"])
def api_getUploads():
    if "fileDirectory" not in session:
        return { "files" : [] }

    print(fileManager[session["fileDirectory"]])
    return { "files": fileManager[session["fileDirectory"]] }

@app.route("/api/saveUploads", methods=["POST"])
def api_saveUploads():
    data = request.get_json() 
    
    if not isinstance(data, list):
        return jsonify({"error": "Expected a list of objects"}), 400

    if session["fileDirectory"] not in fileManager:
        fileManager[session["fileDirectory"]] = []
    for item in data:
        match = -1
        for i, existing in enumerate(fileManager[session["fileDirectory"]]):
            if existing["name"] == item["name"]:
                match = i
        if match != -1:
            fileManager[session["fileDirectory"]][i] = item
        else:
            fileManager[session["fileDirectory"]].append(item) 


    return jsonify({"message": "Successfully received list", "count": len(data)}), 200

@app.route("/api/upload", methods=["POST"])
def api_upload():
    """
        Upload endpoint for file management
        Can expect a single file in the "file" portion of request
    """

    #   Prevent user from accessing pages without regestering with server
    #       Also ensures the user has a local directory
    if "fileDirectory" not in session:
        return redirect("/")

    #name = request.get_json()
    file = request.files.get("files")

    if not file or not file.filename:
        return {"status": "error", "message": "General File error"}

    if not any([file.filename.endswith(fileType) for fileType in VALID_TYPES]):
        return {"status": "error", "message": "Not a valid file type"}

    path = os.path.join(UPLOAD_DIR, session["fileDirectory"], file.filename)
    file.save(path)

    results = {"status": "good"}
    if file.filename.endswith(".csv"):
        results["dependancies"] = checkDependancies(path)

    return results

@app.route("/settingChange", methods=["POST"])
def settingsChange():
    if "fileDirectory" not in session:
        return redirect("/")

    data = dict(request.form)

    settingManager[session["fileDirectory"]] = data

    return redirect("/files")


#################
# Socket Events #
#################

@sock.route("/process/<fileId>")
def socket_process(ws, fileId):
    print(f"WebSocket connected: {fileId}")

    file_directory = session.get("fileDirectory")
    
    if not file_directory:
        ws.send(json.dumps({"type": "error", "message": "Session expired or invalid"}))
        return
    
    runImageProcessing([fileId], ws, file_directory)

    print(f"WebSocket disconnected for file: {fileId}")
    
if __name__ == "__main__":
    app.run(debug=True)