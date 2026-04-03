
from flask import Flask, Response, render_template, request, session, redirect, send_from_directory, send_file
from flask_sock import Sock
from io import BytesIO
import pandas as pd
import os
import uuid
import random

import json
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

# Map socket session ID to user directory
sid_directory_map = {}

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
    print(files)
    for i, file in enumerate(files):
        try:
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

###############
# HTTP Routes #
###############

@app.route("/")
@app.route("/files")
def files():
    if "fileDirectory" not in session:
        print("Making folder")
        session["fileDirectory"] = str(uuid.uuid4())
    usr_upload_dir = os.path.join(UPLOAD_DIR, session["fileDirectory"])
    usr_result_dir = os.path.join(RESULT_DIR, session["fileDirectory"])
    os.makedirs(usr_upload_dir, exist_ok=True)
    os.makedirs(usr_result_dir, exist_ok=True)
    

    return render_template("files.html")    

@app.route("/results")
def results():
    return render_template("results.html")

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
    fig = PLOT_FUNCTION_MAP[plotname](session["fileDirectory"])
    
    print(type(fig))

    if (isinstance(fig, tuple)):
        fig = fig[0]

    #   write figure image to buffer
    buf = BytesIO()
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

    file = request.files.get("files")

    if not file.filename:
        return {"status": "error", "message": "General File error"}

    if not any([file.filename.endswith(fileType) for fileType in VALID_TYPES]):
        return {"status": "error", "message": "Not a valid file type"}

    path = os.path.join(UPLOAD_DIR, session["fileDirectory"], file.filename)
    file.save(path)

    results = {"status": "good"}
    if file.filename.endswith(".csv"):
        results["dependancies"] = checkDependancies(path)

    return results

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