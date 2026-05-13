import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers

# Load training data
imageSize = (32, 32)  # Basys-3 friendly resolution

train_ds = keras.preprocessing.image_dataset_from_directory(
    "data",
    image_size=imageSize,
    color_mode="grayscale",
    batch_size=32,
    label_mode="categorical"  # 3 classes
)

# Normalize images
def preprocess(image, label):
    img = tf.cast(image, tf.float32) / 255.0
    return img, label

train_ds = train_ds.map(preprocess)

# Updated Neural Network Architecture to fit Basys-3 resources
def make_model():
    return keras.Sequential([
        layers.Input(shape=(32, 32, 1)),
        layers.MaxPooling2D(pool_size=(2, 2)),
	layers.Flatten(),
	layers.Dense(4, activation='relu'),
	layers.Dense(8,activation='relu'),
	layers.Dense(3)
    ])

model = make_model()

# Use categorical crossentropy with logits
model.compile(
    optimizer='adam',
    loss=tf.keras.losses.CategoricalCrossentropy(from_logits=True),
    metrics=['accuracy']
)

# Train
history = model.fit(train_ds, epochs=60)

# Save model
model.save("cnn_bed_fall_detection.h5")

print("Training complete. Model saved as cnn_bed_fall_detection.h5")

