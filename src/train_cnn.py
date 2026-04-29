import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers

# Load training data
imageSize = (32, 32)  # Even smaller input for Basys-3

train_ds = keras.preprocessing.image_dataset_from_directory(
    "data",
    image_size=imageSize,
    color_mode="grayscale",
    batch_size=32,
    label_mode="categorical"  # 3 classes
)

# Preprocess the image
def preprocess(image, label):
    img = tf.cast(image, tf.float32) / 255.0
    return img, label

train_ds = train_ds.map(preprocess)

# CNN
def make_model():
    return keras.Sequential([
        layers.Conv2D(8, 3, activation='relu', padding='same', input_shape=(32, 32, 1)),
        layers.MaxPooling2D(),

        layers.Conv2D(16, 3, activation='relu', padding='same'),
        layers.MaxPooling2D(),

        layers.Flatten(),
        layers.Dense(16, activation='relu'),
        layers.Dense(3, activation='softmax')
    ])

# Base float model
model = make_model()

# Compile
model.compile(
    optimizer='adam',
    loss='categorical_crossentropy',   # FIXED
    metrics=['accuracy']
)

# Train
history = model.fit(train_ds, epochs=60)

# Save
model.save("cnn_bed_fall_detection.h5")

print("Training complete. Model saved as cnn_bed_fall_detection.h5")
