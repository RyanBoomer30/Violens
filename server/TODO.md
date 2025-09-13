# What we have done
1. Video summarize function
2. Violence detection function

# Flow
1. Receive the video from the camera
2. Run analyze_video() to check if the video is violence or not:
    - If yes, saves the video, parses the video into generate_report() and save the report
    - If no, just delete the video and ignore it
3. After a week, compile a weekly report
4. Send everything to the frontend
