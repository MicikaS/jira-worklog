from setuptools import setup, find_packages

setup(
    name='jiracli',
    version='0.1',
    packages=find_packages(),
    install_requires=[
        'python-decouple>=3.8',
        'requests>=2.31,<3',
        'rich>=13,<14',
        'typer>=0.7,<1',
    ],
    entry_points={
        'console_scripts': [
            'jiracli=jiracli_pkg.main:app'
        ]
    },
)
