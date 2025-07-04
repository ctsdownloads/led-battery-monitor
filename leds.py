import serial
import time
import math
import psutil
import platform
import glob
import os
import json

def clear_screen():
    """Clear the terminal screen"""
    os.system('clear' if os.name == 'posix' else 'cls')

# Configuration
COM_PORT = '/dev/ttyUSB0'
BAUD_RATE = 115200
WIDTH = 9
HEIGHT = 34
TIME_WIDTH = 9
TIME_HEIGHT = 34
MAX_BRIGHT = 255
MIN_M = 10 / 255
SIGMA = 2.0
STEP_SCALE = 100.0
FADE_SPEED = 0.01
PULSE_SPEED_MODIFIER = 2.0
CMD_STAGE_COL = 0x07
CMD_FLUSH_COLS = 0x08

# Runtime settings (can be changed via menu)
settings = {
    'battery_brightness': 255,
    'time_brightness': 255,
    'fps': 10,
    'pulse_enabled': True,
    'battery_enabled': True,
    'time_enabled': True,
    'dim_timeout': 0,  # Auto-dim disabled by default
    'auto_dim_level': 25,  # Percentage brightness when dimmed
    'music_enabled': True,  # Music display enabled
    'music_scroll_speed': 1,  # Scroll speed for track names
    'start_dimmed': False,  # Whether to start the program already dimmed
    'startup_battery_brightness': 255,  # Default startup brightness for battery LED
    'startup_time_brightness': 255  # Default startup brightness for time LED
}

# Settings file path
SETTINGS_FILE = os.path.expanduser("~/.led_battery_monitor_settings.json")

def load_settings():
    global settings
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r') as f:
                loaded_settings = json.load(f)
            settings.update(loaded_settings)
            print(f"✓ Settings loaded from {SETTINGS_FILE}")
            print(f"  Battery brightness: {settings['battery_brightness']}")
            print(f"  Time brightness: {settings['time_brightness']}")
            print(f"  Auto-dim: {settings['dim_timeout']}s → {settings['auto_dim_level']}%")
        else:
            print(f"No settings file found, using defaults")
            save_settings()
    except Exception as e:
        print(f"❌ Error loading settings: {e}")
        save_settings()

def save_settings():
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=2)
        print(f"✓ Settings saved to {SETTINGS_FILE}")
    except Exception as e:
        print(f"❌ Error saving settings: {e}")
        pass

last_activity_time = time.time()

def get_spotify_info():
    """Get currently playing Spotify track info via MPRIS"""
    try:
        import subprocess
        
        # Check if Spotify is running and playing
        result = subprocess.run([
            'dbus-send', '--print-reply', '--dest=org.mpris.MediaPlayer2.spotify',
            '/org/mpris/MediaPlayer2', 'org.freedesktop.DBus.Properties.Get',
            'string:org.mpris.MediaPlayer2.Player', 'string:PlaybackStatus'
        ], capture_output=True, text=True, timeout=2)
        
        if result.returncode != 0:
            return None  # Spotify not running
            
        is_playing = 'Playing' in result.stdout
        
        if not is_playing:
            return None  # Only return data when actually playing
        
        # Get track metadata
        metadata_result = subprocess.run([
            'dbus-send', '--print-reply', '--dest=org.mpris.MediaPlayer2.spotify',
            '/org/mpris/MediaPlayer2', 'org.freedesktop.DBus.Properties.Get',
            'string:org.mpris.MediaPlayer2.Player', 'string:Metadata'
        ], capture_output=True, text=True, timeout=2)
        
        if metadata_result.returncode != 0:
            return None
            
        # Parse the metadata (simple parsing)
        lines = metadata_result.stdout.split('\n')
        artist = ''
        track = ''
        length_us = 0  # Track length in microseconds
        
        for i, line in enumerate(lines):
            if 'xesam:artist' in line:
                # Look for the artist in the next few lines
                for j in range(i+1, min(i+5, len(lines))):
                    if 'string' in lines[j] and lines[j].strip():
                        artist = lines[j].split('"')[1] if '"' in lines[j] else ''
                        break
            elif 'xesam:title' in line:
                # Look for the title in the next few lines
                for j in range(i+1, min(i+5, len(lines))):
                    if 'string' in lines[j] and lines[j].strip():
                        track = lines[j].split('"')[1] if '"' in lines[j] else ''
                        break
            elif 'mpris:length' in line:
                # Get track length
                for j in range(i+1, min(i+3, len(lines))):
                    if 'int64' in lines[j]:
                        try:
                            length_us = int(lines[j].split()[-1])
                        except:
                            pass
                        break
        
        # Get current position in track
        position_us = 0
        try:
            position_result = subprocess.run([
                'dbus-send', '--print-reply', '--dest=org.mpris.MediaPlayer2.spotify',
                '/org/mpris/MediaPlayer2', 'org.freedesktop.DBus.Properties.Get',
                'string:org.mpris.MediaPlayer2.Player', 'string:Position'
            ], capture_output=True, text=True, timeout=2)
            
            if position_result.returncode == 0:
                for line in position_result.stdout.split('\n'):
                    if 'int64' in line:
                        try:
                            position_us = int(line.split()[-1])
                        except:
                            pass
                        break
        except:
            pass
        
        # Calculate progress percentage
        progress = 0
        if length_us > 0:
            progress = min(100, int((position_us / length_us) * 100))
        
        return {
            'status': 'playing',
            'artist': artist,
            'track': track,
            'progress': progress
        }
        
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, Exception):
        return None

def get_battery_info():
    """Get battery information cross-platform"""
    battery = psutil.sensors_battery()
    if battery is None:
        return None, 0, 0, None
    
    # Basic battery percentage
    percentage = battery.percent
    
    # Try to get power consumption info (Linux-specific)
    charge_rate = 0
    discharge_rate = 0
    time_remaining_minutes = None
    
    if platform.system() == "Linux":
        try:
            # Get time remaining from upower (more reliable than our calculation)
            import subprocess
            try:
                upower_cmd = "upower -i $(upower -e | grep 'BAT') | grep -E 'time to empty|time to full'"
                result = subprocess.run(upower_cmd, shell=True, capture_output=True, text=True, timeout=5)
                if result.returncode == 0 and result.stdout:
                    time_line = result.stdout.strip()
                    if 'time to empty' in time_line:
                        # Parse time like "time to empty:     1.5 hours"
                        time_part = time_line.split(':')[1].strip()
                        if 'hour' in time_part:
                            hours = float(time_part.split()[0])
                            time_remaining_minutes = int(hours * 60)
                        elif 'minute' in time_part:
                            minutes = float(time_part.split()[0])
                            time_remaining_minutes = int(minutes)
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError, ValueError, IndexError):
                time_remaining_minutes = None
            
            # Read power consumption from /sys/class/power_supply/
            battery_paths = glob.glob('/sys/class/power_supply/BAT*')
            if battery_paths:
                battery_path = battery_paths[0]
                
                # Try to read current power consumption
                power_now_path = os.path.join(battery_path, 'power_now')
                current_now_path = os.path.join(battery_path, 'current_now')
                voltage_now_path = os.path.join(battery_path, 'voltage_now')
                status_path = os.path.join(battery_path, 'status')
                
                if os.path.exists(power_now_path):
                    with open(power_now_path, 'r') as f:
                        power_now = int(f.read().strip()) / 1000000.0  # Convert µW to W
                elif os.path.exists(current_now_path) and os.path.exists(voltage_now_path):
                    with open(current_now_path, 'r') as f:
                        current_now = int(f.read().strip()) / 1000000.0  # Convert µA to A
                    with open(voltage_now_path, 'r') as f:
                        voltage_now = int(f.read().strip()) / 1000000.0  # Convert µV to V
                    power_now = current_now * voltage_now
                else:
                    power_now = 0
                
                # Check if charging or discharging
                if os.path.exists(status_path):
                    with open(status_path, 'r') as f:
                        status = f.read().strip()
                    
                    if status == "Charging":
                        charge_rate = power_now * 1000  # Convert to mW for compatibility
                        discharge_rate = 0
                    elif status == "Discharging":
                        discharge_rate = power_now * 1000  # Convert to mW for compatibility
                        charge_rate = 0
                    else:
                        charge_rate = 0
                        discharge_rate = 0
                        
        except Exception as e:
            print(f"Error reading Linux power info: {e}")
            charge_rate = 0
            discharge_rate = 0
    
    return percentage, charge_rate, discharge_rate, time_remaining_minutes

def find_serial_port():
    """Find available serial ports"""
    # Common Linux serial port patterns
    ports = glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*') + glob.glob('/dev/ttyS*')
    
    if not ports:
        print("No serial ports found. Common Linux ports:")
        print("  /dev/ttyUSB0, /dev/ttyUSB1, ... (USB-to-serial adapters)")
        print("  /dev/ttyACM0, /dev/ttyACM1, ... (Arduino, etc.)")
        print("  /dev/ttyS0, /dev/ttyS1, ... (built-in serial ports)")
        return None
    
    return ports[0]  # Return first available port

# Try to find the correct serial port
serial_port = find_serial_port()
if serial_port is None:
    print("Please check your serial device connection and update COM_PORT variable")
    exit(1)

# Find second serial port for time display
available_ports = glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*') + glob.glob('/dev/ttyS*')
time_port = None
for port in available_ports:
    if port != serial_port:
        time_port = port
        break

try:
    ser = serial.Serial(serial_port, BAUD_RATE, timeout=1)
except serial.SerialException as e:
    print(f"Failed to open serial port {serial_port}: {e}")
    print("Make sure:")
    print("1. Your device is connected")
    print("2. You have permission to access the serial port (try: sudo usermod -a -G dialout $USER)")
    print("3. No other program is using the port")
    exit(1)

# Try to connect to second LED for time display
ser_time = None
if time_port:
    try:
        ser_time = serial.Serial(time_port, BAUD_RATE, timeout=1)
    except serial.SerialException as e:
        print(f"Could not connect to time display on {time_port}: {e}")
        print("Time display will be disabled")

def send_column(column_id, values, serial_port=ser, brightness_scale=1.0):
    cmd = [0x32, 0xAC, CMD_STAGE_COL, column_id]
    for val in values:
        scaled_val = int(val * brightness_scale)
        val = max(0, min(255, scaled_val))
        cmd.append(val)
    serial_port.write(bytearray(cmd))

def send_flush(serial_port=ser):
    cmd = [0x32, 0xAC, CMD_FLUSH_COLS]
    serial_port.write(bytearray(cmd))

def clear_all_leds(serial_port=ser, width=WIDTH, height=HEIGHT):
    """Turn off all LEDs"""
    for col in range(width):
        send_column(col, [0] * height, serial_port)
    send_flush(serial_port)

def show_main_menu():
    """Display main menu and handle all interactions"""
    global last_activity_time
    
    # Update activity time when showing menu (user interaction)
    last_activity_time = time.time()
    
    while True:
        clear_screen()
        print("🔋 LED BATTERY MONITOR v2.0")
        print("="*50)
        print("1. Start Battery Monitoring (Silent)")
        print("2. Battery Brightness (Left LED)")
        print("3. Time Brightness (Right LED)") 
        print("4. Display Settings")
        print("5. Music Settings")
        print("6. Battery Status")
        print("7. About")
        print("8. Dim displays now (one-time)")
        print("9. Disable auto-dim (stop timeout)")
        print("0. Exit")
        print("="*50)
        
        try:
            choice = input("Select option (0-9): ").strip()
            
            # Update activity time on any menu interaction
            last_activity_time = time.time()
            
            if choice == '0':
                clear_screen()
                print("Goodbye!")
                return False
            elif choice == '1':
                clear_screen()
                print("Battery monitoring started silently in background...")
                print("LEDs will update automatically. Press Enter to return to menu.")
                run_battery_monitoring()
            elif choice == '2':
                brightness_menu("battery")
            elif choice == '3':
                brightness_menu("time")
            elif choice == '4':
                display_settings_menu()
            elif choice == '5':
                music_settings_menu()
            elif choice == '6':
                show_battery_status()
            elif choice == '7':
                show_about()
            elif choice == '8':
                force_dim_now()
                print("✓ Displays dimmed immediately")
                input("Press Enter to continue...")
            elif choice == '9':
                settings['dim_timeout'] = 0
                save_settings()
                last_activity_time = time.time()  # Reset activity time
                print("✓ Auto-dim disabled - LEDs will stay at set brightness")
                input("Press Enter to continue...")
            else:
                print("Invalid option. Please try again.")
                time.sleep(1)
                
        except (ValueError, EOFError, KeyboardInterrupt):
            clear_screen()
            print("Returning to menu...")
            time.sleep(1)

def run_battery_monitoring():
    """Run battery monitoring silently until user presses Enter"""
    import threading
    import sys
    
    monitoring = True
    
    def monitor_loop():
        nonlocal monitoring
        pulse_pos = None
        pulse_fade = 0.0
        discharge_history = []
        SMOOTH_SAMPLES = 10
        scroll_offset = 0
        
        while monitoring:
            try:
                loop_start = time.time()
                frame_time = 1.0 / settings['fps']
                
                # Get battery info (cross-platform)
                battery_data = get_battery_info()
                if battery_data[0] is None:
                    break
                    
                p, charge_rate, discharge_rate, time_remaining_minutes = battery_data
                
                # Use system time remaining if available, otherwise fallback to calculation
                if time_remaining_minutes is not None:
                    minutes_remaining = time_remaining_minutes
                else:
                    # Fallback to our calculation with smoothing
                    if discharge_rate > 0:
                        discharge_history.append(discharge_rate)
                        if len(discharge_history) > SMOOTH_SAMPLES:
                            discharge_history.pop(0)
                        smooth_discharge = sum(discharge_history) / len(discharge_history)
                        # Simple fallback calculation
                        estimated_capacity = 50.0  # Wh
                        remaining_wh = (p / 100.0) * estimated_capacity
                        hours_remaining = remaining_wh / (smooth_discharge / 1000.0)
                        minutes_remaining = max(1, min(1440, int(hours_remaining * 60)))  # 1 min to 24 hours
                    else:
                        minutes_remaining = None
                
                # Check for auto-dim
                dim_factor = check_dim_timeout()
                
                # Check if music is playing (FIXED: Only when actually playing)
                music_info = get_spotify_info()
                music_is_playing = (music_info is not None and 
                                  settings['music_enabled'] and
                                  music_info.get('artist', '') != '' and
                                  music_info.get('track', '') != '')
                
                # Update right LED (time or music)
                if ser_time and settings['time_enabled']:
                    if music_is_playing:
                        # Show music scrolling on right LED
                        music_matrix = create_music_display(music_info, scroll_offset)
                        brightness_scale = (settings['time_brightness'] / 255.0) * dim_factor
                        for col in range(TIME_WIDTH):
                            column_data = [music_matrix[row][col] for row in range(TIME_HEIGHT)]
                            send_column(col, column_data, ser_time, brightness_scale)
                        send_flush(ser_time)
                        # Update scroll for music
                        scroll_offset += settings['music_scroll_speed']
                        if scroll_offset > len(f"{music_info['artist']} - {music_info['track']}") * 6:
                            scroll_offset = -TIME_HEIGHT
                    else:
                        # Show normal time on right LED
                        time_matrix = create_time_display(minutes_remaining)
                        brightness_scale = (settings['time_brightness'] / 255.0) * dim_factor
                        for col in range(TIME_WIDTH):
                            column_data = [time_matrix[row][col] for row in range(TIME_HEIGHT)]
                            send_column(col, column_data, ser_time, brightness_scale)
                        send_flush(ser_time)
                
                # Update left LED (battery or progress)
                if ser and settings['battery_enabled']:
                    if music_is_playing:
                        # Show track progress bar on left LED
                        progress = music_info.get('progress', 0)
                        progress_columns = create_progress_display(progress)
                        brightness_scale = (settings['battery_brightness'] / 255.0) * dim_factor
                        for col in range(WIDTH):
                            send_column(col, progress_columns[col], ser, brightness_scale)
                        send_flush(ser)
                    else:
                        # Show normal battery on left LED (ORIGINAL WORKING CODE)
                        charge_watts = charge_rate / 1000.0
                        discharge_watts = discharge_rate / 1000.0
                        mode = "charge" if charge_watts > 0 else "discharge" if discharge_watts > 0 else "idle"
                        
                        if settings['pulse_enabled'] and mode != "idle":
                            target_fade = 1.0
                        else:
                            target_fade = 0.0
                            
                        pulse_fade += FADE_SPEED if pulse_fade < target_fade else -FADE_SPEED if pulse_fade > target_fade else 0
                        pulse_fade = max(0.0, min(1.0, pulse_fade))

                        fill_level = (p / 100.0) * 30
                        full_rows = math.floor(fill_level)
                        top_fill = 32 - full_rows

                        c = None
                        if settings['pulse_enabled'] and pulse_fade > 0:
                            if mode == "charge" and charge_watts > 0:
                                if pulse_pos is None:
                                    pulse_pos = 33
                                else:
                                    pulse_pos -= (charge_watts / STEP_SCALE) * PULSE_SPEED_MODIFIER
                                if pulse_pos < top_fill:
                                    pulse_pos = 33
                                c = pulse_pos
                            elif mode == "discharge" and discharge_watts > 0:
                                if pulse_pos is None:
                                    pulse_pos = top_fill
                                else:
                                    pulse_pos += (discharge_watts / STEP_SCALE) * PULSE_SPEED_MODIFIER
                                if pulse_pos > 33:
                                    pulse_pos = top_fill
                                c = pulse_pos
                            else:
                                if pulse_pos is None:
                                    pulse_pos = 20
                                pulse_pos += 0.5
                                if pulse_pos > 30:
                                    pulse_pos = 10
                                c = pulse_pos

                        columns = create_battery_frame(p, c, pulse_fade)
                        brightness_scale = (settings['battery_brightness'] / 255.0) * dim_factor
                        for col in range(WIDTH):
                            send_column(col, columns[col], ser, brightness_scale)
                        send_flush(ser)

                elapsed = time.time() - loop_start
                if elapsed < frame_time:
                    time.sleep(frame_time - elapsed)
                    
            except Exception:
                break  # Silent error handling
    
    # Start monitoring in background thread
    monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
    monitor_thread.start()
    
    # Wait for user to press Enter
    try:
        input()
    except (EOFError, KeyboardInterrupt):
        pass
    
    # Stop monitoring
    monitoring = False

def create_progress_display(progress_percentage):
    """Create track progress display matrix - shows song progress as a vertical bar WITHOUT borders"""
    columns = []
    fill_level = (progress_percentage / 100.0) * 30  # 30 rows (2 to 32) for 0-100%
    full_rows = math.floor(fill_level)
    partial_fraction = fill_level - full_rows
    partial_row = 32 - full_rows if full_rows < 30 else None

    for col in range(WIDTH):
        column = [0] * HEIGHT
        
        # NO BORDERS - only fill inner columns 2-6
        if 2 <= col <= 6:
            for row in range(2, 33):
                if row > 32 - full_rows:
                    column[row] = MAX_BRIGHT  # Full rows
                elif row == partial_row and partial_row is not None:
                    # Center-out fade for partial row
                    if col == 4:
                        fade_factor = min(1.0, partial_fraction / 0.33)
                    elif col in (3, 5):
                        fade_factor = max(0.0, (partial_fraction - 0.33) / 0.33)
                    elif col in (2, 6):
                        fade_factor = max(0.0, (partial_fraction - 0.66) / 0.34)
                    column[row] = int(round(MAX_BRIGHT * fade_factor))
                else:
                    column[row] = 0
        
        columns.append(column)

    return columns

def create_music_display(music_info, scroll_offset=0):
    """Create music display matrix with scrolling text vertically"""
    matrix = [[0 for _ in range(TIME_WIDTH)] for _ in range(TIME_HEIGHT)]
    
    if not music_info:
        # Show music note when no music
        note_pattern = [
            [0,1,1,1,0],
            [0,1,1,1,1],
            [0,1,1,1,1],
            [0,1,1,1,1],
            [1,1,1,1,1],
            [1,1,1,1,0],
            [1,1,1,0,0],
            [1,1,0,0,0]
        ]
        
        start_col = (TIME_WIDTH - 5) // 2
        start_row = (TIME_HEIGHT - 8) // 2
        
        for row_idx, pattern_row in enumerate(note_pattern):
            for col_idx, pixel in enumerate(pattern_row):
                display_row = start_row + row_idx
                display_col = start_col + col_idx
                if 0 <= display_row < TIME_HEIGHT and 0 <= display_col < TIME_WIDTH and pixel:
                    matrix[display_row][display_col] = MAX_BRIGHT
        
        return matrix
    
    # Display format: "Artist - Track" scrolling vertically
    display_text = f"{music_info['artist']} - {music_info['track']}"
    
    # Simple 3x5 font for scrolling text (same as time display)
    font = {
        'A': [[1,1,1],[1,0,1],[1,1,1],[1,0,1],[1,0,1]],
        'B': [[1,1,0],[1,0,1],[1,1,0],[1,0,1],[1,1,0]],
        'C': [[1,1,1],[1,0,0],[1,0,0],[1,0,0],[1,1,1]],
        'D': [[1,1,0],[1,0,1],[1,0,1],[1,0,1],[1,1,0]],
        'E': [[1,1,1],[1,0,0],[1,1,0],[1,0,0],[1,1,1]],
        'F': [[1,1,1],[1,0,0],[1,1,0],[1,0,0],[1,0,0]],
        'G': [[1,1,1],[1,0,0],[1,0,1],[1,0,1],[1,1,1]],
        'H': [[1,0,1],[1,0,1],[1,1,1],[1,0,1],[1,0,1]],
        'I': [[1,1,1],[0,1,0],[0,1,0],[0,1,0],[1,1,1]],
        'J': [[1,1,1],[0,0,1],[0,0,1],[1,0,1],[1,1,1]],
        'K': [[1,0,1],[1,1,0],[1,0,0],[1,1,0],[1,0,1]],
        'L': [[1,0,0],[1,0,0],[1,0,0],[1,0,0],[1,1,1]],
        'M': [[1,0,1],[1,1,1],[1,1,1],[1,0,1],[1,0,1]],
        'N': [[1,0,1],[1,1,1],[1,1,1],[1,0,1],[1,0,1]],
        'O': [[1,1,1],[1,0,1],[1,0,1],[1,0,1],[1,1,1]],
        'P': [[1,1,1],[1,0,1],[1,1,1],[1,0,0],[1,0,0]],
        'Q': [[1,1,1],[1,0,1],[1,0,1],[1,1,1],[0,0,1]],
        'R': [[1,1,1],[1,0,1],[1,1,0],[1,0,1],[1,0,1]],
        'S': [[1,1,1],[1,0,0],[1,1,1],[0,0,1],[1,1,1]],
        'T': [[1,1,1],[0,1,0],[0,1,0],[0,1,0],[0,1,0]],
        'U': [[1,0,1],[1,0,1],[1,0,1],[1,0,1],[1,1,1]],
        'V': [[1,0,1],[1,0,1],[1,0,1],[1,0,1],[0,1,0]],
        'W': [[1,0,1],[1,0,1],[1,1,1],[1,1,1],[1,0,1]],
        'X': [[1,0,1],[0,1,0],[0,1,0],[0,1,0],[1,0,1]],
        'Y': [[1,0,1],[1,0,1],[0,1,0],[0,1,0],[0,1,0]],
        'Z': [[1,1,1],[0,0,1],[0,1,0],[1,0,0],[1,1,1]],
        '0': [[1,1,1],[1,0,1],[1,0,1],[1,0,1],[1,1,1]],
        '1': [[0,1,0],[1,1,0],[0,1,0],[0,1,0],[1,1,1]],
        '2': [[1,1,1],[0,0,1],[1,1,1],[1,0,0],[1,1,1]],
        '3': [[1,1,1],[0,0,1],[1,1,1],[0,0,1],[1,1,1]],
        '4': [[1,0,1],[1,0,1],[1,1,1],[0,0,1],[0,0,1]],
        '5': [[1,1,1],[1,0,0],[1,1,1],[0,0,1],[1,1,1]],
        '6': [[1,1,1],[1,0,0],[1,1,1],[1,0,1],[1,1,1]],
        '7': [[1,1,1],[0,0,1],[0,0,1],[0,1,0],[1,0,0]],
        '8': [[1,1,1],[1,0,1],[1,1,1],[1,0,1],[1,1,1]],
        '9': [[1,1,1],[1,0,1],[1,1,1],[0,0,1],[1,1,1]],
        ' ': [[0,0,0],[0,0,0],[0,0,0],[0,0,0],[0,0,0]],
        '-': [[0,0,0],[0,0,0],[1,1,1],[0,0,0],[0,0,0]],
        '.': [[0,0,0],[0,0,0],[0,0,0],[0,0,0],[0,1,0]],
        ',': [[0,0,0],[0,0,0],[0,0,0],[0,1,0],[1,0,0]],
        '!': [[0,1,0],[0,1,0],[0,1,0],[0,0,0],[0,1,0]],
        '?': [[1,1,1],[0,0,1],[0,1,0],[0,0,0],[0,1,0]]
    }
    
    # Render scrolling text vertically (like time display)
    start_col = 3  # Center in columns 3,4,5
    
    # Apply scroll offset vertically
    row_offset = -scroll_offset
    
    for char in display_text.upper():
        if char in font and row_offset < TIME_HEIGHT:
            pattern = font[char]
            for row_idx, pattern_row in enumerate(pattern):
                display_row = row_offset + row_idx
                if 0 <= display_row < TIME_HEIGHT:
                    for col_idx, pixel in enumerate(pattern_row):
                        display_col = start_col + col_idx
                        if pixel and display_col < TIME_WIDTH:
                            matrix[display_row][display_col] = MAX_BRIGHT
            row_offset += 6  # Move down for next character (5 rows + 1 space)
    
    return matrix

def show_battery_status():
    """Show current battery status"""
    battery_data = get_battery_info()
    if battery_data[0] is None:
        print("❌ No battery found!")
        input("Press Enter to continue...")
        return
        
    p, charge_rate, discharge_rate, time_remaining_minutes = battery_data
    
    clear_screen()
    print(f"\n🔋 Current Battery Status")
    print("="*30)
    print(f"Battery Level: {p:.1f}%")
    print(f"Charge Rate: {charge_rate:.0f}mW")
    print(f"Discharge Rate: {discharge_rate:.0f}mW")
    
    if time_remaining_minutes is not None:
        hours = time_remaining_minutes // 60
        mins = time_remaining_minutes % 60
        print(f"Time Remaining: {hours:02d}:{mins:02d}")
        print("Source: System (upower)")
    else:
        print("Time Remaining: Unknown")
        print("Source: Not available")
    
    if charge_rate > 0:
        print("Status: 🔌 Charging")
    elif discharge_rate > 0:
        print("Status: 🔋 Discharging")
    else:
        print("Status: ⚡ Idle")
    
    print("="*30)
    input("Press Enter to continue...")

def brightness_menu(display_type):
    """Brightness settings menu"""
    global last_activity_time
    display_name = "Battery (Left LED)" if display_type == "battery" else "Time (Right LED)"
    setting_key = f"{display_type}_brightness"
    startup_key = f"startup_{display_type}_brightness"
    
    while True:
        # Update activity time when in brightness menu
        last_activity_time = time.time()
        
        clear_screen()
        current_val = settings[setting_key]
        startup_val = settings.get(startup_key, 255)
        percentage = int((current_val / 255) * 100)
        startup_percentage = int((startup_val / 255) * 100)
        
        print(f"🔆 {display_name} Brightness")
        print("="*50)
        print(f"Current: {current_val} ({percentage}%)")
        print(f"Startup Default: {startup_val} ({startup_percentage}%)")
        print("="*50)
        print("CURRENT BRIGHTNESS:")
        print("1. Set to 25% (64)")
        print("2. Set to 50% (128)")
        print("3. Set to 75% (192)")
        print("4. Set to 100% (255)")
        print("5. Custom value")
        print()
        print("STARTUP DEFAULT BRIGHTNESS:")
        print("6. Set startup to 25% (64)")
        print("7. Set startup to 50% (128)")
        print("8. Set startup to 75% (192)")
        print("9. Set startup to 100% (255)")
        print("10. Custom startup value")
        print()
        print("TESTING:")
        print("11. Test current brightness")
        print("12. Flash test (confirm it's working)")
        print("13. Show current settings file")
        print("0. Back to main menu")
        print("="*50)
        
        choice = input("Select option: ").strip()
        
        # Update activity time on any input
        last_activity_time = time.time()
        
        if choice == '0':
            break
        elif choice == '1':
            print(f"Setting {display_name} current brightness to 25% (64)...")
            settings[setting_key] = 64
            apply_brightness_immediately(display_type)
            print(f"✓ {display_name} current brightness set to 25%")
            input("Press Enter to continue...")
        elif choice == '2':
            print(f"Setting {display_name} current brightness to 50% (128)...")
            settings[setting_key] = 128
            apply_brightness_immediately(display_type)
            print(f"✓ {display_name} current brightness set to 50%")
            input("Press Enter to continue...")
        elif choice == '3':
            print(f"Setting {display_name} current brightness to 75% (192)...")
            settings[setting_key] = 192
            apply_brightness_immediately(display_type)
            print(f"✓ {display_name} current brightness set to 75%")
            input("Press Enter to continue...")
        elif choice == '4':
            print(f"Setting {display_name} current brightness to 100% (255)...")
            settings[setting_key] = 255
            apply_brightness_immediately(display_type)
            print(f"✓ {display_name} current brightness set to 100%")
            input("Press Enter to continue...")
        elif choice == '5':
            try:
                val = int(input(f"Enter current brightness (0-255): "))
                last_activity_time = time.time()  # Update activity after input
                settings[setting_key] = max(0, min(255, val))
                print(f"Setting {display_name} current brightness to {settings[setting_key]}...")
                apply_brightness_immediately(display_type)
                percentage = int((settings[setting_key] / 255) * 100)
                print(f"✓ {display_name} current brightness set to {settings[setting_key]} ({percentage}%)")
                input("Press Enter to continue...")
            except ValueError:
                print("Invalid number")
                input("Press Enter to continue...")
        elif choice == '6':
            print(f"Setting {display_name} startup default to 25% (64)...")
            settings[startup_key] = 64
            save_settings()
            print(f"✓ {display_name} will start at 25% brightness on next program launch")
            input("Press Enter to continue...")
        elif choice == '7':
            print(f"Setting {display_name} startup default to 50% (128)...")
            settings[startup_key] = 128
            save_settings()
            print(f"✓ {display_name} will start at 50% brightness on next program launch")
            input("Press Enter to continue...")
        elif choice == '8':
            print(f"Setting {display_name} startup default to 75% (192)...")
            settings[startup_key] = 192
            save_settings()
            print(f"✓ {display_name} will start at 75% brightness on next program launch")
            input("Press Enter to continue...")
        elif choice == '9':
            print(f"Setting {display_name} startup default to 100% (255)...")
            settings[startup_key] = 255
            save_settings()
            print(f"✓ {display_name} will start at 100% brightness on next program launch")
            input("Press Enter to continue...")
        elif choice == '10':
            try:
                val = int(input(f"Enter startup default brightness (0-255): "))
                last_activity_time = time.time()  # Update activity after input
                settings[startup_key] = max(0, min(255, val))
                save_settings()
                percentage = int((settings[startup_key] / 255) * 100)
                print(f"✓ {display_name} will start at {settings[startup_key]} ({percentage}%) on next program launch")
                input("Press Enter to continue...")
            except ValueError:
                print("Invalid number")
                input("Press Enter to continue...")
        elif choice == '11':
            print(f"Testing {display_name} brightness...")
            if display_type == "battery":
                test_battery_brightness()
            else:
                test_time_brightness()
        elif choice == '12':
            flash_test(display_type)
        elif choice == '13':
            show_settings_file()

def flash_test(display_type):
    """Flash the display to confirm it's working"""
    display_name = "Battery (Left)" if display_type == "battery" else "Time (Right)"
    
    if display_type == "battery" and ser and settings['battery_enabled']:
        print(f"Flashing {display_name} LED...")
        for i in range(3):
            # Full brightness
            columns = create_battery_frame(100, None, 0)
            for col in range(WIDTH):
                send_column(col, columns[col], ser, 1.0)
            send_flush(ser)
            time.sleep(0.3)
            
            # Off
            clear_all_leds(ser, WIDTH, HEIGHT)
            time.sleep(0.3)
        
        # Restore current brightness
        apply_brightness_immediately(display_type)
        print(f"✓ {display_name} LED flash test complete")
        
    elif display_type == "time" and ser_time and settings['time_enabled']:
        print(f"Flashing {display_name} LED...")
        for i in range(3):
            # Full brightness
            test_matrix = create_time_display(5328)  # 88:48
            for col in range(TIME_WIDTH):
                column_data = [test_matrix[row][col] for row in range(TIME_HEIGHT)]
                send_column(col, column_data, ser_time, 1.0)
            send_flush(ser_time)
            time.sleep(0.3)
            
            # Off
            clear_all_leds(ser_time, TIME_WIDTH, TIME_HEIGHT)
            time.sleep(0.3)
        
        # Restore current brightness
        apply_brightness_immediately(display_type)
        print(f"✓ {display_name} LED flash test complete")
        
    else:
        print(f"{display_name} LED not available")
    
    input("Press Enter to continue...")

def apply_brightness_immediately(display_type):
    """Apply brightness change to display immediately"""
    try:
        # Check for auto-dim factor
        dim_factor = check_dim_timeout()
        
        if display_type == "battery" and ser and settings['battery_enabled']:
            # Get current battery info for battery display
            battery_data = get_battery_info()
            if battery_data[0] is None:
                return
            p, charge_rate, discharge_rate, time_remaining_minutes = battery_data
            
            # Update battery display with new brightness (including auto-dim)
            columns = create_battery_frame(p, None, 0)  # No pulse for immediate update
            brightness_scale = (settings['battery_brightness'] / 255.0) * dim_factor
            for col in range(WIDTH):
                send_column(col, columns[col], ser, brightness_scale)
            send_flush(ser)
            
        elif display_type == "time" and ser_time and settings['time_enabled']:
            # Get current battery info for time calculation
            battery_data = get_battery_info()
            if battery_data[0] is None:
                # If no battery data, show test pattern
                test_matrix = create_time_display(5328)  # 88:48
            else:
                p, charge_rate, discharge_rate, time_remaining_minutes = battery_data
                
                # Calculate time remaining
                minutes_remaining = time_remaining_minutes
                if minutes_remaining is None and discharge_rate > 0:
                    # Simple fallback calculation
                    estimated_capacity = 50.0
                    remaining_wh = (p / 100.0) * estimated_capacity
                    hours_remaining = remaining_wh / (discharge_rate / 1000.0)
                    minutes_remaining = max(1, min(1440, int(hours_remaining * 60)))
                
                test_matrix = create_time_display(minutes_remaining)
            
            # Update time display with new brightness (including auto-dim)
            brightness_scale = (settings['time_brightness'] / 255.0) * dim_factor
            for col in range(TIME_WIDTH):
                column_data = [test_matrix[row][col] for row in range(TIME_HEIGHT)]
                send_column(col, column_data, ser_time, brightness_scale)
            send_flush(ser_time)
            
    except Exception as e:
        print(f"Error applying brightness: {e}")

def display_settings_menu():
    """Display settings menu"""
    while True:
        clear_screen()
        print(f"🖥️  Display Settings")
        print("="*50)
        print(f"1. Battery Display: {'ON' if settings['battery_enabled'] else 'OFF'}")
        print(f"2. Time Display: {'ON' if settings['time_enabled'] else 'OFF'}")
        print(f"3. Pulse Animation: {'ON' if settings['pulse_enabled'] else 'OFF'}")
        
        # Show auto-dim status more clearly
        if settings['dim_timeout'] == 0:
            dim_status = "DISABLED"
        else:
            dim_status = f"ON ({settings['dim_timeout']}s → {settings['auto_dim_level']}%)"
        print(f"4. Auto-Dim: {dim_status}")
        
        print("5. Disable Auto-Dim Completely")
        print("6. Fix Time Display (if showing square)")
        print("0. Back to main menu")
        print("="*50)
        
        choice = input("Select option: ").strip()
        
        if choice == '0':
            break
        elif choice == '1':
            settings['battery_enabled'] = not settings['battery_enabled']
            save_settings()
            print(f"✓ Battery display {'enabled' if settings['battery_enabled'] else 'disabled'}")
            time.sleep(1)
        elif choice == '2':
            settings['time_enabled'] = not settings['time_enabled']
            save_settings()
            print(f"✓ Time display {'enabled' if settings['time_enabled'] else 'disabled'}")
            time.sleep(1)
        elif choice == '3':
            settings['pulse_enabled'] = not settings['pulse_enabled']
            save_settings()
            print(f"✓ Pulse animation {'enabled' if settings['pulse_enabled'] else 'disabled'}")
            time.sleep(1)
        elif choice == '4':
            auto_dim_submenu()
        elif choice == '5':
            settings['dim_timeout'] = 0
            save_settings()
            print("✓ Auto-dim completely disabled")
            time.sleep(1)
        elif choice == '6':
            fix_time_display()

def music_settings_menu():
    """Music settings menu"""
    while True:
        clear_screen()
        print("🎵 Music Settings")
        print("="*50)
        print("1. Scroll Speed: ", settings['music_scroll_speed'])
        print("2. Test Spotify Connection")
        print("3. Music Display Mode (Test)")
        print("0. Back to main menu")
        print("="*50)
        print("Music mode is automatic - when Spotify plays:")
        print("• Left LED = Track progress bar")
        print("• Right LED = Artist/song scrolling")
        
        choice = input("Select option: ").strip()
        
        if choice == '0':
            break
        elif choice == '1':
            try:
                val = int(input("Enter scroll speed (1-5): "))
                settings['music_scroll_speed'] = max(1, min(5, val))
                save_settings()
                print(f"✓ Scroll speed set to {settings['music_scroll_speed']}")
                time.sleep(1)
            except ValueError:
                print("Invalid number")
                time.sleep(1)
        elif choice == '2':
            test_spotify_connection()
        elif choice == '3':
            music_display_mode()

def test_spotify_connection():
    """Test Spotify connection"""
    print("Testing Spotify connection...")
    music_info = get_spotify_info()
    
    if music_info is None:
        print("❌ Spotify not detected. Make sure:")
        print("  - Spotify desktop app is running")
        print("  - You have dbus-send installed")
        print("  - Spotify is not in private/incognito mode")
        print("  - A song is currently playing (not paused)")
    else:
        print("✅ Spotify detected and playing!")
        print(f"Artist: {music_info['artist']}")
        print(f"Track: {music_info['track']}")
        print(f"Progress: {music_info['progress']}%")
    
    input("Press Enter to continue...")

def music_display_mode():
    """Test music display on right LED"""
    if not ser_time:
        print("❌ Right LED not available")
        input("Press Enter to continue...")
        return
    
    print("Music display mode - Right LED will show current Spotify track")
    print("Press Enter to stop...")
    
    import threading
    import time
    
    running = True
    scroll_offset = 0
    
    def display_loop():
        nonlocal running, scroll_offset
        while running:
            music_info = get_spotify_info()
            music_matrix = create_music_display(music_info, scroll_offset)
            
            brightness_scale = settings['time_brightness'] / 255.0
            for col in range(TIME_WIDTH):
                column_data = [music_matrix[row][col] for row in range(TIME_HEIGHT)]
                send_column(col, column_data, ser_time, brightness_scale)
            send_flush(ser_time)
            
            # Update scroll
            if music_info and music_info.get('artist', '') != '':
                scroll_offset += settings['music_scroll_speed']
                if scroll_offset > len(f"{music_info['artist']} - {music_info['track']}") * 6:
                    scroll_offset = -TIME_HEIGHT
            
            time.sleep(0.2)  # 5 FPS for smooth scrolling
    
    # Start display thread
    display_thread = threading.Thread(target=display_loop, daemon=True)
    display_thread.start()
    
    # Wait for user input
    try:
        input()
    except (EOFError, KeyboardInterrupt):
        pass
    
    running = False
    
    # Clear display
    clear_all_leds(ser_time, TIME_WIDTH, TIME_HEIGHT)
    print("Music display stopped")

def fix_time_display():
    """Fix corrupted time display"""
    print("Fixing time display...")
    
    if not ser_time:
        print("❌ Time display not connected")
        input("Press Enter to continue...")
        return
    
    try:
        # Step 1: Clear the display completely
        print("1. Clearing display...")
        clear_all_leds(ser_time, TIME_WIDTH, TIME_HEIGHT)
        time.sleep(1)
        
        # Step 2: Test with simple pattern
        print("2. Testing with simple pattern...")
        for col in range(3, 6):  # Center columns
            column_data = [0] * TIME_HEIGHT
            column_data[TIME_HEIGHT//2] = MAX_BRIGHT  # Single dot in middle
            send_column(col, column_data, ser_time, 1.0)
        send_flush(ser_time)
        time.sleep(1)
        
        # Step 3: Clear again
        print("3. Clearing again...")
        clear_all_leds(ser_time, TIME_WIDTH, TIME_HEIGHT)
        time.sleep(1)
        
        # Step 4: Show test time
        print("4. Showing test time...")
        test_matrix = create_time_display(5328)  # 88:48
        brightness_scale = settings['time_brightness'] / 255.0
        for col in range(TIME_WIDTH):
            column_data = [test_matrix[row][col] for row in range(TIME_HEIGHT)]
            send_column(col, column_data, ser_time, brightness_scale)
        send_flush(ser_time)
        
        print("✓ Time display reset complete")
        print("The right LED should now show '88:48'")
        
    except Exception as e:
        print(f"❌ Error fixing display: {e}")
    
    input("Press Enter to continue...")

def auto_dim_submenu():
    """Auto-dim configuration submenu"""
    while True:
        clear_screen()
        print("⏰ Auto-Dim Settings")
        print("="*50)
        if settings['dim_timeout'] == 0:
            print("Auto-dim is currently DISABLED")
        else:
            print(f"Current: Dim to {settings['auto_dim_level']}% after {settings['dim_timeout']} seconds")
        
        # Show start dimmed status
        start_dimmed_status = "ON" if settings.get('start_dimmed', False) else "OFF"
        print(f"Start dimmed: {start_dimmed_status}")
        print()
        print("1. Set timeout to 30 seconds")
        print("2. Set timeout to 60 seconds") 
        print("3. Set timeout to 300 seconds (5 minutes)")
        print("4. Set custom timeout")
        print("5. Set dim level (1-100%)")
        print("6. Disable auto-dim")
        print("7. Toggle 'Start Dimmed' (begin program already dimmed)")
        print("8. Start dimmed immediately (one-time)")
        print("0. Back to display settings")
        print("="*50)
        
        choice = input("Select option: ").strip()
        
        if choice == '0':
            break
        elif choice == '1':
            settings['dim_timeout'] = 30
            save_settings()
            print("✓ Auto-dim set to 30 seconds")
            time.sleep(1)
        elif choice == '2':
            settings['dim_timeout'] = 60
            save_settings()
            print("✓ Auto-dim set to 60 seconds")
            time.sleep(1)
        elif choice == '3':
            settings['dim_timeout'] = 300
            save_settings()
            print("✓ Auto-dim set to 5 minutes")
            time.sleep(1)
        elif choice == '4':
            try:
                val = int(input("Enter timeout in seconds (0=disabled): "))
                settings['dim_timeout'] = max(0, val)
                save_settings()
                print(f"✓ Auto-dim timeout set to {settings['dim_timeout']}s")
                time.sleep(1)
            except ValueError:
                print("Invalid number")
                time.sleep(1)
        elif choice == '5':
            try:
                val = int(input("Enter dim level (1-100%): "))
                settings['auto_dim_level'] = max(1, min(100, val))
                save_settings()
                print(f"✓ Auto-dim level set to {settings['auto_dim_level']}%")
                time.sleep(1)
            except ValueError:
                print("Invalid number")
                time.sleep(1)
        elif choice == '6':
            settings['dim_timeout'] = 0
            save_settings()
            print("✓ Auto-dim disabled")
            time.sleep(1)
        elif choice == '7':
            settings['start_dimmed'] = not settings.get('start_dimmed', False)
            save_settings()
            status = "enabled" if settings['start_dimmed'] else "disabled"
            print(f"✓ Start dimmed {status}")
            print(f"  Program will {'start' if settings['start_dimmed'] else 'not start'} already dimmed")
            time.sleep(2)
        elif choice == '8':
            force_dim_now()
            print("✓ Displays dimmed immediately")
            input("Press Enter to continue...")

def test_battery_brightness():
    """Test battery display brightness"""
    if ser and settings['battery_enabled']:
        print("Testing battery display...")
        columns = create_battery_frame(75, None, 0)  # 75% battery
        brightness_scale = settings['battery_brightness'] / 255.0
        for col in range(WIDTH):
            send_column(col, columns[col], ser, brightness_scale)
        send_flush(ser)
        print(f"Battery display showing at {int((settings['battery_brightness']/255)*100)}% brightness")
        input("Press Enter to continue...")
        # Keep the current display instead of clearing
    else:
        print("Battery display not available")

def test_time_brightness():
    """Test time display brightness"""
    if ser_time and settings['time_enabled']:
        print("Testing time display...")
        test_matrix = create_time_display(5328)  # 88:48
        brightness_scale = settings['time_brightness'] / 255.0
        for col in range(TIME_WIDTH):
            column_data = [test_matrix[row][col] for row in range(TIME_HEIGHT)]
            send_column(col, column_data, ser_time, brightness_scale)
        send_flush(ser_time)
        print(f"Time display showing at {int((settings['time_brightness']/255)*100)}% brightness")
        input("Press Enter to continue...")
        # Keep the current display instead of clearing
    else:
        print("Time display not available")

def show_about():
    """Show about information"""
    clear_screen()
    print(f"📋 About")
    print("="*50)
    print("🔋 LED Battery Monitor v2.0")
    print("Dual LED battery percentage and time remaining display")
    print("With Spotify integration")
    print()
    print(f"Battery port: {ser.port if ser else 'Not connected'}")
    print(f"Time port: {ser_time.port if ser_time else 'Not connected'}")
    print()
    print("Features:")
    print("• Battery level display with pulse animation")
    print("• Time remaining from system power management")
    print("• Spotify track display with scrolling text")
    print("• Brightness controls and auto-dim")
    print("• Menu-driven interface")
    input("Press Enter to continue...")

def show_settings_file():
    """Show the current settings file contents for debugging"""
    clear_screen()
    print("📋 Current Settings File")
    print("="*50)
    print(f"File location: {SETTINGS_FILE}")
    print()
    
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r') as f:
                content = f.read()
            print("File contents:")
            print(content)
        else:
            print("❌ Settings file does not exist!")
    except Exception as e:
        print(f"❌ Error reading settings file: {e}")
    
    print()
    print("Current in-memory settings:")
    for key, value in settings.items():
        print(f"  {key}: {value}")
    
    input("\nPress Enter to continue...")

def force_dim_now():
    """Immediately dim both displays to the auto-dim level"""
    global last_activity_time
    
    if settings['dim_timeout'] == 0:
        print("Auto-dim is disabled - cannot force dim")
        return
    
    # Set activity time far in the past to trigger dimming
    last_activity_time = time.time() - (settings['dim_timeout'] + 10)
    
    # Apply dimming to both displays immediately
    try:
        if ser and settings['battery_enabled']:
            apply_brightness_immediately("battery")
        if ser_time and settings['time_enabled']:
            apply_brightness_immediately("time")
    except Exception as e:
        print(f"Error forcing dim: {e}")

def check_dim_timeout():
    """Check if displays should be dimmed due to inactivity"""
    if settings['dim_timeout'] > 0:
        time_since_activity = time.time() - last_activity_time
        if time_since_activity > settings['dim_timeout']:
            # Debug info
            current_dim_level = settings['auto_dim_level']
            if current_dim_level < 20:
                print(f"🌙 Auto-dim active: dimmed to {current_dim_level}% (very dim - may appear off)")
            return settings['auto_dim_level'] / 100.0
    return 1.0

def compute_multiplier(r, c, sigma, min_m):
    if c is None:
        return 1.0
    dist = (r - c) / sigma
    return 1 - (1 - min_m) * math.exp(-dist**2)

def create_battery_frame(p, c, pulse_fade):
    columns = []
    fill_level = (p / 100.0) * 30  # 30 rows (2 to 32) for 0-100%
    full_rows = math.floor(fill_level)
    partial_fraction = fill_level - full_rows
    partial_row = 32 - full_rows if full_rows < 30 else None

    for col in range(WIDTH):
        column = [0] * HEIGHT
        # Borders
        if 3 <= col <= 5:
            column[0] = MAX_BRIGHT  # Top cap
        if col in (0, 1, 2, 6, 7, 8):
            column[1] = MAX_BRIGHT  # Top border
        for row in range(2, 33):
            if col in (0, 8):
                column[row] = MAX_BRIGHT  # Side borders
            elif 2 <= col <= 6:
                if row > 32 - full_rows:
                    column[row] = MAX_BRIGHT  # Full rows
                elif row == partial_row and partial_row is not None:
                    # Center-out fade for partial row
                    if col == 4:
                        fade_factor = min(1.0, partial_fraction / 0.33)  # 0 to 0.33
                    elif col in (3, 5):
                        fade_factor = max(0.0, (partial_fraction - 0.33) / 0.33)  # 0.33 to 0.66
                    elif col in (2, 6):
                        fade_factor = max(0.0, (partial_fraction - 0.66) / 0.34)  # 0.66 to 1.0
                    column[row] = int(round(MAX_BRIGHT * fade_factor))
                else:
                    column[row] = 0
        column[33] = MAX_BRIGHT  # Bottom border
        columns.append(column)

    # Apply pulse effect with proper clamping
    if c is not None:
        for col in range(2, 7):
            for row in range(2, 33):
                if columns[col][row] > 0:  # Only apply to lit pixels
                    m = compute_multiplier(row, c, SIGMA, MIN_M)
                    new_value = int(round(columns[col][row] * m))
                    columns[col][row] = max(0, min(255, new_value))  # Clamp to valid range

    return columns

    # Apply pulse effect with proper clamping
    if c is not None:
        for col in range(2, 7):
            for row in range(2, 33):
                if columns[col][row] > 0:  # Only apply to lit pixels
                    m = compute_multiplier(row, c, SIGMA, MIN_M)
                    new_value = int(round(columns[col][row] * m))
                    columns[col][row] = max(0, min(255, new_value))  # Clamp to valid range

    return columns

def create_time_display(minutes_remaining):
    """Create time display matrix - shows time vertically with smaller digits"""
    matrix = [[0 for _ in range(TIME_WIDTH)] for _ in range(TIME_HEIGHT)]
    
    if minutes_remaining is None:
        # Show dashes when not discharging
        for row in range(15, 18):
            for col in range(3, 6):
                matrix[row][col] = MAX_BRIGHT
        return matrix
    
    # Format time as HH:MM
    hours = min(99, minutes_remaining // 60)
    mins = minutes_remaining % 60
    time_str = f"{hours:02d}:{mins:02d}"
    
    # Smaller 3x5 digit patterns to fit in 9-column display
    digits = {
        '0': [
            [1,1,1],
            [1,0,1],
            [1,0,1],
            [1,0,1],
            [1,1,1]
        ],
        '1': [
            [0,1,0],
            [1,1,0],
            [0,1,0],
            [0,1,0],
            [1,1,1]
        ],
        '2': [
            [1,1,1],
            [0,0,1],
            [1,1,1],
            [1,0,0],
            [1,1,1]
        ],
        '3': [
            [1,1,1],
            [0,0,1],
            [1,1,1],
            [0,0,1],
            [1,1,1]
        ],
        '4': [
            [1,0,1],
            [1,0,1],
            [1,1,1],
            [0,0,1],
            [0,0,1]
        ],
        '5': [
            [1,1,1],
            [1,0,0],
            [1,1,1],
            [0,0,1],
            [1,1,1]
        ],
        '6': [
            [1,1,1],
            [1,0,0],
            [1,1,1],
            [1,0,1],
            [1,1,1]
        ],
        '7': [
            [1,1,1],
            [0,0,1],
            [0,0,1],
            [0,1,0],
            [1,0,0]
        ],
        '8': [
            [1,1,1],
            [1,0,1],
            [1,1,1],
            [1,0,1],
            [1,1,1]
        ],
        '9': [
            [1,1,1],
            [1,0,1],
            [1,1,1],
            [0,0,1],
            [1,1,1]
        ],
        ':': [
            [0,0,0],
            [0,1,0],
            [0,0,0],
            [0,1,0],
            [0,0,0]
        ]
    }
    
    # Calculate starting position to center all digits
    total_height = len(time_str) * 6 - 1  # 5 rows per digit + 1 space, minus last space
    start_row = (TIME_HEIGHT - total_height) // 2
    
    # Draw time vertically down the display
    row_offset = start_row
    for char in time_str:
        if char in digits and row_offset + 5 < TIME_HEIGHT:
            pattern = digits[char]
            for row_idx, pattern_row in enumerate(pattern):
                display_row = row_offset + row_idx
                for col_idx, pixel in enumerate(pattern_row):
                    display_col = 3 + col_idx  # Center in columns 3,4,5
                    if pixel and display_col < TIME_WIDTH and display_row >= 0:
                        matrix[display_row][display_col] = MAX_BRIGHT
            row_offset += 6  # Move down for next character (5 rows + 1 space)
    
    return matrix

# Load settings on startup
load_settings()

# Set startup brightness from saved settings
settings['battery_brightness'] = settings.get('startup_battery_brightness', 255)
settings['time_brightness'] = settings.get('startup_time_brightness', 255)

print(f"🔆 Startup brightness: Battery={settings['battery_brightness']}, Time={settings['time_brightness']}")

# Initialize last_activity_time based on start_dimmed setting
if settings.get('start_dimmed', False) and settings['dim_timeout'] > 0:
    # Start already dimmed by setting activity time in the past
    last_activity_time = time.time() - (settings['dim_timeout'] + 10)
    print(f"🌙 Auto-dim active: will dim to {settings['auto_dim_level']}% after inactivity")
else:
    # Start at full brightness
    last_activity_time = time.time()

# Main program
if __name__ == "__main__":
    try:
        # Show main menu - this is the only interface
        show_main_menu()
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        # Clean shutdown
        try:
            if ser:
                clear_all_leds(ser, WIDTH, HEIGHT)
                ser.close()
        except:
            pass
        try:
            if ser_time:
                clear_all_leds(ser_time, TIME_WIDTH, TIME_HEIGHT)
                ser_time.close()
        except:
            pass
