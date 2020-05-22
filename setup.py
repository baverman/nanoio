import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="nanoio",
    version="0.1",
    author="Anton Bobrov",
    author_email="baverman@gmail.com",
    description="Minimal and fast io loop to create simple servers",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/baverman/nanoio",
    py_modules=['nanoio'],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.5',
)
