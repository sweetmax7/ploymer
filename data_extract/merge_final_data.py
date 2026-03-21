import pandas as pd
import os

# Configuration
BASE_DIR = "/Users/aari/Documents/lunwen"
TARGET_FILE = os.path.join(BASE_DIR, "all-data.csv")
OUTPUT_FILE = os.path.join(BASE_DIR, "all-data_filled.csv")

# Define series configuration
# Start index is based on 0-based dataframe index (Line # in file - 2, since line 1 is header)
# Lengths are verified: Z=638, 起始-2=190, 起始-1=231, NEW-1=97, NEW-2=80
SERIES_CONFIG = [
    {
        "name": "Z",
        "file": "Z/data_final.csv",
        "start_idx": 0,
        "length": 638,
        "col_map": {"Annealing atmosphere": "退火氛围"} # Mapping specific for Z
    },
    {
        "name": "起始-2",
        "file": "起始-2/data_final.csv",
        "start_idx": 640, # Line 642 in file -> 642 - 2 = 640
        "length": 190,
        "col_map": {}
    },
    {
        "name": "起始-1",
        "file": "起始-1/data_final.csv",
        "start_idx": 831, # Line 833 in file -> 833 - 2 = 831
        "length": 231,
        "col_map": {}
    },
    {
        "name": "NEW-1",
        "file": "NEW-1/data_final.csv",
        "start_idx": 1063, # Line 1065 in file -> 1065 - 2 = 1063
        "length": 97,
        "col_map": {}
    },
    {
        "name": "NEW-2",
        "file": "NEW-2/data_final.csv",
        "start_idx": 1161, # Line 1163 in file -> 1163 - 2 = 1161
        "length": 80,
        "col_map": {}
    }
]

def main():
    print(f"Reading target file: {TARGET_FILE}")
    # Read target csv without index_col to keep row integer indexing simple
    df_target = pd.read_csv(TARGET_FILE)
    
    # Check total rows
    print(f"Total rows in target: {len(df_target)}")

    for series in SERIES_CONFIG:
        name = series["name"]
        file_path = os.path.join(BASE_DIR, series["file"])
        start = series["start_idx"]
        length = series["length"]
        col_map = series["col_map"]
        
        print(f"\nProcessing series: {name}")
        print(f"  - Source: {file_path}")
        print(f"  - Target Row Range: {start} to {start + length - 1} (Size: {length})")
        
        if not os.path.exists(file_path):
            print(f"  ! Error: File not found: {file_path}")
            continue
            
        # Read source file
        df_source = pd.read_csv(file_path)
        print(f"  - Source rows read: {len(df_source)}")
        
        if len(df_source) != length:
            print(f"  ! Warning: Source row count ({len(df_source)}) does not match expected length ({length})!")
            # We will proceed but truncation or mismatches might occur if we strictly use indices
            # But the user logic is "fill in", so we take min of both
        
        # Rename columns in source if needed
        if col_map:
            df_source.rename(columns=col_map, inplace=True)
            print(f"  - Renamed columns: {col_map}")

        # Iterate over common columns and update
        common_cols = [c for c in df_target.columns if c in df_source.columns and "Unnamed" not in c]
        
        print(f"  - Updating {len(common_cols)} columns: {common_cols}")
        
        # Determine the slice to update
        # We assume the source rows map 1-to-1 to the target slice
        rows_to_update = min(length, len(df_source))
        
        target_indices = range(start, start + rows_to_update)
        # Verify indices are within bounds
        if target_indices[-1] >= len(df_target):
             print(f"  ! Error: Target indices out of bounds! Max index {len(df_target)-1}, trying to access {target_indices[-1]}")
             continue

        # Bulk update using values
        # We use .values to ignore index alignment issues, assuming row order is preserved/correct
        for col in common_cols:
            df_target.loc[target_indices, col] = df_source[col].iloc[0:rows_to_update].values

    # Save output
    print(f"\nSaving filled data to: {OUTPUT_FILE}")
    df_target.to_csv(OUTPUT_FILE, index=False)
    print("Done.")

if __name__ == "__main__":
    main()
