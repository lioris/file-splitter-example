# binary_splitter_core.py (Corrected detect_frame_size function)
import os
import argparse
import json

def load_config_defaults(config_file_path="config.json"):
    """Loads default values from a JSON configuration file."""
    defaults = {
        "default_frame_size_bytes": 1111,
        "default_bulk_size_gb": 2.0,
        "default_sync_word_hex": "4711" # Default sync word
    }
    try:
        with open(config_file_path, 'r') as f:
            config = json.load(f)
            defaults.update(config)
    except FileNotFoundError:
        print(f"Warning: Configuration file '{config_file_path}' not found. Using hardcoded defaults.")
    except json.JSONDecodeError:
        print(f"Warning: Error decoding JSON in '{config_file_path}'. Using hardcoded defaults.")
    return defaults


def detect_frame_size(input_file_path, sync_word_hex, search_chunk_size=4096, max_frame_size_guess=65536):
    """
    Attempts to auto-detect frame size from a binary file by searching for a sync word.

    Args:
        input_file_path (str): Path to the input binary file.
        sync_word_hex (str): Sync word in hexadecimal format (e.g., "4711").
        search_chunk_size (int, optional): Chunk size to read from the file for searching. Defaults to 4096 bytes.
        max_frame_size_guess (int, optional): Maximum reasonable frame size to guess. Defaults to 65536 bytes.

    Returns:
        int: Detected frame size in bytes, or None if detection fails.
    """
    try:
        sync_word_bytes = bytes.fromhex(sync_word_hex)
    except ValueError:
        raise ValueError("Invalid sync word hex format.")

    if not sync_word_bytes:
        raise ValueError("Sync word cannot be empty.")

    try:
        with open(input_file_path, 'rb') as infile:
            chunk = infile.read(search_chunk_size)
            first_sync_index = chunk.find(sync_word_bytes)

            if first_sync_index == -1:
                return None  # Sync word not found in the initial chunk

            # Seek to just after the first sync word and read another chunk to find the next sync word
            infile.seek(first_sync_index + len(sync_word_bytes))
            search_chunk_next = infile.read(max_frame_size_guess) # Limit search to max frame size
            second_sync_index = search_chunk_next.find(sync_word_bytes)

            if second_sync_index == -1:
                return None # Second sync word not found within max frame size

            # Corrected frame size calculation: Distance to the start of the second sync word from the *beginning* of the frame.
            detected_frame_size = second_sync_index + len(sync_word_bytes) # Corrected calculation

            if detected_frame_size <= len(sync_word_bytes): # Frame size too small or invalid
                return None

            return detected_frame_size

    except FileNotFoundError:
        raise FileNotFoundError(f"Input file not found: {input_file_path}")
    except IOError as e:
        raise IOError(f"IOError during frame size detection: {e}")



def split_binary_file(input_file_path, bulk_size_gb, frame_size_bytes, output_prefix="output_bulk", progress_callback=None, stop_flag=None):
    """
    Splits a binary file into bulks of specified size, respecting frame boundaries,
    and writes the output bulks to the same directory as the input file.

    Args:
        input_file_path (str): Path to the input binary file.
        bulk_size_gb (float): Desired bulk size in gigabytes (GB).
        frame_size_bytes (int): Size of each data frame in bytes.
        output_prefix (str, optional): Prefix for the output bulk files. Defaults to "output_bulk".
        progress_callback (callable, optional): Callback function to report progress (percentage).
        stop_flag (callable, optional): Function that returns True if the operation should stop.
    """

    bulk_size_bytes = bulk_size_gb * 1024 * 1024 * 1024
    bulk_count = 1
    current_bulk_size = 0
    output_directory = os.path.dirname(input_file_path) if input_file_path else "."
    output_prefix_to_use = output_prefix

    if output_prefix == "output_bulk":
        output_prefix_to_use = os.path.splitext(os.path.basename(input_file_path))[0]

    try:
        total_size = os.path.getsize(input_file_path)
        bytes_processed = 0

        with open(input_file_path, 'rb') as infile:
            output_file = None

            while True:
                if stop_flag and stop_flag():
                    print("Split operation stopped.")
                    if output_file:
                        output_file.close()
                    return

                frame_data = infile.read(frame_size_bytes)
                if not frame_data:
                    break

                if output_file is None or current_bulk_size + len(frame_data) > bulk_size_bytes:
                    if output_file:
                        output_file.close()
                    output_filename = os.path.join(output_directory, f"{output_prefix_to_use}_{bulk_count:03d}.bin")
                    output_file = open(output_filename, 'wb')
                    print(f"Creating bulk file: {output_filename}")
                    current_bulk_size = 0
                    bulk_count += 1

                output_file.write(frame_data)
                current_bulk_size += len(frame_data)
                bytes_processed += len(frame_data)

                if progress_callback and total_size > 0:
                    progress_percentage = int((bytes_processed / total_size) * 100)
                    progress_callback(progress_percentage)

            if output_file:
                output_file.close()

        print("Binary file splitting complete.")

    except FileNotFoundError:
        raise FileNotFoundError(f"Input file not found: {input_file_path}")
    except IOError as e:
        raise IOError(f"IOError during splitting: {e}")


def reconstruct_binary_file(output_prefix, output_directory, output_file_name="reconstructed_file.bin"): # Keep for potential future CLI usage or other scripts
    """
    Reconstructs the original binary file from the bulk files, expecting bulks in the
    specified output directory.

    Args:
        output_prefix (str): Prefix used for the output bulk files (e.g., "output_bulk").
        output_directory (str): Directory where the bulk files are located.
        output_file_name (str, optional): Name of the reconstructed output file. Defaults to "reconstructed_file.bin".
    """
    bulk_count = 1
    reconstructed_data = bytearray()

    try:
        while True:
            bulk_filename = os.path.join(output_directory, f"{output_prefix}_{bulk_count:03d}.bin")
            if not os.path.exists(bulk_filename):
                break

            with open(bulk_filename, 'rb') as bulk_file:
                bulk_data = bulk_file.read()
                reconstructed_data.extend(bulk_data)
                print(f"Reading bulk file: {bulk_filename}")
            bulk_count += 1

        if reconstructed_data:
            reconstructed_path = os.path.join(output_directory, output_file_name)
            with open(reconstructed_path, 'wb') as outfile:
                outfile.write(reconstructed_data)
            print(f"Reconstructed file saved as: {reconstructed_path}")
        else:
            print("No bulk files found to reconstruct.")

    except FileNotFoundError:
        raise FileNotFoundError("Bulk file not found during reconstruction.")
    except IOError as e:
        raise IOError(f"IOError during reconstruction: {e}")


if __name__ == "__main__":
    defaults = load_config_defaults()

    parser = argparse.ArgumentParser(description="Splits a binary file into bulks.")
    parser.add_argument("input_file", help="Path to the input binary file")
    parser.add_argument("--bulk_size_gb", type=float, default=defaults["default_bulk_size_gb"], help=f"Desired bulk size in GB (default: from config.json or {defaults['default_bulk_size_gb']} GB)")
    parser.add_argument("--frame_size_bytes", type=int, default=defaults["default_frame_size_bytes"], help=f"Frame size in bytes (default: from config.json or {defaults['default_frame_size_bytes']} bytes)")
    parser.add_argument("--output_prefix", default="output_bulk", help="Prefix for output bulk files (optional)")
    parser.add_argument("--sync_word_hex", default=defaults["default_sync_word_hex"], help=f"Sync word in hex for auto-detection (default: from config.json or '{defaults['default_sync_word_hex']}')")
    parser.add_argument("--auto_detect_frame_size", action="store_true", help="Enable auto-detection of frame size")


    args = parser.parse_args()

    input_file = args.input_file
    bulk_gb = args.bulk_size_gb
    output_prefix = args.output_prefix
    sync_word_hex = args.sync_word_hex
    auto_detect_frame_size = args.auto_detect_frame_size

    frame_size = args.frame_size_bytes # Initialize with provided frame size, might be overwritten by auto-detect

    if auto_detect_frame_size:
        try:
            detected_frame_size = detect_frame_size(input_file, sync_word_hex)
            if detected_frame_size:
                frame_size = detected_frame_size
                print(f"Auto-detected frame size: {frame_size} bytes")
            else:
                print("Frame size auto-detection failed. Using provided frame size or default if not provided.")
        except Exception as e:
            print(f"Error during frame size auto-detection: {e}. Using provided frame size or default if not provided.")
            # Fallback to using provided frame_size or default if auto-detection fails

    split_binary_file(input_file, bulk_gb, frame_size, output_prefix)
