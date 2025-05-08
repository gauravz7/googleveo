# Veo & Lyria Streamlit AI Generation Hub

This Streamlit application allows users to generate videos using Google's Veo model and music using Google's Lyria model, both via Vertex AI. It supports various advanced video generation features and standard text-to-video/image-to-video.

## Features

-   **Veo Video Generation (Tabbed Interface):**
    -   **Standard Generation:**
        -   Text prompts.
        -   Direct image file uploads (supports multiple files).
        -   Image URLs (paste multiple URLs, one per line).
    -   **Interpolation:** Generate video by interpolating between a first and last uploaded frame.
    -   **Video Extension:** Extend an existing uploaded video by 4-7 seconds.
    -   **Camera Controls:** Apply specific camera movements (e.g., PAN_LEFT, PULL_OUT) to a video generated from a starting image.
-   **Movie Creator Tab:**
    -   Upload up to 10 video clips.
    -   For each clip, add text that appears word-by-word (animation speed adjustable).
    -   Adjust playback tempo for each video clip (1.0x, 1.05x, 1.1x, 1.15x, 1.2x).
    -   Select font for text overlays.
    -   Optionally, upload a background audio file for the final combined movie.
    -   Concatenates all processed clips into a single movie.
-   **Lyria Music Generation (Tabbed Interface):**
    -   Generate music from text prompts.
    -   Option for negative prompts.
    -   Configurable number of samples.
-   **Configuration:**
    -   Most configurations are managed via a `.env` file (e.g., GCP Project IDs, GCS bucket).
    -   Streamlit sidebar for runtime parameters (seed, aspect ratio, duration, etc.).
    -   Configurable local output directory for generated media.
-   **Google Cloud Integration:**
    -   Uses Vertex AI for video (Veo) and music (Lyria) generation.
    -   Utilizes Google Cloud Storage (GCS) for intermediate storage of uploaded images/videos and generated videos.
-   **Google Drive Integration (Optional):**
    -   Upload generated videos and music directly to a specified Google Drive folder.
    -   Requires OAuth 2.0 setup (`credentials.json`).
-   **Local Output:**
    -   Videos and music are downloaded to a user-specified local directory (videos in main, music in a `lyria_music_outputs` subdirectory).
    -   Media is displayed and autoplayed (videos) or made playable (music) in the Streamlit app.
-   **Environment Management:**
    -   `requirements.txt` for Python dependencies.
    -   `.gitignore` to exclude sensitive files and local artifacts.
    -   Modular code with `lyria.py` for music generation logic.

## Setup

1.  **Clone the Repository (or set up your local copy):**
    ```bash
    # If you haven't already, initialize git and add remote
    # git init
    # git remote add origin https://github.com/gauravz7/googleveo.git 
    ```

2.  **Create and Configure `.env` File:**
    -   Create a `.env` file in the root directory.
    -   Example `.env` content:
        ```env
        DEFAULT_PROJECT_ID="your-veo-gcp-project-id"
        DEFAULT_LYRIA_PROJECT_ID="your-lyria-gcp-project-id" # Can be the same or different from Veo's
        DEFAULT_OUTPUT_GCS_BUCKET="your-gcs-bucket-name"
        CLIENT_SECRETS_FILE="credentials.json" # Path to your OAuth client secrets for Drive
        DEFAULT_DRIVE_FOLDER_LINK="your-google-drive-folder-link-optional"
        # IMAGE_UPLOAD_GCS_PREFIX="uploads/" (optional, defaults in script)
        # VIDEO_UPLOAD_GCS_PREFIX="video_uploads/" (optional, defaults in script)
        # DEFAULT_TEMP_MEDIA_DIR="temp_media" (optional, defaults in script)
        ```
    -   **Important:** The `.env` file is ignored by git.

3.  **Google Cloud Project Setup:**
    -   Ensure you have Google Cloud Project(s) with billing enabled.
    -   Enable the **Vertex AI API** and **Cloud Storage API** for the project(s) used. (Lyria also uses Vertex AI endpoints).
    -   Authenticate `gcloud` for Application Default Credentials:
        ```bash
        gcloud auth application-default login
        ```

4.  **Google Drive API Setup (Optional, for Drive Uploads):**
    -   In your GCP Console (associated with the project whose credentials you'll use for Drive), enable the **Google Drive API**.
    -   Configure the **OAuth consent screen**.
    -   Create an **OAuth 2.0 Client ID** for a "Web application".
        -   Add `http://localhost:8501` (or your Streamlit port, e.g., 8502, 8503...) as an "Authorized redirect URI". You might also need to add `http://localhost`.
    -   Download the client secrets JSON file, rename it to `credentials.json` (or the name specified in your `.env` for `CLIENT_SECRETS_FILE`), and place it in the project root (or the specified path).
    -   `credentials.json` is ignored by git.

5.  **Install Dependencies:**
    -   It's recommended to use a Python virtual environment. For this project, Python 3.12 is used.
    ```bash
    python3.12 -m venv .venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    pip install -r requirements.txt
    ```
    -   If you are on macOS and need Ruby (e.g., for certain gems or tools that might be indirectly used or if you plan to extend with Ruby-based tools):
    ```bash
    brew install ruby
    ```
    -   For video processing capabilities, ensure FFmpeg and ImageMagick are installed. On macOS, you can install them via Homebrew:
    ```bash
    brew install ffmpeg
    brew install imagemagick
    ```
    *Note: ImageMagick is required for text rendering in `moviepy` version 1.0.3, which this project currently uses.*

## Running the Application

1.  Ensure your `.env` file is configured and `credentials.json` (if using Drive) is in place.
2.  Run the Streamlit app:
    ```bash
    streamlit run veo_streamlit_app.py
    ```
3.  Open the provided local URL in your browser.
4.  Select the desired generation tab (Standard Veo, Veo Advanced Features, Lyria Music).
5.  Configure parameters in the sidebar and within the tab, then click the generate button.
    -   If using Google Drive upload for the first time, you'll be guided through an authentication flow (copy URL, authorize, paste code back into the app). A `token.json` will be created to store your authorization for future sessions. `token.json` is ignored by git.

## Files to Keep Private

-   `.env`
-   `credentials.json`
-   `token.json`
These are included in `.gitignore`.
