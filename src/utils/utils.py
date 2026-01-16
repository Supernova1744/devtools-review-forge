import os
import pandas as pd

def parse_rating(rating):
    """Parse rating to float."""
    try:
        return float(rating)
    except (ValueError, TypeError):
        return None

def load_csv_data(csv_path):
    """Loads the reviews CSV into a pandas DataFrame."""
    if not os.path.exists(csv_path):
        print(f"❌ Error: Data file not found at {csv_path}")
        return pd.DataFrame()
    
    try:
        df = pd.read_csv(csv_path)
        return df
    except Exception as e:
        print(f"❌ Error loading CSV: {e}")
        return pd.DataFrame()