import os
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


img_path = input("Enter path to image: ").strip()

if not os.path.exists(img_path):
    raise FileNotFoundError("Image path is invalid.")

img = cv2.imread(img_path)
img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
img = cv2.resize(img, (244, 244))
img = img.astype(np.float32) / 255.0
img = np.expand_dims(img, axis=0)


# Load Pruned Model

model = tf.keras.models.load_model('pruned.keras')
prediction = model.predict(img)

predicted_index = np.argmax(prediction, axis=1)[0]
predicted_class = class_names[predicted_index]
confidence = float(np.max(prediction))

print(f"Predicted class: {predicted_class}")
print(f"Confidence: {confidence:.4f}")

# Load TFLite model
'''
interpreter = tf.lite.Interpreter(model_path="qat_8int.tflite")
interpreter.allocate_tensors()

input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()

# If model expects INT8 input
if input_details[0]['dtype'] == np.int8:
    scale, zero_point = input_details[0]['quantization']
    img = img / scale + zero_point
    img = img.astype(np.int8)

# Run inference
interpreter.set_tensor(input_details[0]['index'], img)
interpreter.invoke()

output = interpreter.get_tensor(output_details[0]['index'])
prediction = np.argmax(output)

print("Predicted class:", class_names[prediction])

'''
