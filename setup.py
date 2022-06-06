from setuptools import setup

setup(
    name='JupyterHub-Collection',
    version='1.1',
    description='Extension for JupyterHub. Used for Jupyter-jsc.',
    author='Tim Kreuzer',
    author_email='jupyter.jsc@fz-juelich.de',
    packages=['j4j_proxy', 'j4j_authenticator', 'j4j_handler', 'j4j_spawner'],
    install_requires=['jupyterhub>=1.1.0', 'oauthenticator==15.0.0', 'pyjwt>=1.7.1', 'psycopg2-binary>=2.8.5']
)
