import re
from datetime import datetime
from dataclasses import dataclass
from typing import List, Optional
from collections import defaultdict
from pathlib import Path
import matplotlib.pyplot as plt
import io
import base64
import json
from ..liquid_class_db import get_liquid_class_parameter

class USBTraceParser:
    block_start_re = re.compile(r'C0([AD]Sid)(\d+)er')
    tadm_re = re.compile(r'>.*?(P[1-8])QNid\d+qn([+\-\d\s]+)')

    def __init__(self, debug: bool = False):
        self.debug = debug

    def parse_file(self, filename: str | Path):
        blocks = []
        current_block = None

        with open(filename, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                start_match = self.block_start_re.search(line)
                if start_match:
                    if current_block:
                        blocks.append(current_block)

                    block_type = start_match.group(1)
                    block_id = start_match.group(2)
                    current_block = {
                        "id": f"{block_type}{block_id}",
                        "type": "AS" if "AS" in block_type else "DS",
                        "channels": defaultdict(list),
                        "raw_lines": [line],
                        "index": len(blocks)
                    }
                    continue

                if current_block:
                    current_block["raw_lines"].append(line)
                    tadm_match = self.tadm_re.search(line)
                    if tadm_match:
                        channel = tadm_match.group(1)
                        numbers = [int(x) for x in tadm_match.group(2).split()]
                        current_block["channels"][channel].extend(numbers)

        if current_block:
            blocks.append(current_block)

        return blocks

# ------------------------------
# Dataclasses
# ------------------------------
@dataclass
class LiquidHandlerCommand:
    timestamp: datetime
    command_type: str
    status: str
    details: str
    line_number: int
    container: Optional[str] = None
    channel_info: Optional[List[tuple]] = None  # List of (position, volume) tuples
    liquid_class: Optional[str] = None
    aspirate_flow_rate: Optional[float] = None
    dispense_flow_rate: Optional[float] = None


@dataclass
class Association:
    liquid_handler_cmd: LiquidHandlerCommand
    usb_block: Optional[dict]
    time_offset_ms: Optional[float]

# ------------------------------
# TraceParser for LH and association
# ------------------------------
class TraceParser:
    def __init__(self, debug=False):
        self.liquid_commands: List[LiquidHandlerCommand] = []
        self.usb_blocks: List[dict] = []
        self.debug = debug

    def parse_liquid_handler_trace(self, content: str):
        commands = []
        lines = content.strip().split("\n")

        # Look for complete lines with channel information
        aspirate_pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+).*Channel Aspirate.*- complete;.*> channel'
        dispense_pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+).*Channel Dispense.*- complete;.*> channel'
        
        # New pattern to find the HSLHttp line and capture its JSON content
        hsl_http_pattern = r'HSLHttp : HttpGET - progress;.*Response Content: (\{.*\})'

        liquid_class = None
        aspirate_flow_rate = None
        dispense_flow_rate = None

        for i, line in enumerate(lines):
            # Check for HSLHttp line first, which precedes a liquid handling command
            hsl_match = re.search(hsl_http_pattern, line)
            if hsl_match:
                json_str = hsl_match.group(1)
                try:
                    data = json.loads(json_str)
                    liquid_class = data.get("liquidClass")
                    command_type = data.get("command")
                    if liquid_class:
                        if command_type == "channelAspirate":
                            aspirate_flow_rate = get_liquid_class_parameter(liquid_class, "AsFlowRate")
                        elif command_type == "channelDispense":
                            dispense_flow_rate = get_liquid_class_parameter(liquid_class, "DsFlowRate")
                except json.JSONDecodeError as e:
                    print(f"Error decoding JSON on line {i}: {e}")
                continue

            match = re.search(aspirate_pattern, line)
            if match:
                timestamp = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S.%f')
                container, channel_info = self.extract_channel_info(line)
                commands.append(LiquidHandlerCommand(
                    timestamp, "Aspirate", "complete", line, i, container, channel_info, liquid_class, aspirate_flow_rate, None
                ))
                # Reset variables for next command
                liquid_class = None
                aspirate_flow_rate = None
                dispense_flow_rate = None
                continue
                
            match = re.search(dispense_pattern, line)
            if match:
                timestamp = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S.%f')
                container, channel_info = self.extract_channel_info(line)
                commands.append(LiquidHandlerCommand(
                    timestamp, "Dispense", "complete", line, i, container, channel_info, liquid_class, None, dispense_flow_rate
                ))
                # Reset variables for next command
                liquid_class = None
                aspirate_flow_rate = None
                dispense_flow_rate = None

        self.liquid_commands = commands
        return commands

    def extract_channel_info(self, line: str):
        """Extract container and channel information from complete trace line"""
        # Pattern to match: > channel X: container, position, volume
        channel_pattern = r'> channel \d+: ([^,]+), ([^,]+), ([^>]+)'
        matches = re.findall(channel_pattern, line)
        
        if not matches:
            return None, None
            
        # Extract container (assume all channels use same container)
        container = matches[0][0].strip()
        
        # Extract channel info as (position, volume) tuples
        channel_info = []
        for match in matches:
            position = match[1].strip()
            volume = match[2].strip()
            channel_info.append((position, volume))
            
        return container, channel_info

    def associate_commands(self) -> List[Association]:
        associations = []
        used_blocks = set()
        
        # We need to match the last liquid handling command with the last TADM block and work backwards
        # First, filter the blocks by type (AS or DS) and reverse them
        aspirate_blocks = [b for b in self.usb_blocks if b['type'] == 'AS'][::-1]
        dispense_blocks = [b for b in self.usb_blocks if b['type'] == 'DS'][::-1]
        
        # Create a reverse copy of the liquid commands
        reversed_lh_cmds = self.liquid_commands[::-1]
        
        # Pointers for our reversed lists
        asp_idx = 0
        disp_idx = 0

        for lh_cmd in reversed_lh_cmds:
            best_match = None
            if lh_cmd.command_type == "Aspirate" and asp_idx < len(aspirate_blocks):
                best_match = aspirate_blocks[asp_idx]
                asp_idx += 1
            elif lh_cmd.command_type == "Dispense" and disp_idx < len(dispense_blocks):
                best_match = dispense_blocks[disp_idx]
                disp_idx += 1

            associations.append(Association(lh_cmd, best_match, None))

        # We need to reverse the associations list back to the correct chronological order
        return associations[::-1]

# ------------------------------
# Extract clean command from trace line
# ------------------------------
def extract_clean_command(trace_line: str) -> str:
    """
    Extract clean command from trace line.
    Input: '2025-09-10 13:35:03.996 Microlab STAR : 1000ul Channel Aspirate (Single Step) - complete;'
    Output: '1000ul Channel Aspirate'
    """
    # Remove the trailing ';'
    line = trace_line.rstrip(';')
    
    # Find the part after 'Microlab STAR : '
    star_marker = 'Microlab STAR : '
    star_index = line.find(star_marker)
    if star_index != -1:
        command_part = line[star_index + len(star_marker):].strip()
    else:
        # Fallback: just remove timestamp if no 'Microlab STAR' found
        command_part = re.sub(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+\s*', '', line).strip()
    
    # Remove ' - complete' from the end and everything after it
    command_part = re.sub(r'\s*-\s*complete.*$', '', command_part)
    command_part = re.sub(r'\s*\([^)]*\)', '', command_part)
    
    return command_part

def format_channel_info(lh_cmd: LiquidHandlerCommand) -> str:
    """Format channel information as a string: container: [(pos, vol), ...]"""
    if not lh_cmd.channel_info or not lh_cmd.container:
        return ""
    
    # Format as: container: [(pos1, vol1), (pos2, vol2), ...]
    channel_parts = [f"({pos}, {vol})" for pos, vol in lh_cmd.channel_info]
    formatted_channels = ", ".join(channel_parts)
    
    return f"{lh_cmd.container}: [{formatted_channels}]"

# ------------------------------
# Generate HTML report
# ------------------------------
def generate_html_report(associations: list, output_file: str):
    html = """
<html>
<head>
<style>
body { font-family: Arial, sans-serif; margin: 20px; }
h1 {
    font-size: 1.2em;
    font-weight: bold;
}
.command { 
    margin-bottom: 15px; 
    padding: 10px; 
}
.command-line { font-size: 0.9em; color: #000; }
.channel-details { font-size: 0.9em; color: #000; }
.liquid-class { font-size: 0.9em; color: #000; }
.flow-rate { font-size: 0.9em; color: #000; }
.usb-section {
    margin-top: 10px;
}
.toggle-arrow {
    cursor: pointer;
    font-size: 0.8em;
    padding-right: 5px;
    display: inline-block;
    transition: transform 0.2s;
}
.usb-header {
    font-size: 0.9em;
    color: #0000EE; /* Blue like a link */
    cursor: pointer;
}
img { max-width: 100%; height: auto; border: 1px solid #ccc; }
</style>
<script>
function toggle(id, arrow_id) {
  var content = document.getElementById(id);
  var arrow = document.getElementById(arrow_id);
  if (content.style.display === "none") { 
    content.style.display = "block"; 
    arrow.style.transform = "rotate(90deg)";
  } else { 
    content.style.display = "none"; 
    arrow.style.transform = "rotate(0deg)";
  }
}
</script>
</head>
<body>
<h1>Liquid Handler/ USB Report</h1>
"""

    for i, assoc in enumerate(associations, 1):
        lh = assoc.liquid_handler_cmd
        ts_str = lh.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        clean_command = extract_clean_command(lh.details)
        channel_info = format_channel_info(lh)
        
        cmd_line = f'<div class="command-line">{ts_str} {clean_command}</div>'
        
        html += f'<div class="command">{cmd_line}'
        if channel_info:
            html += f'<div class="channel-details">{channel_info}</div>'
            
        if lh.liquid_class:
            html += f'<div class="liquid-class">Liquid Class: {lh.liquid_class}</div>'
            
        if lh.aspirate_flow_rate is not None:
            html += f'<div class="flow-rate">Aspirate Flow Rate: {lh.aspirate_flow_rate} uL/s</div>'
        elif lh.dispense_flow_rate is not None:
            html += f'<div class="flow-rate">Dispense Flow Rate: {lh.dispense_flow_rate} uL/s</div>'

        if assoc.usb_block:
            img_base64 = usb_block_plot_base64(assoc.usb_block)
            
            html += f"""
            <div class="usb-section">
                <span class="usb-header" onclick="toggle('block{i}', 'arrow{i}')">
                    <span id="arrow{i}" class="toggle-arrow">&#9658;</span>
                    TADM Graph
                </span>
                <div id="block{i}" style="display:none;">
                    <img src="data:image/png;base64,{img_base64}"/>
                </div>
            </div>
            """
        else:
            html += "<em>No USB data associated</em>"
        html += "</div>"

    html += "</body></html>"

    with open(output_file, "w") as f:
        f.write(html)
    print(f"Report saved to {output_file}")

# ------------------------------
# Plot function with bigger figures
# ------------------------------
def usb_block_plot_base64(usb_block: dict) -> str:
    plt.figure(figsize=(8, 4))  # 2x bigger
    for ch, data in usb_block["channels"].items():
        plt.plot(data, label=ch)
    plt.title(f"{usb_block['id']} ({usb_block['type']})")
    plt.xlabel("Time")
    plt.ylabel("Pressure")
    plt.tight_layout()
    plt.legend(fontsize='small')

    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    plt.close()
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode("utf-8")
    return img_base64

def find_most_recent_trace_file(directory: Path, pattern: str) -> Optional[Path]:
    """
    Finds the most recently modified file in a directory that matches a given pattern.
    """
    try:
        # Use glob to find all files matching the pattern
        list_of_files = list(directory.glob(pattern))
        if not list_of_files:
            return None
        # Return the file with the most recent modification time
        return max(list_of_files, key=lambda f: f.stat().st_mtime)
    except FileNotFoundError:
        print(f"Error: The directory {directory} was not found.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while searching for files: {e}")
        return None
    
def generate_tadm_report(output = "tadm_report.html"):
    log_dir = Path(r"C:\Program Files (x86)\Hamilton\Logfiles")
    output_html = "lh_usb_report_graphs.html"

    # Automatically find the most recent trace files
    lh_file = find_most_recent_trace_file(log_dir, "*_Trace.trc")
    usb_file = find_most_recent_trace_file(log_dir, "HxUsbComm*.trc")
    
    if not lh_file:
        print(f"No liquid handler trace file ending with '_Trace.trc' found in {log_dir}. Exiting.")
        return
    elif not usb_file:
        print(f"No USB trace file starting with 'HxUsbComm' found in {log_dir}. Exiting.")
        return

    print(f"Using Liquid Handler file: {lh_file}")
    print(f"Using USB file: {usb_file}")

    parser = TraceParser(debug=False)

    with open(lh_file, encoding='latin-1') as f:
        parser.parse_liquid_handler_trace(f.read())

    usb_parser = USBTraceParser()
    parser.usb_blocks = usb_parser.parse_file(usb_file)

    associations = parser.associate_commands()

    # datestamp output html by concatenating current date/time onto existing output_html
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_html = output.replace(".html", f"_{timestamp}.html")
    generate_html_report(associations, output_html)


if __name__ == "__main__":
    generate_tadm_report()