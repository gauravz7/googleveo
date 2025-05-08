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

# Google Drive API imports
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request as GoogleAuthRequest # Alias to avoid conflict

# Load environment variables (though main app also does this)
load_dotenv()

# --- Configuration & Constants from v0-streamlit.py ---
# These might be overridden by passed-in arguments or main app's config
# For now, keeping them here for reference or potential local defaults if not passed
V0_DEFAULT_PROJECT_ID = os.getenv("DEFAULT_PROJECT_ID", "veo-testing") # Will be overridden by arg
V0_DEFAULT_OUTPUT_GCS_BUCKET = os.getenv("DEFAULT_OUTPUT_GCS_BUCKET", "fk-test-veo") # Will be overridden
V0_CLIENT_SECRETS_FILE = os.getenv("CLIENT_SECRETS_FILE", "credentials.json")
V0_DEFAULT_DRIVE_FOLDER_LINK_ENV = os.getenv("DEFAULT_DRIVE_FOLDER_LINK", "https://drive.google.com/drive/folders/15SK65dQ7bsFIYPR1y9UXmwPgoqK7X41b?resourcekey=0-Zc4YZjA43nl6weUSbHsOWQ&usp=drive_link") # Will be overridden

V0_IMAGE_UPLOAD_GCS_PREFIX = os.getenv("IMAGE_UPLOAD_GCS_PREFIX", "uploads/")
V0_TEMP_IMAGE_DIR = os.getenv("DEFAULT_TEMP_IMAGE_DIR", "temp_images")


# --- Helper Functions (Copied from v0-streamlit.py, prefixed with v0_ or kept local) ---
DRIVE_SCOPES_V0 = ['https://www.googleapis.com/auth/drive.file']

def v0_get_drive_service():
    creds = None
    token_path = 'token_v0.json' # Use a different token path to avoid conflict
    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, DRIVE_SCOPES_V0)
        except Exception as e:
            st.warning(f"Could not load {token_path}: {e}. Will attempt to re-authenticate.")
            creds = None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(GoogleAuthRequest())
            except Exception as e:
                st.error(f"Error refreshing Drive token: {e}")
                return None
        else:
            if not os.path.exists(V0_CLIENT_SECRETS_FILE):
                st.error(f"OAuth client secrets file ('{V0_CLIENT_SECRETS_FILE}') not found.")
                return None
            try:
                flow = InstalledAppFlow.from_client_secrets_file(V0_CLIENT_SECRETS_FILE, DRIVE_SCOPES_V0)
                auth_url, _ = flow.authorization_url(prompt='consent')
                # This interactive part is problematic for a module.
                # The main app should handle auth and pass the service.
                # For now, this will likely fail if auth is needed within the tab.
                st.info(f"Please go to this URL to authorize access to Google Drive (for v0 module): {auth_url}")
                auth_code = st.text_input("Enter the authorization code here (for v0 module):", key="v0_drive_auth_code")
                if auth_code:
                    flow.fetch_token(code=auth_code)
                    creds = flow.credentials
                else:
                    return None 
            except Exception as e:
                st.error(f"Error during Drive authentication flow (v0 module): {e}")
                return None
        try:
            with open(token_path, 'w') as token_file: token_file.write(creds.to_json())
        except Exception as e: st.error(f"Error saving Drive token (v0 module): {e}")
    
    if creds and creds.valid:
        try: return build('drive', 'v3', credentials=creds)
        except Exception as e: st.error(f"Error building Drive service (v0 module): {e}")
    return None

def v0_extract_folder_id_from_link(link):
    if not link: return None
    try:
        if "/folders/" in link:
            folder_id_part = link.split("/folders/")[1]
            return folder_id_part.split("?")[0]
    except Exception: pass # Keep it silent for now
    return None

def v0_upload_to_drive(drive_service, folder_id, file_path, file_name=None):
    if not drive_service: st.error("Drive service not available for upload (v0 module)."); return None
    # ... (rest of the function from v0-streamlit.py, ensuring it uses st for UI)
    if not file_name: file_name = os.path.basename(file_path)
    file_metadata = {'name': file_name, 'parents': [folder_id] if folder_id else []}
    try:
        drive_mime_type, _ = mimetypes.guess_type(file_path)
        if drive_mime_type is None: drive_mime_type = 'application/octet-stream'
        media = MediaFileUpload(file_path, mimetype=drive_mime_type, resumable=True)
        with st.spinner(f"Uploading {file_name} to Google Drive (v0)..."):
            request = drive_service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink')
            response = None
            progress_bar = st.progress(0)
            while response is None:
                status, response_chunk = request.next_chunk() # Renamed to avoid conflict
                if status: progress_bar.progress(int(status.progress() * 100))
                if response_chunk is not None: response = response_chunk # Actual response
            progress_bar.empty()
            st.success(f"File '{file_name}' uploaded to Google Drive (v0). Link: {response.get('webViewLink')}")
            return response.get('id'), response.get('webViewLink')
    except Exception as e:
        st.error(f"Error uploading {file_name} to Drive (v0): {e}")
    return None, None


def v0_download_image_from_url(image_url, temp_dir=V0_TEMP_IMAGE_DIR):
    if not image_url: return None
    try:
        response_req = requests.get(image_url, stream=True) # Renamed
        response_req.raise_for_status() 
        parsed_url = urlparse(image_url)
        original_filename = os.path.basename(parsed_url.path) or f"{uuid.uuid4()}.jpg"
        safe_filename = "".join(c if c.isalnum() or c in ('.','_','-') else '_' for c in original_filename) or f"{uuid.uuid4()}{os.path.splitext(original_filename)[1]}"
        os.makedirs(temp_dir, exist_ok=True)
        temp_file_path = os.path.join(temp_dir, f"{uuid.uuid4()}_{safe_filename}")
        with open(temp_file_path, 'wb') as f:
            for chunk in response_req.iter_content(chunk_size=8192): f.write(chunk)
        st.info(f"Image downloaded (v0) from {image_url} to {temp_file_path}")
        return temp_file_path
    except Exception as e: st.error(f"Error downloading image (v0) from {image_url}: {e}"); return None

def v0_get_gcs_client():
    try:
        credentials, project = google.auth.default()
        return storage.Client(credentials=credentials)
    except Exception as e: st.error(f"Error initializing GCS client (v0): {e}"); return None

def v0_upload_to_gcs(storage_client, bucket_name, source_file_path, destination_blob_name):
    if not storage_client: return None, None
    try:
        bucket = storage_client.bucket(bucket_name)
        mime_type, _ = mimetypes.guess_type(source_file_path)
        if mime_type is None: mime_type = 'application/octet-stream'
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_filename(source_file_path, content_type=mime_type)
        gcs_uri = f"gs://{bucket_name}/{destination_blob_name}"
        st.info(f"File {source_file_path} uploaded to {gcs_uri} (v0)")
        return gcs_uri, mime_type
    except Exception as e: st.error(f"Error uploading {source_file_path} to GCS (v0): {e}"); return None, None

def v0_download_from_gcs(storage_client, bucket_name, source_blob_name, destination_file_name):
    if not storage_client: return False
    try:
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(source_blob_name)
        os.makedirs(os.path.dirname(destination_file_name), exist_ok=True)
        blob.download_to_filename(destination_file_name)
        st.info(f"File {source_blob_name} downloaded to {destination_file_name} (v0)")
        return True
    except Exception as e: st.error(f"Error downloading {source_blob_name} from GCS (v0): {e}"); return False

def v0_send_request_to_google_api(api_endpoint, data=None): # project_id removed as it's in endpoint
    try:
        creds, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
        auth_req = google.auth.transport.requests.Request()
        creds.refresh(auth_req)
        headers = {'Authorization': f'Bearer {creds.token}', 'Content-Type': 'application/json'}
        response_req = requests.post(api_endpoint, headers=headers, json=data) # Renamed
        response_req.raise_for_status()
        return response_req.json()
    except Exception as e: st.error(f"An error occurred sending request to Google API (v0): {e}"); return None

def v0_compose_videogen_request(prompt, parameters, image_gcs_uri: str = "", image_mime_type: str = "image/png"):
  instance = {"prompt": prompt}
  if image_gcs_uri: instance["image"] = {"gcsUri": image_gcs_uri, "mimeType": image_mime_type}
  return {"instances": [instance], "parameters": parameters}

def v0_fetch_operation(fetch_api_endpoint, lro_name): # project_id removed
  request_payload = {'operationName': lro_name}
  max_retries = 60
  with st.spinner(f"Fetching operation status for {lro_name} (v0)..."):
    for i in range(max_retries):
        resp = v0_send_request_to_google_api(fetch_api_endpoint, data=request_payload)
        if resp:
            st.write(f"Attempt {i+1}/{max_retries}: Checking status (v0)...")
            if 'done' in resp and resp['done']: st.success(f"Operation {lro_name} completed (v0)."); return resp
        else: st.error("Failed to fetch operation status (v0). Aborting."); return None
        time.sleep(10)
  st.warning(f"Operation {lro_name} did not complete (v0)."); return None

def v0_generate_video_api_call(predict_api_endpoint, fetch_api_endpoint, prompt, parameters, image_gcs_uri: str = "", image_mime_type: str = "image/png"): # project_id removed
  req = v0_compose_videogen_request(prompt, parameters, image_gcs_uri, image_mime_type)
  st.write("Sending video generation request (v0)..."); st.json(req)
  resp = v0_send_request_to_google_api(predict_api_endpoint, data=req)
  if resp and 'name' in resp:
    st.info(f"Video generation initiated (v0). Operation name: {resp['name']}")
    return v0_fetch_operation(fetch_api_endpoint, resp['name'])
  else:
    st.error("Failed to initiate video generation (v0)."); 
    if resp: st.json(resp)
  return None

def v0_process_and_display_videos(operation_result, gcs_client_main, current_local_output_dir, source_identifier="video_v0", drive_service_main=None, drive_folder_id_main=None, current_drive_folder_link_main=None):
    if operation_result and operation_result.get('response') and operation_result['response'].get('videos'):
        st.success(f"Video generation successful for {source_identifier}!")
        videos_data = operation_result['response']['videos']
        os.makedirs(current_local_output_dir, exist_ok=True)
        for i, video_info in enumerate(videos_data):
            video_gcs_uri = video_info.get('gcsUri')
            if video_gcs_uri and video_gcs_uri.startswith("gs://"):
                parts = video_gcs_uri[5:].split("/", 1)
                video_bucket_name, video_blob_name = parts[0], parts[1] if len(parts) > 1 else ""
                base_name = os.path.basename(video_blob_name) or f"video_{uuid.uuid4()}.mp4" # Ensure mp4 extension
                local_video_filename = os.path.join(current_local_output_dir, f"generated_{source_identifier}_sample_{i+1}_{base_name}")
                if v0_download_from_gcs(gcs_client_main, video_bucket_name, video_blob_name, local_video_filename):
                    st.success(f"Video downloaded: {local_video_filename}")
                    with open(local_video_filename, "rb") as fp:
                        st.download_button(f"Download Video ({source_identifier} S{i+1})", fp, os.path.basename(local_video_filename), "video/mp4", key=f"v0_dl_vid_{source_identifier}_{i}")
                    st.video(local_video_filename, autoplay=True, muted=True)
                    if drive_service_main and drive_folder_id_main: 
                        v0_upload_to_drive(drive_service_main, drive_folder_id_main, local_video_filename)
                else: st.error(f"Failed to download {video_gcs_uri}")
            else: st.warning(f"Invalid or missing GCS URI for video sample {i+1}")
    elif operation_result and operation_result.get('error'):
        st.error(f"Video generation failed for {source_identifier}: {operation_result['error'].get('message', 'Unknown error')}")
        st.json(operation_result['error'])
    else:
        st.error(f"Video generation failed or timed out for {source_identifier}.")
        if operation_result: st.json(operation_result)


# This is the main function to be called by veo_streamlit_app.py for the tab
def display_standard_veo_tab_from_v0(
    # Inputs from the main app's sidebar
    main_project_id, 
    main_output_gcs_bucket, 
    main_local_output_dir,
    main_drive_folder_link,
    # Helper functions/clients from the main app
    main_gcs_client,
    main_get_drive_service_func, # This is tricky due to interactive auth in v0_get_drive_service
    main_extract_folder_id_from_link_func
    # Note: The v0 code has its own API call and processing logic.
    # Reusing main app's API call functions would require more refactoring of v0 logic.
    # For now, v0 module uses its own API call chain.
):
    st.header("Standard Veo Generation (v0 Logic)")

    # UI elements previously in v0's sidebar, now in the tab's main area
    uploaded_image_files = st.file_uploader("Upload Image(s) (Optional)", type=["png", "jpg", "jpeg"], accept_multiple_files=True, key="v0_std_img_upload")
    image_urls_input = st.text_area("Or Paste Image URLs (Optional, one per line)", height=100, placeholder="https://example.com/image1.jpg\nhttps://example.com/image2.png", key="v0_std_img_urls")
    
    prompt_input = st.text_area("Prompt", height=100, placeholder="e.g., A majestic lion roaming the savanna", key="v0_std_prompt")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        seed_input = st.number_input("Seed", value=777, min_value=0, key="v0_std_seed")
        aspect_ratio_input = st.selectbox("Aspect Ratio", options=["PORTRAIT", "LANDSCAPE"], index=0, key="v0_std_aspect")
    with col2:
        sample_count_input = st.number_input("Sample Count", value=1, min_value=1, max_value=4, key="v0_std_samples")
        duration_input = st.number_input("Duration (seconds)", value=8, min_value=1, max_value=60, key="v0_std_duration")
    with col3:
        enhance_prompt_input = st.checkbox("Enhance Prompt", value=False, key="v0_std_enhance")

    if st.button("Generate Video (v0 Logic)", key="v0_std_generate_btn"):
        if not main_project_id: st.error("Project ID is required (from main app config).")
        elif not main_output_gcs_bucket: st.error("Output GCS Bucket Name is required (from main app config).")
        elif not main_local_output_dir: st.error("Local Output Directory is required (from main app config).")
        elif not prompt_input and not uploaded_image_files and not image_urls_input.strip():
            st.error("Either a Prompt, an Uploaded Image, or Image URLs (or a combination) is required.")
        else:
            # Use main_gcs_client passed from the main app
            # The v0_get_drive_service is problematic due to its interactive auth.
            # For now, let's try to use it, but it might need user interaction within this tab.
            # A better approach would be for the main app to handle Drive auth once and pass the service.
            current_drive_service = None
            current_target_drive_folder_id = None
            if main_drive_folder_link:
                st.info("Attempting to init Google Drive service (v0 logic)...")
                # This is where it gets tricky. v0_get_drive_service has its own st.text_input
                # This might not work well when embedded.
                # For a quick test, we can call it. If it fails, Drive upload won't happen.
                # drive_service = v0_get_drive_service() # This is problematic
                drive_service_status_placeholder = st.empty()
                with drive_service_status_placeholder.container():
                     current_drive_service = main_get_drive_service_func() # Try using main app's drive service
                
                if current_drive_service:
                    drive_service_status_placeholder.success("Using main app's Google Drive service.")
                    current_target_drive_folder_id = main_extract_folder_id_from_link_func(main_drive_folder_link)
                    if not current_target_drive_folder_id:
                        st.error(f"Could not extract Folder ID from main app's Drive link: {main_drive_folder_link}")
                else:
                    drive_service_status_placeholder.warning("Could not get Drive service from main app. Drive uploads will be skipped.")


            _PREDICT_API_ENDPOINT = f'https://us-central1-autopush-aiplatform.sandbox.googleapis.com/v1beta1/projects/{main_project_id}/locations/us-central1/publishers/google/models/veo-2.0-generate-001:predictLongRunning'
            _FETCH_API_ENDPOINT = f'https://us-central1-autopush-aiplatform.sandbox.googleapis.com/v1beta1/projects/{main_project_id}/locations/us-central1/publishers/google/models/veo-2.0-generate-001:fetchPredictOperation'
            
            video_gen_params = {
                "storageUri": f"gs://{main_output_gcs_bucket}/video_outputs_v0_std/", # Unique path
                "sampleCount": sample_count_input, "seed": seed_input,
                "aspectRatio": "16:9" if aspect_ratio_input == "LANDSCAPE" else "9:16",
                "durationSeconds": duration_input, "enhancePrompt": enhance_prompt_input,
                "personGeneration": "allow_adult",
            }
            st.subheader("Video Generation Progress (v0 Logic)")

            image_sources_to_process = []
            if uploaded_image_files:
                for uploaded_file in uploaded_image_files:
                    image_sources_to_process.append({"type": "file", "data": uploaded_file, "name": uploaded_file.name})
            if image_urls_input.strip():
                urls = [url.strip() for url in image_urls_input.strip().splitlines() if url.strip()]
                for i, url_item in enumerate(urls): # Renamed url to url_item
                    image_sources_to_process.append({"type": "url", "data": url_item, "name": f"url_image_{i+1}_{os.path.basename(urlparse(url_item).path) or uuid.uuid4()}"})
            
            if not image_sources_to_process and prompt_input:
                st.info("Generating video based on prompt (v0 logic, no images)...")
                operation_result = v0_generate_video_api_call(_PREDICT_API_ENDPOINT, _FETCH_API_ENDPOINT, prompt_input, video_gen_params)
                v0_process_and_display_videos(operation_result, main_gcs_client, main_local_output_dir, "prompt_based_v0", current_drive_service, current_target_drive_folder_id, main_drive_folder_link)
            
            elif image_sources_to_process:
                for image_source in image_sources_to_process:
                    st.markdown(f"--- \n ### Processing image (v0): {image_source['name']}")
                    image_gcs_uri_for_api = ""
                    image_mime_type_for_api = "image/png" 
                    temp_image_path_for_gcs = None

                    if image_source["type"] == "file":
                        uploaded_image_file_obj = image_source["data"]
                        # Save to a temporary local path before uploading to GCS
                        temp_dir_for_upload = os.path.join(".", V0_TEMP_IMAGE_DIR, "temp_uploads")
                        os.makedirs(temp_dir_for_upload, exist_ok=True)
                        temp_image_path_for_gcs = os.path.join(temp_dir_for_upload, uploaded_image_file_obj.name)
                        with open(temp_image_path_for_gcs, "wb") as f:
                            f.write(uploaded_image_file_obj.getbuffer())
                    
                    elif image_source["type"] == "url":
                        with st.spinner(f"Downloading image from URL (v0): {image_source['data']} ..."):
                            temp_image_path_for_gcs = v0_download_image_from_url(image_source['data'], V0_TEMP_IMAGE_DIR)
                        if not temp_image_path_for_gcs:
                            st.error(f"Failed to download image from URL (v0): {image_source['data']}. Skipping.")
                            continue
                    
                    if temp_image_path_for_gcs:
                        with st.spinner(f"Uploading {image_source['name']} to GCS (v0)..."):
                            image_extension = os.path.splitext(image_source['name'])[1] if image_source['name'] else ".jpg"
                            unique_image_filename_gcs = f"{uuid.uuid4()}{image_extension}"
                            destination_image_blob_name = f"{V0_IMAGE_UPLOAD_GCS_PREFIX}{unique_image_filename_gcs}"
                            
                            image_gcs_uri_for_api, image_mime_type_for_api = v0_upload_to_gcs(
                                main_gcs_client, # Use main GCS client
                                main_output_gcs_bucket,
                                temp_image_path_for_gcs,
                                destination_image_blob_name
                            )
                            try: # Cleanup temp file
                                os.remove(temp_image_path_for_gcs)
                                if image_source["type"] == "url" and os.path.dirname(temp_image_path_for_gcs) == V0_TEMP_IMAGE_DIR and not os.listdir(V0_TEMP_IMAGE_DIR):
                                    os.rmdir(V0_TEMP_IMAGE_DIR) 
                            except OSError: pass # Ignore cleanup error

                            if not image_gcs_uri_for_api:
                                st.error(f"GCS Image upload failed for {image_source['name']} (v0). Skipping.")
                                continue
                        
                        st.info(f"Generating video for {image_source['name']} (v0)...")
                        operation_result = v0_generate_video_api_call(_PREDICT_API_ENDPOINT, _FETCH_API_ENDPOINT, prompt_input, video_gen_params, image_gcs_uri=image_gcs_uri_for_api, image_mime_type=image_mime_type_for_api)
                        v0_process_and_display_videos(operation_result, main_gcs_client, main_local_output_dir, image_source['name'], current_drive_service, current_target_drive_folder_id, main_drive_folder_link)
                    else:
                        st.error(f"Could not get temp path for image: {image_source['name']} (v0). Skipping.")
            else: # Should not happen due to initial checks, but as a fallback
                 st.error("No valid input for video generation (v0).")


if __name__ == "__main__":
    # This part is for testing the module independently if needed
    st.set_page_config(layout="wide", page_title="Standard Veo (v0) Test")
    
    # Mock necessary inputs if running standalone
    mock_project_id = os.getenv("DEFAULT_PROJECT_ID", "your-gcp-project-id")
    mock_gcs_bucket = os.getenv("DEFAULT_OUTPUT_GCS_BUCKET", "your-gcs-bucket")
    mock_local_dir = "Output_v0_test"
    mock_drive_link = "" # Or a test link

    # Mock GCS client for standalone UI test (won't actually connect)
    class MockGCSClient:
        def bucket(self, name): return self
        def blob(self, name): return self
        def upload_from_filename(self, path, content_type): pass
        def download_to_filename(self, path): pass
    
    mock_gcs_client_obj = MockGCSClient()

    # Mock drive functions for UI test
    def mock_get_drive_service(): return None
    def mock_extract_id(link): return "mock_folder_id" if link else None

    st.sidebar.info("Standalone Test Mode for standard_veo_module.py")
    st.sidebar.text_input("Test Project ID", value=mock_project_id, key="main_proj_id_test")
    # ... add other mock inputs if needed for full UI test

    display_standard_veo_tab_from_v0(
        main_project_id=mock_project_id,
        main_output_gcs_bucket=mock_gcs_bucket,
        main_local_output_dir=mock_local_dir,
        main_drive_folder_link=mock_drive_link,
        main_gcs_client=mock_gcs_client_obj, # Pass the mock
        main_get_drive_service_func=mock_get_drive_service,
        main_extract_folder_id_from_link_func=mock_extract_id
    )
