#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import sys
from threading import Thread, Event
import signal
import time
import socket
import sounddevice as sd
import numpy as np
import argparse
from queue import Queue
import logging


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
        self.logger = logging.getLogger("AudioReceiver")

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
            s.settimeout(1)
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
            self.logger.info("Audio stream started")

            network_thread = Thread(target=self.network_thread)
            network_thread.start()

            while not self.shutdown_event.is_set():
                time.sleep(0.1)

        except Exception as e:
            self.logger.error(f"Error: {e}")
        finally:
            self.cleanup()

    def cleanup(self):
        self.shutdown_event.set()
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception as e:
                self.logger.error(f"Error stopping stream: {e}")
        self.logger.info("Audio receiver stopped")


class AudioReceiverApp:
    def __init__(self, root):
        self.root = root
        self.root.title("FastiMic - Audio Receiver")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Variables
        self.receiver_thread = None
        self.receiver = None
        self.is_running = False
        self.audio_devices = self.get_audio_devices()

        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler(sys.stdout)],
        )
        self.logger = logging.getLogger("AudioReceiverApp")

        # UI Setup
        self.create_widgets()
        self.center_window()

    def get_audio_devices(self):
        """Get available audio output devices"""
        devices = []
        try:
            host_apis = sd.query_hostapis()
            for api in host_apis:
                for device_idx in api["devices"]:
                    device = sd.query_devices(device_idx)
                    if device["max_output_channels"] > 0:
                        devices.append(
                            (device_idx, f"{device['name']} ({api['name']})")
                        )
        except Exception as e:
            self.logger.error(f"Error getting audio devices: {e}")
            devices = [(None, "Default Device")]
        return devices

    def get_ip_address(self):
        """Get the current IP address of the machine"""
        try:
            if sys.platform == "linux":
                result = subprocess.run(
                    ["hostname", "-I"], capture_output=True, text=True
                )
                if result.returncode == 0:
                    return result.stdout.strip()

            hostname = socket.gethostname()
            ip_address = socket.gethostbyname(hostname)
            if ip_address.startswith("127."):
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                ip_address = s.getsockname()[0]
                s.close()
            return ip_address
        except Exception as e:
            self.logger.error(f"Error getting IP address: {e}")
            return "Unable to determine IP"

    def create_widgets(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # IP Address display
        ip_frame = ttk.Frame(main_frame, padding="5")
        ip_frame.pack(fill=tk.X, pady=(0, 10))

        current_ip = self.get_ip_address()
        ttk.Label(ip_frame, text="Current IP Address:").pack(side=tk.LEFT, padx=5)
        ttk.Label(
            ip_frame,
            text=current_ip,
            font=("TkDefaultFont", 10, "bold"),
            foreground="#2E86C1",
        ).pack(side=tk.LEFT)

        # Connection settings frame
        conn_frame = ttk.LabelFrame(
            main_frame, text="Connection Settings", padding="10"
        )
        conn_frame.pack(fill=tk.X, pady=5)

        # Host
        ttk.Label(conn_frame, text="Host:").grid(
            row=0, column=0, sticky="e", padx=5, pady=5
        )
        self.host_entry = ttk.Entry(conn_frame)
        self.host_entry.insert(0, "0.0.0.0")
        self.host_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=5)

        # Port
        ttk.Label(conn_frame, text="Port:").grid(
            row=1, column=0, sticky="e", padx=5, pady=5
        )
        self.port_entry = ttk.Entry(conn_frame)
        self.port_entry.insert(0, "5555")
        self.port_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=5)

        # Audio settings frame
        audio_frame = ttk.LabelFrame(main_frame, text="Audio Settings", padding="10")
        audio_frame.pack(fill=tk.X, pady=5)

        # Device
        ttk.Label(audio_frame, text="Output Device:").grid(
            row=0, column=0, sticky="e", padx=5, pady=5
        )
        self.device_var = tk.StringVar()
        self.device_menu = ttk.Combobox(
            audio_frame,
            textvariable=self.device_var,
            values=[name for idx, name in self.audio_devices],
            state="readonly",
            width=40,
        )
        if self.audio_devices:
            self.device_menu.current(0)
        self.device_menu.grid(row=0, column=1, sticky="ew", padx=5, pady=5)

        # Sample Rate
        ttk.Label(audio_frame, text="Sample Rate:").grid(
            row=1, column=0, sticky="e", padx=5, pady=5
        )
        self.rate_var = tk.IntVar(value=44100)
        self.rate_menu = ttk.Combobox(
            audio_frame,
            textvariable=self.rate_var,
            values=[8000, 11025, 16000, 22050, 44100, 48000],
            state="readonly",
            width=10,
        )
        self.rate_menu.grid(row=1, column=1, sticky="w", padx=5, pady=5)

        # Channels
        ttk.Label(audio_frame, text="Channels:").grid(
            row=2, column=0, sticky="e", padx=5, pady=5
        )
        self.channels_var = tk.IntVar(value=1)
        self.channels_menu = ttk.Combobox(
            audio_frame,
            textvariable=self.channels_var,
            values=[1, 2],
            state="readonly",
            width=10,
        )
        self.channels_menu.grid(row=2, column=1, sticky="w", padx=5, pady=5)

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(
            main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W
        )
        status_bar.pack(fill=tk.X, pady=(5, 0))

        # Control buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        self.start_button = ttk.Button(
            button_frame, text="Start Receiver", command=self.start_receiver, width=15
        )
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = ttk.Button(
            button_frame,
            text="Stop Receiver",
            command=self.stop_receiver,
            width=15,
            state=tk.DISABLED,
        )
        self.stop_button.pack(side=tk.LEFT, padx=5)

        ttk.Button(button_frame, text="Exit", command=self.on_close, width=15).pack(
            side=tk.RIGHT, padx=5
        )

        # Configure grid weights
        conn_frame.columnconfigure(1, weight=1)
        audio_frame.columnconfigure(1, weight=1)

    def center_window(self):
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def start_receiver(self):
        host = self.host_entry.get().strip()
        port = self.port_entry.get().strip()
        rate = self.rate_var.get()
        channels = self.channels_var.get()

        # Get selected device
        device_idx = None
        if self.audio_devices and self.device_var.get():
            for idx, name in self.audio_devices:
                if name == self.device_var.get():
                    device_idx = idx
                    break

        # Validate inputs
        if not host:
            messagebox.showerror("Error", "Please enter a valid host address")
            return

        try:
            port = int(port)
            if not (1 <= port <= 65535):
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid port number (1-65535)")
            return

        try:
            self.receiver = AudioReceiver(
                host=host,
                port=port,
                sample_rate=rate,
                channels=channels,
                device=device_idx,
            )

            self.receiver_thread = Thread(target=self.receiver.start, daemon=True)
            self.receiver_thread.start()

            self.is_running = True
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.status_var.set(f"Receiver running on {host}:{port}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to start receiver: {str(e)}")
            self.reset_ui()

    def stop_receiver(self):
        if self.receiver and self.is_running:
            try:
                self.receiver.shutdown_event.set()
                if self.receiver_thread:
                    self.receiver_thread.join(timeout=2)
                self.reset_ui()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to stop receiver: {str(e)}")

    def reset_ui(self):
        self.is_running = False
        self.receiver = None
        self.receiver_thread = None
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.status_var.set("Ready")

    def on_close(self):
        if self.is_running:
            if messagebox.askokcancel(
                "Quit", "Receiver is still running. Do you want to stop it and quit?"
            ):
                self.stop_receiver()
                self.root.destroy()
        else:
            self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = AudioReceiverApp(root)

    # Set window icon if available
    try:
        if sys.platform.startswith("win"):
            root.iconbitmap(default="icon.ico")
        else:
            img = tk.PhotoImage(file="icon.png")
            root.tk.call("wm", "iconphoto", root._w, img)
    except:
        pass

    root.mainloop()
