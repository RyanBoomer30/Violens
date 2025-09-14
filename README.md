# Real-Time Bullying and Violence Detection
Introduction

This project was born from the shared personal experiences of our team members with bullying during their school years. Frustrated by the inadequate measures in place to address such issues, we were inspired to create a proactive solution. Our goal is to create a safer learning environment for students from all backgrounds.

## What it Does

Our system is an intelligent, two-tiered AI pipeline that detects, verifies, and reports acts of violence in real time from a webcam feed.

Local Detection (Client-Side): A lightweight CNN and LSTM ensemble continuously monitors video streams for signs of aggression. If a potential threat is detected, the client records a short video clip.

Server-Side Verification: The clip is sent to a FastAPI backend, which calls OpenAI’s GPT-4o for secondary analysis.

Incident Report: The server returns a JSON response with:

Violence determination (yes/no)

Classification (for example, Fighting, Self-harm)

A concise, actionable incident report

This creates a robust and efficient safety monitoring solution with both speed and accuracy.

## How We Built It

Client-Side Monitoring: Python and OpenCV for live webcam feed and TensorFlow/Keras for initial real-time detection.

Backend API: FastAPI to receive video uploads and trigger analysis.

Advanced AI Analysis: GPT-4o (multimodal) samples video frames and outputs structured incident reports.

Communication: Client and server communicate via HTTP requests for seamless integration.

# Installation

## Clone the repository:

```bash 
git clone https://github.com/your-repo/bullying-detection.git
cd bullying-detection
```

Set up a virtual environment and install dependencies:

```bash
python -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create a .env file in the root directory and add your OpenAI API key:

```bash 
OPENAI_API_KEY=your_api_key_here
```
Run the client:

```bash 
python client.py
```

Run the server:

```bash 
uvicorn server:app --reload
```
## Frontend Setup

Navigate to the frontend folder:
```bash
cd frontend
npm install
npm start
```
## Dependencies
```bash
Python 3.9+

TensorFlow / Keras

OpenCV

NumPy

FastAPI

Uvicorn

Requests

OpenAI API

```
(See requirements.txt for the complete list.)

## Challenges We Ran Into

Model Compatibility: Struggled with deprecated TensorFlow/Keras versions.

Real-Time Performance: Balancing latency with inference speed was difficult.

Dataset Scarcity: Ethical, diverse violence datasets are limited, restricting robustness.


## What We Learned

Going from theory to application is harder and more rewarding than expected.

How to ensemble CNN and LSTM for video classification.

How to build a client-server ML pipeline with real-time data streams.

FastAPI and OpenAI integration for multimodal AI.

## What is Lacking and Future Work

Performance Tuning: Further optimization needed for ultra-low latency.

Dataset Expansion: More diverse and ethically sourced training data.

Deployment: Currently works locally; scaling to production requires containerization and cloud infrastructure.

Privacy Considerations: Future versions need built-in anonymization and data handling policies.
