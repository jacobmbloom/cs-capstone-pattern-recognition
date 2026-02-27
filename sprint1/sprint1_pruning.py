import pandas as pd
import numpy as np
import tensorflow as tf
from tensorflow import data as tf_data
import keras
from keras import layers, models
from keras.layers import Dense
from keras.models import Sequential
import matplotlib.pyplot as plt
import tempfile
import os
import zipfile
import tensorflow_model_optimization as tfmot


#### HYPERPARAMS / VARS

train_data_directory ="Cars_Body_Type/train"
test_data_directory ="Cars_Body_Type/test"

image_height = 224
image_width = 224
image_size = 224
batch_size = 32


epochs = 5
prune_epochs = 5
batch_size = 128
val_split = 0.1


#### HELPER FUNCTIONS

def get_file_size(file):
    return os.path.getsize(file)

def convert_float32_tflite(model):
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    tflite_model = converter.convert()

    file = tempfile.mktemp('.tflite')
    with open(file, 'wb') as f:
        f.write(tflite_model)

    return file

def convert_int8_tflite(model, representative_data):
    converter = tf.lite.TFLiteConverter.from_keras_model(model)

    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.representative_dataset = representative_data

    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    converter.inference_input_type = tf.int8
    converter.inference_output_type = tf.int8

    tflite_model = converter.convert()

    file = tempfile.mktemp('.tflite')
    with open(file, 'wb') as f:
        f.write(tflite_model)

    return file

def convert_qat_tflite(model):
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    tflite_model = converter.convert()

    fd, file = tempfile.mkstemp(suffix='.tflite')
    os.close(fd)
    with open(file, 'wb') as f:
        f.write(tflite_model)
    return file


def evaluate_tflite_model(tflite_file, test_images, test_labels):
    # Load TFLite model
    interpreter = tf.lite.Interpreter(model_path=tflite_file)
    interpreter.allocate_tensors()

    input_index = interpreter.get_input_details()[0]['index']
    output_index = interpreter.get_output_details()[0]['index']

    correct = 0
    total = len(test_images)

    for i in range(total):
        img = test_images[i:i+1]
        img = img.astype(np.float32) / 255.0
        # INT8 models expect int8 input, so scale if needed
        input_details = interpreter.get_input_details()[0]
        if input_details['dtype'] == np.int8:
            scale, zero_point = input_details['quantization']
            img = img / scale + zero_point
            img = img.astype(np.int8)

        interpreter.set_tensor(input_index, img)
        interpreter.invoke()
        output = interpreter.get_tensor(output_index)

        pred = np.argmax(output, axis=1)[0]
        if pred == test_labels[i]:
            correct += 1

    return correct / total


def representative_dataset():
    for i in range(100):
        yield [test_images[i:i+1]]


#### load dataset
valid_ds = tf.keras.utils.image_dataset_from_directory(
    train_data_directory,
    seed=123,
    image_size=(image_height, image_width),
    batch_size=batch_size,
    label_mode="int"
)

# normalize data
rescaler = layers.Rescaling(1./255, input_shape=(image_size,image_size,3))
valid_ds = valid_ds.map(lambda x, y: (rescaler(x), y))

# convert dataset to arrays for functions
test_images = []
test_labels = []

for images, labels in valid_ds:
    test_images.append(images.numpy())
    test_labels.append(labels.numpy())

test_images = np.concatenate(test_images, axis=0)
test_labels = np.concatenate(test_labels, axis=0)


# load previously saved model for testing, pruning, and quantization
model_base = tf.keras.models.load_model("base2.keras", compile=False)
model_base.summary()


model_base.compile(optimizer='adam', loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True), metrics=['accuracy'])

loss, accuracy = model_base.evaluate(valid_ds)
print("test accuracy: ", accuracy)

prune_low_magnitude = tfmot.sparsity.keras.prune_low_magnitude

steps_per_epoch = np.ceil(len(test_images) / batch_size)
end_step = steps_per_epoch * epochs

pruning_params = {
    'pruning_schedule': tfmot.sparsity.keras.PolynomialDecay(
        initial_sparsity=0.90,
        final_sparsity=0.95,
        begin_step=0,
        end_step=end_step
    )
}

#create a new model, that can be pruned, based on the OLD model + the prune params
model_pruned = prune_low_magnitude(model_base, **pruning_params)

#compile new model again before training
model_pruned.compile(
    optimizer='adam',
    loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True),
    metrics=['accuracy']
)

callbacks = [tfmot.sparsity.keras.UpdatePruningStep()]

print("----------------- FIT PRUNING MODEL -----------")

#Fine tuning
model_pruned.fit(test_images, test_labels,
                 batch_size=batch_size,
                 epochs=prune_epochs,
                 validation_split=val_split,
                 callbacks=callbacks)

#Strip away pruned coponents
model_pruned = tfmot.sparsity.keras.strip_pruning(model_pruned)

# RECOMPILE AFTER STRIPPING
model_pruned.compile(
    optimizer='adam',
    loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True),
    metrics=['accuracy']
)

_, pruned_accuracy = model_pruned.evaluate(test_images, test_labels)
model_pruned.save("pruned.keras")

##################################
# Convert Models to TFLite
##################################
# FLOAT32 versions
baseline_tflite = convert_float32_tflite(model_base)
pruned_tflite = convert_float32_tflite(model_pruned)

# FULL INT8 versions
baseline_int8_tflite = convert_int8_tflite(model_base, representative_dataset)
pruned_int8_tflite = convert_int8_tflite(model_pruned, representative_dataset)


# QUANTIZATION
# Apply QAT on pruned model
model_qat = tfmot.quantization.keras.quantize_model(model_pruned)

model_qat.compile(
    optimizer='adam',
    loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True),
    metrics=['accuracy']
)


print("----------------- FIT QAT MODEL -----------")

# Fine-tune QAT model (short training is usually enough)
model_qat.fit(
    test_images, test_labels,
    batch_size=batch_size,
    epochs=epochs,
    validation_split=val_split
)

# Evaluate QAT model
_, qat_accuracy = model_qat.evaluate(test_images, test_labels)
model_qat.save("qat.keras")

qat_int8_tflite = convert_qat_tflite(model_qat)

##################################
# Compare Accuracy
##################################

baseline_accuracy = accuracy
print("\n========== MODEL ACCURACY ==========")
print("Baseline Accuracy:", baseline_accuracy)
print("Pruned Accuracy:", pruned_accuracy)
print("QAT Model Accuracy:", qat_accuracy)

##################################
# Compare Sizes
##################################

print("\n========== TFLITE MODEL SIZES ==========")
print("Baseline FLOAT32:", get_file_size(baseline_tflite))
print("Pruned FLOAT32:", get_file_size(pruned_tflite))
print("Baseline INT8:", get_file_size(baseline_int8_tflite))
print("Pruned INT8:", get_file_size(pruned_int8_tflite))
print("QAT INT8 TFLite Size:", get_file_size(qat_int8_tflite))


print("\n========== TFLITE MODEL ACCURACY ==========")


pruned_int8_accuracy = evaluate_tflite_model(pruned_int8_tflite, test_images, test_labels)
print("Pruned INT8 TFLite Accuracy (No QAT):", pruned_int8_accuracy)

qat_int8_tflite_accuracy = evaluate_tflite_model(qat_int8_tflite, test_images, test_labels)
print("QAT INT8 TFLite Accuracy (No QAT):", qat_int8_tflite_accuracy)