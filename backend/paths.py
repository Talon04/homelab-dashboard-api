import os
BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
DATA_DIR = os.path.join(BASE_DIR, 'data')
# Create the data directory if it doesn't exist
os.makedirs(DATA_DIR, exist_ok=True)