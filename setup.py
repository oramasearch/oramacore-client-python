"""
Setup script for Orama Python client.
"""

from setuptools import setup, find_packages
import os

# Read the contents of README file
this_directory = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name="oramacore-client",
    version="1.2.0",
    author="Orama",
    author_email="hello@orama.com", 
    description="Python client for OramaCore and Orama Cloud",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/oramasearch/oramacore-client-python",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU Affero General Public License v3",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Internet :: WWW/HTTP :: Indexing/Search",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.8",
    install_requires=[
        "aiohttp>=3.8.0",
        "typing-extensions>=4.0.0"
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "black>=22.0.0",
            "flake8>=5.0.0",
            "mypy>=1.0.0",
            "isort>=5.0.0"
        ]
    },
    keywords="search, vector database, embeddings, AI, LLM, full-text search",
    project_urls={
        "Bug Reports": "https://github.com/oramasearch/oramacore-client-python/issues",
        "Source": "https://github.com/oramasearch/oramacore-client-python",
        "Documentation": "https://docs.orama.com"
    }
)