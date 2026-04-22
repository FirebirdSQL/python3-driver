import sys
import os

from firebird.driver.fbapi import load_api
sys.path.append(os.getcwd())
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(script_dir)
from firebird.driver.core import connect_server

load_api("/home/artmkn/wspace/reps/rdb5trace/gen/Debug/firebird/lib/libfbclient.so")

with connect_server('', user='SYSDBA', password='masterkey') as srv:

    trace_session_id = srv.trace.start(config="#MESSAGETRACE\ndatabase\n{\nenabled = true\n}", name="messagetrace")
    print(trace_session_id)

    a = input()
    # K = 1
    # V = TraceSession(id=1, user='SYSDBA', timestamp=..., name=<LONG_NAME_OF_TRACE_SESSION>, flags=['active', ' trace'])
    # for k,v in srv.trace.sessions.items():
    #     if v.flags[0] == 'active':
    #         print(f"Trace {v.name}: Plugins: {v.plugins}")


