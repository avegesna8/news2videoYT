import srt, math, os, glob
from datetime import timedelta
from faster_whisper import WhisperModel

# Create srt output directory
SRT_DIR = "srt"
os.makedirs(SRT_DIR, exist_ok=True)

MODEL_SIZE = "small"            # "base", "small", "medium"; small is a good balance
MAX_LINE_CHARS = 42             # wrap lines nicely
MAX_CUE_SEC = 5.0               # avoid very long subtitles
MIN_CUE_SEC = 0.7               # avoid blink-fast subs
OUT_SRT = os.path.join(SRT_DIR, "subs.srt")

def group_words(words, max_chars=MAX_LINE_CHARS, max_dur=MAX_CUE_SEC):
    """
    Group word items (each has 'word','start','end') into subtitle chunks
    by character budget and max duration.
    """
    chunk, chunks = [], []
    chunk_start = None
    for w in words:
        if chunk_start is None:
            chunk_start = w["start"]
        new_text = (" ".join([x["word"] for x in chunk] + [w["word"]])).strip()
        new_dur = (w["end"] - chunk_start)
        if len(new_text) > max_chars or new_dur > max_dur:
            if chunk:
                chunks.append((chunk_start, chunk[-1]["end"], " ".join(x["word"] for x in chunk)))
            chunk, chunk_start = [w], w["start"]
        else:
            chunk.append(w)
    if chunk:
        chunks.append((chunk_start, chunk[-1]["end"], " ".join(x["word"] for x in chunk)))
    return chunks

def clamp_duration(start, end, min_sec=MIN_CUE_SEC):
    if end - start < min_sec:
        end = start + min_sec
    return start, end

def to_srt(chunks):
    subs = []
    for i, (st, en, text) in enumerate(chunks, 1):
        st, en = clamp_duration(st, en)
        subs.append(srt.Subtitle(
            index=i,
            start=timedelta(seconds=st),
            end=timedelta(seconds=en),
            content=text
        ))
    return srt.compose(subs)

def generate_srt_from_audio(audio_file: str, output_filename: str = None):
    """
    Generate SRT subtitles from an audio file using Whisper.
    
    Args:
        audio_file: Path to the audio file
        output_filename: Custom name for output SRT file (optional)
    
    Returns:
        str: Path to the generated SRT file
    """
    if not os.path.exists(audio_file):
        raise FileNotFoundError(f"Audio file not found: {audio_file}")
    
    # Set output file path
    if output_filename is None:
        base_name = os.path.splitext(os.path.basename(audio_file))[0]
        output_filename = f"{base_name}_subs.srt"
    
    if not output_filename.endswith('.srt'):
        output_filename += '.srt'
    
    output_path = os.path.join(SRT_DIR, output_filename)
    
    print(f"Generating SRT from audio: {audio_file}")
    print(f"Using Whisper model: {MODEL_SIZE}")
    
    # Load Whisper model
    model = WhisperModel(MODEL_SIZE, compute_type="auto")  # CPU/GPU auto
    
    # Transcribe with word timestamps
    segments, _ = model.transcribe(audio_file, word_timestamps=True)
    
    # Extract words with timestamps
    words = []
    for seg in segments:
        if not seg.words:  # fallback to segment timing
            words.append({"word": seg.text.strip(), "start": seg.start, "end": seg.end})
        else:
            for w in seg.words:
                words.append({"word": w.word.strip(), "start": w.start, "end": w.end})
    
    # Clean empty words
    words = [w for w in words if w["word"]]
    
    # Group words into subtitle chunks
    chunks = group_words(words)
    
    # Generate SRT content
    srt_content = to_srt(chunks)
    
    # Write to file
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(srt_content)
    
    print(f"SRT generated successfully: {output_path}")
    return output_path

def get_audio_file_by_name(filename: str, audio_dir: str = "audio") -> str:
    """Get a specific audio file by name from the audio directory."""
    audio_path = os.path.join(audio_dir, filename)
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file '{audio_path}' not found")
    return audio_path

def main():
    """Legacy main function - kept for backward compatibility"""
    # This would need an AUDIO variable to be set
    print("Error: Please use generate_srt_from_audio() function with audio file path")
    print("Example: generate_srt_from_audio('audio/audio_20251004_132034.wav')")

if __name__ == "__main__":
    # Test with the audio file in your audio folder
    try:
        # Get the audio file by name
        audio_path = get_audio_file_by_name("audio_20251004_132034.wav")
        print(f"Found audio file: {audio_path}")
        
        # Generate SRT subtitles
        srt_path = generate_srt_from_audio(audio_path, "test_subs")
        print(f"Test completed! SRT file created: {srt_path}")
        
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
    except Exception as e:
        print(f"Error generating SRT: {e}")
        print("Make sure you have faster-whisper installed: pip install faster-whisper")