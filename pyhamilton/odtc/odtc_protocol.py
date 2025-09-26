import xml.etree.ElementTree as ET
from datetime import datetime

class ThermalCyclerProtocol:
    """
    A class to programmatically generate thermal cycler protocols in XML format.
    """
    def __init__(self, creator="stefan", variant=960000, plate_type=0, fluid_quantity=1):
        self.creator = creator
        self.variant = variant
        self.plate_type = plate_type
        self.fluid_quantity = fluid_quantity
        self.pre_method = {
            "methodName": "PreMethod",
            "TargetBlockTemperature": 25,
            "TargetLidTemp": 110
        }
        self.steps = []
        self.pid_set = {
            1: {
                "PHeating": 60, "PCooling": 80,
                "IHeating": 250, "ICooling": 100,
                "DHeating": 10, "DCooling": 10,
                "PLid": 100, "ILid": 70
            }
        }

    def add_step(self, plateau_temp, plateau_time, slope=1, overshoot_temp=0, overshoot_time=0,
                 overshoot_slope1=0.1, overshoot_slope2=0.1, goto_number=0, loop_number=0, pid_number=1,
                 lid_temp=110):
        """Adds a single step to the protocol."""
        step_data = {
            "Number": len(self.steps) + 1,
            "Slope": slope,
            "PlateauTemperature": plateau_temp,
            "PlateauTime": plateau_time,
            "OverShootSlope1": overshoot_slope1,
            "OverShootTemperature": overshoot_temp,
            "OverShootTime": overshoot_time,
            "OverShootSlope2": overshoot_slope2,
            "GotoNumber": goto_number,
            "LoopNumber": loop_number,
            "PIDNumber": pid_number,
            "LidTemp": lid_temp,
        }
        self.steps.append(step_data)
        return self

    def add_pcr_cycle(self, denaturation_temp, denaturation_time, annealing_temp, annealing_time,
                      extension_temp, extension_time, num_cycles):
        """Adds a complete PCR cycle block with looping."""
        start_loop_step = len(self.steps) + 1
        
        # Denaturation step
        self.add_step(denaturation_temp, denaturation_time)
        
        # Annealing step (part of the loop)
        self.add_step(annealing_temp, annealing_time)
        
        # Extension step (part of the loop, with loop parameters)
        self.add_step(extension_temp, extension_time, goto_number=start_loop_step, loop_number=num_cycles)
        
        return self
    
    def add_final_extension(self, temp, time):
        """Adds a final extension step."""
        return self.add_step(temp, time)

    def set_pid_parameters(self, pid_number, p_heating, p_cooling, i_heating, i_cooling, d_heating, d_cooling, p_lid, i_lid):
        """Sets custom PID parameters for a given PID number."""
        self.pid_set[pid_number] = {
            "PHeating": p_heating, "PCooling": p_cooling,
            "IHeating": i_heating, "ICooling": i_cooling,
            "DHeating": d_heating, "DCooling": d_cooling,
            "PLid": p_lid, "ILid": i_lid
        }
        return self

    def set_pre_method(self, block_temp=25, lid_temp=110):
        """Sets the pre-method parameters."""
        self.pre_method["TargetBlockTemperature"] = block_temp
        self.pre_method["TargetLidTemp"] = lid_temp
        return self

    def generate_xml(self, filename="protocol.xml"):
        """Generates the XML file from the class data."""
        method_set = ET.Element("MethodSet")
        
        # PreMethod
        pre_method = ET.SubElement(method_set, "PreMethod", 
                                   methodName=self.pre_method["methodName"], 
                                   creator=self.creator, 
                                   dateTime=datetime.now().isoformat())
        ET.SubElement(pre_method, "TargetBlockTemperature").text = str(self.pre_method["TargetBlockTemperature"])
        ET.SubElement(pre_method, "TargetLidTemp").text = str(self.pre_method["TargetLidTemp"])
        
        # Method
        method = ET.SubElement(method_set, "Method", 
                               methodName="Method", 
                               creator=self.creator, 
                               dateTime=datetime.now().isoformat())
        ET.SubElement(method, "Variant").text = str(self.variant)
        ET.SubElement(method, "PlateType").text = str(self.plate_type)
        ET.SubElement(method, "FluidQuantity").text = str(self.fluid_quantity)
        ET.SubElement(method, "PostHeating").text = "true"
        ET.SubElement(method, "StartBlockTemperature").text = str(self.pre_method["TargetBlockTemperature"])
        ET.SubElement(method, "StartLidTemperature").text = str(self.pre_method["TargetLidTemp"])
        
        # Steps
        for step_data in self.steps:
            step = ET.SubElement(method, "Step")
            for key, value in step_data.items():
                ET.SubElement(step, key).text = str(value)
        
        # PIDSet
        pid_set_elem = ET.SubElement(method, "PIDSet")
        for num, params in self.pid_set.items():
            pid = ET.SubElement(pid_set_elem, "PID", number=str(num))
            for key, value in params.items():
                ET.SubElement(pid, key).text = str(value)
        
        # Write to file
        tree = ET.ElementTree(method_set)
        ET.indent(tree, space="  ", level=0)
        tree.write(filename, encoding="utf-8", xml_declaration=True)



if __name__ == "__main__":
    # Create an instance of the class
    protocol = ThermalCyclerProtocol(creator="Your Name", fluid_quantity=25)

    # Build a standard PCR protocol using the class methods
    protocol.add_step(plateau_temp=95, plateau_time=120) 
    protocol.add_pcr_cycle(
        denaturation_temp=95, denaturation_time=30,
        annealing_temp=60, annealing_time=30,
        extension_temp=72, extension_time=60,
        num_cycles=35
    )
    protocol.add_final_extension(temp=72, time=300) 
    protocol.add_step(plateau_temp=4, plateau_time=600)

    # Generate the XML file
    protocol.generate_xml("pcr_protocol_class.xml")

    print("pcr_protocol_class.xml has been generated.")
