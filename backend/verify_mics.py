import socket
import struct
import numpy as np

UDP_IP = "0.0.0.0"
UDP_PORT = 5005
HDR = struct.Struct("<BBBBII")

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))
print(f"Listening on port {UDP_PORT} for ESP32 microphone data...")
print("Tap each microphone physically to verify channel mapping.")
print("-" * 60)

try:
    while True:
        data, addr = sock.recvfrom(4096)
        if len(data) < HDR.size:
            continue
            
        ptype, ver, ch, _, seq, t_ms = HDR.unpack_from(data)
        if ptype != 0x01 or ch != 4:
            continue
            
        pcm = np.frombuffer(data, dtype="<i2", offset=HDR.size).reshape(-1, 4)
        
        rms = np.sqrt(np.mean(pcm.astype(np.float32)**2, axis=0))
        
        meters = []
        for i, r in enumerate(rms):
            bars = "█" * min(int(r / 500), 10)
            meters.append(f"Ch{i}: {int(r):5d} {bars:<10}")
            
        print(f"\rSeq {seq:5d} | " + " | ".join(meters), end="", flush=True)

except KeyboardInterrupt:
    print("\nVerification stopped.")
    sock.close()
