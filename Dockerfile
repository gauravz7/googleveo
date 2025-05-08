# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install system dependencies: ffmpeg for video processing, ImageMagick for text in moviepy
RUN apt-get update && \
    apt-get install -y ffmpeg imagemagick && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt /app/

# Install any needed packages specified in requirements.txt
# Ensure google-cloud-aiplatform is included for Gemini/Vertex AI calls
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container at /app
COPY . /app/

# Make port 8501 available to the world outside this container
EXPOSE 8501

# Define the command to run the app
# Use --server.address=0.0.0.0 to make it accessible from outside the container
# The healthcheck for Cloud Run will ping the base URL, Streamlit handles this.
CMD ["streamlit", "run", "veo_streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
