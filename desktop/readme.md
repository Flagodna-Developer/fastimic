# Desktop Application

This folder contains the desktop version of the application with enhanced customization options and better integration for desktop environments.

## Files in this folder

- `app.py` - Main application file (run this to start the application)
- `receiver.py` - Receiver module for handling incoming data/signals

## Quick Start

### Prerequisites

Make sure you have Python 3.7+ installed on your system.

### Required Dependencies

Install the required packages:

```bash
pip install sounddevice
```

### Platform-specific packages

Depending on your Linux distribution, you may need additional packages:

**Ubuntu/Debian:**

```bash
sudo apt update
sudo apt install python3-sounddevice portaudio19-dev
```

**Fedora/RHEL:**

```bash
sudo dnf install python3-sounddevice portaudio-devel
```

**Arch Linux:**

```bash
sudo pacman -S python-sounddevice portaudio
```

**Windows:**

```bash
pip install sounddevice
```

## Running the Application

To start the desktop application, simply run:

```bash
python app.py
```

or

```bash
python3 app.py
```

## Features

- Enhanced desktop integration
- Better customization options
- Optimized for desktop environments
- Improved audio handling with sounddevice

## Customization

This desktop version includes additional customization options compared to the mobile version:

- Desktop-specific configurations
- Enhanced audio settings
- Custom themes and layouts
- Better file management integration

## Troubleshooting

### Common Issues

1. **Audio not working:**

   - Make sure sounddevice is properly installed
   - Check if your system has the required audio libraries
   - Try running: `python -c "import sounddevice; print('Audio OK')"`

2. **Permission errors:**

   - On Linux, you might need to add your user to the audio group:

   ```bash
   sudo usermod -a -G audio $USER
   ```

   - Log out and log back in for changes to take effect

3. **Module not found errors:**
   - Make sure all dependencies are installed
   - Try using virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

## Support

If you encounter any issues:

1. Check that all dependencies are installed correctly
2. Verify your Python version is 3.7 or higher
3. Make sure your audio system is working properly
4. Refer to the main project documentation

## Notes

- This desktop version is optimized for desktop environments
- For mobile deployment, use the main project files
- The receiver.py module handles background operations - do not run it directly
- Always run app.py as the main entry point
