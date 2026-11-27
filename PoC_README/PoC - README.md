# FPGA-Vision Fall Alert System

## Team
- Devin Roberson (GitHub: @devin-roberson)
- Jan Michael Maturan (GitHub: @jm-mat)
- Joshua Lu (GitHub: @josh8ml)
- Miguel Rodriguez Martinez (GitHub: @MiguelM831)

## Project Description
An FPGA-based pose detection system that would send alerts when the subject is about to fall from their bed. Video Feed from a camera module will be enhanced with Super Resolution models to improve prediction accuracy.

## Proof of Concept Scope
The PoC demonstrates a barebones custom trained CNN that would identify an input image or video frame if a subject is in a safe or unsafe bed position. Hardware implementation, Super Resolution model inclusion and alert mechanisms are not part of this PoC scope.

## Prerequisites
Python 3.10.x
pip

## Installation
-Download and copy all python scripts, trained model file, and sample inputs into the same directory
-Install and/or verify python version(3.10.x)
-Create and activate new Conda environment
-Install required python packages
pip install tensorflow==2.10.0
pip install numpy==1.23.5
pip install h5py==3.16.0
pip install pillow==12.2.0
pip install opencv-python==4.13.0.90
pip install hls4ml

## Running the PoC
Linux: 
- Activate Conda Environment
- change directory to src folder (cd ~\src\)
- run scripts (python train_cnn.py /python predictimage.py/ python predictvideo.py/python convert_to_hls.py) 

## Demo
**Model training completed**
![Model training completed](model_training_output.png)
**Result of sample_input1 in predictimage.py**
![Result of sample_input1 in predictimage.py](safe_output.png)
**Result of sample_input2 in predictimage.py**
![Result of sample_input2 in predictimage.py](unsafe_output.jpg)
**Result of input_video in predictvideo.py**
![Result of input_video in predictvideo.py](predictvideo_output.gif)

## Technical Stack
Python 3.10.20
TensorFlow 2.10.0
Pillow (PIL) 12.2.0
OpenCV (cv2) 4.13.0.90
NumPy 1.23.5
Vivado 2020.1

## What's Next (195B)
-Super Resolution model training and implementation 
-Camera module integration
-FPGA implementation
-Alert Mechanism(Mobile App) 
