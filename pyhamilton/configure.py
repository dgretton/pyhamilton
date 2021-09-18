import os,shutil
import csv

lib_path  = os.path.abspath(os.path.join(os.path.abspath(__file__), '..', '..','library'))
lib_list = os.listdir(lib_path)

lib_full_paths = [os.path.join(lib_path, module) for module in lib_list]

hamilton_path = input('Please provide the path to your HAMILTON installation folder (e.g. C:/Program Files (x86)/HAMILTON): ')

hamilton_path = os.path.abspath(hamilton_path)
hamilton_lib_path = os.path.join(hamilton_path,'Library')

for libfile in lib_full_paths:
    if os.path.basename(libfile) not in os.listdir(hamilton_lib_path):
        print("Copying " + libfile + " to Hamilton library")
        if os.path.isfile(libfile):
            shutil.copy(libfile, os.path.join(hamilton_lib_path,os.path.basename(libfile)))
        elif os.path.isdir(libfile):
            shutil.copytree(libfile, os.path.join(hamilton_lib_path,os.path.basename(libfile)))


fan_status = input('Do you have a fan? (Y/N): ')

while True:
    if fan_status not in ('Y','N'):
        fan_status = input('Please enter either Y (for Yes) or N (for No): ')
    elif fan_status == 'Y':
        with open('installation_config.csv', 'w', newline='') as csvfile:
            writer = csv.writer(csvfile, delimiter=',')
            writer.writerow(['Fan','Yes'])
        break
    elif fan_status == 'N':
        with open('installation_config.csv','w',newline='') as csvfile:
            writer = csv.writer(csvfile, delimiter=',')
            writer.writerow(['Fan','No'])
        break




