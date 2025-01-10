from setuptools import setup, find_packages

setup(
    name='codecollector',
    version='1.0.0',
    author='Brandon Chapman',
    author_email='bchappublic@gmail.com',
    description='A CLI tool to consolidate code files from directories into a single file.',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/emergentcomplex/codecollector',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'codecollector=codecollector.codecollector:main',
        ],
    },
    classifiers=[
        'Programming Language :: Python :: 3',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.6',
)
