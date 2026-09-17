import sounddevice as sd
import soundfile as sf
import os
from dotenv import load_dotenv
from ai_engine import AIEngine

load_dotenv()
HF_TOKEN = os.getenv("HF_TOKEN")

SAMPLE_RATE = 16000
DURATION = 5
TEMP_WAV = "temp_test.wav"

def record_audio():
    print(f"\n🎤 Recording for {DURATION} seconds... Speak now!")
    recording = sd.rec(int(DURATION * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype='float32')
    sd.wait()
    print("✅ Recording complete.")
    
    sf.write(TEMP_WAV, recording, SAMPLE_RATE)
    return TEMP_WAV

if __name__ == "__main__":
    engine = AIEngine(hf_token=HF_TOKEN)
    
    audio_file = record_audio()
    
    print("\n🧠 Processing via AI Engine...")
    result = engine.process_audio(audio_file)
    
    print("\n" + "="*40)
    print("🎯 RESULTS")
    print("="*40)
    print(f"Speaker: {result['speaker']}")
    print(f"Text   : {result['text']}")
    print("="*40 + "\n")
    
    if os.path.exists(TEMP_WAV):
        os.remove(TEMP_WAV)
