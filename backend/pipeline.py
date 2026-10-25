import math
import numpy as np
import torch
from faster_whisper import WhisperModel
from speechbrain.inference.speaker import EncoderClassifier


class AudioPipeline:
    def __init__(self, rate=16000, width=0.14, depth=0.07):
        self.rate = rate
        self.width = width
        self.depth = depth
        self.sound_speed = 343.0
        self.speech_rms = 0.012
        self.alert_rms = 0.18
        self.sim_thresh = 0.68
        self.max_speakers = 6
        self.speakers = []

        device = "cuda" if torch.cuda.is_available() else "cpu"
        compute = "float16" if device == "cuda" else "int8"
        self.asr = WhisperModel("base.en", device=device, compute_type=compute)
        self.encoder = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            run_opts={"device": device},
        )

    def gcc_phat(self, sig, ref, max_tau):
        n = sig.shape[0] + ref.shape[0]
        sig_fft = np.fft.rfft(sig, n=n)
        ref_fft = np.fft.rfft(ref, n=n)
        cross = sig_fft * np.conj(ref_fft)
        denom = np.abs(cross)
        denom[denom < 1e-12] = 1e-12
        cc = np.fft.irfft(cross / denom, n=n)

        max_shift = min(int(self.rate * max_tau) + 1, n // 2)
        cc = np.concatenate((cc[-max_shift:], cc[: max_shift + 1]))
        shift = np.argmax(cc) - max_shift
        return shift / float(self.rate)

    def estimate_angle(self, chunk):
        max_lr = self.width / self.sound_speed
        max_fb = self.depth / self.sound_speed

        tau_lr_front = self.gcc_phat(chunk[0], chunk[1], max_lr)
        tau_lr_rear = self.gcc_phat(chunk[2], chunk[3], max_lr)
        tau_lr = 0.5 * (tau_lr_front + tau_lr_rear)

        tau_fb_left = self.gcc_phat(chunk[2], chunk[0], max_fb)
        tau_fb_right = self.gcc_phat(chunk[3], chunk[1], max_fb)
        tau_fb = 0.5 * (tau_fb_left + tau_fb_right)

        vy = tau_lr / self.width
        vx = tau_fb / self.depth
        if abs(vx) < 1e-9 and abs(vy) < 1e-9:
            return 0
        return int(round(math.degrees(math.atan2(vy, vx))))

    def identify_speaker(self, mono):
        wav = torch.from_numpy(mono).unsqueeze(0)
        with torch.no_grad():
            emb = self.encoder.encode_batch(wav).squeeze().cpu().numpy()
        norm = np.linalg.norm(emb)
        if norm > 0:
            emb = emb / norm

        best_idx = -1
        best_sim = -1.0
        for idx, centroid in enumerate(self.speakers):
            sim = float(np.dot(emb, centroid))
            if sim > best_sim:
                best_sim = sim
                best_idx = idx

        if best_sim >= self.sim_thresh and best_idx >= 0:
            updated = 0.8 * self.speakers[best_idx] + 0.2 * emb
            self.speakers[best_idx] = updated / np.linalg.norm(updated)
            return f"Speaker {best_idx + 1}"

        if len(self.speakers) < self.max_speakers:
            self.speakers.append(emb)
            return f"Speaker {len(self.speakers)}"

        return f"Speaker {best_idx + 1}"

    def process(self, chunk):
        mono = np.mean(chunk, axis=0)
        rms = float(np.sqrt(np.mean(mono**2)))

        if rms < self.speech_rms:
            return None

        angle = self.estimate_angle(chunk)
        rear_voice = abs(angle) > 100
        loud_sound = rms >= self.alert_rms
        haptic = bool(rear_voice or loud_sound)

        segments, _ = self.asr.transcribe(
            mono,
            language="en",
            beam_size=1,
            vad_filter=True,
            without_timestamps=True,
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()

        if not text:
            if loud_sound:
                return {
                    "text": "[Loud Sound Alert]",
                    "speaker": "Alert",
                    "angle": angle,
                    "haptic": True,
                }
            return None

        speaker = self.identify_speaker(mono)
        return {
            "text": text[:63],
            "speaker": speaker[:15],
            "angle": angle,
            "haptic": haptic,
        }
