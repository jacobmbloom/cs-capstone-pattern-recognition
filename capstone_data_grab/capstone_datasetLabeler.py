import os
import cv2
import shutil

# Paths
UNLABELED_DIR = "dataset/unlabeled"
TRAINING_DIR = "dataset/training"

# Label mapping (key press -> folder name)
LABELS = {
    ord('v'): 'VAN',
    ord('u'): 'SUV',
    ord('m'): 'SEMI',
    ord('t'): 'TRUCK',
    ord('s'): 'SEDAN'
}

# Makes sure directories are made for training (creates them if not)
for label in LABELS.values():
    path = os.path.join(TRAINING_DIR, label)
    os.makedirs(path, exist_ok=True)

# Get files from unlabeled folder
files = os.listdir(UNLABELED_DIR)

for filename in files:
    # Skip files starting with full_img
    # These hold which cars in each img are not found so they can be manually grabbed later without repeats
    if filename.startswith("full_img"):
        continue

    filepath = os.path.join(UNLABELED_DIR, filename)

    # Try to read image
    img = cv2.imread(filepath)
    if img is None:
        print(f"Skipping non-image file: {filename}")
        continue

    # Show image
    cv2.imshow("Image", img)
    print(f"\nLabeling: {filename}")
    print("Press key: [v]=VAN [u]=SUV [m]=SEMI [t]=TRUCK [s]=SEDAN [q]=quit [k]=skip")

    key = cv2.waitKey(0)

    # Quit
    if key == ord('q'):
        print("Quitting...")
        break

    # Skip
    if key == ord('k'):
        print("Skipped")
        continue

    # Label
    if key in LABELS:
        label = LABELS[key]
        dest_dir = os.path.join(TRAINING_DIR, label)
        dest_path = os.path.join(dest_dir, filename)

        shutil.move(filepath, dest_path)
        print(f"Moved to {label}")
    else:
        print("Invalid key, skipping...")

cv2.destroyAllWindows()

