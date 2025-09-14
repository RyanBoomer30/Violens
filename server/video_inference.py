import cv2
import base64
import os
import json
import shutil
from openai import OpenAI

# It's highly recommended to use environment variables for API keys
# client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
# For this hackathon, we'll use the provided key directly
client = OpenAI(api_key="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")


def analyze_video_and_generate_report(file_address):
    """
    Analyzes video frames using a single, efficient API call to an OpenAI model.

    This function reads a video, converts frames to base64, and sends them to the 
    OpenAI API with a prompt that asks for a JSON object containing:
    - violence_detected (bool): Whether violence was detected.
    - classification (str): A one-word classification (e.g., "Self-harm", "Fighting", "Safe").
    - detailed_report (str): A brief summary of the events.

    Returns:
        A dictionary containing the analysis results, or a default "error" dictionary if analysis fails.
    """
    try:
        video = cv2.VideoCapture(file_address)
        base64Frames = []
        while video.isOpened():
            success, frame = video.read()
            if not success:
                break
            _, buffer = cv2.imencode(".jpg", frame)
            base64Frames.append(base64.b64encode(buffer).decode("utf-8"))
        video.release()

        if not base64Frames:
            print("Warning: Could not read any frames from the video.")
            return {
                "violence_detected": False,
                "classification": "Error",
                "detailed_report": "Could not read frames from video file."
            }
        
        # --- START OF NEW DEBUGGING CODE ---
        # Create a temporary directory to store frames for visual inspection.
        TEMP_FRAMES_DIR = "temp_frames_for_debugging"
        if os.path.exists(TEMP_FRAMES_DIR):
            shutil.rmtree(TEMP_FRAMES_DIR)
        os.makedirs(TEMP_FRAMES_DIR)
        
        # Sample the frames that will be sent to the API.
        sampled_frames = base64Frames[0::5]
        print(f"Read {len(base64Frames)} frames. Saving {len(sampled_frames)} sampled frames to '{TEMP_FRAMES_DIR}' for debugging...")

        # Save the sampled frames to disk so you can see what the AI sees.
        for i, frame_data in enumerate(sampled_frames):
            img_data = base64.b64decode(frame_data)
            file_path = os.path.join(TEMP_FRAMES_DIR, f"frame_{i+1:03d}.jpg")
            with open(file_path, 'wb') as f:
                f.write(img_data)
        # --- END OF NEW DEBUGGING CODE ---

        print(f"Sending {len(sampled_frames)} frames for analysis...")

        # Construct the prompt for the OpenAI API using the sampled frames
        prompt_messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Analyze the following video frames for any form of violence, fighting, self-harm, or aggression. "
                            "Based on your analysis, you MUST respond with only a single JSON object in the following format: "
                            '{"violence_detected": <true_or_false>, "classification": "<One-word classification>", "detailed_report": "<A brief, 1-2 sentence summary of the incident or observation>"}. '
                            "Do not include any text or markdown formatting before or after the JSON object."
                        )
                    },
                    *[
                        {
                            "type": "image_url", 
                            "image_url": {"url": f"data:image/jpeg;base64,{frame}"}
                        }
                        for frame in sampled_frames
                    ]
                ],
            }
        ]

        # Use the gpt-4o model for better vision and JSON capabilities
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=prompt_messages,
            max_tokens=400
        )
        
        # Check the reason the model stopped generating text
        finish_reason = response.choices[0].finish_reason
        if finish_reason == 'content_filter':
            print("Error: OpenAI's content filter was triggered.")
            return {
                "violence_detected": True, # If the filter is triggered, it's a strong signal of problematic content
                "classification": "Content Filtered",
                "detailed_report": "The video was flagged by the AI's content safety system, likely due to depicting self-harm or severe violence."
            }

        response_text = response.choices[0].message.content
        print(f"Raw OpenAI response: {response_text}")

        # Handle cases where the response might still be None for other reasons
        if response_text is None:
            print(f"Error: OpenAI response content is None. Finish reason: {finish_reason}")
            return {
                "violence_detected": False,
                "classification": "API Error",
                "detailed_report": f"The AI model returned an empty response. The reason was '{finish_reason}'."
            }
        
        # Clean the response to remove markdown code block fences if they exist
        if response_text.strip().startswith("```json"):
            response_text = response_text.strip()[7:-4].strip()
        
        json_response = json.loads(response_text)
        return json_response

    except json.JSONDecodeError as e:
        print(f"Error: Could not decode JSON from OpenAI response. Error: {e}")
        print(f"Received text: {response_text}")
        return {
            "violence_detected": False, # Default to false on error
            "classification": "Parsing Error",
            "detailed_report": "The model's response was not valid JSON."
        }
    except Exception as e:
        print(f"An unexpected error occurred during video analysis: {e}")
        return {
            "violence_detected": False,
            "classification": "Analysis Error",
            "detailed_report": str(e)
        }

