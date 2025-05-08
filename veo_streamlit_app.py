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
from urllib.parse import urlparse # For extracting filename from URL
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Google Drive API imports
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request as GoogleAuthRequest # Alias to avoid conflict

# --- Configuration & Constants ---
# Values will be loaded from .env or use hardcoded defaults if not found
DEFAULT_PROJECT_ID = os.getenv("DEFAULT_PROJECT_ID", "veo-testing")
DEFAULT_OUTPUT_GCS_BUCKET = os.getenv("DEFAULT_OUTPUT_GCS_BUCKET", "fk-test-veo")
CLIENT_SECRETS_FILE = os.getenv("CLIENT_SECRETS_FILE", "credentials.json")
DEFAULT_DRIVE_FOLDER_LINK_ENV = os.getenv("DEFAULT_DRIVE_FOLDER_LINK", "https://drive.google.com/drive/folders/15SK65dQ7bsFIYPR1y9UXmwPgoqK7X41b?resourcekey=0-Zc4YZjA43nl6weUSbHsOWQ&usp=drive_link")

IMAGE_UPLOAD_GCS_PREFIX = os.getenv("IMAGE_UPLOAD_GCS_PREFIX", "uploads/")
TEMP_IMAGE_DIR = os.getenv("DEFAULT_TEMP_IMAGE_DIR", "temp_images")


# --- Helper Functions ---

# --- Google Drive Helper Functions ---
DRIVE_SCOPES = ['https://www.googleapis.com/auth/drive.file']
# CLIENT_SECRETS_FILE is now loaded from .env

def get_drive_service():
    """Authenticates and returns a Google Drive service object."""
    creds = None
    token_path = 'token.json' # Can also be made configurable via .env if needed
    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, DRIVE_SCOPES)
        except Exception as e:
            st.warning(f"Could not load {token_path}: {e}. Will attempt to re-authenticate.")
            creds = None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(GoogleAuthRequest())
            except Exception as e:
                st.error(f"Error refreshing Drive token: {e}")
                st.info("Please try authenticating again.")
                return None
        else:
            if not os.path.exists(CLIENT_SECRETS_FILE):
                st.error(f"OAuth client secrets file ('{CLIENT_SECRETS_FILE}') not found. "
                         "Please ensure it's correctly named and in the specified path (check .env).")
                return None
            try:
                flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, DRIVE_SCOPES)
                auth_url, _ = flow.authorization_url(prompt='consent')
                st.info(f"Please go to this URL to authorize access to Google Drive: {auth_url}")
                auth_code = st.text_input("Enter the authorization code here:")
                if auth_code:
                    flow.fetch_token(code=auth_code)
                    creds = flow.credentials
                else:
                    st.info("Awaiting authorization code to proceed with Drive authentication.")
                    return None
            except Exception as e:
                st.error(f"Error during Drive authentication flow: {e}")
                return None
        try:
            with open(token_path, 'w') as token_file:
                token_file.write(creds.to_json())
            st.success(f"Drive authentication successful. Token saved to {token_path}.")
        except Exception as e:
            st.error(f"Error saving Drive token: {e}")
    if creds and creds.valid:
        try:
            service = build('drive', 'v3', credentials=creds)
            return service
        except Exception as e:
            st.error(f"Error building Drive service: {e}")
            return None
    else:
        st.error("Failed to obtain valid Google Drive credentials.")
        return None

def extract_folder_id_from_link(link):
    if not link: return None
    try:
        if "/folders/" in link:
            folder_id_part = link.split("/folders/")[1]
            return folder_id_part.split("?")[0]
    except Exception as e: st.error(f"Could not parse Drive folder ID from link '{link}': {e}")
    return None

def upload_to_drive(drive_service, folder_id, file_path, file_name=None):
    if not drive_service: st.error("Drive service not available for upload."); return None
    if not file_name: file_name = os.path.basename(file_path)
    file_metadata = {'name': file_name, 'parents': [folder_id] if folder_id else []}
    try:
        drive_mime_type, _ = mimetypes.guess_type(file_path)
        if drive_mime_type is None: drive_mime_type = 'application/octet-stream'
        media = MediaFileUpload(file_path, mimetype=drive_mime_type, resumable=True)
        with st.spinner(f"Uploading {file_name} to Google Drive..."):
            request = drive_service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink')
            response = None
            progress_bar = st.progress(0)
            while response is None:
                status, response = request.next_chunk()
                if status: progress_bar.progress(int(status.progress() * 100))
            progress_bar.empty()
            st.success(f"File '{file_name}' uploaded to Google Drive. Link: {response.get('webViewLink')}")
            return response.get('id'), response.get('webViewLink')
    except Exception as e:
        st.error(f"Error uploading {file_name} to Drive: {e}")
        if "invalidParents" in str(e).lower(): st.error("The specified Google Drive folder ID might be incorrect or you may not have write permissions.")
        elif "notFound" in str(e).lower() and "file" in str(e).lower(): st.error(f"The file to upload ({file_path}) was not found locally.")
        return None, None

# --- GCS and Image Helper Functions ---
def download_image_from_url(image_url, temp_dir=TEMP_IMAGE_DIR):
    """Downloads an image from a URL and saves it to a temporary directory."""
    if not image_url:
        return None
    try:
        response = requests.get(image_url, stream=True)
        response.raise_for_status() 

        parsed_url = urlparse(image_url)
        original_filename = os.path.basename(parsed_url.path)
        if not original_filename: 
             original_filename = f"{uuid.uuid4()}.jpg" 

        safe_filename = "".join(c if c.isalnum() or c in ('.', '_', '-') else '_' for c in original_filename)
        if not safe_filename: 
            safe_filename = f"{uuid.uuid4()}{os.path.splitext(original_filename)[1]}"

        os.makedirs(temp_dir, exist_ok=True)
        temp_file_path = os.path.join(temp_dir, f"{uuid.uuid4()}_{safe_filename}")

        with open(temp_file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        st.info(f"Image downloaded from {image_url} to {temp_file_path}")
        return temp_file_path
    except requests.exceptions.RequestException as e:
        st.error(f"Error downloading image from {image_url}: {e}")
        return None
    except Exception as e:
        st.error(f"An unexpected error occurred while downloading {image_url}: {e}")
        return None

def get_gcs_client():
    try:
        credentials, project = google.auth.default()
        return storage.Client(credentials=credentials)
    except Exception as e:
        st.error(f"Error initializing GCS client: {e}")
        st.error("Please ensure you have authenticated via 'gcloud auth application-default login' or set GOOGLE_APPLICATION_CREDENTIALS.")
        return None

def upload_to_gcs(storage_client, bucket_name, source_file_path, destination_blob_name):
    if not storage_client: return None
    try:
        bucket = storage_client.bucket(bucket_name)
        mime_type, _ = mimetypes.guess_type(source_file_path)
        if mime_type is None: mime_type = 'application/octet-stream'
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_filename(source_file_path, content_type=mime_type)
        gcs_uri = f"gs://{bucket_name}/{destination_blob_name}"
        st.info(f"File {source_file_path} uploaded to {gcs_uri}")
        return gcs_uri, mime_type
    except Exception as e: st.error(f"Error uploading {source_file_path} to GCS: {e}"); return None, None

def download_from_gcs(storage_client, bucket_name, source_blob_name, destination_file_name):
    if not storage_client: return False
    try:
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(source_blob_name)
        os.makedirs(os.path.dirname(destination_file_name), exist_ok=True)
        blob.download_to_filename(destination_file_name)
        st.info(f"File {source_blob_name} downloaded to {destination_file_name}")
        return True
    except Exception as e: st.error(f"Error downloading {source_blob_name} from GCS: {e}"); return False

def send_request_to_google_api(api_endpoint, project_id, data=None):
    try:
        creds, detected_project_id = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
        auth_req = google.auth.transport.requests.Request()
        creds.refresh(auth_req)
        headers = {'Authorization': f'Bearer {creds.token}', 'Content-Type': 'application/json'}
        response = requests.post(api_endpoint, headers=headers, json=data)
        response.raise_for_status()
        return response.json()
    except google.auth.exceptions.DefaultCredentialsError:
        st.error("Could not automatically find credentials. Please run 'gcloud auth application-default login' or set GOOGLE_APPLICATION_CREDENTIALS.")
    except requests.exceptions.HTTPError as http_err: st.error(f"HTTP error occurred: {http_err} - {response.text}")
    except Exception as e: st.error(f"An error occurred while sending request to Google API: {e}")
    return None

def compose_videogen_request(prompt, parameters, image_gcs_uri: str = "", image_mime_type: str = "image/png"):
  instance = {"prompt": prompt}
  if image_gcs_uri: instance["image"] = {"gcsUri": image_gcs_uri, "mimeType": image_mime_type}
  return {"instances": [instance], "parameters": parameters}

def fetch_operation(fetch_api_endpoint, project_id, lro_name):
  request_payload = {'operationName': lro_name}
  max_retries = 60
  with st.spinner(f"Fetching operation status for {lro_name}... This may take several minutes."):
    for i in range(max_retries):
        resp = send_request_to_google_api(fetch_api_endpoint, project_id, data=request_payload)
        if resp:
            st.write(f"Attempt {i+1}/{max_retries}: Checking status...")
            if 'done' in resp and resp['done']: st.success(f"Operation {lro_name} completed."); return resp
        else: st.error("Failed to fetch operation status. Aborting."); return None
        time.sleep(10)
  st.warning(f"Operation {lro_name} did not complete after {max_retries*10} seconds."); return None

def generate_video_api_call(project_id, predict_api_endpoint, fetch_api_endpoint, prompt, parameters, image_gcs_uri: str = "", image_mime_type: str = "image/png"):
  req = compose_videogen_request(prompt, parameters, image_gcs_uri, image_mime_type)
  st.write("Sending video generation request..."); st.json(req)
  resp = send_request_to_google_api(predict_api_endpoint, project_id, data=req)
  if resp and 'name' in resp:
    st.info(f"Video generation initiated. Operation name: {resp['name']}")
    return fetch_operation(fetch_api_endpoint, project_id, resp['name'])
  else:
    st.error("Failed to initiate video generation.")
    if resp: st.json(resp)
    return None

# --- Streamlit UI ---
st.set_page_config(layout="wide")
st.title("🎬 Veo Video Generation with Vertex AI")

st.sidebar.header("🔑 GCP Configuration")
project_id_input = st.sidebar.text_input("Google Cloud Project ID", value=DEFAULT_PROJECT_ID)
output_gcs_bucket_name_input = st.sidebar.text_input("GCS Bucket for Output (Videos & Image Uploads)", value=DEFAULT_OUTPUT_GCS_BUCKET)
local_output_dir_input = st.sidebar.text_input("Local Output Directory for Videos", value=os.getenv("DEFAULT_LOCAL_OUTPUT_DIR", "Output"), placeholder="e.g., GeneratedVideos")


st.sidebar.header("💾 Google Drive Output (Optional)")
drive_folder_link_input = st.sidebar.text_input("Google Drive Folder Link", value=DEFAULT_DRIVE_FOLDER_LINK_ENV, placeholder="Enter Google Drive folder link or leave blank")

st.sidebar.header("🖼️ Image Input")
uploaded_image_files = st.sidebar.file_uploader("Upload Image(s) (Optional)", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
image_urls_input = st.sidebar.text_area("Or Paste Image URLs (Optional, one per line)", height=150, placeholder="https://example.com/image1.jpg\nhttps://example.com/image2.png")

st.sidebar.header("📝 Video Generation Parameters")
prompt_input = st.sidebar.text_area("Prompt", height=100, placeholder="e.g., A majestic lion roaming the savanna") # Renamed to avoid conflict if 'prompt' is used as var
seed_input = st.sidebar.number_input("Seed", value=777, min_value=0)
aspect_ratio_input = st.sidebar.selectbox("Aspect Ratio", options=["PORTRAIT", "LANDSCAPE"], index=0)
sample_count_input = st.sidebar.number_input("Sample Count", value=1, min_value=1, max_value=4)
duration_input = st.sidebar.number_input("Duration (seconds)", value=8, min_value=1, max_value=60)
enhance_prompt_input = st.sidebar.checkbox("Enhance Prompt", value=False)

def process_and_display_videos(operation_result, gcs_client, current_local_output_dir, source_identifier="video", drive_service=None, drive_folder_id=None, current_drive_folder_link=None): # Added current_drive_folder_link
    """Helper function to process API result, display videos, and upload to Drive."""
    if operation_result and operation_result.get('response') and operation_result['response'].get('videos'):
        st.success(f"Video generation successful for {source_identifier}!")
        videos_data = operation_result['response']['videos']
        os.makedirs(current_local_output_dir, exist_ok=True)
        for i, video_info in enumerate(videos_data):
            video_gcs_uri = video_info.get('gcsUri')
            if video_gcs_uri:
                st.write(f"Generated video GCS URI ({source_identifier} - Sample {i+1}): {video_gcs_uri}")
                if video_gcs_uri.startswith("gs://"):
                    parts = video_gcs_uri[5:].split("/", 1)
                    video_bucket_name = parts[0]
                    video_blob_name = parts[1] if len(parts) > 1 else ""
                    base_name = os.path.basename(video_blob_name)
                    local_video_filename = os.path.join(current_local_output_dir, f"generated_{source_identifier}_sample_{i+1}_{base_name}")
                    with st.spinner(f"Downloading {video_gcs_uri} to {local_video_filename}..."):
                        download_success = download_from_gcs(gcs_client, video_bucket_name, video_blob_name, local_video_filename)
                    if download_success:
                        st.success(f"Video downloaded to: {local_video_filename}")
                        with open(local_video_filename, "rb") as fp:
                            st.download_button(label=f"Download Video ({source_identifier} - Sample {i+1})", data=fp, file_name=os.path.basename(local_video_filename), mime="video/mp4")
                        st.video(local_video_filename, autoplay=True, muted=True)
                        if drive_service and drive_folder_id:
                            upload_to_drive(drive_service, drive_folder_id, local_video_filename)
                        elif drive_service and not drive_folder_id and current_drive_folder_link: 
                            st.warning("Google Drive link provided, but could not determine Folder ID. Video not uploaded to Drive.")
                    else: st.error(f"Failed to download video {video_gcs_uri}")
                else: st.warning(f"Could not parse GCS URI for video: {video_gcs_uri}")
            else: st.warning(f"Video information found for {source_identifier} (Sample {i+1}), but GCS URI is missing.")
    elif operation_result and operation_result.get('error'):
        st.error(f"Video generation failed for {source_identifier} with error: {operation_result['error'].get('message', 'Unknown error')}")
        st.json(operation_result['error'])
    else:
        st.error(f"Video generation failed or timed out for {source_identifier}. Check logs for details.")
        if operation_result: st.json(operation_result)

# Main section
st.header("🚀 Generate Video")
if st.button("Generate Video"):
    # Get values from UI inputs
    current_project_id = project_id_input
    current_output_gcs_bucket = output_gcs_bucket_name_input
    current_local_output_dir = local_output_dir_input.strip()
    current_drive_folder_link = drive_folder_link_input.strip()
    current_prompt = prompt_input
    
    if not current_project_id: st.error("Project ID is required.")
    elif not current_output_gcs_bucket: st.error("Output GCS Bucket Name is required.")
    elif not current_local_output_dir: st.error("Local Output Directory is required.")
    elif not current_prompt and not uploaded_image_files and not image_urls_input.strip():
        st.error("Either a Prompt, an Uploaded Image, or Image URLs (or a combination) is required.")
    else:
        gcs_client = get_gcs_client()
        if not gcs_client: st.stop()
        
        drive_service = None
        target_drive_folder_id = None
        if current_drive_folder_link:
            st.info("Attempting to authenticate with Google Drive...")
            drive_auth_placeholder = st.empty() 
            with drive_auth_placeholder.container():
                drive_service = get_drive_service()
            if drive_service:
                drive_auth_placeholder.success("Google Drive authenticated.")
                target_drive_folder_id = extract_folder_id_from_link(current_drive_folder_link)
                if not target_drive_folder_id:
                    st.error(f"Could not extract a valid Folder ID from the provided Google Drive link: {current_drive_folder_link}. Videos will not be uploaded to Drive.")
                else: st.info(f"Videos will be uploaded to Google Drive Folder ID: {target_drive_folder_id}")
            else: drive_auth_placeholder.error("Google Drive authentication failed or was not completed. Videos will not be uploaded to Drive.")
        
        _PREDICT_API_ENDPOINT = f'https://us-central1-autopush-aiplatform.sandbox.googleapis.com/v1beta1/projects/{current_project_id}/locations/us-central1/publishers/google/models/veo-2.0-generate-001:predictLongRunning'
        _FETCH_API_ENDPOINT = f'https://us-central1-autopush-aiplatform.sandbox.googleapis.com/v1beta1/projects/{current_project_id}/locations/us-central1/publishers/google/models/veo-2.0-generate-001:fetchPredictOperation'
        video_gen_params = {
            "storageUri": f"gs://{current_output_gcs_bucket}/video_outputs/",
            "sampleCount": sample_count_input, "seed": seed_input,
            "aspectRatio": "16:9" if aspect_ratio_input == "LANDSCAPE" else "9:16",
            "durationSeconds": duration_input, "enhancePrompt": enhance_prompt_input,
            "personGeneration": "allow_adult",
        }
        st.subheader("Video Generation Progress")

        image_sources_to_process = []
        if uploaded_image_files:
            for uploaded_file in uploaded_image_files:
                image_sources_to_process.append({"type": "file", "data": uploaded_file, "name": uploaded_file.name})
        if image_urls_input.strip():
            urls = [url.strip() for url in image_urls_input.strip().splitlines() if url.strip()]
            for i, url in enumerate(urls):
                image_sources_to_process.append({"type": "url", "data": url, "name": f"url_image_{i+1}_{os.path.basename(urlparse(url).path) or uuid.uuid4()}"})
        
        if not image_sources_to_process and current_prompt:
            st.info("Generating video based on prompt (no images provided)...")
            operation_result = generate_video_api_call(current_project_id, _PREDICT_API_ENDPOINT, _FETCH_API_ENDPOINT, current_prompt, video_gen_params)
            process_and_display_videos(operation_result, gcs_client, current_local_output_dir, "prompt_based", drive_service, target_drive_folder_id, current_drive_folder_link)
        
        elif image_sources_to_process:
            for image_source in image_sources_to_process:
                st.markdown(f"--- \n ### Processing image: {image_source['name']}")
                image_gcs_uri_for_api = ""
                image_mime_type_for_api = "image/png" 
                temp_image_path_for_gcs = None

                if image_source["type"] == "file":
                    uploaded_image_file_obj = image_source["data"]
                    temp_image_path_for_gcs = os.path.join(".", uploaded_image_file_obj.name) 
                    with open(temp_image_path_for_gcs, "wb") as f:
                        f.write(uploaded_image_file_obj.getbuffer())
                
                elif image_source["type"] == "url":
                    with st.spinner(f"Downloading image from URL: {image_source['data']} ..."):
                        temp_image_path_for_gcs = download_image_from_url(image_source['data'])
                    if not temp_image_path_for_gcs:
                        st.error(f"Failed to download image from URL: {image_source['data']}. Skipping this image.")
                        continue
                
                if temp_image_path_for_gcs:
                    with st.spinner(f"Uploading {image_source['name']} to GCS..."):
                        image_extension = os.path.splitext(image_source['name'])[1] if image_source['name'] else ".jpg"
                        unique_image_filename_gcs = f"{uuid.uuid4()}{image_extension}"
                        destination_image_blob_name = f"{IMAGE_UPLOAD_GCS_PREFIX}{unique_image_filename_gcs}"
                        
                        image_gcs_uri_for_api, image_mime_type_for_api = upload_to_gcs(
                            gcs_client,
                            current_output_gcs_bucket, # Use current value
                            temp_image_path_for_gcs,
                            destination_image_blob_name
                        )
                        try:
                            os.remove(temp_image_path_for_gcs)
                            if image_source["type"] == "url" and os.path.dirname(temp_image_path_for_gcs) == TEMP_IMAGE_DIR and not os.listdir(TEMP_IMAGE_DIR):
                                os.rmdir(TEMP_IMAGE_DIR) 
                        except OSError as e:
                            st.warning(f"Could not remove temporary image file {temp_image_path_for_gcs}: {e}")

                        if not image_gcs_uri_for_api:
                            st.error(f"GCS Image upload failed for {image_source['name']}. Skipping this image.")
                            continue
                    
                    st.info(f"Generating video for {image_source['name']}...")
                    operation_result = generate_video_api_call(current_project_id, _PREDICT_API_ENDPOINT, _FETCH_API_ENDPOINT, current_prompt, video_gen_params, image_gcs_uri=image_gcs_uri_for_api, image_mime_type=image_mime_type_for_api)
                    process_and_display_videos(operation_result, gcs_client, current_local_output_dir, image_source['name'], drive_service, target_drive_folder_id, current_drive_folder_link)
                else:
                    st.error(f"Could not obtain a temporary local path for image source: {image_source['name']}. Skipping.")

st.markdown("---")
st.markdown("Ensure you have authenticated with Google Cloud: `gcloud auth application-default login`")
st.markdown("And that the necessary APIs (Vertex AI, Cloud Storage) are enabled for your project.")
