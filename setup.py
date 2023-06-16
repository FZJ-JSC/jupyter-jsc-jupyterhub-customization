from setuptools import find_packages
from setuptools import setup

setup(
    name="jupyter-jsc-jupyterhub-customization",
    version="4.0.0.1",
    description="JupyterHub customization collection, used by Jupyter-JSC.",
    url="https://github.com/FZJ-JSC/jupyter-jsc-jupyterhub-customization",
    author="Alice Grosch, Tim Kreuzer",
    author_email="a.grosch@fz-juelich.de, t.kreuzer@fz-juelich.de",
    license="3-BSD",
    packages=find_packages(),
    install_requires=["jsonformatter","jupyterhub-backendspawner", "oauthenticator"],
    python_requires=">=3.9",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
)
