import setuptools
import os

with open("README.md", "r") as f:
    long_description = f.read()

setuptools.setup(
    name="plenoirf",
    version="0.1.2",
    description="Explore magnetic deflection of cosmic-rays below 10GeV.",
    long_description=long_description,
    url="https://github.com/cherenkov-plenoscope",
    author="Sebastian Achim Mueller",
    author_email="sebastian-achim.mueller@mpi-hd.mpg.de",
    license="GPL v3",
    packages=["plenoirf",],
    install_requires=[
        "cosmic_fluxes",
        "corsika_primary",
        "propagate_uncertainties>=0.1.0",
        "iminuit==1.4.9",
        "shapely",
        "binning_utils_sebastian-achim-mueller",
        "json_numpy_sebastian-achim-mueller",
    ],
    package_data={"plenoirf": [os.path.join("summary", "scripts", "*")]},
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
        "Natural Language :: English",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Physics",
        "Topic :: Scientific/Engineering :: Astronomy",
    ],
)
