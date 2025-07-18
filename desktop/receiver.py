#!/usr/bin/env python3
import socket
import sounddevice as sd
import numpy as np
import argparse
from queue import Queue
from threading import Thread, Event
import logging
import signal
import sys


class AudioReceiver:
    def __init__(
        self, host="0.0.0.0", port=5555, sample_rate=44100, channels=1, device=None
    ):
        self.host = host
        self.port = port
        self.sample_rate = sample_rate
        self.channels = channels
        self.device = device
        self.audio_queue = Queue(maxsize=20)
        self.shutdown_event = Event()
        self.stream = None

        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler("receiver.log"),
            ],
        )
        self.logger = logging.getLogger("AudioReceiver")

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.shutdown_event.set()

    def callback(self, outdata, frames, time, status):
        if status:
            self.logger.warning(f"Audio stream status: {status}")

        if not self.audio_queue.empty():
            data = self.audio_queue.get()
            try:
                audio_data = np.frombuffer(data, dtype=np.int16)

                # Ensure proper size
                if len(audio_data) < frames * self.channels:
                    padding = np.zeros(
                        frames * self.channels - len(audio_data), dtype=np.int16
                    )
                    audio_data = np.concatenate((audio_data, padding))
                elif len(audio_data) > frames * self.channels:
                    audio_data = audio_data[: frames * self.channels]

                outdata[:] = audio_data.reshape(-1, self.channels)
            except Exception as e:
                self.logger.error(f"Audio processing error: {e}")
                outdata.fill(0)
        else:
            outdata.fill(0)

    def network_thread(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.settimeout(1)  # Shorter timeout for more responsive shutdown
            s.bind((self.host, self.port))
            s.listen(1)
            self.logger.info(f"Listening on {self.host}:{self.port}")

            try:
                while not self.shutdown_event.is_set():
                    try:
                        conn, addr = s.accept()
                    except socket.timeout:
                        continue

                    self.logger.info(f"Connected by {addr}")
                    conn.settimeout(1)

                    with conn:
                        chunk_size = int(self.sample_rate * 0.02) * self.channels * 2
                        self.logger.info(f"Using chunk size: {chunk_size} bytes")

                        while not self.shutdown_event.is_set():
                            try:
                                data = conn.recv(chunk_size)
                                if not data:
                                    break
                                self.audio_queue.put(data)
                            except socket.timeout:
                                continue
                            except Exception as e:
                                self.logger.error(f"Network error: {e}")
                                break

            except Exception as e:
                if not self.shutdown_event.is_set():
                    self.logger.error(f"Connection error: {e}")
            finally:
                self.logger.info("Network thread stopping")

    def start(self):
        try:
            self.stream = sd.OutputStream(
                device=self.device,
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="int16",
                callback=self.callback,
                blocksize=int(self.sample_rate * 0.02),
            )
            self.stream.start()
            self.logger.info(f"Audio stream started on device {self.device}")

            network_thread = Thread(target=self.network_thread)
            network_thread.start()

            # Main loop with shutdown check
            while not self.shutdown_event.is_set():
                sd.sleep(100)

        except Exception as e:
            self.logger.error(f"Error: {e}")
        finally:
            self.cleanup()

    def cleanup(self):
        """Clean up resources"""
        self.shutdown_event.set()
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception as e:
                self.logger.error(f"Error stopping stream: {e}")
        self.logger.info("Audio receiver stopped")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Audio Streaming Receiver")
    parser.add_argument("--host", default="0.0.0.0", help="Host IP to bind to")
    parser.add_argument("--port", type=int, default=5555, help="Port to listen on")
    parser.add_argument(
        "--rate",
        type=int,
        default=44100,
        choices=[8000, 11025, 16000, 22050, 44100, 48000],
        help="Sample rate",
    )
    parser.add_argument(
        "--channels",
        type=int,
        default=1,
        choices=[1, 2],
        help="Number of audio channels",
    )
    parser.add_argument("--device", type=int, help="Output device ID")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.debug("Debug logging enabled")

    # List available devices if requested
    if args.device is None:
        print("Available output devices:")
        devices = sd.query_devices()
        for i, d in enumerate(devices):
            if d["max_output_channels"] > 0:
                print(f"{i}: {d['name']} (channels: {d['max_output_channels']})")
        print("\nUse --device <ID> to select an output device")

    receiver = AudioReceiver(
        host=args.host,
        port=args.port,
        sample_rate=args.rate,
        channels=args.channels,
        device=args.device,
    )

    try:
        receiver.start()
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        sys.exit(1)
