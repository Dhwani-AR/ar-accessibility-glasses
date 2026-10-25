import socket
import json
import logging
import queue
import struct
import threading
import numpy as np

from pipeline import AudioPipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

HOST = "0.0.0.0"
PORT = 5005
BUFFER_SIZE = 4096

HDR = struct.Struct("<BBBBII")  # type, version, channels, reserved, seq, t_ms
PROTOCOL_VERSION = 1
PTYPE_AUDIO = 0x01
PTYPE_HEARTBEAT = 0x02

CHANNELS = 4
SAMPLE_RATE = 16000
CHUNK_SECONDS = 2.0
CHUNK_FRAMES = int(SAMPLE_RATE * CHUNK_SECONDS)
MAX_GAP_PACKETS = 50  # cap zero-fill so a bogus seq jump cannot allocate huge arrays

def process_chunks(q: queue.Queue, sock: socket.socket):
    pipe = AudioPipeline(rate=SAMPLE_RATE, width=0.14, depth=0.07)
    while True:
        chunk, addr = q.get()
        reply = pipe.process(chunk)
        if reply is not None:
            logging.info(f"Out -> {reply}")
            sock.sendto(json.dumps(reply).encode("utf-8"), addr)

def parse_packet(pkt: bytes):
    """Return (ptype, seq, t_ms, audio), or None if the packet is malformed.

    audio is None for packets that carry no samples (heartbeats).
    """
    if len(pkt) < HDR.size:
        return None
    ptype, ver, ch, _reserved, seq, t_ms = HDR.unpack_from(pkt)
    if ver != PROTOCOL_VERSION:
        return None
    if ptype == PTYPE_HEARTBEAT:
        return ptype, seq, t_ms, None
    payload = len(pkt) - HDR.size
    if ptype != PTYPE_AUDIO or ch != CHANNELS or payload == 0 or payload % (2 * ch):
        return None
    pcm = np.frombuffer(pkt, dtype="<i2", offset=HDR.size)
    audio = pcm.reshape(-1, ch).T.astype(np.float32) / 32768.0
    return ptype, seq, t_ms, audio


def process_chunks(q: queue.Queue, sock: socket.socket):
    """Worker thread: inference runs here so the receive loop never blocks."""
    while True:
        chunk, addr = q.get()
        # TODO: transcribe, diarize, estimate angle
        reply = {"text": "Chunk Processed", "speaker": "Speaker 1", "angle": 0, "haptic": False}
        sock.sendto(json.dumps(reply).encode("utf-8"), addr)


def run_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1 << 20)
    sock.bind((HOST, PORT))
    logging.info(f"AI Backend listening for UDP packets on port {PORT}...")

    work_q = queue.Queue(maxsize=4)
    threading.Thread(target=process_chunks, args=(work_q, sock), daemon=True).start()

    ring_buf = np.zeros((CHANNELS, 0), dtype=np.float32)
    last_seq = None

    try:
        while True:
            data, addr = sock.recvfrom(BUFFER_SIZE)
            parsed = parse_packet(data)
            if parsed is None:
                continue
            ptype, seq, t_ms, audio = parsed

            if ptype == PTYPE_HEARTBEAT:
                logging.info(f"Heartbeat seq={seq}, t_ms={t_ms} from {addr}")
                reply = {"text": f"Sync OK #{seq}", "speaker": "Speaker 1", "angle": 45, "haptic": True}
                sock.sendto(json.dumps(reply).encode("utf-8"), addr)
                continue

            if last_seq is not None:
                delta = (seq - last_seq) & 0xFFFFFFFF
                if delta == 0:
                    continue  # duplicate
                if delta >= 0x80000000:  # went backwards: device restarted or packet reordered
                    logging.warning(f"Sequence went backwards to seq={seq}; resyncing")
                    ring_buf = ring_buf[:, :0]
                elif delta > 1:
                    logging.warning(f"Lost {delta - 1} packets before seq={seq}")
                    fill = min(delta - 1, MAX_GAP_PACKETS) * audio.shape[1]
                    gap = np.zeros((CHANNELS, fill), dtype=np.float32)
                    ring_buf = np.concatenate((ring_buf, gap), axis=1)
            last_seq = seq

            ring_buf = np.concatenate((ring_buf, audio), axis=1)
            if ring_buf.shape[1] >= CHUNK_FRAMES:
                chunk = ring_buf[:, :CHUNK_FRAMES].copy()
                ring_buf = ring_buf[:, CHUNK_FRAMES:]
                logging.info(f"Chunk ready: {chunk.shape} at seq={seq}")
                try:
                    work_q.put_nowait((chunk, addr))
                except queue.Full:
                    logging.warning("Worker is behind; dropping chunk")

    except KeyboardInterrupt:
        logging.info("Shutting down AI Backend server.")
    finally:
        sock.close()


if __name__ == "__main__":
    run_server()
