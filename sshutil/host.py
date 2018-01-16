# -*- coding: utf-8 eval: (yapf-mode 1) -*-
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
import functools
import paramiko as ssh
from sshutil.cmd import shell_escape_single_quote, SSHCommand, ShellCommand
from sshutil.conn import SSHClientSession

__author__ = 'Christian Hopps'
__version__ = '1.0'
__docformat__ = "restructuredtext en"


class Host(object):
    """A Host object is either local (shell) or remote host (ssh) and provides easy access to the given
    host for running commands etc.
    """

    def __init__(self,
                 server=None,
                 port=22,
                 cwd=None,
                 username=None,
                 password=None,
                 debug=False,
                 cache=None,
                 proxycmd=None):
        """Get a 'connection' to a host (local or remote)

        :param server: The host to execute commands on `None` for using the local shell.
        :param port: The ssh port to use.
        :param cwd: The directory commands should execute from.
        :param username: The username to authenticate with if `None` getpass.get_user() is used.
        :param password: The password or public key to authenticate with.
                         If `None` given will also try using an SSH agent.
        :type password: str or ssh.PKey
        :param debug: True to enable debug level logging.
        :param cache: A connection cache to use.
        :type cache: SSHConnectionCache
        :param proxycmd: Proxy command to use when making the ssh connection.
        """

        self.sftp = None
        self.sftp_session = None
        self.cwd = cwd
        if server:
            self.cmd_class = functools.partial(
                SSHCommand,
                host=server,
                port=port,
                username=username,
                password=password,
                debug=debug,
                cache=cache,
                proxycmd=proxycmd)
            self.session_class = functools.partial(
                SSHClientSession,
                host=server,
                port=port,
                username=username,
                password=password,
                debug=debug,
                cache=cache,
                proxycmd=proxycmd)
        else:
            self.cmd_class = functools.partial(ShellCommand, debug=debug)
            self.session_class = None
            # XXX we'd really like to pretend to be connected to localhost without
            # actually requiring ssh be functional for connect to localhost.

        if not self.cwd:
            self.cwd = self.cmd_class("pwd").run().strip()

    def _get_sftp(self):
        if self.sftp is None:
            self.sftp_session = self.session_class(subsystem="sftp")
            try:
                self.sftp = ssh.sftp_client.SFTPClient(self.sftp_session.chan)
            except Exception as unused:
                pass
                # if debug:
                #     import pdb
                #     pdb.set_trace()
            self.sftp.chdir(self.cwd)
        return self.sftp

    def _get_cmd(self, command):
        return "bash -c 'cd {} && {}'".format(self.cwd, shell_escape_single_quote(command))

    def run_status_stderr(self, command):
        """Run the command returning exit code, stdout and stderr.

        :return: (returncode, stdout, stderr)

        >>> host = Host()
        >>> status, output, error = host.run_status_stderr("ls -d /etc")
        >>> status
        0
        >>> print(output, end="")
        /etc
        >>> print(error, end="")
        >>> status, output, error = host.run_status_stderr("grep foobar doesnt-exist")
        >>> status
        2
        >>> print(output, end="")
        >>>
        >>> print(error, end="")
        grep: doesnt-exist: No such file or directory
        """
        return self.cmd_class(self._get_cmd(command)).run_status_stderr()

    def run_status(self, command):
        """Run a command, return exitcode and stdout.

        :return: (status, stdout)
        """
        return self.cmd_class(self._get_cmd(command)).run_status()

    def run_stderr(self, command):
        """Run a command, return stdout and stderr,

        :return: (stdout, stderr)
        :raises: CalledProcessError
        """
        return self.cmd_class(self._get_cmd(command)).run_stderr()

    def run(self, command):
        """Run a command, return stdout.

        :return: stdout
        :raises: CalledProcessError
        """

        return self.cmd_class(self._get_cmd(command)).run()

    def copy_to(self, localfile, remotefile):
        if self.session_class:
            sftp = self._get_sftp()
            sftp.put(localfile, remotefile)
        else:
            # XXX Invoke local version
            pass
