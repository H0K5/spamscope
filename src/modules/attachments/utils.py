#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Copyright 2016 Fedele Mantuano (https://twitter.com/fedelemantuano)

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import hashlib
import logging
import magic
import os
import patoolib
import ssdeep
import tempfile
from .exceptions import TempIOError

try:
    from functools import lru_cache
except ImportError:
    from backports.functools_lru_cache import lru_cache

log = logging.getLogger(__name__)


@lru_cache()
def fingerprints(data):
    """This function return the fingerprints of data.

    Args:
        data (string): raw data

    Returns:
        tuple: fingerprints md5, sha1, sha256, sha512, ssdeep
    """

    # md5
    md5 = hashlib.md5()
    md5.update(data)
    md5 = md5.hexdigest()

    # sha1
    sha1 = hashlib.sha1()
    sha1.update(data)
    sha1 = sha1.hexdigest()

    # sha256
    sha256 = hashlib.sha256()
    sha256.update(data)
    sha256 = sha256.hexdigest()

    # sha512
    sha512 = hashlib.sha512()
    sha512.update(data)
    sha512 = sha512.hexdigest()

    # ssdeep
    ssdeep_ = ssdeep.hash(data)

    return md5, sha1, sha256, sha512, ssdeep_


@lru_cache()
def check_archive(data, write_sample=False):
    """Check if data is an archive.

    Args:
        data (string): raw data
        write_sample (boolean): if True it writes sample on disk

    Returns:
        boolean: only True is archive (False otherwise)
                    if write_sample is False
        tuple (boolean, string): True is archive (False otherwise) and
                                    sample path
    """

    is_archive = True
    try:
        temp = tempfile.mkstemp()[1]
        with open(temp, 'wb') as f:
            f.write(data)
    except:
        raise TempIOError("Failed opening '{}' file".format(temp))

    try:
        patoolib.test_archive(temp, verbosity=-1)
    except:
        is_archive = False
    finally:
        if write_sample:
            return is_archive, temp
        else:
            os.remove(temp)
            return is_archive


@lru_cache()
def contenttype(payload):
    mime = magic.Magic(mime=True)
    return mime.from_buffer(payload)


def extension(filename):
    ext = os.path.splitext(filename)
    return ext[-1].lower() if len(ext) > 1 else None
