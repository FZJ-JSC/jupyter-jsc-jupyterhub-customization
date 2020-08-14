'''
Created on May 10, 2019

@author: kreuzer
'''

import asyncio
import json
import os
import psycopg2
import requests
import subprocess
import time
import uuid

from contextlib import closing
from datetime import datetime, timedelta
from tornado import gen, web

from j4j_spawner.file_loads import get_token

from jupyterhub.apihandlers.base import APIHandler
from jupyterhub.handlers.base import BaseHandler
from jupyterhub.handlers.login import LogoutHandler
from jupyterhub.utils import maybe_future, admin_only, new_token
from jupyterhub import orm

from jupyterhub.metrics import RUNNING_SERVERS, SERVER_STOP_DURATION_SECONDS, ServerStopStatus
from jupyterhub.apihandlers.users import admin_or_self



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

class J4J_2FAAPIHandler(APIHandler):
    @admin_or_self
    async def post(self, name):
        user = self.current_user
        if user is None:
            raise web.HTTPError(403)
        if user.name != name:
            raise web.HTTPError(403)
        uuidcode = uuid.uuid4().hex
        await user.authenticator.update_mem(user, uuidcode)
        self.log.info("uuidcode={} - action=request2fa - Remove User from 2FA optional group: {}".format(uuidcode, user.name))
        send2fa_config_path = user.authenticator.send2fa_config_path
        with open(send2fa_config_path, 'r') as f:
            send2fa_config = json.load(f)
        code = uuid.uuid4().hex
        generated = datetime.now()
        unit = ''
        value = ''
        if send2fa_config.get('timedelta', {}).get('unit', 'default') == 'default' or send2fa_config.get('timedelta', {}).get('unit', 'default') == 'hours':
            expired = generated + timedelta(hours=send2fa_config.get('timedelta', {}).get('value', 2))
            unit = 'hours'
            value = send2fa_config.get('timedelta', {}).get('value', 2)
        elif send2fa_config.get('timedelta', {}).get('unit', 'default') == 'days':
            expired = generated + timedelta(days=send2fa_config.get('timedelta', {}).get('value', 1))
            unit = 'days'
            value = send2fa_config.get('timedelta', {}).get('value', 1)
        elif send2fa_config.get('timedelta', {}).get('unit', 'default') == 'minutes':
            expired = generated + timedelta(minutes=send2fa_config.get('timedelta', {}).get('value', 30))
            unit = 'minutes'
            value = send2fa_config.get('timedelta', {}).get('value', 30)
        else:
            expired = generated + timedelta(hours=2)
            unit = 'hours'
            value = 2
        generated_s = generated.strftime('%Y-%m-%d-%H:%M:%S')
        expired_s = expired.strftime('%Y-%m-%d-%H:%M:%S')
        path = user.authenticator.database_json_path
        with open(path, 'r') as f:
            database = json.load(f)
        with closing(psycopg2.connect(host=database.get('host'),
                                      port=database.get('port'),
                                      user=database.get('user'),
                                      password=database.get('password'),
                                      database=database.get('database'))) as con: # auto closes
            with closing(con.cursor()) as cur: # auto closes
                with con: # auto commit
                    cmd = "INSERT INTO send2fa (username, code, generated, expired) VALUES (%s, %s, %s, %s)"
                    self.log.info("Execute: {}".format(cmd))
                    cur.execute(cmd, (name,
                                      code,
                                      generated_s,
                                      expired_s
                                      ))
        if 'script' not in send2fa_config.keys() or 'python3' not in send2fa_config.keys():
            self.log.error("script or python3 not defined in {}".format(send2fa_config_path))
            self.set_status(500)
        else:
            cmd = [send2fa_config.get('python3'),
                   send2fa_config.get('script'),
                   user.name,
                   code,
                   unit,
                   str(value)]
            subprocess.Popen(cmd)
            self.set_status(204)

    @admin_or_self
    async def delete(self, name):
        user = self.current_user
        if user is None:
            raise web.HTTPError(403)
        if user.name != name:
            raise web.HTTPError(403)
        if user:
            try:
                uuidcode = uuid.uuid4().hex
                await user.authenticator.update_mem(user, uuidcode)
                self.log.info("uuidcode={} - action=delete2faopt - Remove User from 2FA optional group: {}".format(uuidcode, user.name))
                unity_path = os.environ.get('UNITY_FILE', '<no unity file path defined>')
                with open(unity_path, 'r') as f:
                    unity = json.load(f)
                token_url = os.environ.get('JSCLDAP_TOKEN_URL', '<no token url defined>')
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
                if os.environ.get('2FASENDADMINMAIL', 'true').lower() == 'true':
                    send2fa_config_path = user.authenticator.send2fa_config_path
                    with open(send2fa_config_path, 'r') as f:
                        send2fa_config = json.load(f)
                    if 'adminremovescript' not in send2fa_config.keys() or 'python3' not in send2fa_config.keys():
                        self.log.error("adminremovescript or python3 not defined in {}".format(send2fa_config_path))
                        self.set_status(204)
                    else:
                        cmd = [send2fa_config.get('python3'),
                               send2fa_config.get('adminremovescript'),
                               user.name]
                        subprocess.Popen(cmd)
                        self.set_status(204)
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


class J4J_2FACodeHandler(BaseHandler):
    @web.authenticated
    async def get(self, code):
        uuidcode = uuid.uuid4().hex
        user = self.current_user
        self.log.info("uuidcode={} - action=activate2facode - user={}".format(uuidcode, user.name))
        await user.authenticator.update_mem(user, uuidcode)
        path = user.authenticator.database_json_path
        with open(path, 'r') as f:
            database = json.load(f)
        with closing(psycopg2.connect(host=database.get('host'),
                                      port=database.get('port'),
                                      user=database.get('user'),
                                      password=database.get('password'),
                                      database=database.get('database'))) as con: # auto closes
            with closing(con.cursor()) as cur: # auto closes
                with con: # auto commit
                    cmd = "SELECT generated, expired FROM send2fa WHERE code = %s AND username = %s"
                    self.log.debug("uuidcode={} - Execute: {}".format(uuidcode, cmd))
                    cur.execute(cmd, (code, user.name))
                    results = cur.fetchall()
        if len(results) > 1:
            self.log.error("uuidcode={} - Code {} is more than once in the database".format(uuidcode, code))
            html = self.render_template(
                    '2FA.html',
                    user=user,
                    code=True,
                    code_success=False,
                    code_header="2FA activation failed",
                    code_text="Please contact support to activate 2-Factor Authentication.")
            self.finish(html)
            return
        if len(results) == 0:
            self.log.error("uuidcode={} - There is no such token {}".format(uuidcode, code))
            html = self.render_template(
                    '2FA.html',
                    user=user,
                    code=True,
                    code_success=False,
                    code_header="2FA activation failed",
                    code_text="Please contact support to activate 2-Factor Authentication.")
            self.finish(html)
            return
        with closing(psycopg2.connect(host=database.get('host'),
                                      port=database.get('port'),
                                      user=database.get('user'),
                                      password=database.get('password'),
                                      database=database.get('database'))) as con: # auto closes
            with closing(con.cursor()) as cur: # auto closes
                with con: # auto commit
                    cmd = "DELETE FROM send2fa WHERE code = %s AND username = %s"
                    self.log.debug("uuidcode={} - Execute: {}".format(uuidcode, cmd))
                    cur.execute(cmd, (code, user.name))
        expired_s = results[0][1]
        expired = datetime.strptime(expired_s, '%Y-%m-%d-%H:%M:%S')
        if expired > datetime.now():
            try:
                self.log.debug("uuidcode={} - Add user to 2FA group in unity".format(uuidcode))
                unity_path = user.authenticator.unity_file
                with open(unity_path, 'r') as f:
                    unity = json.load(f)
                token_url = os.environ.get('JSCLDAP_TOKEN_URL', '<no token url defined>')
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
                html = self.render_template(
                        '2FA.html',
                        user=user,
                        code=True,
                        code_success=True,
                        code_header="2FA activation successful",
                        code_text="You'll be able to add a second factor the next time you log in.")
                self.finish(html)
                return
            except:
                self.log.exception("uuidcode={} - Unknown Error in Code2FA".format(uuidcode))
                html = self.render_template(
                        '2FA.html',
                        user=user,
                        code=True,
                        code_success=False,
                        code_header="2FA activation failed",
                        code_text="Please contact support to activate 2-Factor Authentication.")
                self.finish(html)
                return
        else:
            self.log.error("uuidcode={} - Expired code. Now: {} - Expired: {}".format(uuidcode, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), expired.strftime('%Y-%m-%d %H:%M:%S')))
            html = self.render_template(
                    '2FA.html',
                    user=user,
                    code=True,
                    code_success=False,
                    code_header="2FA activation failed",
                    code_text="The link is expired since {}. Please request a new one.".format(expired.strftime('%Y-%m-%d %H:%M:%S')))
            self.finish(html)
            return

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
