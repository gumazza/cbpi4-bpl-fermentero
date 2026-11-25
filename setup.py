from os import path

from setuptools import setup

this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, "README.md"), encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="cbpi4-bpl-fermentero",
    version="0.1.0",
    description="CraftBeerPi 4 — integração Fermentero BrewPiLess (MAZZA)",
    author="MAZZA Brew Systems",
    url="https://github.com/gumazza/cbpi4-bpl-fermentero",
    include_package_data=True,
    package_data={
        "": ["*.yaml"],
        "cbpi4-bpl-fermentero": ["*.yaml"],
    },
    packages=["cbpi4-bpl-fermentero"],
    long_description=long_description,
    long_description_content_type="text/markdown",
    install_requires=["paho-mqtt>=1.6.1"],
)