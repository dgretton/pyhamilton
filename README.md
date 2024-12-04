# PyHamilton

**Python for Hamilton liquid handling robots**

Hamilton software only works on Windows, so the same goes for PyHamilton.

Developed for Hamilton STAR and STARlet on Windows XP, Windows 7, and Windows 10. VANTAGE series supported with plugin. Other robot models and operating systems not supported yet.

Please post on [labautomation.io](https://forums.pylabrobot.org/) if you have any questions, comments, issues, or feedback! You can also email contactpyhamilton@gmail.com for troubleshooting help.


**Disclaimer:** PyHamilton is not officially endorsed or supported by the Hamilton Company. Please direct any questions to the above email address, and not to Hamilton Company. 

## Example usage
```python
if __name__ == "__main__":

    from pyhamilton import HamiltonInterface, INITIALIZE
    with HamiltonInterface() as ham_int:
    
        ham_int.wait_on_response(ham_int.send_command(INITIALIZE))
```

## Documentation

[Available online](https://dgretton.github.io/pyhamilton-docs/).

## Tutorial Video
https://www.youtube.com/watch?v=G92neaVfvyw

## Installation

1. **Install and test the standard Hamilton software suite for your system.** We no longer host the link here, please contact Hamilton for a copy of the Venus 4 software if you don't have one already
2. **Install 32-bit python**, preferably using the executable installer at [https://www.python.org/downloads/release/python-390/](https://www.python.org/downloads/release/python-3119/). Python 3.12+ is known to cause an installation issue with some required pythonnet modules.
3. **Make sure git is installed.** https://git-scm.com/download/win
4. **Make sure you have .NET framework 4.0 or higher installed.** https://www.microsoft.com/en-us/download/details.aspx?id=17851
5. **Update your pip and setuptools.**
    ```
    > python -m pip install --upgrade pip
    > pip install --upgrade setuptools
    ```
6. **Install pyhamilton.**
   
   **If** you want to install normally:
   ```
    pip install pyhamilton
    ```

   **Or, if** you plan on adding new functionality or changing pyhamilton, do a project install:
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

## AI Coding Assistant

PyHamilton now comes with a project template for using an AI coding assistant that interprets natural language prompts into robot commands via the `assist()` function. To use this project, follow these instructions:

1. Make an OpenAI account and get an API key. Set your key to an environment variable named `OPENAI_API_KEY`.

2. `pip install IPython openai`

3. From the command line, run:

```
mkdir ai_project
cd ai_project
pyhamilton-ai-project
py robot_method.py
```

4. Press the green arrow in Run Control to start the method

You now are inside an IPython terminal from which you can run any Python or PyHamilton code that will execute within your Venus session. Use `assist()` to convert a natural language prompt into a robot command. **Warning:** Do not use this outside of simulation mode until you are completely sure of how it works. 

5. `[1]: assist('pick up tips from the eighth column of tips_0')` or `[1]: assist(voice_to_text())`


## Installation Troubleshooting
1. If you encounter an error relating to HxFan (i.e., your robot does not have a fan), open pyhamilton/star-oem/VENUS_Method/STAR_OEM_Test.med, navigate to the "HxFan" grouping, and delete all commands under this grouping.

2. If you would like to test your PyHamilton installation on a computer not connected to a Hamilton robot, use `HamiltonInterface(simulate=True)` to open your interface inside your robot script. 

3. If your initialization hangs (such as on initial_error_example.py), try these steps:
    </br>a. Make sure you don't have any other program running which is communicating with the robot e.g. Venus run control
    </br>b. Make sure the .dlls referenced in ```__init__.py``` are unblocked. See [this StackOverflow thread](https://stackoverflow.com/questions/28840880/pythonnet-filenotfoundexception-unable-to-find-assembly) for more details.

Please see the list of **Ongoing Projects** for information on other issues with PyHamilton

## Ongoing Projects
PyHamilton is an open-source project, and we have a ton of work to do! If you'd like to contribute to the PyHamilton project, please consider these following areas of ongoing work and don't hesitate to reach out if you want to discuss collaborating with the team.

- **PyHamilton for Nimbus:** Right now PyHamilton only works on the STAR line of liquid-handling robots, but we have recently received the appropriate libraries for expanding the framework to Hamilton Nimbus, a much more affordable and low-footprint robot. This project is in its very early stages so collaborators will have the opportunity to influence crucial design decisions.
- **PyHamilton for Linux:** One of the biggest limitations for PyHamilton, Hamilton robots, and much of lab automation in general is their exclusive dependence on Windows as an operating system. We are working to recreate the Venus application (which runs on Windows and which PyHamilton depends on in turn) as a Python library, so that PyHamilton will effectively become OS-agnostic. 
- **Package Manager**

## Applications

- [A high-throughput platform for feedback-controlled directed evolution](https://www.biorxiv.org/content/10.1101/2020.04.01.021022v1), _preprint_

- [Flexible open-source automation for robotic bioengineering](https://www.biorxiv.org/content/10.1101/2020.04.14.041368v1), _preprint_


_Developed for the Sculpting Evolution Group at the MIT Media Lab_
