import socket
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

HOST = "0.0.0.0"
PORT = 5005
BUFFER_SIZE = 4096

def run_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((HOST, PORT))
    
    logging.info(f"AI Backend listening for UDP packets on port {PORT}...")

    try:
        while True:
            data, addr = sock.recvfrom(BUFFER_SIZE)
            logging.info(f"Received {len(data)} bytes from {addr}")

            # TODO AI Inference happens here
            # audio_array = process_pcm(data)
            # text = transcribe(audio_array)
            # speaker = diarize(audio_array)

            response_payload = {
                "text": "Network Sync OK",
                "speaker": "Speaker 1",
                "angle": 45,
                "haptic": True
            }
            
            json_bytes = json.dumps(response_payload).encode('utf-8')
            sock.sendto(json_bytes, addr)
            logging.info(f"Sent JSON payload back to {addr}")

    except KeyboardInterrupt:
        logging.info("Shutting down AI Backend server.")
    finally:
        sock.close()

if __name__ == "__main__":
    run_server()
