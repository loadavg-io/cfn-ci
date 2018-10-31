from setuptools import setup, find_packages

setup(
    name = 'cfn-ci',
    version = '0.0.1a',
    url = 'https://github.com/loadavg-io/cfn-ci.git',
    author = 'Loadavg New Zealand (Etienne Kruger)',
    author_email = 'el@loadavg.io',
    description = 'AWS CloudFormation continuous integration tool.',
    packages = ['cfnci'],
    install_requires = [
        'boto3 >= 1.9.29',
        'click >= 7.0',
        'pyyaml >= 3.13',
        'clint >= 0.5.1',
    ],
    entry_points={
        'console_scripts': ['cfn-ci=cfnci:cli'],
    }
)
