import streamlit as st
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip, concatenate_videoclips, AudioFileClip
import os

# Ensure the output directory exists
OUTPUT_DIR = "Output/movie_creator_output"
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# Define available fonts
AVAILABLE_FONTS = ["Arial", "Times-New-Roman", "Courier-New", "Verdana", "Georgia"]

def animate_text_word_by_word(video_clip, text, font, fontsize=50, color='white', stroke_color='black', stroke_width=1):
    """
    Adds text to a video clip, appearing word by word.
    Words accumulate on screen.
    """
    words = text.split()
    if not words:  # Handle empty text or text with only spaces
        return video_clip
        
    # Adjust word appearance speed
    base_duration_per_word = video_clip.duration / len(words)
    # User requested 1.5x faster than original
    speed_factor = 1.5 
    duration_per_word = base_duration_per_word / speed_factor
    
    final_text_clips = []
    accumulated_words = ""
    for i, word in enumerate(words):
        accumulated_words += (word + " ")
        # Create a text clip for the current accumulated words
        # Using method='caption' and size for better text wrapping and positioning.
        # Adjust video_clip.w * 0.8 (width for text) as needed.
        txt_clip = TextClip(accumulated_words.strip(), fontsize=fontsize, font=font, color=color,
                            stroke_color=stroke_color, stroke_width=stroke_width,
                            method='caption', align='center', size=(video_clip.w * 0.8, None))
        txt_clip = txt_clip.set_pos('center')

        start_time = i * duration_per_word
        # Duration for this specific text state:
        # If it's the last word, it lasts till the end of the video clip.
        # Otherwise, it lasts until the next word is supposed to appear.
        clip_duration = (video_clip.duration - start_time) if (i == len(words) - 1) else duration_per_word
        
        txt_clip = txt_clip.set_start(start_time).set_duration(clip_duration)
        final_text_clips.append(txt_clip)

    if not final_text_clips:
        return video_clip # Should not happen if words exist, but as a safeguard

    return CompositeVideoClip([video_clip] + final_text_clips, size=video_clip.size)


def movie_creator_tab():
    st.header("🎬 Movie Creator")

    st.write("""
    Upload up to 10 video clips. For each clip, you can add text that will appear word by word.
    Optionally, upload an audio file to use as background music for the final combined movie.
    """)

    # --- Video Upload and Configuration ---
    st.subheader("1. Upload Video Clips & Add Text")
    
    if 'video_inputs' not in st.session_state:
        st.session_state.video_inputs = []

    def add_video_input():
        if len(st.session_state.video_inputs) < 10:
            st.session_state.video_inputs.append({"id": len(st.session_state.video_inputs) + 1, "file": None, "text": "", "font": AVAILABLE_FONTS[0], "tempo": 1.0}) # Added tempo
        else:
            st.warning("Maximum of 10 video clips allowed.")

    def remove_video_input(index_to_remove):
        st.session_state.video_inputs.pop(index_to_remove)
        # Re-assign IDs to maintain consistency after removal
        for idx, item in enumerate(st.session_state.video_inputs):
            item["id"] = idx + 1


    cols_buttons = st.columns(2)
    with cols_buttons[0]:
        if st.button("➕ Add Video Clip Slot", key="add_video_slot"):
            add_video_input()
    
    if not st.session_state.video_inputs:
        st.info("Click 'Add Video Clip Slot' to begin.")

    for i, video_input_item in enumerate(st.session_state.video_inputs):
        st.markdown(f"---")
        # Use unique ID for widget keys, 'i' changes if items are removed from middle
        item_key_suffix = video_input_item["id"] 
        st.markdown(f"#### Video Clip {item_key_suffix}")
        
        cols_main = st.columns([3, 2, 1]) # Main columns for file, text, remove
        with cols_main[0]:
            video_input_item["file"] = st.file_uploader(f"Upload Video Clip {item_key_suffix}", type=["mp4", "mov", "avi", "mkv"], key=f"video_file_{item_key_suffix}")
        
        text_font_col, tempo_col = cols_main[1].columns(2) # Sub-columns for text/font and tempo

        with text_font_col:
            video_input_item["text"] = st.text_area(f"Text for Video {item_key_suffix}", value=video_input_item.get("text", ""), key=f"video_text_{item_key_suffix}", height=100)
            video_input_item["font"] = st.selectbox(f"Font for Video {item_key_suffix}", AVAILABLE_FONTS, index=AVAILABLE_FONTS.index(video_input_item.get("font", AVAILABLE_FONTS[0])), key=f"video_font_{item_key_suffix}")
        
        with tempo_col:
            tempo_options_display = ["Normal (1.0x)", "1.05x", "1.1x", "1.15x", "1.2x"]
            tempo_options_values = [1.0, 1.05, 1.1, 1.15, 1.2]
            selected_tempo_display = f"{video_input_item.get('tempo', 1.0)}x"
            if video_input_item.get('tempo', 1.0) == 1.0:
                selected_tempo_display = "Normal (1.0x)"

            # Find current index for selectbox
            current_tempo_value = video_input_item.get("tempo", 1.0)
            try:
                current_tempo_idx = tempo_options_values.index(current_tempo_value)
            except ValueError:
                current_tempo_idx = 0 # Default to Normal

            selected_tempo_display_val = st.selectbox(f"Tempo for Video {item_key_suffix}", 
                                                      options=tempo_options_display, 
                                                      index=current_tempo_idx, 
                                                      key=f"video_tempo_{item_key_suffix}")
            video_input_item["tempo"] = tempo_options_values[tempo_options_display.index(selected_tempo_display_val)]

        with cols_main[2]:
            st.markdown("## ") # Add some space for button alignment
            if st.button(f"🗑️ Remove Clip {item_key_suffix}", key=f"remove_video_{item_key_suffix}"):
                remove_video_input(i) # Pass current list index for removal
                st.rerun() 

    # --- Audio Upload ---
    st.markdown(f"---")
    st.subheader("2. Upload Background Audio (Optional)")
    audio_file_uploaded = st.file_uploader("Upload an audio file (mp3, wav, aac)", type=["mp3", "wav", "aac"], key="main_audio_file")

    # --- Generate Movie ---
    st.markdown(f"---")
    st.subheader("3. Generate Movie")
    if st.button("✨ Generate Movie", key="generate_movie_button"):
        valid_clips_to_process = []
        for idx, v_input_data in enumerate(st.session_state.video_inputs):
            if v_input_data["file"]:
                valid_clips_to_process.append(v_input_data)
            else:
                st.warning(f"Video Clip {v_input_data['id']} is missing a file and will be skipped.")

        if not valid_clips_to_process:
            st.error("No valid video clips uploaded to process.")
            return

        with st.spinner("Generating your movie... This might take a while! ⏳"):
            final_video_clips_processed = []
            temp_file_paths = [] # To keep track of temporary files for cleanup

            try:
                for i, v_data in enumerate(valid_clips_to_process):
                    st.write(f"Processing video {i+1}/{len(valid_clips_to_process)}: {v_data['file'].name}...")
                    
                    temp_video_filename = f"temp_video_{v_data['id']}_{v_data['file'].name}"
                    temp_video_path = os.path.join(OUTPUT_DIR, temp_video_filename)
                    temp_file_paths.append(temp_video_path)

                    with open(temp_video_path, "wb") as f:
                        f.write(v_data["file"].getbuffer()) # Corrected this line
                    
                    video_clip_obj = VideoFileClip(temp_video_path)
                    
                    # Apply tempo adjustment
                    tempo_factor = v_data.get("tempo", 1.0)
                    if tempo_factor != 1.0:
                        st.write(f"... applying tempo {tempo_factor}x")
                        video_clip_obj = video_clip_obj.speedx(tempo_factor)
                    
                    if v_data["text"].strip():
                        video_clip_with_text = animate_text_word_by_word(video_clip_obj, v_data["text"], v_data["font"])
                        final_video_clips_processed.append(video_clip_with_text)
                    else:
                        final_video_clips_processed.append(video_clip_obj)
                    
                if not final_video_clips_processed:
                    st.error("No videos could be processed.")
                    return

                concatenated_video_clip = concatenate_videoclips(final_video_clips_processed, method="compose")

                if audio_file_uploaded:
                    st.write("Adding audio...")
                    temp_audio_filename = f"temp_audio_{audio_file_uploaded.name}"
                    temp_audio_path = os.path.join(OUTPUT_DIR, temp_audio_filename)
                    temp_file_paths.append(temp_audio_path)

                    with open(temp_audio_path, "wb") as f:
                        f.write(audio_file_uploaded.getbuffer())
                    
                    audio_clip_obj = AudioFileClip(temp_audio_path)
                    final_output_video = concatenated_video_clip.set_audio(audio_clip_obj.set_duration(concatenated_video_clip.duration))
                else:
                    final_output_video = concatenated_video_clip

                output_filename = f"final_movie_{len(os.listdir(OUTPUT_DIR))}.mp4" # Simpler naming
                final_output_path = os.path.join(OUTPUT_DIR, output_filename)
                
                st.write(f"Writing final movie to {final_output_path}...")
                final_output_video.write_videofile(final_output_path, codec="libx264", audio_codec="aac", 
                                                   temp_audiofile=os.path.join(OUTPUT_DIR, 'temp-audio.m4a'), 
                                                   remove_temp=True, 
                                                   ffmpeg_params=["-pix_fmt", "yuv420p"])

                st.success(f"🎉 Movie generated successfully! 🎉")
                st.video(final_output_path)
                
                # Close all MoviePy clips to release resources
                for clip in final_video_clips_processed:
                    clip.close()
                concatenated_video_clip.close()
                if audio_file_uploaded:
                    audio_clip_obj.close()
                final_output_video.close()

            except Exception as e:
                st.error(f"An error occurred during movie generation: {e}")
                import traceback
                st.error(traceback.format_exc())
            finally:
                # Clean up all temporary files
                for path in temp_file_paths:
                    if os.path.exists(path):
                        try:
                            os.remove(path)
                        except Exception as e_clean:
                            st.warning(f"Could not clean up temp file {path}: {e_clean}")

if __name__ == "__main__":
    st.set_page_config(layout="wide", page_title="Movie Creator Test")
    movie_creator_tab()
