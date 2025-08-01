import pyodbc
import pandas as pd
import warnings
from .defaults import defaults



def get_liquid_class_volume(liquid_class_name: str) -> int | None:
    """
    Look up the volume capacity (in µL) for a given Hamilton LiquidClassName using TipType mapping.
    Returns the volume in µL, or None if not found or unknown TipType.
    """

    cfg = defaults()


    warnings.filterwarnings("ignore", category=UserWarning, module="pandas")

    # TipType enum mapping
    tip_type_to_volume = {
        3: 10,
        1: 300,
        23: 50,
        5: 1000,
        # Add more if needed
    }

    # Database connection info
    mdb_path = cfg.liquids_database
    driver = 'Microsoft Access Driver (*.mdb, *.accdb)'
    conn_str = f"DRIVER={{{driver}}};DBQ={mdb_path};"

    try:
        conn = pyodbc.connect(conn_str)
        df = pd.read_sql("SELECT * FROM LiquidClass", conn)
        conn.close()

        match = df[df['LiquidClassName'] == liquid_class_name]
        if match.empty:
            print(f"No LiquidClass found with name: {liquid_class_name}")
            return None

        tip_type = int(match.iloc[0]['TipType'])
        volume = tip_type_to_volume.get(tip_type)

        if volume is None:
            print(f"Unknown TipType: {tip_type} — update mapping if needed.")
            return None

        return volume

    except pyodbc.Error as e:
        print("Database error:", e)
        return None

# Example usage
if __name__ == "__main__":
    name = "Tip_50ulFilter_Water_DispenseSurface_Empty"
    volume = get_liquid_class_volume(name)
    print(volume if volume else "No valid result.")
