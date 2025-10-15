# PyHamilton

**Python for Hamilton liquid handling robots**

Hamilton software only works on Windows, so the same goes for PyHamilton.

Developed for Hamilton STAR and STARlet on Windows XP, Windows 7, and Windows 10. VANTAGE series supported with plugin. Other robot models and operating systems not supported yet.

Please post on [labautomation.io](https://labautomation.io/) if you have any questions, comments, issues, or feedback! You can also email stefanmgolas@gmail.com for troubleshooting help.


**Disclaimer:** PyHamilton is not officially endorsed or supported by the Hamilton Company. Please direct any questions to the above email address, and not to Hamilton Company. 

## Example usage
```python
if __name__ == "__main__":

    from pyhamilton import HamiltonInterface, INITIALIZE
    with HamiltonInterface() as ham_int:
    
        ham_int.wait_on_response(ham_int.send_command(INITIALIZE))
```

## Guides

Here is a protocol repository with guides about how to do things like magnetic bead washes and thermal cycling. These are all NGS protocols, but you can use the same steps in many other experiments.

[NGS Protocol Library](https://github.com/stefangolas/ngs-protocols)

## Documentation

[Available online](https://dgretton.github.io/pyhamilton-docs/).

## Tutorial Video
https://www.youtube.com/watch?v=G92neaVfvyw

## Installation

1. **Install and test the standard Hamilton software suite for your system.** We no longer host the link here, please contact Hamilton for a copy of the Venus 4 software if you don't have one already
2. **Install [Python <=3.13](https://www.python.org/downloads/windows/)**
3. **Make sure git is installed.** https://git-scm.com/download/win
4. **Make sure you have .NET framework 4.0 or higher installed.** https://www.microsoft.com/en-us/download/details.aspx?id=17851
5. **Update your pip and setuptools.**
    ```
    > python -m pip install --upgrade pip
    > pip install --upgrade setuptools
    ```
6. **Install pyhamilton.**
   
   ```
   git clone https://github.com/dgretton/pyhamilton
   cd pyhamilton
   pip install -e .
   ```
   Now changes you make to the cloned repo will be reflected in your package install. You can test new code this way and then push it to a fork. 
    
8. **Run the pyhamilton autoconfig tool from the command line.** 
This will automatically execute all the installers in `pyhamilton/bin` and will copy all the files in `pyhamilton\library` to `C:/Program Files (x86)/HAMILTON/Library`. You are welcome to forgo this command and perform the steps manually if you are concerned about file overwriting.

    ```
    pyhamilton-configure
    ``` 

    Press accept to proceed with the bundled installers.
    
9. **Test your PyHamilton installation** </br>
The easiest way to test your PyHamilton installation is by running the following in your terminal

    ```
    mkdir new-project
    cd new-project
    pyhamilton-new-project
    py robot_method.py
    ```

10. **Run.** If you have other Python versions installed, always run pyhamilton with `py yourmethod.py` (the bundled Python launcher, which interprets shebangs) or `python3 yourmethod.py`



## Installation Troubleshooting
1. If you encounter an error relating to HxFan (i.e., your robot does not have a fan), open pyhamilton/star-oem/VENUS_Method/STAR_OEM_Test.med, navigate to the "HxFan" grouping, and delete all commands under this grouping.

2. If you would like to test your PyHamilton installation on a computer not connected to a Hamilton robot, use `HamiltonInterface(simulate=True)` to open your interface inside your robot script. 

3. If your initialization hangs (such as on initial_error_example.py), try these steps:
    </br>a. Make sure you don't have any other program running which is communicating with the robot e.g. Venus run control
    </br>b. Make sure the .dlls referenced in ```__init__.py``` are unblocked. See [this StackOverflow thread](https://stackoverflow.com/questions/28840880/pythonnet-filenotfoundexception-unable-to-find-assembly) for more details.

## Applications

- [A high-throughput platform for feedback-controlled directed evolution](https://www.biorxiv.org/content/10.1101/2020.04.01.021022v1), _preprint_

- [Flexible open-source automation for robotic bioengineering](https://www.biorxiv.org/content/10.1101/2020.04.14.041368v1), _preprint_


_Developed for the Sculpting Evolution Group at the MIT Media Lab_
