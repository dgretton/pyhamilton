from setuptools import setup, find_packages

long_description = open('README.md', encoding='utf-8').read()

setup(
    name='pyhamilton',
    version='1.48',
    packages=find_packages(exclude=['tests*', 'examples*']),
    license='MIT',
    description='Python for Hamilton liquid handling robots',
    long_description='Forthcoming due to markdown incompatibility',
    install_requires=['requests', 'pythonnet', 'pywin32', 'pyserial'],
    package_data={'pyhamilton': ['star-oem/*', 'star-oem/VENUS_Method/*', 'bin/*','library/*',
                                 'library/HSLInhecoTEC/*','library/HSLAppsLib/*','library/ASWStandard/*',
                                 'library/DaisyChainedTiltModule/*','library/SchedulingDev/*',]},
    url='https://github.com/dgretton/pyhamilton.git',
    author='Dana Gretton',
    author_email='dgretton@mit.edu',
    entry_points={
        'console_scripts': [
            'pyhamilton-quickstart = pyhamilton.cmd.quickstart:main',
            'pyhamilton-configure = pyhamilton.__init__:autoconfig'
        ],
    },
)
