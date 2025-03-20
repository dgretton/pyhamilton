from pyhamilton.interface import run_hamilton_process
from multiprocessing import Process
import time
import os
import signal

if __name__ == '__main__':
    oem_process = Process(target=run_hamilton_process, args=())
    oem_process.start()
    while True:
        try:
            time.sleep(1)
        except:
             try:
                os.kill(oem_process.pid, signal.SIGTERM)
                oem_process.join()
             except PermissionError:
                 time.sleep(1)


