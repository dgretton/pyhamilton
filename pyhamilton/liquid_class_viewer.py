from importlib import util
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text
from .defaults import defaults   # your config helper


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


def get_liquid_class_volume(liquid_class_name: str) -> int:
    """
    Return the tip volume (µL) for a Hamilton LiquidClass.
    Raises:
        ModuleNotFoundError – if the Access dialect is missing.
        ValueError           – if the LiquidClass or TipType is unknown.
        sqlalchemy.exc.*     – for genuine DB errors.
    """
    cfg = defaults()

    tip_type_to_volume = {3: 10, 1: 300, 23: 50, 5: 1000}

    engine = _build_engine(cfg.liquids_database)

    stmt = text(
        "SELECT TipType FROM LiquidClass "
        "WHERE LiquidClassName = :name"
    )

    with engine.connect() as conn:
        row = conn.execute(stmt, {"name": liquid_class_name}).fetchone()

    if row is None:
        raise ValueError(f"No LiquidClass found: {liquid_class_name!r}")

    tip_type = int(row.TipType)
    try:
        return tip_type_to_volume[tip_type]
    except KeyError:
        raise ValueError(
            f"Unknown TipType {tip_type} for {liquid_class_name!r}; "
            f"update mapping if needed."
        ) from None



# Example usage
if __name__ == "__main__":
    name = "Tip_50ulFilter_Water_DispenseSurface_Empty"
    volume = get_liquid_class_volume(name)
    print(volume if volume else "No valid result.")
