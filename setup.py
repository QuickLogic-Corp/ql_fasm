import setuptools

with open("README.rst", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="qlf_fasm",
    version="0.0.1",
    packages=["qlf_fasm"],
    long_description=long_description,
    url="https://github.com/QuickLogic-Corp/ql_fasm",
    author="Antmicro Ltd.",
    author_email="contact@antmicro.com",
    entry_points={
        'console_scripts': ['qlf_fasm=qlf_fasm.qlf_fasm:main']
    },
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    install_requires = [
        "fasm"
    ],
)
