from setuptools import setup, find_packages

VERSION = '0.2.0'
DESCRIPTION = 'A utility library to enhance discord.py bot development, now with advanced pagination and forms.'
LONG_DESCRIPTION = """\
Dispyplus is a Python library that provides several enhancements and utility features
for developing Discord bots with discord.py. It simplifies common tasks such as
configuration management, custom event handling, UI components like paginators and
confirmation dialogs, and more.
"""

setup(
    name="dispyplus",
    version=VERSION,
    author="meow",
    description=DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/markdown",
    packages=find_packages(include=['dispyplus', 'dispyplus.*']),
    install_requires=[
        "discord.py>=2.0.0", 
        "aiohttp>=3.8.0",  
    ],
    keywords=['python', 'discord', 'discord.py', 'bot', 'utility'],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Communications :: Chat",
    ],
    python_requires='>=3.8',
    url="https://github.com/meowkawaiijp/Discord.py-Plus",
    project_urls={
        "Bug Tracker": "https://github.com/meowkawaiijp/Discord.py-Plus/issues",
        "Source Code": "https://github.com/meowkawaiijp/Discord.py-Plus",
    },
)
