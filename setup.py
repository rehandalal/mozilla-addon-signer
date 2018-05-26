from setuptools import setup


setup(
    name='mozilla-addon-signer',
    version='0.2.0',
    py_modules=[
        'mozilla_addon_signer',
    ],
    install_requires=[
        'boto3',
        'Click',
        'colorama',
        'requests',
        'six',
        'untangle',
    ],
    entry_points={
        'console_scripts': [
            'mozilla-addon-signer = mozilla_addon_signer.cli:cli',
        ],
    },
)
