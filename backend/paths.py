import os
BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
DATA_DIR = os.path.join(BASE_DIR, 'data')
CODE_DIR = os.path.join(DATA_DIR, 'user_code')
# Create the data and code directory if it doesn't exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(CODE_DIR, exist_ok=True)