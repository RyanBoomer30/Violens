import os
import cv2
import numpy as np
import tensorflow as tf
import keras
from collections import deque
from keras.layers import *
from keras.models import Sequential
from keras.applications.mobilenet_v2 import MobileNetV2

# Model configuration
CLASSES_LIST = ["NonViolence", "Violence"]
SEQUENCE_LENGTH = 16  # Use 16 frames instead of 32
IMAGE_HEIGHT, IMAGE_WIDTH = 64, 64

# Initialize MobileNetV2
mobilenet = MobileNetV2(include_top=False, weights="imagenet")
mobilenet.trainable = False

def create_model():
    """Create and load the violence detection model"""
    model = Sequential()

    # Specifying Input to match features shape
    model.add(Input(shape=(SEQUENCE_LENGTH, IMAGE_HEIGHT, IMAGE_WIDTH, 3)))
    
    # Passing mobilenet in the TimeDistributed layer to handle the sequence
    model.add(TimeDistributed(mobilenet))
    
    model.add(Dropout(0.25))
    model.add(TimeDistributed(Flatten()))

    lstm_fw = LSTM(units=32)
    lstm_bw = LSTM(units=32, go_backwards=True)  

    model.add(Bidirectional(lstm_fw, backward_layer=lstm_bw))
    
    model.add(Dropout(0.25))
    model.add(Dense(256, activation='relu'))
    model.add(Dropout(0.25))
    model.add(Dense(32, activation='relu'))
    model.add(Dropout(0.25))
    model.add(Dense(len(CLASSES_LIST), activation='softmax'))

    # --- FIX ---
    # Construct an absolute path to the model weights file to avoid FileNotFoundError.
    # This makes the script runnable from any directory.
    try:
        # __file__ is the path to the current script (violence_model.py)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        # Assumes the model file is in the parent directory of the script's directory
        parent_dir = os.path.dirname(script_dir)
        weights_path = os.path.join(parent_dir, 'trained_model_smaller.weights.h5')

        if not os.path.exists(weights_path):
            # As a fallback, check in the current directory as well
            weights_path = 'trained_model_smaller.weights.h5'
            if not os.path.exists(weights_path):
                 raise FileNotFoundError

        print(f"Loading model weights from: {os.path.abspath(weights_path)}")
        model.load_weights(weights_path)
    
    except FileNotFoundError:
        print("\n" + "="*50)
        print("FATAL ERROR: Could not find 'trained_model_smaller.weights.h5'")
        print("Please ensure the model weights file is located in the root directory of the project, one level above the 'Camera' folder.")
        print("="*50 + "\n")
        # Exit gracefully if the model can't be found
        exit()
        
    return model

# Global model instance
_model = None

def get_model():
    """Get or create the model instance"""
    global _model
    if _model is None:
        _model = create_model()
    return _model

def predict_frames_from_camera(cap, num_frames=16):
    """
    Capture frames from camera and predict violence using the model.
    Returns True if violence is detected, False otherwise.
    """
    try:
        model = get_model()
        frames_queue = deque(maxlen=SEQUENCE_LENGTH)
        
        # Capture the specified number of frames
        for _ in range(num_frames):
            ret, frame = cap.read()
            if not ret:
                break
                
            # Resize the Frame to fixed Dimensions
            resized_frame = cv2.resize(frame, (IMAGE_HEIGHT, IMAGE_WIDTH))
            
            # Normalize the resized frame 
            normalized_frame = resized_frame / 255
            
            # Append the pre-processed frame into the frames list
            frames_queue.append(normalized_frame)
        
        # Check if we have enough frames
        if len(frames_queue) < SEQUENCE_LENGTH:
            print(f"Warning: Only captured {len(frames_queue)} frames, need {SEQUENCE_LENGTH}")
            return False
        
        # Pass the normalized frames to the model and get the predicted probabilities
        predicted_labels_probabilities = model.predict(np.expand_dims(frames_queue, axis=0))[0]
        
        # Get the index of class with highest probability
        predicted_label = np.argmax(predicted_labels_probabilities)
        
        # Get the class name using the retrieved index
        predicted_class_name = CLASSES_LIST[predicted_label]
        
        # Return True if violence is detected
        return predicted_class_name == "Violence"
        
    except Exception as e:
        print(f"Error in violence prediction: {str(e)}")
        return False
