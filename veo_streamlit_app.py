# -*- coding: utf-8 -*-
import streamlit as st
import requests
import time
import google.auth
import google.auth.transport.requests
from google.cloud import storage
import os
import uuid
import mimetypes
from urllib.parse import urlparse
from dotenv import load_dotenv
from PIL import Image as PIL_Image 

# Load environment variables from .env file
load_dotenv()

# Google Drive API imports
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request as GoogleAuthRequest

# Import Lyria function
from lyria import generate_lyria_music

# --- Configuration & Constants ---
DEFAULT_PROJECT_ID = os.getenv("DEFAULT_PROJECT_ID", "veo-testing")
DEFAULT_LYRIA_PROJECT_ID = os.getenv("DEFAULT_LYRIA_PROJECT_ID", "music-generation-434117") # Updated Lyria default
DEFAULT_OUTPUT_GCS_BUCKET = os.getenv("DEFAULT_OUTPUT_GCS_BUCKET", "fk-test-veo")
CLIENT_SECRETS_FILE = os.getenv("CLIENT_SECRETS_FILE", "credentials.json")
DEFAULT_DRIVE_FOLDER_LINK_ENV = os.getenv("DEFAULT_DRIVE_FOLDER_LINK", "https://drive.google.com/drive/folders/15SK65dQ7bsFIYPR1y9UXmwPgoqK7X41b?resourcekey=0-Zc4YZjA43nl6weUSbHsOWQ&usp=drive_link")

IMAGE_UPLOAD_GCS_PREFIX = os.getenv("IMAGE_UPLOAD_GCS_PREFIX", "uploads/")
VIDEO_UPLOAD_GCS_PREFIX = os.getenv("VIDEO_UPLOAD_GCS_PREFIX", "video_uploads/") 
MUSIC_OUTPUT_SUBDIR = "lyria_music_outputs" # Subdirectory for Lyria outputs within local_output_dir
TEMP_MEDIA_DIR = os.getenv("DEFAULT_TEMP_MEDIA_DIR", "temp_media")


_PREDICT_API_ENDPOINT_STD = f'https://us-central1-autopush-aiplatform.sandbox.googleapis.com/v1beta1/projects/{DEFAULT_PROJECT_ID}/locations/us-central1/publishers/google/models/veo-2.0-generate-001:predictLongRunning'
_FETCH_API_ENDPOINT_STD = f'https://us-central1-autopush-aiplatform.sandbox.googleapis.com/v1beta1/projects/{DEFAULT_PROJECT_ID}/locations/us-central1/publishers/google/models/veo-2.0-generate-001:fetchPredictOperation'

VEO_ADVANCED_MODEL_BASE = f"https://us-central1-aiplatform.googleapis.com/v1/projects/{DEFAULT_PROJECT_ID}/locations/us-central1/publishers/google/models/veo-2.0-generate-exp"
PREDICTION_ENDPOINT_ADV = f"{VEO_ADVANCED_MODEL_BASE}:predictLongRunning"
FETCH_ENDPOINT_ADV = f"{VEO_ADVANCED_MODEL_BASE}:fetchPredictOperation"

DRIVE_SCOPES = ['https://www.googleapis.com/auth/drive.file']

def get_drive_service():
    creds = None; token_path = 'token.json'
    if os.path.exists(token_path):
        try: creds = Credentials.from_authorized_user_file(token_path, DRIVE_SCOPES)
        except Exception as e: st.warning(f"Could not load {token_path}: {e}. Will re-auth.")
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try: creds.refresh(GoogleAuthRequest())
            except Exception as e: st.error(f"Error refreshing Drive token: {e}"); return None
        else:
            if not os.path.exists(CLIENT_SECRETS_FILE): st.error(f"OAuth secrets file ('{CLIENT_SECRETS_FILE}') not found."); return None
            try:
                flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, DRIVE_SCOPES)
                auth_url, _ = flow.authorization_url(prompt='consent')
                st.info(f"Authorize Drive: {auth_url}")
                auth_code = st.text_input("Drive Auth Code:")
                if auth_code: flow.fetch_token(code=auth_code); creds = flow.credentials
                else: st.info("Awaiting Drive auth code."); return None
            except Exception as e: st.error(f"Drive auth error: {e}"); return None
        try:
            with open(token_path, 'w') as token_file: token_file.write(creds.to_json())
            st.success(f"Drive token saved to {token_path}.")
        except Exception as e: st.error(f"Error saving Drive token: {e}")
    if creds and creds.valid:
        try: return build('drive', 'v3', credentials=creds)
        except Exception as e: st.error(f"Error building Drive service: {e}")
    else: st.error("Failed to get valid Drive credentials.")
    return None

def extract_folder_id_from_link(link):
    if not link: return None
    try:
        if "/folders/" in link: return link.split("/folders/")[1].split("?")[0]
    except Exception as e: st.error(f"Could not parse Drive folder ID: {e}")
    return None

def upload_to_drive(drive_service, folder_id, file_path, file_name=None):
    if not drive_service: st.error("Drive service NA for upload."); return
    if not file_name: file_name = os.path.basename(file_path)
    file_metadata = {'name': file_name, 'parents': [folder_id] if folder_id else []}
    try:
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type is None: mime_type = 'application/octet-stream'
        media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)
        with st.spinner(f"Uploading {file_name} to Drive..."):
            request = drive_service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink')
            response = None; pbar = st.progress(0)
            while response is None: status, response = request.next_chunk(); pbar.progress(int(status.progress()*100) if status else 0)
            pbar.empty(); st.success(f"Uploaded to Drive: {response.get('webViewLink')}")
            return response.get('id'), response.get('webViewLink')
    except Exception as e: st.error(f"Drive upload error for {file_name}: {e}")
    return None, None

def download_image_from_url(image_url, temp_dir=TEMP_MEDIA_DIR):
    if not image_url: return None
    try:
        response = requests.get(image_url, stream=True); response.raise_for_status()
        parsed_url = urlparse(image_url); original_filename = os.path.basename(parsed_url.path) or f"{uuid.uuid4()}.jpg"
        safe_filename = "".join(c if c.isalnum() or c in ('.','_','-') else '_' for c in original_filename) or f"{uuid.uuid4()}{os.path.splitext(original_filename)[1]}"
        os.makedirs(temp_dir, exist_ok=True)
        temp_file_path = os.path.join(temp_dir, f"{uuid.uuid4()}_{safe_filename}")
        with open(temp_file_path, 'wb') as f:
            for chunk in response.iter_content(8192): f.write(chunk)
        st.info(f"Downloaded {image_url} to {temp_file_path}")
        return temp_file_path
    except Exception as e: st.error(f"Error downloading {image_url}: {e}"); return None

def get_gcs_client():
    try: credentials, project = google.auth.default(); return storage.Client(credentials=credentials)
    except Exception as e: st.error(f"GCS client error: {e}"); return None

def upload_to_gcs(storage_client, bucket_name, source_file_path, destination_blob_name_prefix=""):
    if not storage_client or not source_file_path : return None, None
    try:
        bucket = storage_client.bucket(bucket_name)
        file_name = os.path.basename(source_file_path)
        destination_blob_name = f"{destination_blob_name_prefix}{uuid.uuid4()}_{file_name}"
        mime_type, _ = mimetypes.guess_type(source_file_path)
        if mime_type is None: mime_type = 'application/octet-stream'
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_filename(source_file_path, content_type=mime_type)
        gcs_uri = f"gs://{bucket_name}/{destination_blob_name}"
        st.info(f"Uploaded {source_file_path} to {gcs_uri}")
        return gcs_uri, mime_type
    except Exception as e: st.error(f"GCS upload error for {source_file_path}: {e}"); return None, None

def download_from_gcs(storage_client, bucket_name, source_blob_name, destination_file_name):
    if not storage_client: return False
    try:
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(source_blob_name)
        os.makedirs(os.path.dirname(destination_file_name), exist_ok=True)
        blob.download_to_filename(destination_file_name)
        st.info(f"Downloaded gs://{bucket_name}/{source_blob_name} to {destination_file_name}")
        return True
    except Exception as e: st.error(f"GCS download error for gs://{bucket_name}/{source_blob_name}: {e}"); return False

def send_veo_api_request(project_id, api_endpoint, data=None):
    try:
        creds, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
        auth_req = GoogleAuthRequest()
        creds.refresh(auth_req)
        headers = {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}
        response = requests.post(api_endpoint, headers=headers, json=data)
        response.raise_for_status()
        return response.json()
    except google.auth.exceptions.DefaultCredentialsError: st.error("GCP Default Credentials Error. Run 'gcloud auth application-default login'.")
    except requests.exceptions.HTTPError as e: st.error(f"HTTP Error: {e} - {e.response.text if e.response else 'No response text'}")
    except Exception as e: st.error(f"API request error: {e}")
    return None

def compose_veo_request(prompt, parameters, image_uri="", video_uri="", last_frame_uri="", camera_control=""):
    instance = {"prompt": prompt}
    if image_uri: instance["image"] = {"gcsUri": image_uri, "mimeType": "image/jpeg"}
    if video_uri: instance["video"] = {"gcsUri": video_uri, "mimeType": "video/mp4"}
    if last_frame_uri: instance["lastFrame"] = {"gcsUri": last_frame_uri, "mimeType": "image/jpeg"}
    if camera_control: instance["cameraControl"] = camera_control
    return {"instances": [instance], "parameters": parameters}

def poll_veo_operation(project_id, fetch_endpoint, lro_name, max_attempts=60, sleep_seconds=10):
    request_payload = {'operationName': lro_name}
    for i in range(max_attempts):
        resp = send_veo_api_request(project_id, fetch_endpoint, data=request_payload)
        if resp:
            if 'done' in resp and resp['done']: st.success(f"Operation {lro_name} completed."); return resp
            st.write(f"Polling Veo operation... Attempt {i+1}/{max_attempts}")
        else: st.error("Failed to fetch Veo operation status. Aborting."); return None
        time.sleep(sleep_seconds)
    st.warning(f"Veo operation {lro_name} timed out after {max_attempts*sleep_seconds}s."); return None

def generate_veo_video(project_id, predict_endpoint, fetch_endpoint, prompt, parameters, 
                       image_uri="", video_uri="", last_frame_uri="", camera_control=""):
    req = compose_veo_request(prompt, parameters, image_uri, video_uri, last_frame_uri, camera_control)
    st.write("Sending Veo API request..."); st.json(req)
    resp = send_veo_api_request(project_id, predict_endpoint, data=req)
    if resp and 'name' in resp:
        st.info(f"Veo operation initiated: {resp['name']}")
        return poll_veo_operation(project_id, fetch_endpoint, resp['name'])
    else:
        st.error("Failed to initiate Veo video generation.")
        if resp: st.json(resp)
    return None

st.set_page_config(layout="wide")
st.title("🎬 Veo & Lyria AI Generation Hub 🎵")

st.sidebar.header("🔑 GCP Configuration")
project_id_input = st.sidebar.text_input("Veo Project ID", value=DEFAULT_PROJECT_ID)
lyria_project_id_input = st.sidebar.text_input("Lyria Project ID (if different)", value=DEFAULT_LYRIA_PROJECT_ID)
output_gcs_bucket_input = st.sidebar.text_input("GCS Bucket for Output", value=DEFAULT_OUTPUT_GCS_BUCKET)
local_output_dir_input = st.sidebar.text_input("Local Output Directory", value=os.getenv("DEFAULT_LOCAL_OUTPUT_DIR", "Output"))

st.sidebar.header("💾 Google Drive Output (Optional)")
drive_folder_link_input = st.sidebar.text_input("Google Drive Folder Link", value=DEFAULT_DRIVE_FOLDER_LINK_ENV)

tab_names = ["Standard Veo", "Veo Interpolation", "Veo Extension", "Veo Camera Controls", "Lyria Music"]
tabs = st.tabs(tab_names)

gcs_client = get_gcs_client()
drive_service = None
target_drive_folder_id = None

if drive_folder_link_input.strip():
    with st.sidebar.expander("Google Drive Status", expanded=False):
        drive_auth_placeholder = st.empty()
        with drive_auth_placeholder.container(): drive_service = get_drive_service()
        if drive_service:
            drive_auth_placeholder.success("Drive Authenticated.")
            target_drive_folder_id = extract_folder_id_from_link(drive_folder_link_input.strip())
            if target_drive_folder_id: st.info(f"Drive Folder ID: {target_drive_folder_id}")
            else: st.error("Could not get Drive Folder ID from link.")
        else: drive_auth_placeholder.error("Drive Auth Failed/Pending.")

def handle_file_upload_to_gcs(uploaded_file_obj, bucket_name, prefix=""):
    if not uploaded_file_obj or not gcs_client or not bucket_name: return None
    os.makedirs(TEMP_MEDIA_DIR, exist_ok=True)
    temp_file_path = os.path.join(TEMP_MEDIA_DIR, f"{uuid.uuid4()}_{uploaded_file_obj.name}")
    try:
        with open(temp_file_path, "wb") as f: f.write(uploaded_file_obj.getbuffer())
        gcs_uri, _ = upload_to_gcs(gcs_client, bucket_name, temp_file_path, prefix)
        return gcs_uri
    except Exception as e: st.error(f"Error processing uploaded file {uploaded_file_obj.name}: {e}")
    finally:
        if os.path.exists(temp_file_path):
            try: os.remove(temp_file_path)
            except OSError: pass

def display_generated_videos(operation_result, current_local_output_dir, source_identifier="video"):
    videos_data = []
    if operation_result and operation_result.get('response'):
        if 'videos' in operation_result['response']: videos_data = operation_result['response']['videos']
        elif 'generatedSamples' in operation_result['response']:
            for sample in operation_result['response']['generatedSamples']:
                if 'video' in sample and 'uri' in sample['video']: videos_data.append({'gcsUri': sample['video']['uri']})
    if not videos_data:
        err_msg = operation_result['error']['message'] if operation_result and operation_result.get('error') else 'Unknown error'
        st.error(f"Video gen failed for {source_identifier}: {err_msg}")
        if operation_result: st.json(operation_result.get('error', operation_result))
        return
    st.success(f"Video generation successful for {source_identifier}!")
    os.makedirs(current_local_output_dir, exist_ok=True)
    for i, video_info in enumerate(videos_data):
        video_gcs_uri = video_info.get('gcsUri')
        if video_gcs_uri and video_gcs_uri.startswith("gs://"):
            parts = video_gcs_uri[5:].split("/", 1); video_bucket_name, video_blob_name = parts[0], parts[1] if len(parts) > 1 else ""
            base_name = os.path.basename(video_blob_name) or f"video_{uuid.uuid4()}.mp4"
            local_video_filename = os.path.join(current_local_output_dir, f"generated_{source_identifier}_sample_{i+1}_{base_name}")
            if download_from_gcs(gcs_client, video_bucket_name, video_blob_name, local_video_filename):
                st.success(f"Video downloaded: {local_video_filename}")
                with open(local_video_filename, "rb") as fp:
                    st.download_button(f"Download Video ({source_identifier} S{i+1})", fp, os.path.basename(local_video_filename), "video/mp4", key=f"dl_vid_{source_identifier}_{i}")
                st.video(local_video_filename, autoplay=True, muted=True)
                if drive_service and target_drive_folder_id: upload_to_drive(drive_service, target_drive_folder_id, local_video_filename)
            else: st.error(f"Failed to download {video_gcs_uri}")
        else: st.warning(f"Invalid or missing GCS URI for video sample {i+1}")

with tabs[0]: # Standard Veo
    st.header("Standard Veo Video Generation")
    # UI elements specific to standard generation
    std_prompt_input = st.text_area("Prompt (Standard Veo)", key="std_veo_prompt")
    std_uploaded_image_files = st.file_uploader("Upload Image(s) (Standard Veo)", type=["png", "jpg", "jpeg"], accept_multiple_files=True, key="std_veo_img_upload")
    std_image_urls_input = st.text_area("Or Paste Image URLs (Standard Veo)", key="std_veo_img_urls")
    # Standard Veo parameters
    col1, col2 = st.columns(2)
    with col1:
        std_seed_input = st.number_input("Seed", value=777, min_value=0, key="std_veo_seed")
        std_aspect_ratio_input = st.selectbox("Aspect Ratio", options=["PORTRAIT", "LANDSCAPE"], index=1, key="std_veo_aspect") # Default LANDSCAPE
    with col2:
        std_sample_count_input = st.number_input("Sample Count", value=1, min_value=1, max_value=4, key="std_veo_samples")
        std_duration_input = st.number_input("Duration (s)", value=8, min_value=1, max_value=60, key="std_veo_duration")
    std_enhance_prompt_input = st.checkbox("Enhance Prompt", value=False, key="std_veo_enhance")

    if st.button("Generate Standard Veo Video", key="std_veo_btn"):
        # Logic from existing "Standard Generation" tab
        current_project_id = project_id_input.strip()
        current_gcs_bucket = output_gcs_bucket_input.strip()
        current_local_dir = local_output_dir_input.strip()
        if not all([current_project_id, current_gcs_bucket, current_local_dir]):
            st.error("Project ID, GCS Bucket, and Local Output Directory must be set.")
        elif not std_prompt_input.strip() and not std_uploaded_image_files and not std_image_urls_input.strip():
            st.error("Provide a prompt, upload images, or paste image URLs for Standard Veo.")
        else:
            predict_ep = _PREDICT_API_ENDPOINT_STD.replace(DEFAULT_PROJECT_ID, current_project_id)
            fetch_ep = _FETCH_API_ENDPOINT_STD.replace(DEFAULT_PROJECT_ID, current_project_id)
            params = {"storageUri": f"gs://{current_gcs_bucket}/video_outputs_std/", "sampleCount": std_sample_count_input, "seed": std_seed_input,
                      "aspectRatio": "16:9" if std_aspect_ratio_input == "LANDSCAPE" else "9:16", "durationSeconds": std_duration_input, 
                      "enhancePrompt": std_enhance_prompt_input, "personGeneration": "allow_adult"}
            
            img_sources = []
            if std_uploaded_image_files: img_sources.extend([{"type": "file", "data": f, "name": f.name} for f in std_uploaded_image_files])
            if std_image_urls_input.strip(): img_sources.extend([{"type": "url", "data": url, "name": f"url_{i}"} for i, url in enumerate(std_image_urls_input.strip().splitlines()) if url.strip()])

            if not img_sources and std_prompt_input.strip():
                op_result = generate_veo_video(current_project_id, predict_ep, fetch_ep, std_prompt_input.strip(), params)
                display_generated_videos(op_result, current_local_dir, "std_veo_prompt")
            elif img_sources:
                for src in img_sources:
                    gcs_img_uri = None
                    if src["type"] == "file": gcs_img_uri = handle_file_upload_to_gcs(src["data"], current_gcs_bucket, IMAGE_UPLOAD_GCS_PREFIX)
                    elif src["type"] == "url":
                        local_path = download_image_from_url(src["data"]);
                        if local_path: gcs_img_uri, _ = upload_to_gcs(gcs_client, current_gcs_bucket, local_path, IMAGE_UPLOAD_GCS_PREFIX); os.remove(local_path)
                    if gcs_img_uri:
                        op_result = generate_veo_video(current_project_id, predict_ep, fetch_ep, std_prompt_input.strip(), params, image_uri=gcs_img_uri)
                        display_generated_videos(op_result, current_local_dir, f"std_veo_{src['name']}")
                    else: st.error(f"Failed to process image {src['name']}")
            else: st.error("No valid input for Standard Veo generation.")


with tabs[1]: # Veo Interpolation
    st.header("Veo Interpolation")
    interp_prompt = st.text_area("Prompt", key="interp_prompt_adv")
    col1, col2 = st.columns(2)
    with col1: interp_first_frame = st.file_uploader("First Frame", type=["png","jpg","jpeg"], key="interp_first")
    with col2: interp_last_frame = st.file_uploader("Last Frame", type=["png","jpg","jpeg"], key="interp_last")
    interp_duration = st.slider("Duration (s)", 4, 8, 5, key="interp_dur_adv")
    interp_aspect_ratio = st.selectbox("Aspect Ratio", ["16:9", "9:16"], key="interp_aspect_adv")

    if st.button("Generate Interpolated Video", key="interp_btn_adv"):
        current_project_id = project_id_input.strip()
        current_gcs_bucket = output_gcs_bucket_input.strip()
        current_local_dir = local_output_dir_input.strip()
        if not all([current_project_id, current_gcs_bucket, current_local_dir, interp_prompt.strip(), interp_first_frame, interp_last_frame]):
            st.error("All fields are required for Interpolation.")
        else:
            predict_ep = PREDICTION_ENDPOINT_ADV.replace(DEFAULT_PROJECT_ID, current_project_id)
            fetch_ep = FETCH_ENDPOINT_ADV.replace(DEFAULT_PROJECT_ID, current_project_id)
            gcs_first = handle_file_upload_to_gcs(interp_first_frame, current_gcs_bucket, IMAGE_UPLOAD_GCS_PREFIX)
            gcs_last = handle_file_upload_to_gcs(interp_last_frame, current_gcs_bucket, IMAGE_UPLOAD_GCS_PREFIX)
            if gcs_first and gcs_last:
                params = {"aspectRatio": interp_aspect_ratio, "storageUri": f"gs://{current_gcs_bucket}/interpolation_videos/", 
                          "durationSeconds": interp_duration, "enhancePrompt": True}
                op_result = generate_veo_video(current_project_id, predict_ep, fetch_ep, interp_prompt.strip(), params, image_uri=gcs_first, last_frame_uri=gcs_last)
                display_generated_videos(op_result, current_local_dir, "interp_video")
            else: st.error("Failed to upload frames for interpolation.")

with tabs[2]: # Veo Extension
    st.header("Veo Video Extension")
    extend_prompt = st.text_area("Prompt", value="Continue the video naturally", key="extend_prompt_adv")
    extend_video_file = st.file_uploader("Video to Extend (MP4)", type=["mp4"], key="extend_file_adv")
    extend_duration = st.slider("Extension Duration (s)", 4, 7, 4, key="extend_dur_adv")
    extend_aspect_ratio = st.selectbox("Aspect Ratio", ["16:9", "9:16"], key="extend_aspect_adv")

    if st.button("Extend Video", key="extend_btn_adv"):
        current_project_id = project_id_input.strip()
        current_gcs_bucket = output_gcs_bucket_input.strip()
        current_local_dir = local_output_dir_input.strip()
        if not all([current_project_id, current_gcs_bucket, current_local_dir, extend_prompt.strip(), extend_video_file]):
            st.error("All fields are required for Video Extension.")
        else:
            predict_ep = PREDICTION_ENDPOINT_ADV.replace(DEFAULT_PROJECT_ID, current_project_id)
            fetch_ep = FETCH_ENDPOINT_ADV.replace(DEFAULT_PROJECT_ID, current_project_id)
            gcs_video = handle_file_upload_to_gcs(extend_video_file, current_gcs_bucket, VIDEO_UPLOAD_GCS_PREFIX)
            if gcs_video:
                params = {"aspectRatio": extend_aspect_ratio, "storageUri": f"gs://{current_gcs_bucket}/extended_videos/",
                          "durationSeconds": extend_duration, "enhancePrompt": True}
                op_result = generate_veo_video(current_project_id, predict_ep, fetch_ep, extend_prompt.strip(), params, video_uri=gcs_video)
                display_generated_videos(op_result, current_local_dir, "extended_video")
            else: st.error("Failed to upload video for extension.")

with tabs[3]: # Veo Camera Controls
    st.header("Veo Camera Controls")
    cam_prompt = st.text_area("Prompt", key="cam_prompt_adv")
    cam_image_file = st.file_uploader("Starting Image", type=["png","jpg","jpeg"], key="cam_image_adv")
    cam_controls = ["FIXED", "PAN_LEFT", "PAN_RIGHT", "PULL_OUT", "PEDESTAL_DOWN", "PUSH_IN", "TRUCK_LEFT", "TRUCK_RIGHT", "PEDESTAL_UP", "TILT_DOWN", "TILT_UP"]
    cam_control_type = st.selectbox("Camera Control", cam_controls, key="cam_ctrl_adv")
    cam_aspect_ratio = st.selectbox("Aspect Ratio", ["16:9", "9:16"], key="cam_aspect_adv")
    # cam_duration = st.slider("Duration (s)", 4, 8, 5, key="cam_dur_adv") # Duration might be fixed for camera moves

    if st.button("Generate with Camera Control", key="cam_btn_adv"):
        current_project_id = project_id_input.strip()
        current_gcs_bucket = output_gcs_bucket_input.strip()
        current_local_dir = local_output_dir_input.strip()
        if not all([current_project_id, current_gcs_bucket, current_local_dir, cam_prompt.strip(), cam_image_file, cam_control_type]):
            st.error("All fields are required for Camera Control generation.")
        else:
            predict_ep = PREDICTION_ENDPOINT_ADV.replace(DEFAULT_PROJECT_ID, current_project_id)
            fetch_ep = FETCH_ENDPOINT_ADV.replace(DEFAULT_PROJECT_ID, current_project_id)
            gcs_image = handle_file_upload_to_gcs(cam_image_file, current_gcs_bucket, IMAGE_UPLOAD_GCS_PREFIX)
            if gcs_image:
                params = {"aspectRatio": cam_aspect_ratio, "storageUri": f"gs://{current_gcs_bucket}/camera_videos/", "enhancePrompt": True}
                # if cam_duration: params["durationSeconds"] = cam_duration # If API supports it
                op_result = generate_veo_video(current_project_id, predict_ep, fetch_ep, cam_prompt.strip(), params, image_uri=gcs_image, camera_control=cam_control_type)
                display_generated_videos(op_result, current_local_dir, f"cam_{cam_control_type}_video")
            else: st.error("Failed to upload image for camera control.")

with tabs[4]: # Lyria Music Generation
    st.header("Lyria Music Generation")
    lyria_prompt = st.text_area("Music Prompt", placeholder="e.g., Epic cinematic score", key="lyria_prompt")
    lyria_neg_prompt = st.text_area("Negative Prompt (Optional)", placeholder="e.g., Off-key, noisy", key="lyria_neg_prompt")
    lyria_sample_count = st.number_input("Number of Samples", 1, 4, 2, key="lyria_samples") # Lyria Colab had fixed 4, making it configurable 1-4

    if st.button("Generate Lyria Music", key="lyria_btn"):
        current_lyria_project_id = lyria_project_id_input.strip()
        current_local_dir = local_output_dir_input.strip()
        if not all([current_lyria_project_id, current_local_dir, lyria_prompt.strip()]):
            st.error("Lyria Project ID, Local Output Dir, and Prompt are required for Music Generation.")
        else:
            music_samples = generate_lyria_music(current_lyria_project_id, lyria_prompt.strip(), lyria_neg_prompt.strip(), lyria_sample_count)
            if music_samples:
                st.success(f"Generated {len(music_samples)} music sample(s)!")
                music_output_path = os.path.join(current_local_dir, MUSIC_OUTPUT_SUBDIR)
                os.makedirs(music_output_path, exist_ok=True)
                for i, sample in enumerate(music_samples):
                    local_music_file = os.path.join(music_output_path, sample["filename"])
                    with open(local_music_file, "wb") as f:
                        f.write(sample["audio_bytes"])
                    st.markdown(f"**Sample {i+1}:** `{sample['filename']}`")
                    st.audio(local_music_file, format='audio/wav')
                    with open(local_music_file, "rb") as fp_music:
                        st.download_button(label=f"Download {sample['filename']}", data=fp_music, file_name=sample["filename"], mime="audio/wav", key=f"dl_music_{i}")
                    if drive_service and target_drive_folder_id:
                        upload_to_drive(drive_service, target_drive_folder_id, local_music_file)
            else:
                st.error("Lyria music generation failed or returned no samples.")

st.markdown("---")
st.markdown("Ensure `gcloud auth application-default login` is done and APIs are enabled.")
