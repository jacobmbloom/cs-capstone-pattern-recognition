from ultralytics import YOLO
import cv2
import numpy as np
import tensorflow as tf


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

img = cv2.imread("capstone_test.png")
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

            confidence = np.max(prediction)

            print(prediction)

            if confidence > 0.8:
                cv2.rectangle(img_rgb, (x1, y1), (x2, y2), (0,255,0), 3)

cv2.imshow("Cars", cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR))
cv2.waitKey(0)
cv2.destroyAllWindows()