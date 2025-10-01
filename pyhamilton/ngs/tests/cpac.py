from pyhamilton import (HamiltonInterface, initialize_cpac, set_temperature_target_cpac, start_temperature_control_cpac, 
                        stop_temperature_control_cpac, terminate_cpac)

with HamiltonInterface(windowed=True, simulating=False) as ham_int:
    
    initialize_cpac(ham_int, controller_id=1, simulating=False)
    set_temperature_target_cpac(ham_int, target_temp=37.0, controller_id=1, device_id=1)
    start_temperature_control_cpac(ham_int, controller_id=1, device_id=1)
    stop_temperature_control_cpac(ham_int, controller_id=1, device_id=1)
    terminate_cpac(ham_int, stop_all_devices=True)
