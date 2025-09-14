from IPython.display import display, Image, Audio

import cv2  # We're using OpenCV to read video, to install !pip install opencv-python
import base64
import time
from openai import OpenAI
import os

# Delete this after the hackathon plzzz
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", "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"))

# Reads the video and returns a list of base64 encoded frames
def read_vid(file_address):
    video = cv2.VideoCapture(file_address)

    base64Frames = []
    while video.isOpened():
        success, frame = video.read()
        if not success:
            break
        _, buffer = cv2.imencode(".jpg", frame)
        base64Frames.append(base64.b64encode(buffer).decode("utf-8"))

    video.release()
    print(len(base64Frames), "frames read.")
    return base64Frames

# Used for testing not really needed for processing
def display_frames(base64Frames):
    display_handle = display(None, display_id=True)
    for img in base64Frames:
        display_handle.update(Image(data=base64.b64decode(img.encode("utf-8"))))
        time.sleep(0.025)

# Analyzes the video frames to detect bullying or depression behavior
# Returns True if bullying or depression behavior is detected, False otherwise
def analyze_video(file_address):
    base64Frames = read_vid(file_address)
    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Analyze these video frames to detect bullying or depression behavior. Look for signs such as: aggressive behavior, physical confrontation, verbal harassment, social exclusion, emotional distress, signs of sadness or withdrawal, self-harm indicators, or other concerning behaviors that might indicate bullying or depression. Respond with only 'True' if you detect any bullying or depression-related behavior, or 'False' if you do not detect such behavior."
                        )
                    },
                    *[
                        {
                            "type": "input_image",
                            "image_url": f"data:image/jpeg;base64,{frame}"
                        }
                        for frame in base64Frames[0::25]
                    ]
                ]
            }
        ],
    )
    
    print("Classification: " + response.output_text)
    
    if response.output_text == "True":
        return True
    elif response.output_text == "False":
        return False
    else:
        raise Exception("Invalid classification: " + response.output_text)

# Generates a report based on the analysis of the video frames
# Returns the report as a dictionary with classification and details
def generate_report(file_address):
    base64Frames = read_vid(file_address)
    
    # First, get the classification of the altercation
    classification_response = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Analyze these video frames and classify the type of altercation or violent behavior. Choose the most appropriate category from: 'Physical Fight', 'Verbal Harassment', 'Bullying/Intimidation', 'Property Damage', 'Threats/Intimidation', 'Social Exclusion', 'Cyberbullying', 'Self-Harm', 'Other'. Respond with only the category name."
                        )
                    },
                    *[
                        {
                            "type": "input_image",
                            "image_url": f"data:image/jpeg;base64,{frame}"
                        }
                        for frame in base64Frames[0::25]
                    ]
                ]
            }
        ],
    )
    
    # Then, get the detailed report
    detailed_report_response = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Generate a concise incident report based on these video frames. Keep it brief and focused. Include: 1) Brief incident summary (1-2 sentences), 2) Key behaviors observed, 3) Recommended action. Maximum 150 words total."
                        )
                    },
                    *[
                        {
                            "type": "input_image",
                            "image_url": f"data:image/jpeg;base64,{frame}"
                        }
                        for frame in base64Frames[0::25]
                    ]
                ]
            }
        ],
    )
    
    return {
        "classification": str(classification_response.output_text).strip(),
        "detailed_report": str(detailed_report_response.output_text)
    }