'''
Created on May 10, 2019

@author: kreuzer
'''

#import asyncio
#import json
#import requests
#import subprocess
#import time
import uuid

#from contextlib import closing
#from datetime import timedelta
#from tornado import gen, web
from tornado import web

#from j4j_spawner.file_loads import get_token


from jupyterhub.apihandlers.base import APIHandler
from jupyterhub.handlers.base import BaseHandler
#from jupyterhub.utils import maybe_future

#from jupyterhub.metrics import RUNNING_SERVERS, SERVER_STOP_DURATION_SECONDS, ServerStopStatus


class J4J_DeletionHandler(APIHandler):
    @web.authenticated
    async def delete(self):
        user = self.current_user
        if user:
            uuidcode = uuid.uuid4().hex
            user.authenticator.update_mem(user, uuidcode)
            self.log.info("uuidcode={} - action=deletion - Delete User: {}".format(uuidcode, user.name))
            """
            with open(user.authenticator.user_deletion_config_path, "r") as f:
                deletion_config = json.load(f)
            if deletion_config.get('deletion', {}).get('hdf', False):
                self.log.debug("uuidcode={} - Delete User from HDF-Cloud Resources".format(uuidcode))
                # ------ User deletion HDF-Cloud
                with open(user.authenticator.j4j_urls_paths, 'r') as f:
                    urls = json.load(f)
                # Remove user from HDF-Cloud Resources
                url = urls.get('dockermaster', {}).get('url_deletion', '<url_deletion_not_defined>')
                header = {"Intern-Authorization": get_token(user.authenticator.dockermaster_token_path),
                          "uuidcode": uuidcode,
                          "email": user.name}
                try:
                    with closing(requests.delete(url, headers=header, verify=False)) as r:
                        if r.status_code != 204:
                            self.log.warning("uuidcode={} - Could not delete user at HDF-Cloud Master: {} {}".format(uuidcode, r.status_code, r.text))
                except:
                    self.log.exception("uuidcode={} - Could not delete user".format(uuidcode))
                # ------ User deletion HDF-Cloud finished
            if deletion_config.get('deletion', {}).get('jhub', False):
                # ------ User deletion JHub
                self.log.debug("uuidcode={} - Delete User from JHub Resources".format(uuidcode))
                for server_name, spawner in user.spawners.items():
                    spawner._stop_pending = True
                    async def stop():
                        ""Stop the server
        
                        1. remove it from the proxy
                        2. stop the server
                        3. notice that it stopped
                        ""
                        tic = time.perf_counter()
                        try:
                            await self.proxy.delete_user(user, server_name)
                            await user.stop(server_name)
                            toc = time.perf_counter()
                            self.log.info(
                                "User %s server took %.3f seconds to stop", user.name, toc - tic
                            )
                            self.statsd.timing('spawner.stop', (toc - tic) * 1000)
                            RUNNING_SERVERS.dec()
                            SERVER_STOP_DURATION_SECONDS.labels(
                                status=ServerStopStatus.success
                            ).observe(toc - tic)
                        except:
                            SERVER_STOP_DURATION_SECONDS.labels(
                                status=ServerStopStatus.failure
                            ).observe(time.perf_counter() - tic)
                        finally:
                            spawner._stop_future = None
                            spawner._stop_pending = False
        
                    future = spawner._stop_future = asyncio.ensure_future(stop())
                    
                    try:
                        await gen.with_timeout(timedelta(seconds=self.slow_stop_timeout), future)
                    except gen.TimeoutError:
                        # hit timeout, but stop is still pending
                        self.log.warning(
                            "User %s:%s server is slow to stop", user.name, server_name
                        )
        
                await maybe_future(self.authenticator.delete_user(user))
                # remove from registry
                self.users.delete(user)
            # ------ User deletion JHub finished ----
            # ------ User deletion Unity-JSC
            if deletion_config.get('deletion', {}).get('unity_jsc', False):
                self.log.debug("uuidcode={} - Delete User from Unity-JSC Resources".format(uuidcode))
                cmd = ['ssh',
                       '-i',
                       deletion_config.get('unity_jsc', {}).get('ssh_key', '<ssh_key_not_defined>'),
                       '{}@{}'.format(deletion_config.get('unity_jsc', {}).get('user', '<ssh_user_not_defined>'), deletion_config.get('unity_jsc', {}).get('hostname', '<ssh_hostname_not_defined>')),
                       'UID={}'.format(user.name)]
                subprocess.Popen(cmd)
            # ------ User deletion Unity-JSC finished
            """
        
    @web.authenticated
    async def get(self):
        user = self.current_user
        html = self.render_template('deletion.html',
                                    user=user)
        self.finish(html)

class J4J_ToSHandler(BaseHandler):
    async def get(self):
        user = self.current_user        
        html = self.render_template(
                    'tos.html',
                    user=user)
        self.finish(html)
        
class J4J_DPSHandler(BaseHandler):
    async def get(self):
        user = self.current_user        
        html = self.render_template(
                    'dps.html',
                    user=user)
        self.finish(html)
        
class J4J_ImprintHandler(BaseHandler):
    async def get(self):
        user = self.current_user        
        html = self.render_template(
                    'imprint.html',
                    user=user)
        self.finish(html)
        
class J4J_TestHandler(BaseHandler):
    async def get(self):
        user = self.current_user        
        html = self.render_template(
                    'test.html',
                    user=user)
        self.finish(html)
        
class J4J_ProjectsHandler(BaseHandler):
    async def get(self):
        user = self.current_user        
        html = self.render_template(
                    'projects.html',
                    user=user)
        self.finish(html)
        
class J4J_KernelHandler(BaseHandler):
    async def get(self):
        user = self.current_user        
        html = self.render_template(
                    'kernel.html',
                    user=user)
        self.finish(html)