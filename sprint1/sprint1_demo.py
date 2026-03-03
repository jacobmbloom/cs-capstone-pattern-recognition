import cv2
import numpy as np
import os
import tensorflow as tf
from tensorflow.keras import models
import tensorflow_model_optimization as tfmot


# =========================
# Load Image
# =========================
img_path = input("Enter path to image: ").strip()

if not os.path.exists(img_path):
    raise FileNotFoundError("Image path is invalid.")

img1 = cv2.imread(img_path)

if img1 is None:
    raise ValueError("Failed to load image.")

frame_out = img1.copy()


# =========================
# Background Subtraction
# =========================
backSub = cv2.createBackgroundSubtractorMOG2()
kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))

fg_mask = backSub.apply(img1)
_, mask_thresh = cv2.threshold(fg_mask, 180, 255, cv2.THRESH_BINARY)
mask_clean = cv2.morphologyEx(mask_thresh, cv2.MORPH_OPEN, kernel)

contours, _ = cv2.findContours(mask_clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)


# =========================
# Load QAT Model Properly
# =========================
with tfmot.quantization.keras.quantize_scope():
    model = models.load_model('qat.keras', compile=False)

print("Model loaded successfully.")
print("Model input shape:", model.input_shape)


# =========================
# Detection Loop
# =========================
min_contour_area = 1000
max_detections = 20
count = 0

for cont in contours:
    if count >= max_detections:
        break

    if cv2.contourArea(cont) > min_contour_area:

        x, y, w, h = cv2.boundingRect(cont)
        roi = img1[y:y+h, x:x+w]

        if roi.size < 50:
            continue

        count += 1

        # -------------------------
        # Preprocess ROI for model
        # -------------------------
        input_h = model.input_shape[1]
        input_w = model.input_shape[2]

        roi_resized = cv2.resize(roi, (input_w, input_h))
        roi_resized = roi_resized.astype("float32") / 255.0
        roi_resized = np.expand_dims(roi_resized, axis=0)

        # -------------------------
        # Predict
        # -------------------------
        prediction = model.predict(roi_resized, verbose=0)

        class_id = np.argmax(prediction)
        confidence = float(np.max(prediction))

        label = f"Class {class_id}: {confidence:.2f}"

        # -------------------------
        # Draw Bounding Box
        # -------------------------
        x1, y1 = x, y
        x2, y2 = x + w, y + h

        cv2.rectangle(frame_out, (x1, y1), (x2, y2), (0, 0, 255), 2)
        cv2.putText(frame_out, label,
                    (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 0, 255),
                    2)


# =========================
# Show Result
# =========================
cv2.imshow("Result", frame_out)
cv2.waitKey(0)
cv2.destroyAllWindows()