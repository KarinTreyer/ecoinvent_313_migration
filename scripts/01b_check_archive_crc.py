"""CRC-test downloaded ecoinvent 7z archives (ecoinvent_interface warned about API size metadata mismatches).

Run:  conda run -n esa_import python scripts/01b_check_archive_crc.py "<archive1.7z>" "<archive2.7z>" ...
"""

import io
import sys

import py7zr

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
for path in sys.argv[1:]:
    with py7zr.SevenZipFile(path, "r") as archive:
        bad = archive.testzip()
        print(path, "CRC test:", "OK" if bad is None else f"BAD {bad}", "members:", len(archive.getnames()))
