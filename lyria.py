# -*- coding: utf-8 -*-
import os
import json
import requests
import google.auth
from google.auth.transport.requests import Request as GoogleAuthRequest
import base64
import streamlit as st # For st.error, st.info etc.
import uuid # Added missing import

def generate_lyria_music(project_id, prompt, negative_prompt="", sample_count=4):
    """
    Generates music using Google's Lyria model.

    Args:
        project_id (str): The Google Cloud Project ID.
        prompt (str): The text prompt for music generation.
        negative_prompt (str, optional): Negative prompt. Defaults to "".
        sample_count (int, optional): Number of samples to generate. Defaults to 4.

    Returns:
        list: A list of dictionaries, where each dictionary contains
              'filename' (str) and 'audio_bytes' (bytes) for a generated sample,
              or None if an error occurs.
    """
    LOCATION_ID = "us-central1"
    API_ENDPOINT_BASE = "us-central1-aiplatform.googleapis.com"
    MODEL_ID = "lyria-base-001" # Or the specific Lyria model ID you have access to

    try:
        credentials, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
        auth_req = GoogleAuthRequest()
        credentials.refresh(auth_req)
        token = credentials.token
    except Exception as e:
        st.error(f"Lyria Auth Error: Failed to get Google Cloud credentials: {e}")
        return None

    request_data = {
        "instances": [
            {
                "prompt": prompt,
                "sampleCount": sample_count,
                "negativePrompt": negative_prompt
            }
        ]
    }

    url = f"https://{API_ENDPOINT_BASE}/v1/projects/{project_id}/locations/{LOCATION_ID}/publishers/google/models/{MODEL_ID}:predict"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    st.info(f"Sending Lyria request to: {url}")
    st.json(request_data) # Show request for debugging

    try:
        response = requests.post(url, headers=headers, json=request_data)
        response.raise_for_status()  # Raises an HTTPError for bad responses (4XX or 5XX)
        response_json = response.json()
        st.success("Lyria API request successful!")
        # st.json(response_json) # For debugging the full response

        predictions = response_json.get('predictions', [])
        generated_samples = []

        if not predictions:
            st.warning("Lyria API returned no predictions.")
            return []

        for i, prediction in enumerate(predictions):
            audio_bytes = None
            if 'bytesBase64Encoded' in prediction and prediction['bytesBase64Encoded']:
                audio_bytes = base64.b64decode(prediction['bytesBase64Encoded'])
            elif 'content' in prediction and prediction['content']: # Fallback, as seen in Colab
                audio_bytes = base64.b64decode(prediction['content'])
            
            if audio_bytes:
                filename = f"lyria_sample_{project_id}_{uuid.uuid4().hex[:8]}_{i+1}.wav"
                generated_samples.append({"filename": filename, "audio_bytes": audio_bytes})
            else:
                st.warning(f"Sample {i+1} from Lyria had no audio content.")
        
        return generated_samples

    except requests.exceptions.HTTPError as http_err:
        st.error(f"Lyria API HTTP error: {http_err}")
        st.error(f"Response content: {response.text}")
    except Exception as e:
        st.error(f"An error occurred during Lyria music generation: {e}")
    
    return None
