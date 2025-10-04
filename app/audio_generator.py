import os
import base64
import requests
import json
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

#Generate Audio from Script Using RunPod API
def generate_audio_from_runpod(script: str, ref_audio_path: str | None = None) -> str:
    audio_dir = os.path.join(os.path.dirname(__file__), "audio")
    os.makedirs(audio_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"audio_{timestamp}.wav"
    
    if not output_filename.endswith('.wav'):
        output_filename += '.wav'
        
    output_path = os.path.join(audio_dir, output_filename)
    
    # RunPod API endpoint
    api_url = f"https://api.runpod.ai/v2/{os.getenv('ENDPOINT_ID')}/runsync"
    
    # Prepare the request payload
    payload = {
        "input": {
            "mode": "tts",
            "text": script
        }
    }

     # ➜ If you have a local reference .wav in assets/, add it as base64
    if ref_audio_path:
        if not os.path.isabs(ref_audio_path):
            ref_audio_path = os.path.join(os.path.dirname(__file__), ref_audio_path)
        with open(ref_audio_path, "rb") as f:
            ref_b64 = base64.b64encode(f.read()).decode("utf-8")
        payload["input"]["ref_audio_b64"] = ref_b64
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.getenv('RUNPOD_API_KEY', '')}"
    }
    
    try:
        print(f"Generating audio for script: {script[:100]}...")
        
        # Make the API request
        response = requests.post(api_url, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        
        # Parse the response
        data = response.json()

        # Helpful metadata (sometimes included)
        run_id = data.get("id") or data.get("jobId")
        status = data.get("status")

        # Check for serverless-level error shapes
        if "error" in data and data["error"]:
            raise RuntimeError(f"RunPod error: {data['error']}")
# Your handler returns {"ok": True, ...} inside "output"
        out = data.get("output") or {}
        if not out.get("ok"):
            raise RuntimeError(f"TTS failed: {json.dumps(out)[:500]} (status={status}, run_id={run_id})")

        audio_b64 = out.get("audio_base64")
        if not audio_b64:
            raise RuntimeError(f"No audio_base64 in response (status={status}, run_id={run_id})")

        audio_bytes = base64.b64decode(audio_b64)
        with open(output_path, "wb") as f:
            f.write(audio_bytes)
            
            print(f"Audio generated successfully: {output_path}")
            return output_path
            
    except requests.exceptions.RequestException as e:
        raise Exception(f"Network error calling RunPod API: {str(e)}")
    except json.JSONDecodeError as e:
        raise Exception(f"Invalid JSON response from API: {str(e)}")
    except Exception as e:
        raise Exception(f"Error generating audio: {str(e)}")

#Generate Audio from LLM Script
def generate_audio_from_llm_script(article_data: dict, max_paragraphs: int = 20, max_chars_per_paragraph: int = 500) -> str:
    from llm_functions import generate_comedic_script
    
    # Generate the comedic script
    script_result = generate_comedic_script(article_data, max_paragraphs, max_chars_per_paragraph)
    
    if script_result['is_too_long']:
        raise Exception("Article is too long for script generation")
    
    script = script_result['script']
    
    # Generate audio from the script
    return generate_audio_from_runpod(script)


# CLI Test
if __name__ == "__main__":
    # Test with a sample script
    test_script = """
    Welcome to Sports Central! I'm your host bringing you the latest NFL drama. 
    Today we've got some breaking news that's going to shake up the league. 
    Stay tuned for all the juicy details coming your way!
    """
    
    try:
        audio_path = generate_audio_from_runpod(test_script, "assets/voice_08.wav")
        print(f"Test audio generated at: {audio_path}")
    except Exception as e:
        print(f"Error in test: {e}")
