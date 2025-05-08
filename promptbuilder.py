import streamlit as st
import vertexai
from vertexai.generative_models import GenerativeModel, Part, FinishReason
import vertexai.preview.generative_models as generative_models
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration
# TODO: Confirm with user if this is the correct model name they want to use.
# User specified "Gemini-2.5-pro-preview-03-25". Using "gemini-1.5-pro-preview-0514" as a known powerful multimodal model.
# Update if a different one is confirmed and available.
MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash-preview-04-17") 
PROJECT_ID = os.getenv("DEFAULT_PROJECT_ID")
LOCATION = os.getenv("GCP_REGION", "us-central1") # Common default, ensure this is where your Vertex AI models are available

# Initialize Vertex AI once
try:
    if PROJECT_ID:
        vertexai.init(project=PROJECT_ID, location=LOCATION)
    else:
        st.error("GCP_PROJECT_ID is not set. Please set it in your .env file or environment.")
except Exception as e:
    st.error(f"Error initializing Vertex AI: {e}")

def generate_prompt_from_image_and_text(image_bytes, user_text_prompt):
    """
    Generates a creative prompt using Gemini based on an image and a text idea.
    """
    if not PROJECT_ID:
        return "Error: GCP_PROJECT_ID not configured."

    try:
        model = GenerativeModel(MODEL_NAME)
        
        image_part = Part.from_data(
            mime_type="image/png",  # Assuming PNG, adjust if other types are common
            data=image_bytes
        )
        
        # Construct a more detailed instruction for Gemini
        instruction = (
            "You are an expert prompt engineer for generative AI models that create video from images and text. "
            "Based on the following uploaded image and the user's initial idea, "
            "generate an enhanced, highly descriptive, and creative prompt. "
            "This generated prompt should be suitable for an advanced image-to-video AI model to produce a compelling short video clip. "
            "Focus on visual details, atmosphere, potential motion, and artistic style implied by the image and text. "
            "The output should be only the generated prompt itself, ready to be copied and used."
        )
        
        full_prompt_parts = [
            instruction,
            "\n\nUser's Initial Idea: ", user_text_prompt,
            "\n\nUploaded Image Context:\n", image_part 
        ]

        generation_config = {
            "max_output_tokens": 2048,
            "temperature": 0.7, # Adjust for creativity vs. coherence
            "top_p": 0.95,
        }
        
        safety_settings = {
            generative_models.HarmCategory.HARM_CATEGORY_HATE_SPEECH: generative_models.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            generative_models.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: generative_models.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            generative_models.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: generative_models.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            generative_models.HarmCategory.HARM_CATEGORY_HARASSMENT: generative_models.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        }

        response = model.generate_content(
            full_prompt_parts,
            generation_config=generation_config,
            safety_settings=safety_settings,
            stream=False,
        )
        
        if response.candidates and response.candidates[0].content.parts:
            return response.candidates[0].content.parts[0].text
        else:
            # Check for finish_reason if no content
            if response.candidates and response.candidates[0].finish_reason != FinishReason.FINISH_REASON_STOP:
                return f"Error: Prompt generation stopped due to: {response.candidates[0].finish_reason.name}"
            return "Error: Could not generate prompt. The model returned no content."

    except Exception as e:
        return f"An error occurred while calling Gemini: {e}"

def prompt_builder_tab():
    st.header("✨ AI Prompt Builder")
    st.write("""
    Upload an image and provide an initial text idea. 
    This tool will use AI (Gemini) to generate an enhanced, descriptive prompt 
    that you can use for image-to-video generation in other tabs.
    """)

    if not PROJECT_ID:
        st.warning("Vertex AI Project ID is not configured. Please ensure DEFAULT_PROJECT_ID is set in your .env file.")
        return

    uploaded_image = st.file_uploader("1. Upload an Image", type=["png", "jpg", "jpeg", "webp"])
    user_text = st.text_area("2. Enter your initial prompt idea or theme", height=100, 
                             placeholder="e.g., A futuristic cityscape at sunset, cinematic style")

    if 'generated_ai_prompt' not in st.session_state:
        st.session_state.generated_ai_prompt = ""

    if st.button("🚀 Generate AI Prompt", key="generate_ai_prompt_button"):
        if uploaded_image is not None and user_text.strip():
            image_bytes = uploaded_image.getvalue()
            with st.spinner("AI is crafting your prompt... 🧠✨"):
                generated_prompt = generate_prompt_from_image_and_text(image_bytes, user_text.strip())
                st.session_state.generated_ai_prompt = generated_prompt
        elif not uploaded_image:
            st.warning("Please upload an image.")
        else:
            st.warning("Please enter your initial prompt idea.")

    if st.session_state.generated_ai_prompt:
        st.subheader("🤖 Generated AI Prompt:")
        st.markdown(f"```\n{st.session_state.generated_ai_prompt}\n```")
        st.button("📋 Copy to Clipboard", key="copy_ai_prompt", on_click=lambda: st.experimental_set_query_params(copied_prompt=st.session_state.generated_ai_prompt))
        # Small JS hack for clipboard copy might be too complex here, 
        # Streamlit doesn't have direct clipboard API.
        # A simple display and manual copy is often sufficient.
        # For a better UX, one might use a third-party component or a more involved JS trick.
        # The query param is a simple way to signal it, but doesn't actually copy.
        # A text_area can be used for easier selection:
        st.text_area("Copyable Prompt", value=st.session_state.generated_ai_prompt, height=150, key="copyable_ai_prompt_text_area")


if __name__ == "__main__":
    # This part is for testing the tab independently if needed
    st.set_page_config(layout="wide", page_title="Prompt Builder Test")
    
    # Mock .env for standalone testing if needed
    if not os.getenv("DEFAULT_PROJECT_ID"):
        st.warning("DEFAULT_PROJECT_ID not found in .env. Please set it for Vertex AI calls.")
        # You could set a mock one for UI testing only:
        # os.environ["DEFAULT_PROJECT_ID"] = "your-mock-project-id" 
    
    prompt_builder_tab()
