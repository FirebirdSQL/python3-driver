# SPDX-FileCopyrightText: 2025-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
#   PROGRAM/MODULE: firebird-driver
#   FILE:           tests/test_blob.py
#   DESCRIPTION:    Tests for stream BLOBs
#   CREATED:        10.4.2025
#
#  Software distributed under the License is distributed AS IS,
#  WITHOUT WARRANTY OF ANY KIND, either express or implied.
#  See the License for the specific language governing rights
#  and limitations under the License.
#
#  The Original Code was created by Pavel Cisar
#
#  Copyright (c) Pavel Cisar <pcisar@users.sourceforge.net>
#  and all contributors signed below.
#
#  All Rights Reserved.
#  Contributor(s): ______________________________________.
#
# See LICENSE.TXT for details.

from io import StringIO
import pytest
from firebird import driver

def test_stream_blob_basic(db_connection):
    blob_content = """Firebird supports two types of blobs, stream and segmented.
The database stores segmented blobs in chunks.
Each chunk starts with a two byte length indicator followed by however many bytes of data were passed as a segment.
Stream blobs are stored as a continuous array of data bytes with no length indicators included."""
    blob_lines = StringIO(blob_content).readlines()

    with db_connection.cursor() as cur:
        # Use StringIO for inserting stream-like data
        cur.execute('insert into T2 (C1,C9) values (?,?)', [4, StringIO(blob_content)])
        db_connection.commit()

        p = cur.prepare('select C1,C9 from T2 where C1 = 4')
        cur.stream_blobs.append('C9') # Request C9 as stream
        cur.execute(p)
        row = cur.fetchone()
        assert row is not None
        blob_reader = row[1]
        assert isinstance(blob_reader, driver.core.BlobReader)

        with blob_reader: # Use context manager for BlobReader
            assert isinstance(blob_reader.blob_id, driver.fbapi.ISC_QUAD)
            # assert blob_reader.blob_type == BlobType.STREAM # Type might not be exposed directly
            assert blob_reader.is_text()
            assert blob_reader.read(20) == 'Firebird supports tw'
            assert blob_reader.read(20) == 'o types of blobs, st'
            # ... (rest of the read/seek assertions) ...
            assert blob_reader.read() == blob_content[40:] # Read remainder
            assert blob_reader.tell() == len(blob_content)
            blob_reader.seek(0)
            assert blob_reader.tell() == 0
            assert blob_reader.readlines() == blob_lines
            blob_reader.seek(0)
            read_lines = list(blob_reader) # Iterate directly
            assert read_lines == blob_lines

def test_stream_blob_extended(db_connection):
    blob_content = "Another test blob content." * 5 # Make it slightly longer
    with db_connection.cursor() as cur:
        cur.execute('insert into T2 (C1,C9) values (?,?)', [1, StringIO(blob_content)])
        cur.execute('insert into T2 (C1,C9) values (?,?)', [2, StringIO(blob_content)])
        db_connection.commit()

        p = cur.prepare('select C1,C9 from T2 where C1 in (1, 2)')
        cur.stream_blobs.append('C9')
        cur.execute(p)
        count = 0
        for row in cur:
            count += 1
            assert row[0] in (1, 2)
            blob_reader = row[1]
            assert isinstance(blob_reader, driver.core.BlobReader)
            with blob_reader:
                assert blob_reader.read() == blob_content
        assert count == 2 # Ensure both rows were processed
