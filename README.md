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

## Key Code Modules

-   **`veo_streamlit_app.py`**: The main Streamlit application. It sets up the overall page configuration, sidebar for global settings (GCP Project ID, GCS bucket, local output directory, Drive link), and orchestrates the different tabs. It also contains common helper functions for GCS, Google Drive, and calling Veo APIs.
-   **`standard_veo_module.py`**: Contains the UI and logic for the "Standard Veo" generation tab. This module was adapted from `v0-streamlit.py` and handles image/URL uploads, prompt input, and calls to the Veo API for standard text-to-video and image-to-video generation. It uses helper functions primarily from `veo_streamlit_app.py` passed as arguments.
-   **`promptbuilder.py`**: Implements the "✨ AI Prompt Builder" tab. This module allows users to upload an image and provide a text idea, then calls the Vertex AI Gemini model to generate an enhanced, descriptive prompt suitable for video generation.
-   **`moviecreator.py`**: Powers the "🎬 Movie Creator" tab. It allows users to upload multiple video clips, add word-by-word animated text overlays with font selection, adjust video playback tempo for each clip, and combine them into a single movie with optional background audio.
-   **`lyria.py`**: Handles the logic for the "Lyria Music" generation tab, interfacing with the Lyria model on Vertex AI to generate music from text prompts.
-   **`.env`**: Used to store environment variables like GCP project IDs, GCS bucket names, and API keys. This file is not committed to Git (see `.gitignore`).
-   **`requirements.txt`**: Lists all Python dependencies required for the project.
-   **`Dockerfile` & `.dockerignore`**: (If present) Files for building a Docker container image of the application, suitable for deployment (e.g., to Google Cloud Run).

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

1.  Ensure your Python virtual environment (`.venv`) is activated:
    ```bash
    source .venv/bin/activate  # On macOS/Linux
    # .venv\Scripts\activate    # On Windows
    ```
2.  Ensure all dependencies are installed (as per the "Install Dependencies" section):
    ```bash
    pip install -r requirements.txt
    ```
3.  Ensure your `.env` file is configured and `credentials.json` (if using Drive) is in place.
4.  Run the Streamlit app:
    ```bash
    streamlit run veo_streamlit_app.py
    ```
    Alternatively, you can combine activation (if not already active) and running in one go (for macOS/Linux):
    ```bash
    source .venv/bin/activate && streamlit run veo_streamlit_app.py
    ```
5.  Open the provided local URL in your browser.
6.  Select the desired generation tab (Standard Veo, Veo Advanced Features, Lyria Music, or Movie Creator).
7.  Configure parameters in the sidebar and within the tab, then click the generate button.
    -   If using Google Drive upload for the first time, you'll be guided through an authentication flow (copy URL, authorize, paste code back into the app). A `token.json` will be created to store your authorization for future sessions. `token.json` is ignored by git.

## Deploying to Google Cloud Run (Optional)

This application can be containerized using Docker and deployed to Google Cloud Run.

### Prerequisites:
-   Google Cloud SDK installed and configured (`gcloud auth login`, `gcloud config set project YOUR_PROJECT_ID`).
-   Docker installed.
-   Your Google Cloud Project ID (let's call it `YOUR_PROJECT_ID`).
-   A preferred Google Cloud region (e.g., `us-central1`, let's call it `YOUR_REGION`).
-   Enable the Cloud Run API and Artifact Registry API (or Container Registry API) in your GCP project.

### Steps:

1.  **Build the Docker Image:**
    Open your terminal in the project root directory and run:
    ```bash
    docker build -t veo-lyria-app .
    ```
    (You can replace `veo-lyria-app` with your preferred image name).

2.  **Tag the Image for Artifact Registry (Recommended) or GCR:**
    *   **Artifact Registry (Recommended):**
        First, create a Docker repository in Artifact Registry if you haven't already (e.g., `veo-apps-repo`):
        ```bash
        gcloud artifacts repositories create veo-apps-repo \
            --repository-format=docker \
            --location=YOUR_REGION \
            --description="Docker repository for Veo/Lyria apps"
        ```
        Then, tag your image:
        ```bash
        docker tag veo-lyria-app YOUR_REGION-docker.pkg.dev/YOUR_PROJECT_ID/veo-apps-repo/veo-lyria-app:latest
        ```
    *   **Google Container Registry (GCR - Legacy):**
        ```bash
        docker tag veo-lyria-app gcr.io/YOUR_PROJECT_ID/veo-lyria-app:latest
        ```

3.  **Push the Image:**
    *   **Artifact Registry:**
        Configure Docker to authenticate with Artifact Registry:
        ```bash
        gcloud auth configure-docker YOUR_REGION-docker.pkg.dev
        ```
        Push the image:
        ```bash
        docker push YOUR_REGION-docker.pkg.dev/YOUR_PROJECT_ID/veo-apps-repo/veo-lyria-app:latest
        ```
    *   **Google Container Registry (GCR):**
        ```bash
        docker push gcr.io/YOUR_PROJECT_ID/veo-lyria-app:latest
        ```

4.  **Deploy to Cloud Run:**
    Replace `YOUR_SERVICE_NAME` (e.g., `veo-lyria-service`), `YOUR_PROJECT_ID`, `YOUR_REGION`, and the image path with your actual values.
    ```bash
    gcloud run deploy YOUR_SERVICE_NAME \
        --image YOUR_REGION-docker.pkg.dev/YOUR_PROJECT_ID/veo-apps-repo/veo-lyria-app:latest \
        # Or for GCR: --image gcr.io/YOUR_PROJECT_ID/veo-lyria-app:latest \
        --platform managed \
        --region YOUR_REGION \
        --allow-unauthenticated \
        --port 8501 \
        --memory 2Gi \  # Adjust memory as needed, video processing can be memory intensive
        --cpu 1         # Adjust CPU as needed
        # Add other flags as necessary, e.g., for environment variables or secrets
    ```

5.  **Configure Environment Variables and Secrets on Cloud Run:**
    The application relies on variables from an `.env` file and potentially a `credentials.json` file for Google Drive. These **should not** be included in the Docker image.
    -   **Environment Variables:** For each variable in your `.env` file (e.g., `DEFAULT_PROJECT_ID`, `DEFAULT_OUTPUT_GCS_BUCKET`, `CLIENT_SECRETS_FILE`), set them directly in the Cloud Run service configuration. For `CLIENT_SECRETS_FILE`, you'd set its value to the path where the secret will be mounted (e.g., `/app/credentials.json`).
        Example:
        ```bash
        gcloud run services update YOUR_SERVICE_NAME \
            --update-env-vars DEFAULT_PROJECT_ID=your-veo-gcp-project-id,DEFAULT_LYRIA_PROJECT_ID=your-lyria-gcp-project-id,DEFAULT_OUTPUT_GCS_BUCKET=your-gcs-bucket-name,CLIENT_SECRETS_FILE=/app/credentials.json 
            # Add other variables as needed from your .env (GEMINI_MODEL_NAME, GCP_REGION etc.)
        ```
    -   **Secrets (for `credentials.json`):**
        1.  Store your `credentials.json` content in Google Cloud Secret Manager. For example, create a secret named `google-drive-credentials`.
        2.  Grant the Cloud Run service account permission to access this secret (e.g., "Secret Manager Secret Accessor" role).
        3.  Mount the secret as a file in your Cloud Run service. When deploying or updating, use the `--update-secrets` flag:
            ```bash
            gcloud run deploy YOUR_SERVICE_NAME \
                --image YOUR_REGION-docker.pkg.dev/YOUR_PROJECT_ID/veo-apps-repo/veo-lyria-app:latest \
                # ... other flags ...
                --update-secrets="/app/credentials.json=google-drive-credentials:latest"
            ```
            Or for an existing service:
            ```bash
            gcloud run services update YOUR_SERVICE_NAME \
                --update-secrets="/app/credentials.json=google-drive-credentials:latest"
            ```
            This makes the content of the `google-drive-credentials` secret available at the path `/app/credentials.json` inside your container.

    After deployment, Cloud Run will provide a URL to access your application. Remember that the OAuth flow for Google Drive might need its redirect URI updated in your GCP OAuth Client ID configuration if you are accessing Cloud Run via its public URL (e.g., `https://your-service-name-xyz-uc.a.run.app`).

## Files to Keep Private

-   `.env`
-   `credentials.json`
-   `token.json`
These are included in `.gitignore`.
