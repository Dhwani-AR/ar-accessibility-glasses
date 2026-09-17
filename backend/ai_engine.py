from faster_whisper import WhisperModel
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

class AIEngine:
    def __init__(self, hf_token=None):
        logging.info("Initializing AI Engine on CPU...")
        
        self.stt_model = WhisperModel("base.en", device="cpu", compute_type="int8")
        logging.info("Faster-Whisper (base.en) loaded.")

        self.diarization_pipeline = None
        if hf_token:
            from pyannote.audio import Pipeline
            try:
                self.diarization_pipeline = Pipeline.from_pretrained(
                    "pyannote/speaker-diarization-3.1",
                    token=hf_token
                )
                logging.info("Pyannote Diarization pipeline loaded.")
            except Exception as e:
                logging.error(f"Failed to load Pyannote: {e}")
        else:
            logging.warning("No Hugging Face token provided. Diarization disabled.")

    def transcribe(self, audio_input):
        """
        Transcribes audio_input (can be a numpy array or a file path)
        """
        logging.info("Running transcription...")
        segments, info = self.stt_model.transcribe(audio_input, beam_size=5)
        
        transcription = " ".join([segment.text for segment in segments]).strip()
        return transcription

    def process_audio(self, audio_input):
        """
        Master function to run STT and Diarization (if enabled)
        """
        text = self.transcribe(audio_input)
        
        # For now, mock the speaker ID until the pipeline is fully tuned
        speaker_id = "Speaker 1" 
        
        return {
            "text": text,
            "speaker": speaker_id
        }
