# Veo Streamlit Video Generation App

This Streamlit application allows users to generate videos using Google's Veo model via Vertex AI. It supports video generation from text prompts, uploaded images, or direct image URLs.

## Features

-   **Multiple Input Sources:**
    -   Text prompts.
    -   Direct image file uploads (supports multiple files).
    -   Image URLs (paste multiple URLs, one per line).
-   **Configuration:**
    -   Most configurations are managed via a `.env` file (e.g., GCP Project ID, GCS bucket).
    -   Streamlit sidebar for runtime parameters (seed, aspect ratio, duration, etc.).
    -   Configurable local output directory for generated videos.
-   **Google Cloud Integration:**
    -   Uses Vertex AI for video generation.
    -   Utilizes Google Cloud Storage (GCS) for intermediate storage of uploaded images and generated videos.
-   **Google Drive Integration (Optional):**
    -   Upload generated videos directly to a specified Google Drive folder.
    -   Requires OAuth 2.0 setup (`credentials.json`).
-   **Local Output:**
    -   Videos are downloaded to a user-specified local directory.
    -   Videos are displayed and autoplayed in the Streamlit app.
-   **Environment Management:**
    -   `requirements.txt` for Python dependencies.
    -   `.gitignore` to exclude sensitive files and local artifacts.

## Setup

1.  **Clone the Repository (or set up your local copy):**
    ```bash
    # If you haven't already, initialize git and add remote
    # git init
    # git remote add origin https://github.com/gauravz7/googleveo.git
    ```

2.  **Create and Configure `.env` File:**
    -   Copy the existing `veo_streamlit_app.py` default constants or create a new `.env` file in the root directory.
    -   Example `.env` content:
        ```env
        DEFAULT_PROJECT_ID="your-gcp-project-id"
        DEFAULT_OUTPUT_GCS_BUCKET="your-gcs-bucket-name"
        CLIENT_SECRETS_FILE="credentials.json" # Path to your OAuth client secrets
        DEFAULT_DRIVE_FOLDER_LINK="your-google-drive-folder-link-optional"
        # IMAGE_UPLOAD_GCS_PREFIX="uploads/" (optional, defaults in script)
        # DEFAULT_TEMP_IMAGE_DIR="temp_images" (optional, defaults in script)
        ```
    -   **Important:** The `.env` file is ignored by git.

3.  **Google Cloud Project Setup:**
    -   Ensure you have a Google Cloud Project with billing enabled.
    -   Enable the **Vertex AI API** and **Cloud Storage API**.
    -   Authenticate `gcloud` for Application Default Credentials:
        ```bash
        gcloud auth application-default login
        ```

4.  **Google Drive API Setup (Optional, for Drive Uploads):**
    -   In your GCP Console, enable the **Google Drive API**.
    -   Configure the **OAuth consent screen**.
    -   Create an **OAuth 2.0 Client ID** for a "Web application".
        -   Add `http://localhost:8501` (or your Streamlit port) as an "Authorized redirect URI". You might also need to add `http://localhost`.
    -   Download the client secrets JSON file, rename it to `credentials.json` (or the name specified in your `.env` for `CLIENT_SECRETS_FILE`), and place it in the project root (or the specified path).
    -   `credentials.json` is ignored by git.

5.  **Install Dependencies:**
    -   It's recommended to use a virtual environment.
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    pip install -r requirements.txt
    ```

## Running the Application

1.  Ensure your `.env` file is configured and `credentials.json` (if using Drive) is in place.
2.  Run the Streamlit app:
    ```bash
    streamlit run veo_streamlit_app.py
    ```
3.  Open the provided local URL in your browser.
4.  Configure parameters in the sidebar and generate videos.
    -   If using Google Drive upload for the first time, you'll be guided through an authentication flow (copy URL, authorize, paste code back into the app). A `token.json` will be created to store your authorization for future sessions. `token.json` is ignored by git.

## Files to Keep Private

-   `.env`
-   `credentials.json`
-   `token.json`
These are included in `.gitignore`.
