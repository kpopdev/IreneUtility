from setuptools import setup, find_packages

with open("README.md", "r") as f:
    long_description = f.read()


def parse_requirements(filename):
    """Load requirements from a pip requirements file."""
    line_iter = (line.strip() for line in open(filename))
    return [line for line in line_iter if line and not line.startswith("#")]


setup(
    name='IreneUtility',
    version='1.04.1',
    packages=find_packages(),
    install_requires=parse_requirements("requirements.txt"),
    url='https://github.com/MujyKun/IreneUtility/',
    license='MIT License',
    author='MujyKun',
    author_email='mujy@irenebot.com',
    description='Utility Package for IreneBot',
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python",
    ],
    long_description=long_description,
    long_description_content_type="text/markdown",
    python_requires='>=3.8'
)
