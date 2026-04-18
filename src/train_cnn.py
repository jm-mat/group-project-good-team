import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers

# Load training data
imageSize = (96, 96)

train_ds = keras.preprocessing.image_dataset_from_directory(
	"data",
	image_size = imageSize,
	color_mode = "grayscale",
	batch_size = 32,
	label_mode = "binary"
)

# CNN
model = keras.Sequential([
	layers.Rescaling(1./255, input_shape = (96, 96, 1)),

	layers.Conv2D(8,3, activation='relu'),
	layers.MaxPooling2D(),

	layers.Conv2D(16,3, activation='relu'),
	layers.MaxPooling2D(),

	layers.Conv2D(32,3, activation='relu'),
	layers.MaxPooling2D(),

	layers.Flatten(),
	layers.Dense(32, activation='relu'),
	layers.Dense(1, activation='sigmoid')
])

# Compile
model.compile(
	optimizer = 'adam',
	loss = 'binary_crossentropy',
	metrics = ['accuracy']
)

# Train
history = model.fit(train_ds, epochs = 10)

# Save
model.save("cnn_bed_fall_detection.h5")

print("Training complete. Model saved as cnn_bed_fall_detection.h5")