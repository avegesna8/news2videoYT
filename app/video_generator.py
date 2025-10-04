import os, re, subprocess, sys, shutil, glob
from datetime import timedelta
import imageio_ffmpeg

# ---------- ffmpeg binary (prefer venv one) ----------
try:
    import imageio_ffmpeg
    FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
    FFPROBE = getattr(imageio_ffmpeg, "get_ffprobe_exe", None)
except Exception:
    FFMPEG = shutil.which("ffmpeg")
    FFPROBE = shutil.which("ffprobe")

if not FFMPEG:
    sys.exit("No ffmpeg found. `pip install imageio-ffmpeg` or install ffmpeg system-wide.")

# ---------- inputs ----------
AUDIO = None                  # will be set dynamically from audio folder
CHAR  = "assets/character.png"       # PNG with alpha
BG    = "assets/background.mp4"      # set to None for solid color
TEXT  = """Today's news football style will be about how bad Russell Wilson is lol.
And also a quick update on the playoff picture!"""

# Create output directories
VIDEOS_DIR = "videos"
SRT_DIR = "srt"
os.makedirs(VIDEOS_DIR, exist_ok=True)
os.makedirs(SRT_DIR, exist_ok=True)

OUT_VIDEO        = os.path.join(VIDEOS_DIR, "out.mp4")
OUT_VIDEO_BURNED = os.path.join(VIDEOS_DIR, "out_burned.mp4")
OUT_VIDEO_SOFT   = os.path.join(VIDEOS_DIR, "out_softsubs.mp4")
OUT_SRT          = os.path.join(SRT_DIR, "subs.srt")

# frame & layout
WIDTH, HEIGHT, FPS = 1080, 1920, 30
CHAR_WIDTH_RATIO   = 0.45
BOTTOM_MARGIN      = 220
BOB_PIXELS         = 8
BOB_HZ             = 0.5

# subtitle config
SUB_MODE            = "phrase"  # "phrase" or "word"
TARGET_WORDS_PER_LINE = 6
MIN_PHRASE_WORDS    = 3
MAX_PHRASE_WORDS    = 12
BURN_SUBS           = True      # True = burn into pixels, False = soft subs
USE_EXISTING_SRT    = True      # True = use pre-generated subs.srt if available


# ---------- audio file helpers ----------
def get_audio_file_by_name(filename: str, audio_dir: str = "audio") -> str:
    """Get a specific audio file by name from the audio directory."""
    audio_path = os.path.join(audio_dir, filename)
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file '{audio_path}' not found")
    return audio_path

# ---------- helpers ----------
def ffprobe_duration_seconds(path: str) -> float:
    if FFPROBE:
        cmd = [FFPROBE, "-v", "error", "-show_entries", "format=duration",
               "-of", "default=noprint_wrappers=1:nokey=1", path]
        out = subprocess.run(cmd, capture_output=True, text=True)
        return float(out.stdout.strip())
    else:
        cmd = [FFMPEG, "-i", path, "-f", "null", "-"]
        out = subprocess.run(cmd, capture_output=True, text=True)
        txt = out.stderr
        m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", txt)
        if not m:
            raise RuntimeError(f"Couldn't parse duration from: {txt[:200]}…")
        h, m_, s = m.groups()
        return int(h) * 3600 + int(m_) * 60 + float(s)


def srt_timestamp(t: float) -> str:
    td = timedelta(seconds=max(0, t))
    total_seconds = int(td.total_seconds())
    ms = int((t - total_seconds) * 1000)
    hh = total_seconds // 3600
    mm = (total_seconds % 3600) // 60
    ss = total_seconds % 60
    return f"{hh:02}:{mm:02}:{ss:02},{ms:03}"


def split_into_phrases(text: str) -> list[list[str]]:
    text = re.sub(r"\s+", " ", text.strip())
    parts = re.split(r"([.!?;:])", text)
    sentences = []
    for i in range(0, len(parts), 2):
        chunk = parts[i].strip()
        punct = parts[i+1] if i+1 < len(parts) else ""
        if chunk:
            sentences.append((chunk + (punct or "")).strip())

    phrases = []
    for sent in sentences:
        words = sent.split()
        i = 0
        while i < len(words):
            take = min(MAX_PHRASE_WORDS, max(MIN_PHRASE_WORDS, TARGET_WORDS_PER_LINE))
            phrases.append(words[i:i+take])
            i += take
    return phrases


def write_srt_from_text(text: str, audio_len: float, path: str, mode: str = "phrase"):
    words = text.strip().split()
    if not words:
        raise ValueError("No words in text for subtitles.")

    total_words = len(words)
    avg_time_per_word = audio_len / total_words
    entries = []

    if mode == "word":
        t = 0.0
        for i, w in enumerate(words, 1):
            start = t
            end = start + avg_time_per_word
            entries.append((i, start, end, w))
            t = end
    else:
        phrases = split_into_phrases(text)
        t = 0.0
        idx = 1
        for chunk in phrases:
            chunk_words = len(chunk)
            dur = chunk_words * avg_time_per_word
            start = t
            end = min(t + dur, audio_len)
            line = " ".join(chunk)
            entries.append((idx, start, end, line))
            idx += 1
            t = end

    with open(path, "w", encoding="utf-8") as f:
        for idx, start, end, line in entries:
            f.write(f"{idx}\n{srt_timestamp(start)} --> {srt_timestamp(end)}\n{line}\n\n")


# ---------- image cycling helpers ----------
def create_image_cycle_filter(images: list, video_duration: float, output_width: int = 400, output_height: int = 300):
    """
    Create FFmpeg filter for cycling through images evenly throughout video duration.
    
    Args:
        images: List of image file paths
        video_duration: Duration of the video in seconds
        output_width: Width of the image overlay
        output_height: Height of the image overlay
    
    Returns:
        str: FFmpeg filter string for image cycling
    """
    if not images:
        return ""
    
    num_images = len(images)
    duration_per_image = video_duration / num_images
    
    # Create image inputs and scaling filters
    image_filters = []
    for i, img_path in enumerate(images):
        if os.path.exists(img_path):
            # Scale and position each image (input index starts from 3 for article images)
            image_filters.append(
                f"[{i+3}:v]scale={output_width}:{output_height}:force_original_aspect_ratio=decrease,"
                f"pad={output_width}:{output_height}:(ow-iw)/2:(oh-ih)/2:black,"
                f"fade=t=in:st=0:d=0.5:alpha=1,"
                f"fade=t=out:st={duration_per_image-0.5}:d=0.5:alpha=1[img{i}]"
            )
    
    # Create cycling overlay filter
    if len(image_filters) == 1:
        overlay_filter = f"[vbg_with_char][img0]overlay=x=W-w-20:y=20:enable='between(t,0,{video_duration})'[vout]"
    else:
        # Chain overlays for multiple images
        overlay_parts = []
        for i in range(num_images):
            start_time = i * duration_per_image
            end_time = (i + 1) * duration_per_image
            
            if i == 0:
                input_label = "[vbg_with_char]"
            else:
                input_label = f"[v{i-1}]"
            
            output_label = f"[v{i}]" if i < num_images - 1 else "[vout]"
            
            overlay_parts.append(
                f"{input_label}[img{i}]overlay=x=W-w-20:y=20:enable='between(t,{start_time},{end_time})'{output_label}"
            )
        
        overlay_filter = ",".join(overlay_parts)
    
    # Combine all filters
    if image_filters:
        all_filters = ",".join(image_filters) + "," + overlay_filter
    else:
        all_filters = overlay_filter
    return all_filters

# ---------- 1) build the base video ----------
def build_video(audio_file: str = None, char_file: str = None, bg_file: str = None, article_images: list = None):
    """
    Build video with specified audio file and cycling article images.
    
    Args:
        audio_file: Path to audio file (required)
        char_file: Path to character image (if None, uses default)
        bg_file: Path to background video (if None, uses default)
        article_images: List of article image paths to cycle through
    """
    # Set audio file
    if audio_file is None:
        sys.exit("Error: audio_file parameter is required")
    elif not os.path.exists(audio_file):
        sys.exit(f"Missing audio file: {audio_file}")
    
    # Set character and background files
    char_file = char_file or CHAR
    bg_file = bg_file or BG
    
    # Check required files
    for p in [audio_file, char_file]:
        if not os.path.exists(p):
            sys.exit(f"Missing file: {p}")

    inputs, fc = [], []

    if bg_file and os.path.exists(bg_file):
        inputs += ["-stream_loop", "-1", "-i", bg_file]
        fc.append(
            f"[0:v]scale=w={WIDTH}:h={HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop=w={WIDTH}:h={HEIGHT},setsar=1[vbg]"
        )
    else:
        inputs += ["-f", "lavfi", "-i", f"color=c=skyblue:s={WIDTH}x{HEIGHT}:r={FPS}"]
        fc.append("[0:v]format=yuva444p,setsar=1[vbg]")

    inputs += ["-i", audio_file, "-loop", "1", "-i", char_file]
    
    # Add article images as inputs
    if article_images:
        for img_path in article_images:
            if os.path.exists(img_path):
                inputs += ["-loop", "1", "-i", img_path]
                print(f"Added image input: {img_path}")

    char_px = int(WIDTH * CHAR_WIDTH_RATIO)
    fc.append(
        f"[2:v]scale={char_px}:-1,format=rgba,"
        f"colorchannelmixer=aa=0.96,"
        f"fade=t=in:st=0:d=0.25:alpha=1[char]"
    )
    
    # Get video duration for image cycling
    video_duration = ffprobe_duration_seconds(audio_file)
    
    # Create character overlay
    char_overlay = (
        "[vbg][char]overlay="
        f"x=(W-w)/2:y=H-h-{BOTTOM_MARGIN}+{BOB_PIXELS}*sin(2*PI*t*{BOB_HZ}):"
        "shortest=1[vbg_with_char]"
    )
    fc.append(char_overlay)
    
    # Add article images cycling if available
    if article_images and any(os.path.exists(img) for img in article_images):
        print(f"Creating image cycle for {len(article_images)} images over {video_duration:.1f} seconds")
        image_filter = create_image_cycle_filter(article_images, video_duration)
        if image_filter:
            fc.append(image_filter)
        else:
            fc.append("[vbg_with_char]format=yuv420p[v]")
    else:
        fc.append("[vbg_with_char]format=yuv420p[v]")

    # Determine the correct output label based on whether we have article images
    output_label = "[vout]" if (article_images and any(os.path.exists(img) for img in article_images)) else "[v]"
    
    cmd = (
        [FFMPEG, "-nostdin", "-y"] +
        inputs + [
            "-filter_complex", "; ".join(fc),
            "-map", output_label, "-map", "1:a",
            "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
            "-c:a", "aac",
            "-shortest",
            OUT_VIDEO
        ]
    )
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    print("Wrote", OUT_VIDEO)


# ---------- 2) add subtitles ----------
def add_subtitles(text: str, audio_file: str = None):
    """
    Add subtitles to the video.
    
    Args:
        text: The text to create subtitles from
        audio_file: Path to audio file (required)
    """
    if audio_file is None:
        sys.exit("Error: audio_file parameter is required")
    
    if USE_EXISTING_SRT and os.path.exists(OUT_SRT):
        srt_path = OUT_SRT
        print(f"Using existing subtitles: {srt_path}")
    else:
        dur = ffprobe_duration_seconds(audio_file)
        write_srt_from_text(text, dur, OUT_SRT, mode=SUB_MODE)
        srt_path = OUT_SRT
        print(f"Generated subtitles: {srt_path}")

    if BURN_SUBS:
        cmd = [
            FFMPEG, "-nostdin", "-y",
            "-i", OUT_VIDEO,
            "-vf", f"subtitles={srt_path}:force_style='Fontsize=36,Outline=2,BorderStyle=1,Alignment=2'",
            "-c:a", "copy",
            OUT_VIDEO_BURNED
        ]
        print("Burning subs…")
        subprocess.run(cmd, check=True)
        print("Wrote", OUT_VIDEO_BURNED)
    else:
        cmd = [
            FFMPEG, "-nostdin", "-y",
            "-i", OUT_VIDEO, "-i", srt_path,
            "-c", "copy", "-c:s", "mov_text",
            OUT_VIDEO_SOFT
        ]
        print("Muxing soft subs…")
        subprocess.run(cmd, check=True)
        print("Wrote", OUT_VIDEO_SOFT)


# ---------- main workflow functions ----------
def generate_video(audio_file: str, script_text: str, output_name: str = None, article_images: list = None):
    """
    Generate a complete video from an audio file and script text with cycling article images.
    
    Args:
        audio_file: Path to the audio file (e.g., "audio/audio_20251004_132034.wav")
        script_text: The script text for subtitles (should match the audio content)
        output_name: Custom name for output files (optional)
        article_images: List of article image paths to cycle through
    """
    global OUT_VIDEO, OUT_VIDEO_BURNED, OUT_VIDEO_SOFT, OUT_SRT
    
    if output_name:
        OUT_VIDEO = os.path.join(VIDEOS_DIR, f"{output_name}.mp4")
        OUT_VIDEO_BURNED = os.path.join(VIDEOS_DIR, f"{output_name}_burned.mp4")
        OUT_VIDEO_SOFT = os.path.join(VIDEOS_DIR, f"{output_name}_softsubs.mp4")
        OUT_SRT = os.path.join(SRT_DIR, f"{output_name}_subs.srt")
    
    print(f"Generating video from audio: {audio_file}")
    if article_images:
        print(f"Using {len(article_images)} article images for cycling")
    build_video(audio_file=audio_file, article_images=article_images)
    add_subtitles(script_text, audio_file=audio_file)
    
    # Return the actual file paths that were generated
    generated_files = {
        "video": OUT_VIDEO,
        "video_burned": OUT_VIDEO_BURNED,
        "video_soft": OUT_VIDEO_SOFT,
        "srt": OUT_SRT
    }
    
    print(f"Video generation complete! Output files:")
    print(f"  - {OUT_VIDEO}")
    print(f"  - {OUT_VIDEO_BURNED}")
    print(f"  - {OUT_VIDEO_SOFT}")
    
    return generated_files

def generate_video_from_script(script_text: str, output_name: str = None, ref_audio_path: str = None):
    """
    Complete workflow: Generate audio from script, then create video with matching subtitles.
    
    Args:
        script_text: The script text to convert to audio and use for subtitles
        output_name: Custom name for output files (optional)
        ref_audio_path: Reference audio file for voice cloning (optional)
    
    Returns:
        tuple: (audio_path, video_paths)
    """
    from audio_generator import generate_audio_from_runpod
    
    # Generate audio from script
    print("Step 1: Generating audio from script...")
    audio_path = generate_audio_from_runpod(script_text, ref_audio_path)
    
    # Generate video with matching script text
    print("Step 2: Generating video with matching subtitles...")
    generate_video(audio_path, script_text, output_name)
    
    return audio_path, [OUT_VIDEO, OUT_VIDEO_BURNED, OUT_VIDEO_SOFT]

if __name__ == "__main__":
    # Test with the audio file in your audio folder
    try:
        # Get the audio file by name
        audio_path = get_audio_file_by_name("audio_20251004_132034.wav")
        print(f"Found audio file: {audio_path}")
        
        # Use the same script text that was used to create the audio
        # This should match the text that was passed to generate_audio_from_runpod()
        script_text = """Welcome to Sports Central! I'm your host bringing you the latest NFL drama. 
Today we've got some breaking news that's going to shake up the league. 
Stay tuned for all the juicy details coming your way!"""
        
        # Generate video with the matching script text
        generate_video(audio_path, script_text, "test_video_new")
        
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Available audio files:")
        audio_dir = "audio"
        if os.path.exists(audio_dir):
            audio_files = glob.glob(os.path.join(audio_dir, "*.wav"))
            for f in audio_files:
                print(f"  - {os.path.basename(f)}")
        else:
            print("Audio directory not found")