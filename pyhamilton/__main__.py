# -*- coding: utf-8 -*-
"""
Created on Sun Jul  3 13:25:23 2022

@author: stefa
"""

import os
import sys
import shutil
import json

this_file_dir = os.path.dirname(os.path.abspath(__file__))
PACKAGE_DIR = os.path.abspath(os.path.join(this_file_dir))
LIBRARY_DIR = os.path.join(PACKAGE_DIR, 'library')
exe_http = os.path.join(PACKAGE_DIR, 'bin', 'Hamilton HSLHttp Library Installer Version 2.7.exe')
exe_json = os.path.join(PACKAGE_DIR, 'bin', 'HSLJson Library v1.6 Installer.exe')

def full_paths_list(directory_abs_path):
    list_files = os.listdir(directory_abs_path)
    list_file_paths = [directory_abs_path + '\\' + file for file in list_files]
    return list_file_paths


import os
import shutil
import json

def pyhamiltonconfig():
    print("Automatically configuring your PyHamilton installation")

    # Launch configuration executables
    os.startfile(exe_http)
    os.startfile(exe_json)

    # Copy library files
    hamilton_lib_dir = os.path.abspath('C:/Program Files (x86)/HAMILTON/Library')

    def full_paths_list(folder):
        return [os.path.join(folder, f) for f in os.listdir(folder)]

    def recursive_copy(source_dir, target_dir):
        source_list = full_paths_list(source_dir)
        for file in source_list:
            if os.path.isfile(file):
                shutil.copy(file, os.path.join(target_dir, os.path.basename(file)))
            elif os.path.isdir(file):
                target = os.path.join(target_dir, os.path.basename(file))
                if not os.path.exists(target):
                    os.mkdir(target)
                recursive_copy(file, target)

    recursive_copy(LIBRARY_DIR, hamilton_lib_dir)

    # --- Copy prebuilt defaults.json from ./defaults ---
    user_home = os.path.expanduser("~")
    config_dir = os.path.join(user_home, ".pyhamilton")
    os.makedirs(config_dir, exist_ok=True)

    source_defaults_path = os.path.join(os.getcwd(), "defaults", "defaults.json")
    target_defaults_path = os.path.join(config_dir, "defaults.json")

    if not os.path.exists(source_defaults_path):
        print(f"ERROR: Could not find source defaults file at: {source_defaults_path}")
    else:
        shutil.copyfile(source_defaults_path, target_defaults_path)
        print(f"Copied default config to: {target_defaults_path}")

    print("Configuration completed")


            
            
            
            