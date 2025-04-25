# SPDX-FileCopyrightText: 2020-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
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

"""firebird-driver - Driver Hooks

This module defines specific hook points (events) within the firebird-driver
lifecycle where custom functions can be registered and executed. These hooks
allow for extending or modifying driver behavior, logging, or monitoring.

Hooks are registered using `firebird.driver.add_hook()` or the `firebird.base.hooks.hook_manager`.
The specific signature required for each hook function and the context in which
it's called are documented within the driver methods that trigger these hooks
(primarily in `firebird.driver.core`).
"""

from __future__ import annotations

from enum import Enum, auto

from firebird.base.hooks import add_hook, get_callbacks, hook_manager, register_class


class APIHook(Enum):
    """Hooks related to the loading and initialization of the underlying Firebird client API.
    """
    #: Called after the Firebird client library has been successfully loaded and basic interfaces obtained.
    LOADED = auto()

class ConnectionHook(Enum):
    """Hooks related to the lifecycle of a database connection (attachment, detachment, dropping).
    """
    #: Called before attempting to attach to a database, allows interception or modification.
    ATTACH_REQUEST = auto()
    #: Called after a database connection (attachment) has been successfully established.
    ATTACHED = auto()
    #: Called before attempting to detach from a database, allows cancellation.
    DETACH_REQUEST = auto()
    #: Called after a database connection has been successfully closed (detached).
    CLOSED = auto()
    #: Called after a database has been successfully dropped.
    DROPPED = auto()

class ServerHook(Enum):
    """Hooks related to the lifecycle of a service manager connection.
    """
    #: Called after connecting to the Firebird service manager.
    ATTACHED = auto()
