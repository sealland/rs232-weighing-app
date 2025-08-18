# agent.py
from flask import Flask, jsonify
from flask_cors import CORS # Uncomment if you need CORS
import serial
import time
import random  # For simulated data if needed
import configparser
import os
import re  # For parsing

# --- Default Serial Configuration (if config file is missing or incomplete) ---
DEFAULT_AGENT_SERIAL_PORT = "COM1"  # Changed to COM1 as per recent logs
DEFAULT_AGENT_BAUD_RATE = 1200  # Changed to 1200 as per recent logs
DEFAULT_AGENT_PARITY_KEY = "N"
DEFAULT_AGENT_STOP_BITS_KEY = "1"
DEFAULT_AGENT_BYTE_SIZE_KEY = "8"
DEFAULT_AGENT_READ_TIMEOUT = 0.05  # Short timeout for non-blocking reads

CONFIG_FILE_NAME = "scale_config.ini"  # Should match the file saved by rs232_config_tester.py

# --- Helper Dictionaries for mapping config values to serial constants ---
parity_map_agent = {
    "N": serial.PARITY_NONE, "E": serial.PARITY_EVEN, "O": serial.PARITY_ODD,
    "M": serial.PARITY_MARK, "S": serial.PARITY_SPACE
}
stop_bits_map_agent = {
    "1": serial.STOPBITS_ONE, "1.5": serial.STOPBITS_ONE_POINT_FIVE,
    "2": serial.STOPBITS_TWO
}
byte_size_map_agent = {
    "8": serial.EIGHTBITS, "7": serial.SEVENBITS, "6": serial.SIXBITS,
    "5": serial.FIVEBITS
}

# --- Global variables for agent ---
current_serial_config = {}  # Will be loaded
serial_connection = None  # Global serial connection object
agent_read_buffer = b''  # Buffer for incoming serial data
AGENT_STX = b'\x02'  # Start of Text byte
AGENT_ETX = b'\x03'  # End of Text byte
last_known_weight = "N/A"  # Store the last successfully parsed weight


# --- Function to load configuration ---
def load_agent_config():
    global current_serial_config  # Modify global variable
    config = configparser.ConfigParser()

    # Initialize with defaults
    loaded_settings = {
        'port': DEFAULT_AGENT_SERIAL_PORT,
        'baudrate': DEFAULT_AGENT_BAUD_RATE,
        'parity_key': DEFAULT_AGENT_PARITY_KEY,  # Store key for re-saving if needed
        'stopbits_key': DEFAULT_AGENT_STOP_BITS_KEY,
        'bytesize_key': DEFAULT_AGENT_BYTE_SIZE_KEY,
        'timeout': DEFAULT_AGENT_READ_TIMEOUT
    }

    if os.path.exists(CONFIG_FILE_NAME):
        try:
            config.read(CONFIG_FILE_NAME)
            if 'SerialConfig' in config:
                cfg_section = config['SerialConfig']
                loaded_settings['port'] = cfg_section.get('Port', DEFAULT_AGENT_SERIAL_PORT)
                loaded_settings['baudrate'] = cfg_section.getint('BaudRate', DEFAULT_AGENT_BAUD_RATE)
                loaded_settings['parity_key'] = cfg_section.get('Parity', DEFAULT_AGENT_PARITY_KEY).upper()
                loaded_settings['stopbits_key'] = cfg_section.get('StopBits', DEFAULT_AGENT_STOP_BITS_KEY)
                loaded_settings['bytesize_key'] = cfg_section.get('ByteSize', DEFAULT_AGENT_BYTE_SIZE_KEY)
                loaded_settings['timeout'] = cfg_section.getfloat('ReadTimeout', DEFAULT_AGENT_READ_TIMEOUT)
                print(f"Agent: Loaded configuration from {CONFIG_FILE_NAME}")
            else:
                print(f"Agent: 'SerialConfig' section not found in {CONFIG_FILE_NAME}. Using default settings.")
        except Exception as e:
            print(f"Agent: Error loading config file {CONFIG_FILE_NAME}: {e}. Using default settings.")
    else:
        print(f"Agent: Config file {CONFIG_FILE_NAME} not found. Using default settings.")

    # Convert keys to pyserial constants for current_serial_config
    current_serial_config = {
        'port': loaded_settings['port'],
        'baudrate': loaded_settings['baudrate'],
        'parity': parity_map_agent.get(loaded_settings['parity_key'], serial.PARITY_NONE),
        'stopbits': stop_bits_map_agent.get(loaded_settings['stopbits_key'], serial.STOPBITS_ONE),
        'bytesize': byte_size_map_agent.get(loaded_settings['bytesize_key'], serial.EIGHTBITS),
        'timeout': loaded_settings['timeout']
    }
    print(f"Agent: Effective serial settings: {current_serial_config}")


# --- Parser function for the agent ---
def agent_parse_scale_data(cleaned_text):
    # print(f"AGENT_PARSER_INPUT: '{cleaned_text}'") 

    known_weight_indicators_config = [
        ("1CH", r"1CH\s+(0{3,})", True),
        (" H ", r"\sH\s+(0{3,})", True),  # Assuming " H 00000" also means zero
        ("1Rh", r"1Rh\s+(0{3,})", True),  # Assuming "1Rh 00000" also means zero
        ("1BH", r"1BH\s+(\d+)", False),
        ("1@H", r"1@H\s+(\d+)", False),
        # Add more specific non-zero indicators before more general ones if needed
    ]

    extracted_weight_values = []
    for indicator_text, pattern_regex, is_zero_indicator in known_weight_indicators_config:
        matches = re.findall(pattern_regex, cleaned_text)
        if matches:
            for num_str_from_match in matches:
                if is_zero_indicator:
                    extracted_weight_values.append("0")
                else:
                    try:
                        weight_val = str(int(num_str_from_match))
                        extracted_weight_values.append(weight_val)
                    except ValueError:
                        pass

    if extracted_weight_values:
        non_zero_values = [val for val in extracted_weight_values if val != "0"]
        if non_zero_values:
            final_value_to_return = non_zero_values[-1]
        elif "0" in extracted_weight_values:  # Check if "0" was explicitly found
            final_value_to_return = "0"
        else:  # Should not happen if extracted_weight_values is not empty and only contains non-numeric strings that failed int()
            final_value_to_return = "N/A"

            # print(f"AGENT_PARSER_RETURN: '{final_value_to_return}'")
        return final_value_to_return

    # print("AGENT_PARSER_RETURN: 'N/A'")
    return "N/A"


# --- Function to manage serial connection ---
def get_serial_connection():
    global serial_connection
    if serial_connection and serial_connection.is_open:
        # print("Agent: Using existing open serial connection.")
        return serial_connection
    try:
        if serial_connection and not serial_connection.is_open:  # If object exists but port is closed
            print(f"Agent: Serial port {current_serial_config['port']} was closed. Re-opening...")
        else:
            print(f"Agent: Attempting to open serial port {current_serial_config['port']}")

        serial_connection = serial.Serial(
            port=current_serial_config['port'],
            baudrate=current_serial_config['baudrate'],
            parity=current_serial_config['parity'],
            stopbits=current_serial_config['stopbits'],
            bytesize=current_serial_config['bytesize'],
            timeout=current_serial_config['timeout']
        )
        if serial_connection.is_open:
            print(f"Agent: Serial port {current_serial_config['port']} opened successfully.")
            return serial_connection
    except serial.SerialException as e:
        print(f"Agent: Error opening/re-opening serial port {current_serial_config['port']}: {e}")
        if serial_connection:  # Ensure it's closed if opening failed partially
            try:
                serial_connection.close()
            except:
                pass
        serial_connection = None
    return None


# --- Function to read and parse weight from RS232 for the agent ---
# This function will be called by the Flask endpoint.
# For a continuously running agent, this logic would be in a separate thread.
def read_weight_from_rs232_agent():
    global agent_read_buffer, last_known_weight

    ser = get_serial_connection()
    if not ser:
        return "Error: Port Conn"  # More specific error for port connection

    current_parsed_value = "N/A"  # Default for this read attempt

    try:
        bytes_to_read = ser.in_waiting or 1
        if bytes_to_read > 0:
            new_bytes = ser.read(bytes_to_read)
            if new_bytes:
                # print(f"Agent Read Bytes: {new_bytes!r}")
                agent_read_buffer += new_bytes

        # Process buffer for complete messages
        processed_a_message_this_call = False
        while True:  # Loop to extract all complete messages from buffer
            stx_index = agent_read_buffer.find(AGENT_STX)
            if stx_index != -1:
                etx_index = agent_read_buffer.find(AGENT_ETX, stx_index + 1)
                if etx_index != -1:
                    complete_message_bytes = agent_read_buffer[stx_index + 1: etx_index]

                    cleaned_text = ""
                    try:
                        decoded_message = complete_message_bytes.decode('latin-1',
                                                                        errors='replace')  # Or your chosen encoding
                        cleaned_text = decoded_message.strip()
                    except Exception as e_decode:
                        print(f"Agent: Decode error: {e_decode} | MsgBytes: {complete_message_bytes!r}")
                        # Optionally, set current_parsed_value to an error state here
                        agent_read_buffer = agent_read_buffer[etx_index + 1:]  # Consume problematic part
                        continue  # Try next message in buffer

                    parsed_value_from_msg = agent_parse_scale_data(cleaned_text)
                    # print(f"Agent: Parsed from msg: {parsed_value_from_msg}")

                    # Update last_known_weight only if parsing was successful (not N/A or Error)
                    if parsed_value_from_msg not in ["N/A", None] and "Error" not in parsed_value_from_msg:
                        last_known_weight = parsed_value_from_msg
                        processed_a_message_this_call = True

                    agent_read_buffer = agent_read_buffer[etx_index + 1:]
                    # If we want to return the first valid parsed value per call:
                    # if processed_a_message_this_call:
                    #    return last_known_weight 
                else:  # Found STX, no ETX yet
                    if len(agent_read_buffer) > 2048:  # Buffer overflow protection
                        print(
                            f"Agent: Buffer too long while waiting for ETX, clearing from STX: {agent_read_buffer[stx_index:stx_index + 20]}...")
                        agent_read_buffer = agent_read_buffer[stx_index:]
                    break  # Wait for more data
            else:  # No STX in buffer
                if len(agent_read_buffer) > 256:  # Clear old garbage data if no STX
                    print(
                        f"Agent: No STX in buffer, clearing old data from agent_read_buffer: {agent_read_buffer[:20]}...")
                    agent_read_buffer = b''
                break  # No STX, nothing to process from buffer for now

        # If multiple messages were processed, last_known_weight holds the last valid one.
        # If no new valid message was processed in THIS call, return the stored last_known_weight.
        if processed_a_message_this_call:
            return last_known_weight
        else:
            # If no new message was fully processed in this call,
            # but there might be partial data in buffer, or just timeout.
            # We return the globally stored last_known_weight.
            # This ensures the API always returns something, ideally the last good value.
            # If last_known_weight is still initial "N/A", then "N/A" is returned.
            return last_known_weight

    except serial.SerialException as e:
        print(f"Agent: SerialException during read: {e}")
        global serial_connection
        if serial_connection:
            try:
                serial_connection.close()
            except:
                pass
        serial_connection = None
        last_known_weight = "Error: Serial"  # Update global state on error
        return last_known_weight
    except Exception as e_read:
        print(f"Agent: Unexpected error during read: {e_read}")
        last_known_weight = "Error: Read"  # Update global state on error
        return last_known_weight


# --- Flask App ---
app = Flask(__name__)
CORS(app)

@app.route('/get_weight', methods=['GET'])
def get_weight_endpoint():
    weight_data_str = read_weight_from_rs232_agent()
    return jsonify({"weight": weight_data_str})


# --- Main execution ---
if __name__ == '__main__':
    load_agent_config()  # Load config at startup
    print("RS232 Agent (agent.py) is running...")
    print(f"Using serial configuration: {current_serial_config}")

    # For development, Flask's built-in server is fine.
    # For production, use a proper WSGI server like Gunicorn or Waitress.
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
    # threaded=True for Flask dev server can help with responsiveness if read_weight... is slow,
    # but a continuously running background thread for serial reading is a more robust solution for production.