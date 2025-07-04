# LED Battery Monitor (With Spotify Compatibility)

> (This a personal project I put together, because it was fun)

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.12-blue.svg)
![Platform](https://img.shields.io/badge/platform-linux-brightgreen.svg)
![Release](https://img.shields.io/github/v/release/ctsdownloads/led-battery-monitor)
![Downloads](https://img.shields.io/github/downloads/ctsdownloads/led-battery-monitor/total)

A sophisticated Python application that displays real-time battery status and time remaining on **Framework Laptop 16 LED modules**, featuring Spotify integration, customizable brightness controls, and a comprehensive menu system.

## 📖 Quick Navigation

**🚀 Get Started Fast**
- [📦 Installation](#-getting-started) | [💻 Download Latest Release](https://github.com/ctsdownloads/led-battery-monitor/releases/latest)
- [🛒 Hardware Setup](#step-2-hardware-installation) | [🔧 Usage Guide](#-usage)

**📱 Features & Examples**
- [🖼️ Live Display Photos](#️-live-display-examples) | [🌟 Feature Overview](#-features)
- [🎵 Spotify Setup](#spotify-setup) | [🔆 Brightness Settings](#brightness-settings)

**⚙️ Configuration & Support**
- [📋 Settings & Config](#-configuration) | [🔍 Troubleshooting](#-troubleshooting)
- [🛠️ Development Setup](#-development) | [🤝 Contributing](#-contributing)

**📊 Compatibility**
- [🐧 Linux Distributions](#platform-compatibility) | [🔋 Hardware Requirements](#step-1-purchase-hardware)

## 🖼️ Live Display Examples

### Battery Monitoring Mode
![Battery Display](https://raw.githubusercontent.com/ctsdownloads/led-battery-monitor/8ce7cfc879ba07e71badfdfb03dd83a1a20669e6/images/battery.jpg)
*Left module shows battery level with animated fill, right module displays time remaining*

### Charging Mode with Pulse Animation
![Charging Display](https://raw.githubusercontent.com/ctsdownloads/led-battery-monitor/8ce7cfc879ba07e71badfdfb03dd83a1a20669e6/images/charging.jpg)
*Pulse animation indicates active charging, real-time power consumption tracking*

### Spotify Integration Mode
![Spotify Mode 1](https://raw.githubusercontent.com/ctsdownloads/led-battery-monitor/8ce7cfc879ba07e71badfdfb03dd83a1a20669e6/images/Spotify.jpg)
*Automatically switches to music mode when Spotify is playing*

![Spotify Mode 2](https://raw.githubusercontent.com/ctsdownloads/led-battery-monitor/8ce7cfc879ba07e71badfdfb03dd83a1a20669e6/images/spotify2.jpg)
*Left module: track progress bar (**not battery, a progress indicator**), Right module: scrolling artist and song information*

## 🌟 Features

### 🔋 **Framework Laptop 16 LED Module Integration**
- **Dual LED Modules**: Perfect fit for Framework Laptop 16 LED modules
- **Left Module**: Battery level visualization with animated fill levels
- **Right Module**: Time remaining display with digital clock format
- **Pulse Animation**: Visual feedback during charging/discharging cycles

### 🎵 **Spotify Integration**
- **Automatic Detection**: Seamlessly switches to music mode when Spotify is playing
- **Track Progress**: Left module shows song progress bar in real-time
- **Scrolling Display**: Right module displays scrolling artist and track information
- **MPRIS Support**: Uses Linux MPRIS interface for reliable music detection

### 🔆 **Advanced Brightness Control**
- **Dual Brightness Settings**: Current brightness (temporary) and startup brightness (permanent)
- **Auto-Dim Functionality**: Automatically dims displays after configurable inactivity
- **Individual Control**: Separate brightness settings for battery and time displays
- **Flash Testing**: Built-in testing to verify LED module connectivity

### ⚙️ **Comprehensive Menu System**
- **Interactive Configuration**: Full menu-driven setup and customization
- **Settings Persistence**: All configurations saved to `~/.led_battery_monitor_settings.json`
- **Real-time Adjustments**: Change settings while monitoring is active
- **Diagnostic Tools**: Built-in testing and troubleshooting features

## 🛒 Getting Started

### Step 1: Purchase Hardware
1. **Get Framework Laptop 16**: If you don't have one already
2. **You need LED Modules**: [2× LED Matrix modules](https://frame.work/products/16-led-matrix?v=FRAKDE0001) from Framework

### Step 2: Hardware Installation
1. **Power Down**: Shut down your Framework Laptop 16
2. **Install Modules**: Insert LED Matrix modules on either side of the keyboard
3. **Power On**: Boot your Framework Laptop 16

### Step 3: Software Installation
```bash
# Download the universal Linux binary
wget https://github.com/ctsdownloads/led-battery-monitor/releases/latest/download/led-battery-monitor-linux-x64

# Make executable
chmod +x led-battery-monitor-linux-x64

# Log out and back in (or restart) for group changes to take effect
./led-battery-monitor-linux-x64
```

### Platform Compatibility

| Distribution | Binary | Status |
|--------------|--------|--------|
| **Fedora 42+ (Bluefin, Aurora)** | `led-battery-monitor-linux-x64` | ✅ Fully Tested |
| **Ubuntu 24.04+** | `led-battery-monitor-linux-x64` | ✅ Fully Tested |
| **Debian 12+ (Bookworm)** | `led-battery-monitor-linux-x64` | ✅ Compatible |
| **Arch Linux, Manjaro** | `led-battery-monitor-linux-x64` | ✅ Compatible |
| **Pop!_OS, Linux Mint** | `led-battery-monitor-linux-x64` | ✅ Compatible |
| **openSUSE Tumbleweed** | `led-battery-monitor-linux-x64` | ✅ Compatible |

**Ubuntu-Specific Alternative**: If the universal binary doesn't work:
```bash
wget https://github.com/ctsdownloads/led-battery-monitor/releases/latest/download/led-battery-monitor-ubuntu-24.04-x64
chmod +x led-battery-monitor-ubuntu-24.04-x64
./led-battery-monitor-ubuntu-24.04-x64
```

## 🚀 Usage

### Main Menu
```
🔋 LED BATTERY MONITOR v2.0
==================================================
1. Start Battery Monitoring (Silent)
2. Battery Brightness (Left LED)
3. Time Brightness (Right LED)
4. Display Settings
5. Music Settings
6. Battery Status
7. About
8. Dim displays now (one-time)
9. Disable auto-dim (stop timeout)
0. Exit
```

### Brightness Settings
- **Current Brightness**: Immediate changes (temporary)
- **Startup Brightness**: Permanent default (saved across restarts)

**Recommended Settings**:
| Environment | Battery LED | Time LED | Auto-Dim |
|-------------|-------------|----------|----------|
| **Office/Daytime** | 75% (192) | 75% (192) | 50% after 2 min |
| **Evening Work** | 50% (128) | 50% (128) | 25% after 1 min |
| **Night/Dark** | 25% (64) | 25% (64) | 10% after 30 sec |
| **Presentations** | 10% (25) | 10% (25) | Disabled |

### Spotify Setup
**Prerequisites**: Spotify desktop app (not web player) and `dbus-send` command

**Test Connection**:
```bash
dbus-send --print-reply --dest=org.mpris.MediaPlayer2.spotify /org/mpris/MediaPlayer2 org.freedesktop.DBus.Properties.Get string:org.mpris.MediaPlayer2.Player string:PlaybackStatus
```

**Display Modes**:
- **Normal Mode**: Battery percentage (left) + Time remaining (right)
- **Music Mode**: Track progress (left) + Scrolling artist/title (right)

## 🛠️ Development

### Building from Source
```bash
git clone https://github.com/ctsdownloads/led-battery-monitor.git
cd led-battery-monitor
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python leds.py  # Run directly
python -m PyInstaller --onefile --console --name led-battery-monitor leds.py  # Build binary
```

### Distrobox Development (Recommended for Immutable Distros)
```bash
distrobox create --name led-dev --image fedora:39
distrobox enter led-dev
sudo dnf install python3 python3-pip
pip install pyinstaller pyserial psutil
python -m PyInstaller --onefile leds.py
```

## 🔍 Troubleshooting

### Common Solutions
1. **Reseat Modules**: Remove and reinsert LED modules
2. **Flash Test**: Use built-in flash test from brightness menu

### Battery Issues
```bash
upower -i $(upower -e | grep 'BAT')                          # Check battery
python3 -c "import psutil; print(psutil.sensors_battery())"  # Test psutil
```

### Spotify Issues
1. **Desktop App Only**: Must use Spotify desktop, not web player
2. **Must Be Playing**: Spotify must be actively playing (not paused)
3. **Restart Spotify**: Close and reopen application

### Debug Mode
```bash
export LED_MONITOR_DEBUG=1
./led-battery-monitor-linux-x64
```

## 📋 Configuration

Settings are saved to: `~/.led_battery_monitor_settings.json`

**Example Configuration**:
```json
{
  "battery_brightness": 128,
  "time_brightness": 128,
  "startup_battery_brightness": 96,
  "startup_time_brightness": 96,
  "fps": 10,
  "pulse_enabled": true,
  "dim_timeout": 120,
  "auto_dim_level": 20,
  "music_scroll_speed": 2
}
```

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature-name`
3. Test on Framework Laptop 16 hardware
4. Submit pull request with testing details

---

**Made with ❤️ for the Framework Laptop 16 community**

*Optimized for Framework Laptop 16 LED modules on modern Linux distributions*
