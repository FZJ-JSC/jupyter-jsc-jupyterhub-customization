'''
Created on May 10, 2019

@author: kreuzer
'''

import asyncio
import json
import os
import requests
import subprocess
import time
import uuid

from contextlib import closing
from datetime import timedelta
from tornado import gen, web

from j4j_spawner.file_loads import get_token

from jupyterhub.apihandlers.base import APIHandler
from jupyterhub.handlers.base import BaseHandler
from jupyterhub.handlers.login import LogoutHandler
from jupyterhub.utils import maybe_future, admin_only, new_token
from jupyterhub import orm

from jupyterhub.metrics import RUNNING_SERVERS, SERVER_STOP_DURATION_SECONDS, ServerStopStatus


class J4J_LogOffAllAPIHandler(APIHandler, LogoutHandler):
    @admin_only
    async def delete(self):
        db_user_list = list(self.db.query(orm.User))
        self.log.debug(db_user_list)
        self.log.debug(self.app.users)
        for db_user in db_user_list:
            db_user.cookie_id = new_token()
            db_user.db.commit()
        return

class J4J_RemoveAccountBaseHandler(BaseHandler):
    @web.authenticated
    async def get(self):
        user = self.current_user
        totalfiles = ""
        totalsize = ""
        try:
            uuidcode = uuid.uuid4().hex
            self.log.debug("uuidcode={} - Get User Information to display on website")
            with open(user.authenticator.j4j_urls_paths, 'r') as f:
                urls = json.load(f)
            url = urls.get('dockermaster', {}).get('url_removal')
            header = {"Intern-Authorization": get_token(user.authenticator.dockermaster_token_path),
                      "uuidcode": uuidcode,
                      "email": user.name}
            with closing(requests.get(url, headers=header, verify=False)) as r:
                if r.status_code == 200:
                    totalfiles, totalsize = r.text.strip().replace('"', '').replace("'", "").split(':')
        except:
            self.log.exception("Could not get user information")
        html = self.render_template('removal.html',
                                    user=user)
        html = html.replace("<!-- TOTALFILES -->", totalfiles)
        html = html.replace("<!-- TOTALSIZE -->", totalsize)
        self.finish(html)

class J4J_2FAAPIHandler2(APIHandler):
    @web.authenticated
    async def delete(self):
        user = self.current_user
        if user:
            try:
                uuidcode = uuid.uuid4().hex
                await user.authenticator.update_mem(user, uuidcode)
                self.log.info("uuidcode={} - action=delete2faopt - Remove User from 2FA optional group: {}".format(uuidcode, user.name))
                unity_path = os.environ.get('UNITY_FILE', '<no unity file path defined>')
                with open(unity_path, 'r') as f:
                    unity = json.load(f)
                auth_state = await user.get_auth_state()
                if auth_state.get('login_handler') == 'jscldap':
                    token_url = os.environ.get('JSCLDAP_TOKEN_URL', '<no token url defined>')
                elif auth_state.get('login_handler') == 'jscusername':
                    token_url = os.environ.get('JSCUSERNAME_TOKEN_URL', '<no token url defined>')
                elif auth_state.get('login_handler') == 'hdfaai':
                    token_url = os.environ.get('HDFAAI_TOKEN_URL', '<no token url defined>')
                cmd = ['ssh',
                       '-i',
                       unity.get(token_url, {}).get('2FADeactivate', {}).get('key', '<ssh_key_not_defined>'),
                       '-o',
                       'StrictHostKeyChecking=no',
                       '-o',
                       'UserKnownHostsFile=/dev/null',
                       '{}@{}'.format(unity.get(token_url, {}).get('2FADeactivate', {}).get('user', '<ssh_user_not_defined>'), unity.get(token_url, {}).get('2FADeactivate', {}).get('host', '<ssh_hostname_not_defined>')),
                       'UID={}'.format(user.name)]
                self.log.debug("uuidcode={} - Execute {}".format(uuidcode, ' '.join(cmd)))
                subprocess.Popen(cmd)
                self.set_header('Content-Type', 'text/plain')
                self.set_status(204)
            except:
                self.log.exception("Bugfix required")
                self.set_status(500)
                self.write("Something went wrong. Please contact support to deactivate two factor authentication.")
                self.flush()
        else:
            self.set_header('Content-Type', 'text/plain')
            self.set_status(404)
            raise web.HTTPError(404, 'User not found. Please logout, login and try again. If this does not help contact support.')

class J4J_2FAAPIHandler(APIHandler):
    @web.authenticated
    async def delete(self):
        user = self.current_user
        if user:
            try:
                uuidcode = uuid.uuid4().hex
                await user.authenticator.update_mem(user, uuidcode)
                self.log.info("uuidcode={} - action=delete2faopt - Remove User from 2FA optional group: {}".format(uuidcode, user.name))
                unity_path = os.environ.get('UNITY_FILE', '<no unity file path defined>')
                with open(unity_path, 'r') as f:
                    unity = json.load(f)
                auth_state = await user.get_auth_state()
                if auth_state.get('login_handler') == 'jscldap':
                    token_url = os.environ.get('JSCLDAP_TOKEN_URL', '<no token url defined>')
                elif auth_state.get('login_handler') == 'jscusername':
                    token_url = os.environ.get('JSCUSERNAME_TOKEN_URL', '<no token url defined>')
                elif auth_state.get('login_handler') == 'hdfaai':
                    token_url = os.environ.get('HDFAAI_TOKEN_URL', '<no token url defined>')
                cmd = ['ssh',
                       '-i',
                       unity.get(token_url, {}).get('2FARemove', {}).get('key', '<ssh_key_not_defined>'),
                       '-o',
                       'StrictHostKeyChecking=no',
                       '-o',
                       'UserKnownHostsFile=/dev/null',
                       '{}@{}'.format(unity.get(token_url, {}).get('2FARemove', {}).get('user', '<ssh_user_not_defined>'), unity.get(token_url, {}).get('2FARemove', {}).get('host', '<ssh_hostname_not_defined>')),
                       'UID={}'.format(user.name)]
                self.log.debug("uuidcode={} - Execute {}".format(uuidcode, ' '.join(cmd)))
                subprocess.Popen(cmd)
                self.set_header('Content-Type', 'text/plain')
                self.set_status(204)
            except:
                self.log.exception("Bugfix required")
                self.set_status(500)
                self.write("Something went wrong. Please contact support to deactivate two factor authentication.")
                self.flush()
        else:
            self.set_header('Content-Type', 'text/plain')
            self.set_status(404)
            raise web.HTTPError(404, 'User not found. Please logout, login and try again. If this does not help contact support.')

    @web.authenticated
    async def post(self):
        user = self.current_user
        if user:
            try:
                uuidcode = uuid.uuid4().hex
                await user.authenticator.update_mem(user, uuidcode)
                self.log.info("uuidcode={} - action=add2faopt - Add User to 2FA optional group: {}".format(uuidcode, user.name))
                unity_path = os.environ.get('UNITY_FILE', '<no unity file path defined>')
                with open(unity_path, 'r') as f:
                    unity = json.load(f)
                auth_state = await user.get_auth_state()
                if auth_state.get('login_handler') == 'jscldap':
                    token_url = os.environ.get('JSCLDAP_TOKEN_URL', '<no token url defined>')
                elif auth_state.get('login_handler') == 'jscusername':
                    token_url = os.environ.get('JSCUSERNAME_TOKEN_URL', '<no token url defined>')
                elif auth_state.get('login_handler') == 'hdfaai':
                    token_url = os.environ.get('HDFAAI_TOKEN_URL', '<no token url defined>')
                cmd = ['ssh',
                       '-i',
                       unity.get(token_url, {}).get('2FA', {}).get('key', '<ssh_key_not_defined>'),
                       '-o',
                       'StrictHostKeyChecking=no',
                       '-o',
                       'UserKnownHostsFile=/dev/null',
                       '{}@{}'.format(unity.get(token_url, {}).get('2FA', {}).get('user', '<ssh_user_not_defined>'), unity.get(token_url, {}).get('2FA', {}).get('host', '<ssh_hostname_not_defined>')),
                       'UID={}'.format(user.name)]
                self.log.debug("uuidcode={} - Execute {}".format(uuidcode, ' '.join(cmd)))
                subprocess.Popen(cmd)
                self.set_header('Content-Type', 'text/plain')
                self.set_status(204)
            except:
                self.log.exception("Bugfix required")
                self.set_status(500)
                self.write("Something went wrong. Please contact support to activate two factor authentication.")
                self.flush()
        else:
            self.set_header('Content-Type', 'text/plain')
            self.set_status(404)
            raise web.HTTPError(404, 'User not found. Please logout, login and try again. If this does not help contact support.')

class J4J_RemoveAccountAPIHandler(APIHandler, LogoutHandler):
    @web.authenticated
    async def delete(self):
        user = self.current_user
        if user:
            try:
                uuidcode = uuid.uuid4().hex
                await user.authenticator.update_mem(user, uuidcode)
                self.log.info("uuidcode={} - action=removeaccount - Remove User: {}".format(uuidcode, user.name))
                with open(user.authenticator.user_removal_config_path, "r") as f:
                    removal_config = json.load(f)
                if removal_config.get('removal', {}).get('hdf', False):
                    self.log.debug("uuidcode={} - Remove User from HDF-Cloud Resources".format(uuidcode))
                    # ------ User Removal HDF-Cloud
                    with open(user.authenticator.j4j_urls_paths, 'r') as f:
                        urls = json.load(f)
                    # Remove user from HDF-Cloud Resources
                    url = urls.get('dockermaster', {}).get('url_removal', '<url_removal_not_defined>')
                    header = {"Intern-Authorization": get_token(user.authenticator.dockermaster_token_path),
                              "uuidcode": uuidcode,
                              "email": user.name}
                    try:
                        with closing(requests.delete(url, headers=header, verify=False)) as r:
                            if r.status_code != 204:
                                self.log.warning("uuidcode={} - Could not remove user at HDF-Cloud Master: {} {}".format(uuidcode, r.status_code, r.text))
                    except:
                        self.log.exception("uuidcode={} - Could not remove user".format(uuidcode))
                    # ------ User removal HDF-Cloud finished
                # ------ User Removal Unity-JSC
                if removal_config.get('removal', {}).get('unity_jsc', False):
                    self.log.debug("uuidcode={} - Remove User from Unity-JSC Resources".format(uuidcode))
                    cmd = ['ssh',
                           '-i',
                           removal_config.get('unity_jsc', {}).get('ssh_key', '<ssh_key_not_defined>'),
                           '-o',
                           'StrictHostKeyChecking=no',
                           '-o',
                           'UserKnownHostsFile=/dev/null',
                           '{}@{}'.format(removal_config.get('unity_jsc', {}).get('user', '<ssh_user_not_defined>'), removal_config.get('unity_jsc', {}).get('hostname', '<ssh_hostname_not_defined>')),
                           'UID={}'.format(user.name)]
                    subprocess.Popen(cmd)
                # ------ User Removal Unity-JSC finished
                if removal_config.get('removal', {}).get('jhub', False):
                    # ------ User removal JHub
                    self.log.debug("uuidcode={} - Remove User from JHub Resources".format(uuidcode))
                    await self.default_handle_logout()
                    await self.handle_logout()
                    spawner_dic = list(user.spawners.keys())
                    for server_name in spawner_dic:
                        user.spawners[server_name]._stop_pending = True
                        async def stop():
                            """Stop the server
            
                            1. remove it from the proxy
                            2. stop the server
                            3. notice that it stopped
                            """
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
                                user.spawners[server_name]._stop_future = None
                                user.spawners[server_name]._stop_pending = False
            
                        future = user.spawners[server_name]._stop_future = asyncio.ensure_future(stop())
                        
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
                # ------ User Removal JHub finished ----
                self.set_header('Content-Type', 'text/plain')
                self.set_status(204)
            except:
                self.log.exception("Bugfix required")
                self.set_status(500)
                self.write("Something went wrong. Please contact support to remove your account.")
                self.flush()
        else:
            self.set_header('Content-Type', 'text/plain')
            self.set_status(404)
            raise web.HTTPError(404, 'User not found. Please logout, login and try again. If this does not help contact support.')

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

class J4J_2FAHandler(BaseHandler):
    @web.authenticated
    async def get(self):
        user = self.current_user
        html = self.render_template(
                    '2FA.html',
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