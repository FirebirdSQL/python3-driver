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

from __future__ import annotations
from enum import Enum, auto
from firebird.base.hooks import register_class, get_callbacks, add_hook, hook_manager

class APIHook(Enum):
    """Firebird API hooks.
    """
    LOADED = auto()

class ConnectionHook(Enum):
    """Connection hooks.
    """
    ATTACH_REQUEST = auto()
    ATTACHED = auto()
    DETACH_REQUEST = auto()
    CLOSED = auto()
    DROPPED = auto()

class ServerHook(Enum):
    """Server hooks.
    """
    ATTACHED = auto()
