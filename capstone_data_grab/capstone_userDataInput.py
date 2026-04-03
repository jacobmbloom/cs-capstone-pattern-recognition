import os
import cv2

UNLABELED_DIR = "dataset/unlabeled"

# Setting (1000 was pretty small on my pc, not sure if it will be the same for others since its based on screenshots which can be a little dynamic)
min_crop_size = 1000

# Globals for mouse callback
points = []
current_img = None
display_img = None

def mouse_click(event, x, y, flags, param):
    global points, display_img

    if event == cv2.EVENT_LBUTTONDOWN:
        if len(points) < 2:
            points.append((x, y))

        # Draw points / rectangle preview
        display_img = current_img.copy()

        # Draw points
        for p in points:
            cv2.circle(display_img, p, 5, (0, 255, 0), -1)

        # Draw rectangle if 2 points
        if len(points) == 2:
            cv2.rectangle(display_img, points[0], points[1], (0, 255, 0), 2)

        cv2.imshow("Image", display_img)

# Grab all files starting with full_img_
files = []
for f in os.listdir(UNLABELED_DIR):
    if f.startswith("full_img_"):
        files.apnpend(f)

for filename in files:
    # Get the image, convert to cv2
    filepath = os.path.join(UNLABELED_DIR, filename)
    img = cv2.imread(filepath)

    if img is None:
        print(f"Skipping invalid image: {filename}")
        continue

    # Copy img to use for return if someone gives points (I wanted to keep the lines off other cars)
    current_img = img
    display_img = img.copy()
    points = []

    cv2.namedWindow("Image")
    cv2.setMouseCallback("Image", mouse_click)

    print(f"\nProcessing: {filename}")
    print("Instructions:")
    print("- Click 2 points (Top-Left, Bottom-Right)")
    print("- Press 's' to save crop")
    print("- Press 'n' for next image")
    print("- Press 'r' to reset points")
    print("- Press 'q' to quit")

    while True:
        # Show the Image
        cv2.imshow("Image", display_img)
        key = cv2.waitKey(1) & 0xFF

        # Quit program
        if key == ord('q'):
            print("Quitting...")
            cv2.destroyAllWindows()
            exit()

        # Reset points
        elif key == ord('r'):
            points = []
            display_img = current_img.copy()

        # Save crop
        elif key == ord('s'):
            if len(points) == 2:
                (x1, y1), (x2, y2) = points

                # Ensure proper ordering
                x_min, x_max = sorted([x1, x2])
                y_min, y_max = sorted([y1, y2])

                crop = current_img[y_min:y_max, x_min:x_max]

                # Check if box is big enough (too small won't have good results later)
                if crop.size <= min_crop_size:
                    print("Invalid crop, try again.")
                    continue

                # Generate filename
                base_name = os.path.splitext(filename)[0]

                # Remove the full img tag so the other stuff works with the new imgs
                base_name = base_name[len("full_img_"):]

                existing = [f for f in os.listdir(UNLABELED_DIR) if f.startswith(base_name + "_crop")]
                crop_id = len(existing)

                save_name = f"{base_name}_crop_{crop_id}.png"
                save_path = os.path.join(UNLABELED_DIR, save_name)

                cv2.imwrite(save_path, crop)
                print(f"Saved: {save_name}")

                # Reset for next box
                points = []
                display_img = current_img.copy()
            else:
                print("Need exactly 2 points.")

        # Next image
        elif key == ord('n'):
            break

    cv2.destroyAllWindows()
