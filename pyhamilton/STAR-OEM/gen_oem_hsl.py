import os
targets = {'hsl_template_STAR_OEM.txt':'STAR_OEM.hsl', 'sub_template_STAR_OEM.txt':'STAR_OEM.sub'}
port_mark = '$$$'
header_sep = '$END_HEADER$'
thread_main_mark = '$THREAD_MAIN$'
thread_main_name = 'doThreadedCommand'
ports = [3222, 3223]

def parse_methods(text):
    # only feed lines known to contain only methods
    method_blocks = [(block + '\n}').strip() + '\n' for block in text.split('\n}')]
    method_blocks.pop(-1)
    parses = []
    for method_block in method_blocks:
        method_def_pieces = method_block.split('(')[0].split(' ')
        modifiers = ' '.join(method_def_pieces[:-1])
        method_name = method_def_pieces[-1].strip()
        method_body = method_name.join(method_block.split(method_name)[1:])
        parses.append((modifiers, method_name, method_body))
    return parses

def assemble_method(method_parse, port=None):
    modifiers, method_name, method_body = method_parse
    if port is not None and port_mark not in method_body:
        raise ValueError('assemble_method expected a port number')
    method_name = method_name.replace(thread_main_mark, thread_main_name)
    first_part = modifiers + ' ' + method_name 
    if port:
        return first_part + '_' + str(port) + method_body.replace(port_mark, str(port))
    return first_part + method_body

def gen_oem_hsl(template, target):
    with open(template, 'r') as t:
        template_text = t.read()
    header_text, methods_text = template_text.split(header_sep)

    header_lines = [line.strip() for line in header_text.split('\n') if line.strip()]

    parses = parse_methods(methods_text)
    thread_methods = []
    ordinary_methods = []
    for parse in parses:
        modifiers, name, raw_body = parse
        body_lines = []
        for line in raw_body.split('\n'):
            if thread_main_mark in line:
                for port in ports:
                    body_lines.append(line.replace(thread_main_mark, thread_main_mark + '_' + str(port)))
            else:
                body_lines.append(line)
        body = '\n'.join(body_lines)
        if port_mark in body or thread_main_mark in name:
            print(name)
            for port in ports:
                thread_methods.append(assemble_method(parse, port))
            for i, line in enumerate(header_lines):
                if name in line: # This header line defines a threaded method, so mark it so
                    header_lines[i] = line.replace(name, name + '_' + port_mark)
        else:
            ordinary_methods.append(assemble_method((modifiers, name, body)))

    global_header_lines = []
    thread_header_lines = []
    for line in sorted(header_lines):
        if port_mark in line:
            thread_header_lines.append(line)
        else:
            global_header_lines.append(line)
    assembled_text = ''
    assembled_text += '\n'.join(global_header_lines) + '\n'
    for line in thread_header_lines:
        for port in ports:
            assembled_text += line.replace(port_mark, str(port)) + '\n'
    for ordinary_method in ordinary_methods:
        assembled_text += ordinary_method + '\n'
    for thread_method in thread_methods:
        assembled_text += thread_method + '\n'

    with open(target, 'w+') as f:
        f.write(assembled_text)

if __name__ == '__main__':
    for template, target in targets.items():
        gen_oem_hsl(template, target)
