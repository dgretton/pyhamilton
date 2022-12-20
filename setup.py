from setuptools import setup, find_packages

try:
    print("here")
    import pypandoc
    long_description = pypandoc.convert_file('README.md', 'rst')
    print(long_description)
except(IOError, ImportError):
    long_description = open('README.md').read()

setup(
    name='pyhamilton',
    version='1.491.3',
    packages=find_packages(exclude=['tests*', 'examples*']),
    license='MIT',
    description='Python for Hamilton liquid handling robots',
    long_description='Forthcoming due to markdown incompatibility',
    install_requires=['requests', 'pythonnet', 'pywin32', 'pyserial', 'parse', 'waiter'],
    package_data={'pyhamilton': ['star-oem/*', 'star-oem/VENUS_Method/*', 'bin/*','library/*','project-template/*',
                                 'library/HSLInhecoTEC/*','library/HSLAppsLib/*','library/ASWStandard/*',
                                 'library/ASWStandard/ASWGlobal/*','library/ASWStandard/TraceLevel/*',
                                 'library/DaisyChainedTiltModule/*','library/SchedulingDev/*',]},
    url='https://github.com/dgretton/pyhamilton.git',
    author='Dana Gretton',
    author_email='dgretton@mit.edu',
    entry_points={
        'console_scripts': [
            'pyhamilton-new-project = pyhamilton.__init__:create_project',
            'pyhamilton-configure = pyhamilton.__init__:autoconfig'
        ],
    },
)
