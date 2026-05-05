from setuptools import setup, find_packages

setup(
    name="ATLAS.",
    version="0.1.0",
    packages=find_packages(),
    package_data={
        'CASSIA': ['data/*.csv', 'data/*.json', 'data/*.md'],
    },
    include_package_data=True,
    install_requires=[
        "numpy>=1.21.0",
        "pandas>=1.3.0",
        "openai>=1.0.0",
        "anthropic>=0.3.0",
        "requests>=2.25.0",
        "matplotlib>=3.3.0",
        "seaborn>=0.11.0",
        "mygene>=3.2.0",
    ],
    author="Xiaoyi Zhang",
    author_email="xzhang2842@wisc.edu",
    description="A Multi-Agent Large Language Model Framework for Accurate and Interpretable Single-Cell Annotation",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/Anniezhang0402/ATLAS.",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Bio-Informatics",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.10",
)