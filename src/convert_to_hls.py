import tensorflow as tf
from tensorflow import keras
import hls4ml
from hls4ml.utils.config import config_from_keras_model
import numpy as np

# Load trained Keras model
model = keras.models.load_model('cnn_bed_fall_detection.h5', compile=False)

# Create config
config = config_from_keras_model(model, granularity='name')

# diagnose
print(model.summary())

x = np.random.rand(1, 32, 32, 1).astype('float32')
y = model.predict(x)

# SAFETY CHECK (VERY IMPORTANT)
for layer in config['LayerName']:
    if 'conv' in layer:
        raise Exception("Conv layer detected — model not FPGA-safe")
        
print("Model output shape:", y.shape)
print("Model output:", y)

# Global settings
config['Model']['Precision'] = 'ap_fixed<10,3>'
config['Model']['Strategy'] = 'Resource'
config['Model']['Dataflow'] = False
config['Model']['IOType'] = 'io_parallel'
config['Model']['ReuseFactor'] = 24

config['LayerName']['dense']['Strategy'] = 'Resource'
config['LayerName']['dense']['ReuseFactor'] = 32
# Convert model
hls_model = hls4ml.converters.convert_from_keras_model(
    model,
    hls_config=config,
    output_dir='hls4ml_prj',
    part='xc7a35tcpg236-1',
    backend='Vivado'
)

# Compile
hls_model.compile()

# Build
hls_model.build(
    csim=False,
    synth=True,
    cosim=False,
    export=True
)

print("Done: hls4ml project generated.")

