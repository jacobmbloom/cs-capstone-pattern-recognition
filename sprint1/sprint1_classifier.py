#import os
#import cv2
import numpy as np
import tensorflow as tf
from tensorflow.keras.utils import image_dataset_from_directory
from keras import layers
import matplotlib.pyplot as plt
from keras.models import Sequential
from os import listdir
from PIL import Image
import keras


#----------------------------------------------------
# vars and hyperparameters
#----------------------------------------------------
train_data_directory ="Cars_Body_Type/train"
test_data_directory ="Cars_Body_Type/test"
valid_data_directory ="Cars_Body_Type/valid"

image_size = 224
batch_size = 32
seed = 123
epochs = 150


#----------------------------------------------------
# open datasets
#----------------------------------------------------

train_ds = image_dataset_from_directory(
    train_data_directory,
    image_size=(image_size,image_size),
    batch_size=batch_size
)

test_ds = image_dataset_from_directory(
    test_data_directory,
    image_size=(image_size,image_size),
    batch_size=batch_size
)

valid_ds = image_dataset_from_directory(
    valid_data_directory,
    image_size=(image_size,image_size),
    batch_size=batch_size
)


#----------------------------------------------------
# visualize data pre normalizing
#----------------------------------------------------
'''
plt.figure(figsize=(10, 10))
for images, labels in train_ds.take(1):
    for i in range(9):
        ax = plt.subplot(3, 3, i + 1)
        plt.imshow(np.array(images[i]).astype("uint8"))
        plt.title(int(labels[i]))
        plt.axis("off")
plt.show()
'''
#----------------------------------------------------
# create data augmentation layer to get a larger dataset if needed
#----------------------------------------------------

data_augmentation_layers = [
    layers.RandomFlip("horizontal"),
    layers.RandomRotation(0.1),
]


def data_augmentation(images):
    for layer in data_augmentation_layers:
        images = layer(images)
    return images


#----------------------------------------------------
# test data augmentation with visualization
#----------------------------------------------------
'''
plt.figure(figsize=(10, 10))
for images, _ in train_ds.take(1):
    for i in range(9):
        augmented_images = data_augmentation(images)
        ax = plt.subplot(3, 3, i + 1)
        plt.imshow(np.array(augmented_images[0]).astype("uint8"))
        plt.axis("off")
plt.show()
'''
#----------------------------------------------------
# apply data augmentation to our image dataset
#----------------------------------------------------

augmented_ds = train_ds.map(lambda x, y: (data_augmentation(x), y))


#----------------------------------------------------
# normalizing images
#----------------------------------------------------

rescaler = layers.Rescaling(1./255)

# for training can either use augmented ds for larger dataset, or just regular train ds
augmented_ds = augmented_ds.map(lambda x, y: (rescaler(x), y))
train_ds = train_ds.map(lambda x, y: (rescaler(x), y))
test_ds = test_ds.map(lambda x, y: (rescaler(x), y))
valid_ds = valid_ds.map(lambda x, y: (rescaler(x), y))


#----------------------------------------------------
# filter corrupted images
#----------------------------------------------------

def corrupt_checker(directory):
    for filename in listdir(directory):
        if filename.endswith('.jpg'):
            try:
                img = Image.open("./"+filename)
                img.verify()
            except (IOError, SyntaxError) as e:
                print("bad file: " + filename + " with error: " + e)

corrupt_checker(train_data_directory)
corrupt_checker(test_data_directory)
corrupt_checker(valid_data_directory)


#----------------------------------------------------
# build our model
#----------------------------------------------------

model = Sequential([
    #normalization layer (commented out since this layer breaks pruning)
    #layers.Rescaling(1./255, input_shape=(image_size,image_size,3)),
    layers.Input(shape=(image_size, image_size, 3)),


    layers.Conv2D(32, 3, activation='relu'),
    layers.MaxPooling2D(),

    layers.Conv2D(64, 3, activation='relu'),
    layers.MaxPooling2D(),

    layers.Conv2D(128, 3, activation='relu'),
    layers.MaxPooling2D(),

    layers.Conv2D(256, 3, activation='relu'),

    #layers.Flatten(),
    # pooling layer instead of flatten for less features and hopfully overfitting
    layers.GlobalAveragePooling2D(),


    layers.Dense(128, activation='relu'),

    # dropout layer
    layers.Dropout(0.4),


    layers.Dense(7, activation="softmax")
])

model.compile(optimizer=tf.keras.optimizers.Nadam(learning_rate=0.002), loss=tf.keras.losses.SparseCategoricalCrossentropy(), metrics=['accuracy'])

model.summary()

#----------------------------------------------------
# fit model to train_ds, after try fitting with augmented_ds to see if we get any better results
# also display model results as test accuracy versus validation accuracy
#----------------------------------------------------

history = model.fit(train_ds, epochs=epochs, validation_data=valid_ds)

plt.figure(figsize=(10, 10))
plt.plot(history.history['accuracy'], label='accuracy')
plt.plot(history.history['val_accuracy'], label = 'val_accuracy')
plt.xlabel('Epoch')
plt.ylabel('Accuracy')
plt.ylim([0.5, 1])
plt.legend(loc='lower right')
plt.show()

test_loss, test_acc = model.evaluate(train_ds, verbose=2)

#----------------------------------------------------
# save models
#----------------------------------------------------

model.save('sprint1_test1.keras')

# Convert to TFLite with optimization
converter = tf.lite.TFLiteConverter.from_keras_model(model)
converter.optimizations = [tf.lite.Optimize.DEFAULT]

tflite_model = converter.convert()

with open("sprint1_test1.tflite", "wb") as f:
    f.write(tflite_model)

print("Saved sprint1_test1 as keras and tflite files")


#----------------------------------------------------
# test model on a single image and get percentage per class
#----------------------------------------------------
'''
img = keras.utils.load_img("cer_test.jpg", target_size=image_size)
plt.imshow(img)

img_array = keras.utils.img_to_array(img)
img_array = img_array/255.0
img_array = keras.ops.expand_dims(img_array, 0)  # Create batch axis

predictions = model.predict(img_array)

probabilities = predictions[0].numpy()

class_names = train_ds.class_names

for i, prob in enumerate(probabilities):
    print(f"{class_names[i]}: {prob * 100:.2f}%")

predicted_class = class_names[np.argmax(probabilities)]
confidence = np.max(probabilities)

print(f"\nPrediction: {predicted_class} ({confidence * 100:.2f}%)")

'''