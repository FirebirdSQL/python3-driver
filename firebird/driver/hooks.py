#coding:utf-8
#
# PROGRAM/MODULE: firebird-driver
# FILE:           firebird/driver/hooks.py
# DESCRIPTION:    Drivers hooks
# CREATED:        24.3.2020
#
# The contents of this file are subject to the MIT License
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Copyright (c) 2020 Firebird Project (www.firebirdsql.org)
# All Rights Reserved.
#
# Contributor(s): Pavel Císař (original code)
#                 ______________________________________

"""firebird-driver - Drivers hooks


"""

import typing as t
from enum import Enum

class HookType(Enum):
    API_LOADED = 1
    DATABASE_ATTACHED = 2
    DATABASE_ATTACH_REQUEST = 3
    DATABASE_DETACH_REQUEST = 4
    DATABASE_CLOSED = 5
    DATABASE_DROPPED = 6
    SERVICE_ATTACHED = 7

class HookManager:
    """Hook manager object.
"""
    def __init__(self):
        self.hooks = {}
    def add_hook(self, hook_type: HookType, func: t.Callable):
        """Instals hook function for specified hook_type.

        Args:
            hook_type (int): One from `HOOK_*` constants
            func (callable): Hook routine to be installed

        .. important::

            Routine must have a signature required for given hook type.
            However it's not checked when hook is installed, and any
            issue will lead to run-time error when hook routine is executed.
        """
        self.hooks.setdefault(hook_type, list()).append(func)

    def remove_hook(self, hook_type: HookType, func: t.Callable):
        """Uninstalls previously installed hook function for
        specified hook_type.

        Args:
            hook_type (int): One from `HOOK_*` constants
            func (callable): Hook routine to be uninstalled

        If hook routine wasn't previously installed, it does nothing.
        """
        try:
            self.hooks.get(hook_type, list()).remove(func)
        except:
            pass
    def get_hooks(self, hook_type: HookType):
        """Returns list of installed hook routines for specified hook_type.

        Args:
            hook_type (int): One from `HOOK_*` constants

        Returns:
            List of installed hook routines.
        """
        return self.hooks.get(hook_type, list())


hooks = HookManager()

