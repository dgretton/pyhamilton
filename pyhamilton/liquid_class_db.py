from importlib import util
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text, inspect
from .defaults import defaults
import struct
from typing import List, Dict, Any, Optional, Tuple, Union
from enum import Enum
import collections
import os
import csv

class DispenseMode(Enum):
    # Basic modes
    JET = "Jet"
    SURFACE = "Surface"
    
    # Part volume modes
    JET_PART = "Jet Part"
    SURFACE_PART = "Surface Part"
    
    # Empty tip modes  
    JET_EMPTY = "Jet Empty"
    SURFACE_EMPTY = "Surface Empty"

    def to_code(self) -> int:
        """Convert enum to integer code for Hamilton system."""
        mapping = {
            DispenseMode.JET: 0,
            DispenseMode.SURFACE: 1,
            DispenseMode.JET_PART: 2,
            DispenseMode.JET_EMPTY: 3,
            DispenseMode.SURFACE_PART: 4,
            DispenseMode.SURFACE_EMPTY: 5
        }
        return mapping[self]

    @staticmethod
    def from_code(code: int) -> 'DispenseMode':
        """Convert integer code to DispenseMode enum."""
        mapping = {
            0: DispenseMode.JET,
            1: DispenseMode.SURFACE,
            2: DispenseMode.JET_PART,
            3: DispenseMode.JET_EMPTY,
            4: DispenseMode.SURFACE_PART,
            5: DispenseMode.SURFACE_EMPTY
        }
        if code in mapping:
            return mapping[code]
        else:
            raise ValueError(f"Unknown DispenseMode code: {code}")

    @classmethod
    def from_string(cls, identifier: str) -> 'DispenseMode':
        """Convert string identifier to DispenseMode enum."""
        for mode in cls:
            if mode.value == identifier:
                return mode
        
        raise ValueError(f"Unknown DispenseMode identifier: '{identifier}'. "
                         f"Available modes: {[mode.value for mode in cls]}")

def _check_access_dialect() -> None:
    """Raise if `sqlalchemy-access` is not installed."""
    if util.find_spec("sqlalchemy_access") is None:
        raise ModuleNotFoundError(
            "SQLAlchemy Access dialect not found. "
            "Install with: pip install sqlalchemy-access"
        )

def _build_engine(mdb_path: str):
    """Return a SQLAlchemy Engine for a given Access .mdb/.accdb file."""
    _check_access_dialect()

    driver = "Microsoft Access Driver (*.mdb, *.accdb)"
    odbc_str = f"DRIVER={{{driver}}};DBQ={mdb_path};"
    uri = f"access+pyodbc:///?odbc_connect={quote_plus(odbc_str)}"
    return create_engine(uri, future=True)

def _get_liquid_class_data(liquid_class_name: str, columns: Union[str, List[str]]):
    """
    General helper function to query a specific liquid class for given columns.
    
    Args:
        liquid_class_name: The name of the liquid class to query.
        columns: A single column name or a list of column names to retrieve.
        
    Returns:
        A dictionary of the queried data.
        
    Raises:
        ValueError: If the liquid class is not found.
    """
    cfg = defaults()
    engine = _build_engine(cfg.liquids_database)

    if isinstance(columns, str):
        columns = [columns]

    select_clause = ", ".join(columns)
    stmt = text(
        f"SELECT {select_clause} "
        "FROM LiquidClass "
        "WHERE LiquidClassName = :name"
    )

    with engine.connect() as conn:
        row = conn.execute(stmt, {"name": liquid_class_name}).fetchone()

    if row is None:
        raise ValueError(f"No LiquidClass found: {liquid_class_name!r}")
    
    return dict(row._mapping)

def check_liquid_class_exists(liquid_class_name: str) -> bool:
    """
    Check if a liquid class name exists in the database.
    
    Args:
        liquid_class_name: Name of the liquid class to check
        
    Returns:
        bool: True if the liquid class name exists, False otherwise
        
    Raises:
        ModuleNotFoundError: if the Access dialect is missing
        sqlalchemy.exc.*: for genuine DB errors
    """
    cfg = defaults()
    engine = _build_engine(cfg.liquids_database)
    
    stmt = text("SELECT COUNT(*) FROM LiquidClass WHERE LiquidClassName = :name")
    
    with engine.connect() as conn:
        result = conn.execute(stmt, {"name": liquid_class_name}).fetchone()
        return result[0] > 0

def get_liquid_class_column_details() -> List[Dict[str, Any]]:
    """
    Returns detailed schema information for the LiquidClass table,
    including column names, types, and nullability.
    
    Returns:
        List[Dict[str, Any]]: A list of dictionaries, each describing a column.
    """
    cfg = defaults()
    engine = _build_engine(cfg.liquids_database)
    
    inspector = inspect(engine)
    return inspector.get_columns('LiquidClass')

def get_liquid_class_columns() -> List[str]:
    """
    Return a list of all column names in the LiquidClass table.
    
    Returns:
        List[str]: Column names from the LiquidClass table
    """
    return [col['name'] for col in get_liquid_class_column_details()]

def get_liquid_class_columns_with_types() -> Dict[str, str]:
    """
    Return a dictionary of column names and their data types from the LiquidClass table.
    
    Returns:
        Dict[str, str]: Dictionary mapping column names to their SQL data types
    """
    return {col['name']: str(col['type']) for col in get_liquid_class_column_details()}

def print_table_schema():
    """
    Print detailed schema information about the LiquidClass table.
    """
    try:
        print("=== LiquidClass Table Schema ===")
        
        columns = get_liquid_class_columns()
        print(f"\nColumn Names ({len(columns)} total):")
        for i, col in enumerate(columns, 1):
            print(f"  {i:2d}. {col}")
        
        print("\n=== Column Types ===")
        col_types = get_liquid_class_columns_with_types()
        for col_name, col_type in col_types.items():
            print(f"  {col_name:25} : {col_type}")
        
        print("\n=== Detailed Column Information ===")
        detailed_cols = get_liquid_class_column_details()
        for col in detailed_cols:
            nullable = "NULL" if col.get('nullable', True) else "NOT NULL"
            default = f", DEFAULT: {col.get('default')}" if col.get('default') else ""
            print(f"  {col['name']:25} : {col['type']} ({nullable}{default})")
            
    except Exception as e:
        print(f"Error retrieving schema: {e}")

def get_all_table_names() -> List[str]:
    """
    Get all table names in the database.
    
    Returns:
        List[str]: All table names in the database
    """
    cfg = defaults()
    engine = _build_engine(cfg.liquids_database)
    
    inspector = inspect(engine)
    return inspector.get_table_names()

def get_liquid_class_dispense_mode(liquid_class_name: str) -> str:
    """
    Return the DispenseMode for a given LiquidClass name.
    
    Args:
        liquid_class_name (str): The name of the LiquidClass.
        
    Returns:
        str: The DispenseMode value.
        
    Raises:
        ValueError: if the LiquidClass is unknown.
    """
    data = _get_liquid_class_data(liquid_class_name, "DispenseMode")
    return DispenseMode.from_code(int(data["DispenseMode"])).value

def get_liquid_class_volume(liquid_class_name: str, nominal=False) -> int:
    """
    Return the maximum tip volume (µL) available for aspirating with a Hamilton LiquidClass.
    Uses nominal tip capacities and accounts for air transport and overaspirate. 
    
    Raises:
        ValueError: if the LiquidClass or TipType is unknown.
    """
    tip_type_to_volume = {3: 10, 1: 300, 23: 50, 5: 1000}
    
    data = _get_liquid_class_data(
        liquid_class_name,
        ["TipType", "AsAirTransportVolume", "AsOverAspirateVolume"]
    )

    air_transport_volume = float(data["AsAirTransportVolume"])
    overaspirate_volume = float(data["AsOverAspirateVolume"])

    tip_type = int(data["TipType"])
    volume = tip_type_to_volume.get(tip_type)

    if volume is None:
        raise ValueError(f"Unknown TipType {tip_type} for {liquid_class_name!r}")

    if nominal:
        return volume
    
    return int(volume - air_transport_volume - overaspirate_volume)


def get_liquid_class_parameter(liquid_class_name: str, parameter_name: str):
    """
    Return a single parameter for a given LiquidClass name.
    
    Args:
        liquid_class_name (str): The name of the LiquidClass.
        parameter_name (str): The name of the parameter (column) to retrieve.
        
    Returns:
        The value of the specified parameter.
        
    Raises:
        ValueError: if the LiquidClass is unknown.
    """
    data = _get_liquid_class_data(liquid_class_name, parameter_name)
    return data[parameter_name]


def create_correction_curve(data: Tuple[float, ...]) -> collections.OrderedDict:
    if len(data) % 2 != 0:
        raise ValueError("Input data must have an even number of elements.")
    
    unsorted_curve: Dict[float, float] = {}
    for i in range(0, len(data), 2):
        nominal_value = data[i]
        corrected_value = data[i + 1]
        unsorted_curve[nominal_value] = corrected_value
    
    sorted_items = sorted(unsorted_curve.items())
    return collections.OrderedDict(sorted_items)

def unpack_doubles_dynamic(byte_string: bytes) -> tuple:
    string_length = len(byte_string)
    if string_length % 8 != 0:
        raise ValueError("Byte string length is not a multiple of 8.")
    
    num_doubles = string_length // 8
    format_string = f'<{num_doubles}d'
    
    return struct.unpack(format_string, byte_string)

def export_liquid_classes_to_csv(directory="./liquid_class_data", filename="liquid_class_export.csv", predefined=False):
    """
    Exports a list of liquid classes with their detailed aspirate and dispense
    parameters to a CSV file, sorted by aspirate flow rate, for liquid classes
    where OriginalLiquid is 0.

    Args:
        directory (str): The directory where the CSV will be saved.
    """
    cfg = defaults()
    engine = _build_engine(cfg.liquids_database)
    
    os.makedirs(directory, exist_ok=True)
    csv_file_path = os.path.join(directory, filename)

    param_columns = [
        'LiquidClassName',
        'AsFlowRate', 'AsMixFlowRate', 'AsAirTransportVolume', 'AsBlowOutVolume', 
        'AsSwapSpeed', 'AsSettlingTime', 'AsOverAspirateVolume', 'AsClotRetractHeight', 
        'DsFlowRate', 'DsMixFlowRate', 'DsAirTransportVolume', 'DsBlowOutVolume', 
        'DsSwapSpeed', 'DsSettlingTime', 'DsStopFlowRate', 'DsStopBackVolume', 
        'DispenseMode'
    ]

    select_string = ", ".join(param_columns)
    query = (
        f"SELECT {select_string} FROM LiquidClass"
        + ("" if predefined else " WHERE OriginalLiquid = 0")
    )
    stmt = text(query)
    
    with engine.connect() as conn:
        result = conn.execute(stmt).fetchall()
    
    if not result:
        print("No liquid classes found with OriginalLiquid = 0.")
        return
        
    liquid_classes = []
    for row in result:
        liquid_classes.append(dict(row._mapping))

    liquid_classes.sort(key=lambda x: x['AsFlowRate'])

    with open(csv_file_path, 'w', newline='') as csvfile:
        fieldnames = param_columns
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        writer.writerows(liquid_classes)
            
    print(f"Successfully wrote filtered liquid class parameters to {csv_file_path}")

# Example usage
if __name__ == "__main__":
    name = "Tip_50ulFilter_Water_DispenseSurface_Part"
    try:
        volume = get_liquid_class_volume(name)
        print(f"Volume for {name}: {volume} µL")
    except ValueError as e:
        print(e)
    
    print("\nLiquid Class Columns:")
    print(get_liquid_class_columns())

    print("\nDispense Mode:")
    print(get_liquid_class_dispense_mode(name))
    
    print("\nSingle Parameter:")
    try:
        flow_rate = get_liquid_class_parameter(name, "AsFlowRate")
        print(f"Aspirate Flow Rate for {name}: {flow_rate}")
    except ValueError as e:
        print(e)
    
    print("\nFull Schema:")
    print_table_schema()
    
    print("\nTable Names:")
    print(get_all_table_names())