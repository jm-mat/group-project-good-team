import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
import tensorflow_model_optimization as tfmot

# Load training data
imageSize = (48, 48)									#Smaller input for FPGA(Basys 3) for PoC

train_ds = keras.preprocessing.image_dataset_from_directory(
	"data",
	image_size = imageSize,
	color_mode = "grayscale",
	batch_size = 32,
	label_mode = "categorical"				# 3 classes: safe/ unsafe / irrelevant
)

# CNN
def make_model():
    return keras.Sequential([
        layers.Rescaling(1./255, input_shape=(96,96,1)),
        
		layers.SeparableConv2D(8, 3, activation='relu', padding='same'),
        layers.MaxPooling2D(),
        
		layers.SeparableConv2D(16, 3, activation='relu', padding='same'),
        layers.MaxPooling2D(),
        
		layers.SeparableConv2D(32, 3, activation='relu', padding='same'),
        layers.MaxPooling2D(),

		layers.GlobalAveragePooling2D(),									# Replace Flatten() (FPGA compatible)
		layers.Dense(16, activation = 'relu'),
        
		layers.Dense(3,activation ='softmax')
	])

# Base float model
model = make_model()

# Quantization-Aware Training
quantize_model = tfmot.quantization.keras.quantize_model
model = quantize_model(model)

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
