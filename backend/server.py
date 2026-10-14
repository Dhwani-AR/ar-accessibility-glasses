import socket
import json
import logging
import struct
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

HOST = "0.0.0.0"
PORT = 5005
BUFFER_SIZE = 4096

HDR = struct.Struct("<BBBBII")  # type, version, channels, reserved, seq, t_ms
CHANNELS = 4
SAMPLE_RATE = 16000
CHUNK_SECONDS = 2.0
CHUNK_FRAMES = int(SAMPLE_RATE * CHUNK_SECONDS)


def parse_audio(pkt: bytes):
    if len(pkt) < HDR.size:
        return None, None, None, None, None, None

    ptype, ver, ch, reserved, seq, t_ms = HDR.unpack_from(pkt, 0)

    if len(pkt) == HDR.size:
        return ptype, ver, ch, seq, t_ms, None

    pcm = np.frombuffer(pkt, dtype="<i2", offset=HDR.size)
    frames = pcm.size // ch
    audio = (pcm[: frames * ch].reshape(frames, ch).T.astype(np.float32)) / 32768.0

    return ptype, ver, ch, seq, t_ms, audio


def lost_packets(last_seq: int, seq: int) -> int:
    return (seq - last_seq - 1) & 0xFFFFFFFF


def run_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((HOST, PORT))

    logging.info(f"AI Backend listening for UDP packets on port {PORT}...")

    ring_buf = np.zeros((CHANNELS, 0), dtype=np.float32)
    last_seq = None

    try:
        while True:
            data, addr = sock.recvfrom(BUFFER_SIZE)
            if len(data) < HDR.size:
                continue

            ptype, ver, ch, seq, t_ms, audio = parse_audio(data)
            if ptype != 0x01:
                continue

            if last_seq is not None:
                missed = lost_packets(last_seq, seq)
                if missed > 0:
                    logging.warning(f"Lost {missed} packets before seq={seq}")
            last_seq = seq

            if audio is None:
                logging.info(f"Heartbeat seq={seq}, t_ms={t_ms} from {addr}")
                reply = {
                    "text": f"Sync OK #{seq}",
                    "speaker": "Speaker 1",
                    "angle": 45,
                    "haptic": True,
                }
                sock.sendto(json.dumps(reply).encode("utf-8"), addr)
                continue

            ring_buf = np.concatenate((ring_buf, audio), axis=1)

            if ring_buf.shape[1] >= CHUNK_FRAMES:
                chunk = ring_buf[:, :CHUNK_FRAMES]
                ring_buf = ring_buf[:, CHUNK_FRAMES:]

                logging.info(f"Chunk ready: {chunk.shape} at seq={seq}")

                reply = {
                    "text": "Chunk Processed",
                    "speaker": "Speaker 1",
                    "angle": 0,
                    "haptic": False,
                }
                sock.sendto(json.dumps(reply).encode("utf-8"), addr)

    except KeyboardInterrupt:
        logging.info("Shutting down AI Backend server.")
    finally:
        sock.close()


if __name__ == "__main__":
    run_server()
