"""
Setup script for queuectl package
"""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8", errors="ignore") as fh:
    long_description = fh.read()

setup(
    name="queuectl",
    version="1.0.0",
    author="Akshat Bhandari",
    author_email="ak.bhandari29@gmal.com",
    description="A CLI-based background job queue system with workers, retries, and DLQ",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/akshatb29/queuectl",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.12",
    install_requires=[
        "click>=8.1.0",
        "python-dateutil>=2.8.0",
        "tabulate>=0.9.0",
    ],
    entry_points={
        "console_scripts": [
            "queuectl=queuectl.cli:main",
        ],
    },
)