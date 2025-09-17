from pyhamilton import (get_liquid_class_volume, get_liquid_class_columns, 
                        get_liquid_class_dispense_mode, get_liquid_class_parameter, get_all_table_names,
                        plot_original_correction_curves, plot_combined_correction_curves_with_fit,
                        export_flow_rates_to_csv, get_liquid_class_column_details, insert_liquid_class,
                        delete_liquid_class_by_name)
import struct

name = "NEBNext_DNA_II_SVF_Ampure_SurfaceEmpty_FastMix"
volume = get_liquid_class_volume(name, nominal=True)
dispense_mode = get_liquid_class_dispense_mode(name)

print(f"Liquid Class: {name}")
print(f"Volume: {volume} µL")
print(f"Dispense Mode: {dispense_mode}")

import collections




print(get_liquid_class_columns())

print(get_liquid_class_parameter(name, 'AsFlowRate'))


byte_string = get_liquid_class_parameter(name, 'CorrectionCurve')
print("Byte string:", byte_string)



print(get_liquid_class_parameter(name, 'OriginalLiquid'))

print(get_liquid_class_column_details())

#export_flow_rates_to_csv("liquid_classes_flow_rates.csv")
#plot_combined_correction_curves_with_fit(name_filters = ["NEBNext", "QIAseq","10X","PacBio","SureSelectXT","LSK109"])

new_liquid_class_data = {
        'LiquidClassName': 'My_New_LC_100ul',
        'LiquidName': 'Water',
        'LiquidVersion': '1.0',
        'LiquidDevices': 'Pipette',
        'LiquidNotes': 'Example liquid class for testing.',
        'OriginalLiquid': 0,
        'DispenseMode': 4, # Surface Part
        'TipType': 23, # 50 uL Tip
        'CorrectionCurve': b'\x00\x00\x00\x00\x00\x00\xf0?\x00\x00\x00\x00\x00\x00\xf0?\x00\x00\x00\x00\x00\x00\x19@\x00\x00\x00\x00\x00\x00\x1a@',  # Example binary data for two points
        'PressureLLDSensitivity': 0,
        'LLDMaxHeightDifference': 0.0,
        'ValidationState': 0,
        'DesignHistory': b'',
        'AsFlowRate': 100.0,
        'AsMixFlowRate': 150.0,
        'AsAirTransportVolume': 10.0,
        'AsBlowOutVolume': 5.0,
        'AsSwapSpeed': 1000.0,
        'AsSettlingTime': 1.5,
        'AsOverAspirateVolume': 15.0,
        'AsClotRetractHeight': 1.0,
        'DsFlowRate': 100.0,
        'DsMixFlowRate': 150.0,
        'DsAirTransportVolume': 10.0,
        'DsBlowOutVolume': 5.0,
        'DsSwapSpeed': 1000.0,
        'DsSettlingTime': 1.5,
        'DsStopFlowRate': 20.0,
        'DsStopBackVolume': 10.0,
        'WhiPipJson': b'{}', # Example empty JSON as binary data
        'CheckSum': 12345,
}

delete_liquid_class_by_name('My_New_LC_100ul')