# -*- coding: utf-8 eval: (yapf-mode 1) -*-
#
# December 14 2016, Christian Hopps <chopps@gmail.com>
#
# Copyright (c) 2015, Deutsche Telekom AG.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
from __future__ import absolute_import, division, unicode_literals, print_function, nested_scopes
import errno
import getpass
import logging
import socket
import time
from sshutil.cache import SSHConnectionCache, SSHNoConnectionCache
import sshutil.conn as conn
import sshutil.server as server

logger = logging.getLogger(__name__)
ssh_server = None
NC_PORT = None
SERVER_DEBUG = True
CLIENT_DEBUG = True


def setup_module(module):
    del module  # unused
    global ssh_server

    logging.basicConfig(level=logging.DEBUG)

    if ssh_server is not None:
        logger.error("XXX Called setup_module multiple times")
    else:
        server_ctl = server.SSHUserPassController(username=getpass.getuser(), password="admin")
        ssh_server = server.SSHServer(server_ctl, host_key="tests/host_key", debug=SERVER_DEBUG)
        setup_module.init = True


setup_module.init = False


def cleanup_module(module):
    del module  # unused
    if setup_module.init:
        logger.info("Deleting server")

        # Delete the server so that we don't end up with a bunch of logging going on on exit.
        global ssh_server
        del ssh_server
        ssh_server = None

        # now let's force garbage collection to try and get rid of other objects.
        logger.info("Garbage collecting")
        import gc
        gc.collect()


def test_close():
    session = conn.SSHSession(
        "127.0.0.1", password="admin", port=ssh_server.port, debug=CLIENT_DEBUG)
    assert session
    session.close()


def test_multi_session():
    logger.debug("Starting multi-session test")
    sessions = []
    for unused in range(0, 10):
        sessions.append(
            conn.SSHSession(
                "127.0.0.1", password="admin", port=ssh_server.port, debug=CLIENT_DEBUG))
    logger.debug("Multi-session test complete")


def wait_port_open(addr, timeout):
    now = time.time()
    expire = now + timeout

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        while time.time() < expire:
            if sock.connect_ex(addr) == 0:
                return
            time.sleep(.1)
        raise Exception("{} never opened".format(addr))
    finally:
        sock.close()


def _test_server_close(cache):
    server_ctl = server.SSHUserPassController(username=getpass.getuser(), password="admin")
    port = None

    # Find an open reservable port
    test_port_can_start = 10000
    for port in range(test_port_can_start, test_port_can_start + 100):
        try:
            logger.info("Create server on port %d", port)
            ns = server.SSHServer(
                server_ctl, port=port, host_key="tests/host_key", debug=SERVER_DEBUG)
            break
        except socket.error as error:
            logger.info("Got exception: %s %d %d", str(error), error.errno, errno.EADDRINUSE)
            if error.errno != errno.EADDRINUSE:
                raise
    else:
        raise error

    wait_port_open(("127.0.0.1", port))

    logger.info("Connect to server on port %d", port)
    session = conn.SSHSession("127.0.0.1", password="admin", port=port, debug=CLIENT_DEBUG)
    session.close()

    # force closing of cached client sessions
    cache.flush()

    logger.debug("Closing")
    ns.close()
    logger.debug("Joining")
    ns.join()

    # import time
    # time.sleep(.1)

    # Now iterate checking that we can open on the port after cleanup, making sure our cleanup happened
    for i in range(0, 10):
        logger.debug("Starting %d iteration", i)
        ns = server.SSHServer(server_ctl, port=port, host_key="tests/host_key", debug=SERVER_DEBUG)

        wait_port_open(("127.0.0.1", port))

        logger.info("Connect to server on port %d", port)
        session = conn.SSHSession("127.0.0.1", password="admin", port=port, debug=CLIENT_DEBUG)
        session.close()
        # force closing of cached client sessions
        cache.flush()

        logger.debug("Closing")
        ns.close()
        logger.debug("Joining")
        ns.join()

    logger.debug("Test Complete")


def test_server_close_no_cache():
    _test_server_close(SSHNoConnectionCache())


def test_server_close_cache():
    _test_server_close(SSHConnectionCache("test multi open cache"))


def _test_multi_open(client_cache):

    logger.info("Create Server")
    server_ctl = server.SSHUserPassController(username=getpass.getuser(), password="admin")
    ns = server.SSHServer(server_ctl, port=NC_PORT, host_key="tests/host_key", debug=SERVER_DEBUG)
    port = ns.port

    logger.info("Open sessions")
    sessions = [
        conn.SSHSession(
            "127.0.0.1", password="admin", port=port, debug=CLIENT_DEBUG, cache=client_cache)
        for unused in range(0, 25)
    ]

    logger.info("Close sessions")
    for session in sessions:
        session.close()

    session = conn.SSHSession("127.0.0.1", password="admin", port=port, debug=CLIENT_DEBUG)

    # These should be cached
    logger.info("Re-opening")
    sessions = [
        conn.SSHSession("127.0.0.1", password="admin", port=port, debug=CLIENT_DEBUG)
        for unused in range(0, 25)
    ]

    logger.info("Re-closeing")
    for session in sessions:
        session.close()
    logger.info("Flushing socket cache")
    client_cache.flush()

    # These should be cached
    logger.info("Re-re-opening")
    sessions = [
        conn.SSHSession("127.0.0.1", password="admin", port=port, debug=CLIENT_DEBUG)
        for unused in range(0, 25)
    ]

    logger.info("Re-re-closing")
    for session in sessions:
        session.close()

    # force closing of cached client sessions
    logger.info("Flushing socket cache")
    client_cache.flush()

    # Close down the server and join it to make sure it's closed
    logger.info("Closing server")
    ns.close()
    logger.info("Joining server")
    ns.join()

    # Delete the server so that we don't end up with a bunch of logging going on on exit.
    del ns
    del server_ctl


def test_multi_open_no_cache():
    _test_multi_open(SSHNoConnectionCache())


def test_multi_open_cache():
    _test_multi_open(SSHConnectionCache("test multi open cache"))


__author__ = 'Christian Hopps'
__date__ = 'February 17 2015'
__version__ = '1.0'
__docformat__ = "restructuredtext en"

__author__ = 'Christian Hopps'
__date__ = 'December 14 2016'
__version__ = '1.0'
__docformat__ = "restructuredtext en"
