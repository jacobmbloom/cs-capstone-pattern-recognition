# Data from this could be used to show yolo baseline as well

import pyscreenshot
import cv2
import numpy as np
import os
from ultralytics import YOLO
import time

# Settings
TOTAL_RUNTIME = 3000
SCREENSHOT_INTERVAL = 10

# Load model
model = YOLO("yolov8n.pt")

# Class filter
vehicle_classes = {
    2: "car",
    5: "bus",
    7: "truck"
}

# Save path (unlabeled)
save_dir = "dataset/unlabeled"
os.makedirs(save_dir, exist_ok=True)

# Timer
start_time = time.time()

while True:
    if time.time() - start_time > TOTAL_RUNTIME:
        break

    print("Capturing screen...")

    # Take screenshot might be different for your pc (x1, y1, x2, y2), top left bottom right
    image = pyscreenshot.grab(bbox=(150, 150, 1500, 1000))
    image_np = np.array(image)

    # Copy for drawing
    display_img = image_np.copy()

    # Run detection
    results = model(image_np, verbose=False)

    for result in results:
        for box in result.boxes:
            # Get the box as a map
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            conf = float(box.conf[0])
            cls = int(box.cls[0])

            # Determine if it's a car or not
            if cls in vehicle_classes and conf > 0.5:
                label_name = vehicle_classes[cls]
                print(f"Detected {label_name} ({conf:.2f})")

                # IMG Bounds
                h, w, _ = image_np.shape
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w, x2), min(h, y2)

                crop = image_np[y1:y2, x1:x2]

                if crop.size == 0:
                    continue

                # Save boxed image
                filename = os.path.join(
                    save_dir, f"{int(time.time()*1000)}.png"
                )
                cv2.imwrite(filename, crop)

                # Draw bounding box on full image
                cv2.rectangle(display_img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(display_img,
                            f"{label_name} {conf:.2f}",
                            (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.6,
                            (0, 255, 0),
                            2)
    # Save the full image
    filename = os.path.join(
        save_dir, f"full_img_{int(time.time() * 1000)}.png"
    )
    cv2.imwrite(filename, display_img)

    # Show full screenshot with boxes
    cv2.imshow("Detections", display_img)

    cv2.waitKey(2000)
    cv2.destroyAllWindows()
    time.sleep(SCREENSHOT_INTERVAL)

cv2.destroyAllWindows()