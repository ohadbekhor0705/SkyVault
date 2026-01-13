import os
from Crypto.Random import get_random_bytes

def generate_key(key_filename="file_key.bin"):
    """Generates a new AES key and saves it to a file."""
    key = get_random_bytes(32) # 256-bit key
    with open(key_filename, "wb") as key_file:
        key_file.write(key)
    print(f"Key generated and saved to {key_filename}")

def load_key(key_filename="file_key.bin") -> bytes:
    """Loads the AES key from a file."""
    with open(key_filename, "rb") as key_file:
        return key_file.read()

# Run this once to create the key file
generate_key()
