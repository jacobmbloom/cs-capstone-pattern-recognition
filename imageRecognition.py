from ultralytics import YOLO
import cv2
import numpy as np
import tensorflow as tf
import os
import pandas as pd
import matplotlib.pyplot as plt
from io import StringIO


DETECTOR = YOLO("yolov8n.pt")
MODEL = tf.keras.models.load_model("pruned.keras")

CLASS_NAMES = [
        "Convertible",
        "Coupe",
        "Hatchback",
        "Pick-Up",
        "Sedan",
        "SUV",
        "VAN"
        ]

prediction_log = {}

"""
    Extract the bounding box information for the image classification
"""
def process(img_path: str, final_path: str):
    class_names = [
        "Convertible", "Coupe", "Hatchback",
        "Pick-Up", "Sedan", "SUV", "VAN"
    ]

    img = cv2.imread(img_path)
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    new_size = (1280, 720)
    resized_image = cv2.resize(img_rgb, new_size, interpolation=cv2.INTER_LINEAR)

    orig_h, orig_w = img_rgb.shape[:2]
    scale_x = new_size[0] / orig_w
    scale_y = new_size[1] / orig_h

    results = DETECTOR(img)

    detections = []

    for result in results:
        for box in result.boxes:
            cls = int(box.cls[0])
            label = DETECTOR.names[cls]

            if label != "car":
                continue

            x1, y1, x2, y2 = map(int, box.xyxy[0])

            crop = img_rgb[y1:y2, x1:x2]
            crop = cv2.resize(crop, (244, 244))
            crop = crop / 255.0
            crop = np.expand_dims(crop, axis=0)

            prediction = MODEL.predict(crop, verbose=0)[0]
            class_id = int(np.argmax(prediction))
            confidence = float(np.max(prediction))

            predicted_label = class_names[class_id]

            # Scaled box for resized image
            new_x1 = int(x1 * scale_x)
            new_y1 = int(y1 * scale_y)
            new_x2 = int(x2 * scale_x)
            new_y2 = int(y2 * scale_y)

            # Draw
            cv2.rectangle(resized_image, (new_x1, new_y1), (new_x2, new_y2), (0, 255, 0), 3)
            cv2.putText(
                resized_image,
                f"{predicted_label}: {confidence * 100:.1f}%",
                (new_x1, new_y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (0, 255, 0),
                2,
                cv2.LINE_AA
            )

            # Store detection data
            detections.append({
                "label": predicted_label,
                "confidence": confidence,
                "bbox_original": [x1, y1, x2, y2],
                "bbox_resized": [new_x1, new_y1, new_x2, new_y2],
                "all_class_probs": prediction.tolist()
            })

    # Save final image once
    cv2.imwrite(final_path, cv2.cvtColor(resized_image, cv2.COLOR_RGB2BGR))

    return {
        "image_path": img_path,
        "output_path": final_path,
        "image_size_original": (orig_w, orig_h),
        "image_size_resized": new_size,
        "num_cars_detected": len(detections),
        "detections": detections
    }

def image_processing(user_session_id : str, input_path : str, final_path : str):

    # Load YOLO car detector
    detector = YOLO("yolov8n.pt")

    # Load your Keras classifier
    model = tf.keras.models.load_model("pruned.keras")

    img = cv2.imread(input_path)
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # Detect objects
    results = DETECTOR(img)

    for result in results:
        for box in result.boxes:
            cls = int(box.cls[0])
            label = DETECTOR.names[cls]

            if label == "car":
                x1, y1, x2, y2 = map(int, box.xyxy[0])

                crop = img_rgb[y1:y2, x1:x2]
                crop = cv2.resize(crop, (244, 244))
                crop = crop / 255.0
                crop = np.expand_dims(crop, axis=0)

                prediction = model.predict(crop)
                class_id = np.argmax(prediction)
                confidence = np.max(prediction)
                predicted_label = CLASS_NAMES[class_id]
                print(prediction)

                if user_session_id not in prediction_log:
                    prediction_log[user_session_id] = []

                # store predictions to data structure
                prediction_log[user_session_id].append({
                    "filename": os.path.basename(input_path),
                    "label": predicted_label,
                    "confidence": float(confidence),
                    "x1": x1,
                    "y1": y1,
                    "x2": x2,
                    "y2": y2,
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

    cv2.imwrite(final_path,  cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR))

def plot_prediction_timeline(fileDirectory : str):
    if fileDirectory not in prediction_log or not prediction_log[fileDirectory]:
        return None

    df = pd.DataFrame(prediction_log[fileDirectory])

    # Create index (timeline)
    df["index"] = range(len(df))

    # Convert labels to numeric
    label_map = {label: i for i, label in enumerate(df["label"].unique())}
    df["label_id"] = df["label"].map(label_map)

    fig, ax = plt.subplots()
    
    ax.scatter(df["index"], df["label_id"])

    #ax.set_yticks(list(label_map.values()), list(label_map.keys()))
    ax.set_xlabel("Image Order")
    ax.set_ylabel("Predicted Class")

    return fig

def plot_prediction_frequency(fileDirectory : str):
    if fileDirectory not in prediction_log or not prediction_log[fileDirectory]:
        return None

    df = pd.DataFrame(prediction_log[fileDirectory])

    car_counts = df['label'].value_counts()

    fig, ax = plt.subplots()

    ax.bar(car_counts.index, car_counts.values)

    ax.set_xlabel('car type')
    ax.set_ylabel('car count')
    #ax.set_xticks(rotation=20)

    return fig

def plot_confidence_distribution(fileDirectory : str):
    if fileDirectory not in prediction_log or not prediction_log[fileDirectory]:
        return None

    df = pd.DataFrame(prediction_log[fileDirectory])

    fig, ax = plt.subplots()
    ax.hist(df["confidence"], bins=20)

    ax.set_xlabel("Confidence")
    ax.set_ylabel("Frequency")
    ax.set_title("Confidence Distribution")

    return fig

def plot_confidence_per_class(fileDirectory : str):
    if fileDirectory not in prediction_log or not prediction_log[fileDirectory]:
        return None

    df = pd.DataFrame(prediction_log[fileDirectory])

    avg_conf = df.groupby("label")["confidence"].mean()

    fig, ax = plt.subplots()
    ax.bar(avg_conf.index, avg_conf.values)

    ax.set_xlabel("Car Type")
    ax.set_ylabel("Avg Confidence")
    #ax.set_title("Average Confidence per Class")
    #ax.set_xticks(rotation=20)

    return fig

def plot_cumulative_classes(fileDirectory: str):
    if fileDirectory not in prediction_log or not prediction_log[fileDirectory]:
        return None

    df = pd.DataFrame(prediction_log[fileDirectory])
    df["index"] = range(len(df))

    # Create figure and axis (subplot)
    fig, ax = plt.subplots()

    for label in df["label"].unique():
        mask = (df["label"] == label).astype(int)
        cumulative = mask.cumsum()

        ax.plot(df["index"], cumulative, label=label)

    ax.set_xlabel("Image Index")
    ax.set_ylabel("Cumulative Count")
    ax.legend()

    return fig, ax

def plot_detections_per_image(fileDirectory : str):
    if fileDirectory not in prediction_log or not prediction_log[fileDirectory]:
        return None

    df = pd.DataFrame(prediction_log[fileDirectory])

    counts = df.groupby("filename").size()

    fig, ax = plt.subplots()
    plt.hist(counts, bins=10)

    ax.set_xlabel("Detections per Image")
    ax.set_ylabel("Frequency")

    return fig

def export_predictions(fileDirectory : str):
    output = StringIO()
    df = pd.DataFrame(prediction_log[fileDirectory])
    df.to_csv(output, index=False)
    output.seek(0)
    return output.getvalue()
