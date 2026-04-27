from ultralytics import YOLO
import onnxruntime as ort
import cv2
import numpy as np
import tensorflow as tf
import os
import pandas as pd
import matplotlib.pyplot as plt
from io import StringIO
import re
from datetime import datetime
from scipy.signal import find_peaks
from scipy.ndimage import gaussian_filter1d

DETECTOR = YOLO("yolov8n.pt")
MODEL = ort.InferenceSession("best.onnx", providers=["CPUExecutionProvider"])
INPUT_NAME = MODEL.get_inputs()[0].name

print(MODEL.get_inputs()[0].shape)

VALID_YOLO_CLASSES = {"car", "truck", "bus"}
CLASS_NAMES = [
        "SEDAN",
        "SEMI",
        "SUV",
        "TRUCK",
        "VAN",
        ]

prediction_log = {}

def purgePrediction(fileDirectory):
    prediction_log.pop(fileDirectory, None)

"""
    Extract the bounding box information for the image classification
"""
def process(
        img_path: str,
        final_path: str,
        valid_classes = CLASS_NAMES
    ):

    class_names = CLASS_NAMES

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

            if label not in ["car", "truck", "bus"]:
                continue

            x1, y1, x2, y2 = map(int, box.xyxy[0])

            crop = img_rgb[y1:y2, x1:x2]
            crop = cv2.resize(crop, (448, 448))
            crop = crop.astype(np.float32) / 255.0
            crop = np.expand_dims(crop, axis=0)

            prediction = MODEL.run(None, {INPUT_NAME: crop})[0][0]
            class_id = int(np.argmax(prediction))
            confidence = float(np.max(prediction))

            predicted_label = class_names[class_id]

            if predicted_label not in valid_classes:
                continue

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

def image_processing(
    user_session_id: str,
    input_path: str,
    final_path: str,
    valid_classes=CLASS_NAMES
):

    img = cv2.imread(input_path)
    if img is None:
        raise ValueError(f"Failed to read image: {input_path}")

    h, w, _ = img.shape

    results = DETECTOR(img)

    crops = []
    metadata = []  # store box + filename info for later mapping

    for result in results:
        for box in result.boxes:
            cls = int(box.cls[0])
            label = DETECTOR.names[cls]

            if label not in VALID_YOLO_CLASSES:
                continue

            x1, y1, x2, y2 = map(int, box.xyxy[0])

            # Clamp to image bounds
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)

            if x2 <= x1 or y2 <= y1:
                continue

            crop = img[y1:y2, x1:x2]

            crop = cv2.resize(crop, (448, 448))
            crop = crop.astype(np.float32) / 255.0
            crop = np.transpose(crop, (2, 0, 1))

            crops.append(crop)
            metadata.append((x1, y1, x2, y2))

    # Nothing detected
    if not crops:
        cv2.imwrite(final_path, img)
        return
    
    predictions = []

    for crop in crops:
        crop = np.expand_dims(crop, axis=0)  # (1,3,448,448)

        pred = MODEL.run(None, {INPUT_NAME: crop})[0]
        predictions.append(pred[0])

    if user_session_id not in prediction_log:
        prediction_log[user_session_id] = []

    # Process predictions
    for i, pred in enumerate(predictions):
        x1, y1, x2, y2 = metadata[i]

        class_id = int(np.argmax(pred))
        confidence = float(np.max(pred))

        predicted_label = CLASS_NAMES[class_id]

        if predicted_label not in valid_classes:
            continue

        prediction_log[user_session_id].append({
            "filename": os.path.basename(input_path),
            "label": predicted_label,
            "confidence": confidence,
            "x1": x1,
            "y1": y1,
            "x2": x2,
            "y2": y2,
        })
        print("NEW LABEL")

        # Draw box
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 3)

        display_text = f"{predicted_label}: {confidence * 100:.1f}%"

        cv2.putText(
            img,
            display_text,
            (x1, max(0, y1 - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2,
            cv2.LINE_AA
        )

    # Save final image
    cv2.imwrite(final_path, img)

    return {
        "image_path": input_path,
        "output_path": final_path,
        "num_detections": len(prediction_log.get(user_session_id, []))
    }

TIMESTAMP_REGEX = re.compile(r"^(\d{4}-\d{2}-\d{2}) (\d{6})")

def extract_timestamp(filename: str) -> datetime:
    # Strip directory path
    base = os.path.basename(filename)

    match = TIMESTAMP_REGEX.match(base)
    if not match:
        raise ValueError(f"Filename does not match expected format: {filename}")

    date_part = match.group(1)   # YYYY-MM-DD
    time_part = match.group(2)   # HHmmss

    return datetime.strptime(f"{date_part} {time_part}", "%Y-%m-%d %H%M%S")

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
    ax.set_yticks(list(label_map.values()))
    ax.set_yticklabels(list(label_map.keys()))
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
    ax.set_xticks(range(len(car_counts)))
    ax.set_xticklabels(car_counts.index, rotation=20, ha='right')

    return fig

def plot_confidence_distribution(fileDirectory : str):
    if fileDirectory not in prediction_log or not prediction_log[fileDirectory]:
        return None

    df = pd.DataFrame(prediction_log[fileDirectory])

    fig, ax = plt.subplots()
    ax.hist(df["confidence"], bins=20)

    ax.set_xlabel("Confidence")
    ax.set_ylabel("Frequency")

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
    ax.set_xticks(range(len(avg_conf)))
    ax.set_xticklabels(avg_conf.index, rotation=20, ha='right')
    #ax.set_title("Average Confidence per Class")

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

# plot all predictions found per image
def plot_multiple_prediction_timeline(fileDirectory : str):
    if fileDirectory not in prediction_log or not prediction_log[fileDirectory]:
        return None

    df = pd.DataFrame(prediction_log[fileDirectory])

    # count each label per image
    counts = df.groupby(["filename", "label"]).size().unstack(fill_value=0)

    fig, ax = plt.subplots()

    for label in counts.columns:
        ax.plot(range(len(counts.index)), counts[label], marker="o", label=label)

    ax.set_xlabel("Image Order")
    ax.set_ylabel("Detections")
    ax.legend()

    return fig

### get patterns from detections ###

# get patterns like 3+ in a row of the same type of car

def get_repetition_patterns(fileDirectory : str):
    if fileDirectory not in prediction_log or not prediction_log[fileDirectory]:
        return None

    df = pd.DataFrame(prediction_log[fileDirectory])

    labels = df["label"].tolist()

    patterns = []
    current_label = labels[0]
    count = 1
    start_index = 0

    for i in range(1, len(labels)):
        if labels[i] == current_label:
            count += 1
        else:
            if count >= 3:
                patterns.append({
                    "label": current_label,
                    "count": count,
                    "start_index": start_index,
                    "end_index": i - 1
                })
            current_label = labels[i]
            count = 1
            start_index = i

    # final check
    if count >= 3:
        patterns.append({
            "label": current_label,
            "count": count,
            "start_index": start_index,
            "end_index": len(labels) - 1
        })

    return patterns


def plot_repetition_patterns(fileDirectory : str):
    patterns = get_repetition_patterns(fileDirectory)

    if not patterns:
        return None

    fig, ax = plt.subplots()

    y_labels = []
    y_pos = []

    for i, p in enumerate(patterns):
        ax.barh(i, p["count"], left=p["start_index"])
        y_labels.append(p["label"])
        y_pos.append(i)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(y_labels)
    ax.set_xlabel("Timeline Index")
    ax.set_ylabel("Repeated Car Type")
    #ax.set_title("Repetition Patterns (3+ in a Row)")
    fig.tight_layout()

    return fig


# patterns over course of time.
# ie same type of car at the same time of day
# ex: theres an suv roughly every 3 photos

def get_occurrence_patterns(fileDirectory : str):
    if fileDirectory not in prediction_log or not prediction_log[fileDirectory]:
        return None

    df = pd.DataFrame(prediction_log[fileDirectory])

    df["timestamp"] = df["filename"].apply(extract_timestamp)
    df = df.sort_values("timestamp")

    results = {}

    for label in df["label"].unique():
        times = df[df["label"] == label]["timestamp"].values

        if len(times) < 3:
            continue

        gaps = np.diff(times).astype('timedelta64[m]').astype(int)

        if len(gaps) == 0:
            continue

        avg_gap = round(np.mean(gaps), 2)

        results[label] = {
            "occurrences": len(times),
            "average_gap": avg_gap,
            "indices": times.tolist(),
            "names": df[df["label"] == label]["filename"].values.tolist()
        }

    return results

def get_page_format_occurrence(fileDirectory: str):
    patterns = get_occurrence_patterns(fileDirectory)

    if patterns is None:
        return []

    output = []

    for i, (label, data) in enumerate(patterns.items()):
        frames = []

        for name, item in zip(data["names"], data["indices"]):
            ts = pd.to_datetime(item).to_pydatetime()

            frames.append({
                "timestamp": ts.isoformat(),
                "url": f"/results/{name}"
            })

        # Sort frames per pattern
        frames.sort(key=lambda x: x["timestamp"])

        output.append({
            "id": f"pattern_{i}",
            "name": label,
            "description": f"{label} detected {data['occurrences']} times",
            "tags": ["recurring"],  # you can refine this later
            "frames": frames
        })

    return output

def plot_occurrence_patterns(fileDirectory : str):
    patterns = get_occurrence_patterns(fileDirectory)

    if not patterns:
        return None

    labels = list(patterns.keys())
    counts = [patterns[x]["occurrences"] for x in labels]
    gaps = [patterns[x]["average_gap"] for x in labels]

    fig, ax1 = plt.subplots()

    ax1.bar(labels, counts)
    ax1.set_ylabel("Occurrences")
    ax1.set_xlabel("Car Type")

    ax2 = ax1.twinx()
    ax2.plot(labels, gaps, marker="o")
    ax2.set_ylabel("Average Gap")

    #ax1.set_title("Occurrence Patterns")
    fig.tight_layout()

    return fig

def plot_occurrence_timeline(fileDirectory : str):
    patterns = get_occurrence_patterns(fileDirectory)

    if not patterns:
        return None

    fig, ax = plt.subplots()

    labels = list(patterns.keys())

    for i, label in enumerate(labels):
        x = patterns[label]["indices"]
        y = [i] * len(x)
        ax.scatter(x, y, s=80, label=label)

    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels)
    ax.set_xlabel("Timeline Index")
    ax.set_ylabel("Car Type")
    #ax.set_title("Occurrence Positions")
    ax.legend()

    return fig

# patterns like the same sequence occuring multiple times in a row
# ie same sequecne of van suv tuck over and over
# or hackback pickup over and over

def get_sequential_patterns(fileDirectory : str):
    if fileDirectory not in prediction_log or not prediction_log[fileDirectory]:
        return None

    df = pd.DataFrame(prediction_log[fileDirectory])

    labels = df["label"].tolist()

    found_patterns = []

    max_len = min(5, len(labels) // 2)

    for seq_len in range(2, max_len + 1):
        seen = {}

        for i in range(len(labels) - seq_len + 1):
            seq = tuple(labels[i:i + seq_len])

            if seq not in seen:
                seen[seq] = []

            seen[seq].append(i)

        for seq, positions in seen.items():
            if len(positions) >= 2:
                found_patterns.append({
                    "sequence": list(seq),
                    "count": len(positions),
                    "positions": positions
                })

    return found_patterns

def plot_sequential_patterns(fileDirectory : str):
    patterns = get_sequential_patterns(fileDirectory)

    if not patterns:
        return None

    # keep top 10 most common
    patterns = sorted(patterns, key=lambda x: x["count"], reverse=True)[:10]

    labels = [" -> ".join(p["sequence"]) for p in patterns]
    counts = [p["count"] for p in patterns]

    fig, ax = plt.subplots(figsize=(10,6))

    ax.barh(range(len(labels)), counts)

    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels)
    ax.set_xlabel("Times Repeated")
    #ax.set_title("Top Sequential Patterns")

    return fig

def plot_sequential_timeline(fileDirectory : str):
    patterns = get_sequential_patterns(fileDirectory)

    if not patterns:
        return None

    patterns = sorted(patterns, key=lambda x: x["count"], reverse=True)[:8]

    fig, ax = plt.subplots(figsize=(10,6))

    for i, p in enumerate(patterns):
        ax.scatter(
            p["positions"],
            [i] * len(p["positions"]),
            s=80
        )

    return fig

def export_predictions(fileDirectory : str):
    output = StringIO()
    df = pd.DataFrame(prediction_log[fileDirectory])
    df.to_csv(output, index=False)
    output.seek(0)
    return output.getvalue()

def build_time_series(label_df: pd.DataFrame, bin_minutes: int = 15):
    """
    Converts detections into a binned time series.
    Returns the series array and the bin edges as timestamps.
    """
    origin = label_df["timestamp"].min()
    end = label_df["timestamp"].max()

    total_minutes = (end - origin).total_seconds() / 60
    num_bins = int(total_minutes / bin_minutes) + 1

    series = np.zeros(num_bins)

    for _, row in label_df.iterrows():
        minutes = (row["timestamp"] - origin).total_seconds() / 60
        bin_idx = int(minutes / bin_minutes)
        series[bin_idx] += 1

    return series, origin, bin_minutes

def find_recurrence_periods(series, bin_minutes: int, min_period_minutes: int = 30):

    # Normalize
    s = series - series.mean()

    # Full autocorrelation
    autocorr = np.correlate(s, s, mode="full")
    autocorr = autocorr[len(autocorr) // 2:]  # keep positive lags only
    autocorr /= autocorr[0]                   # normalize to 1.0 at lag 0

    # Smooth to reduce noise
    autocorr_smooth = gaussian_filter1d(autocorr, sigma=2)

    # Find peaks — each peak is a candidate period
    min_lag = max(1, min_period_minutes // bin_minutes)
    peaks, props = find_peaks(autocorr_smooth, height=0.1, distance=min_lag)

    periods = []
    for peak in peaks:
        period_minutes = peak * bin_minutes
        strength = float(autocorr_smooth[peak])
        periods.append({
            "period_minutes": period_minutes,
            "period_label": format_period(period_minutes),
            "strength": round(strength, 3),  # 0.0-1.0, higher = stronger pattern
        })

    # Sort by strength descending
    periods.sort(key=lambda x: -x["strength"])
    return periods, autocorr_smooth

def format_period(minutes: int) -> str:
    """Human readable period label."""
    if minutes < 60:
        return f"{minutes}min"
    elif minutes < 1440:
        hours = round(minutes / 60, 1)
        return f"{hours}hr"
    elif minutes < 10080:
        days = round(minutes / 1440, 1)
        return f"{days}d"
    else:
        weeks = round(minutes / 10080, 1)
        return f"{weeks}wk"

def get_occurrences_for_period(label_df: pd.DataFrame, period_minutes: int, window_minutes: int = -1):
    if window_minutes < 0:
        window_minutes = max(15, int(period_minutes * 0.10))

    label_df = label_df.sort_values("timestamp").reset_index(drop=True)
    timestamps = label_df["timestamp"].values
    abs_minutes = label_df["abs_minutes"].values

    visited = np.zeros(len(label_df), dtype=bool)
    groups = []

    for i in range(len(label_df)):
        if visited[i]:
            continue

        group_indices = [i]
        visited[i] = True

        # Walk forward and find detections that are at N * period away
        # (N=1,2,3... — allows missed cycles)
        last_anchor = abs_minutes[i]

        for j in range(i + 1, len(label_df)):
            if visited[j]:
                continue

            gap = abs_minutes[j] - abs_minutes[i]

            # Is this gap a multiple of the period (within tolerance)?
            nearest_multiple = round(gap / period_minutes)
            if nearest_multiple == 0:
                continue

            expected = nearest_multiple * period_minutes
            deviation = abs(gap - expected)

            if deviation <= window_minutes:
                group_indices.append(j)
                visited[j] = True

        if len(group_indices) >= 2:
            group_df = label_df.iloc[group_indices]
            groups.append({
                "timestamps": group_df["timestamp"].tolist(),
                "filenames": group_df["filename"].tolist(),
                "count": len(group_indices),
            })

    return groups


def get_time_patterns(fileDirectory: str, bin_minutes: int = 15, min_occurrences: int = 2):
    if fileDirectory not in prediction_log or not prediction_log[fileDirectory]:
        return None

    df = pd.DataFrame(prediction_log[fileDirectory])
    df["timestamp"] = df["filename"].apply(extract_timestamp)
    df = df.sort_values("timestamp")

    origin = df["timestamp"].min()
    df["abs_minutes"] = (df["timestamp"] - origin).dt.total_seconds() / 60

    results = {}

    for label in df["label"].unique():
        label_df = df[df["label"] == label].copy()

        if len(label_df) < min_occurrences:
            continue

        series, origin_ts, bin_min = build_time_series(label_df, bin_minutes)
        periods, autocorr = find_recurrence_periods(series, bin_min)

        if not periods:
            continue

        label_patterns = []

        for period in periods:
            groups = get_occurrences_for_period(label_df, period["period_minutes"])

            if not groups:
                continue

            # Predict next occurrence for each group
            for group in groups:
                last_seen = max(group["timestamps"])
                next_occurrence = last_seen + pd.Timedelta(minutes=period["period_minutes"])

                group["predicted_next"] = next_occurrence.isoformat()
                group["last_seen"] = last_seen.isoformat()

            label_patterns.append({
                "period": period["period_label"],
                "period_minutes": period["period_minutes"],
                "strength": period["strength"],
                "groups": groups,
            })

        results[label] = {
            "patterns": label_patterns,
            "autocorr": autocorr.tolist(),
        }

    return results

def get_page_format_patterns(fileDirectory: str, bin_minutes: int = 15, min_occurrences: int = 2):
    """
    Converts get_time_patterns() output into the format expected by patterns.html.
    Each detected period per vehicle becomes its own pattern card in the sidebar.
    """
    raw = get_time_patterns(fileDirectory, bin_minutes=bin_minutes, min_occurrences=min_occurrences)

    if not raw:
        return []

    output = []
    pattern_index = 0

    for label, data in raw.items():
        for period_data in data["patterns"]:
            period_label = period_data["period"]
            strength = period_data["strength"]
            total_occurrences = sum(g["count"] for g in period_data["groups"])

            # Flatten all frames across groups, sorted by timestamp
            frames = []
            for group in period_data["groups"]:
                for ts, fname in zip(group["timestamps"], group["filenames"]):
                    frames.append({
                        "timestamp": pd.Timestamp(ts).isoformat(),
                        "url": f"/results/{fname}"
                    })

            frames.sort(key=lambda x: x["timestamp"])

            if not frames:
                continue

            # Confidence label for tags
            if strength >= 0.6:
                confidence_tag = "high"
            elif strength >= 0.3:
                confidence_tag = "medium"
            else:
                confidence_tag = "low"

            output.append({
                "id": f"pattern_{pattern_index}",
                "name": f"{label} — every {period_label}",
                "description": f"{label} detected {total_occurrences} times on a {period_label} cycle",
                "tags": ["recurring", confidence_tag],
                "frames": frames,
                # Extra data available in JS via data-frames if you want to use it later
                "predicted_next": period_data["groups"][-1].get("predicted_next"),
            })

            pattern_index += 1

    # Sort strongest patterns first
    output.sort(key=lambda x: x["frames"].__len__(), reverse=True)
    return output