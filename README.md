# JupyterHub collection for Jupyter-JSC

## J4J_Authenticator
Generic [OAuthentitactor](https://jupyterhub.readthedocs.io/en/stable/reference/authenticators.html) for JupyterHub.
Class to login user with [Unity-IdM](https://www.unity-idm.eu). 
Contains functions to update the memory state from the database. 


## J4J_Spawner
Generic [Spawner](https://jupyterhub.readthedocs.io/en/stable/reference/spawners.html) for JupyterHub.
Users can choose different options for their JupyterLab.

## J4J_Proxy
Custom [Proxy](https://jupyterhub.readthedocs.io/en/stable/reference/proxy.html) for JupyterHub.
Proxy implementation for Jupyter-JSC. Required to run JupyterHub in multiple instances mode.

## J4J_Handler
### API_cancel
Cancel spawning JupyterLab via JupyterHub REST API.

### API_Proxy
Add routes to the proxy via JupyterHub REST API.

### API_Status
Update JupyterLab Status via REST API. Therefore spawner.poll_interval can be -1.

### API_Token
Get OAuth access token, if correct JupyterHub token is granted.

### API_UX_Handler
Receives notifications from UNICORE/X Jobs

### Home
Update memory state for the user that called the function. Therefore multiple instances of JupyterHub can be started behind one proxy.

### Spawn
Setup proxy routes to the correct instance of JupyterHub. 

### Add Page Handler
Configures additional pages. With that you can use the jinja templates for generic sites.

### API UserAccs Handler
Receives information about the users HPC accounts, if they were loaded in the background by another webservice.
