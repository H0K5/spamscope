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
import shutil
import ssdeep
import tempfile
from tika_app.tika_app import TikaApp
from virus_total_apis import PublicApi as VirusTotalPublicApi

log = logging.getLogger(__name__)


class Base64Error(ValueError):
    pass


class TempIOError(Exception):
    pass


class VirusTotalApiKeyInvalid(ValueError):
    pass


class SampleParser(object):

    def __init__(
        self,
        tika_enabled=False,
        tika_jar=None,
        tika_memory_allocation=None,
        tika_content_types=set(),
        blacklist_content_types=set(),
        virustotal_enabled=False,
        virustotal_api_key=None,
    ):
        """Initialize sample parser.
        To enable tika parsing: tika_enabled=True.
        Default server point to localhost port 9998.
        Use tika_server_endpoint to change it.
        """

        # If tika is enabled set a tika_client
        if tika_enabled:
            self._tika_client = TikaApp(
                file_jar=tika_jar,
                memory_allocation=tika_memory_allocation,
            )

        # Init Tika
        self._tika_enabled = tika_enabled
        self._tika_jar = tika_jar
        self._tika_memory_allocation = tika_memory_allocation
        self._tika_content_types = tika_content_types

        # Init VirusTotal
        self._virustotal_enabled = virustotal_enabled
        self._virustotal_api_key = virustotal_api_key

        # blacklist content type
        self._blacklist_content_types = blacklist_content_types

    @property
    def tika_enabled(self):
        return self._tika_enabled

    @property
    def tika_jar(self):
        return self._tika_jar

    @property
    def tika_memory_allocation(self):
        return self._tika_memory_allocation

    @property
    def tika_content_types(self):
        return self._tika_content_types

    @property
    def blacklist_content_types(self):
        return self._blacklist_content_types

    @property
    def virustotal_enabled(self):
        return self._virustotal_enabled

    @property
    def virustotal_api_key(self):
        return self._virustotal_api_key

    @property
    def result(self):
        return self._result

    def fingerprints_from_base64(self, data):
        """This function return the fingerprints of data from base64:
            - md5
            - sha1
            - sha256
            - sha512
            - ssdeep
        """

        try:
            data = data.decode('base64')
        except:
            raise Base64Error("Data '{}' is NOT correct".format(data))

        return self.fingerprints(data)

    def fingerprints(self, data):
        """This function return the fingerprints of data:
            - md5
            - sha1
            - sha256
            - sha512
            - ssdeep
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

    def is_archive_from_base64(self, data, write_sample=False):
        """If write_sample=False this function return only a boolean:
            True if data is a archive, else False.
        Else write_sample=True this function return a tuple:
            (is_archive, path_sample)
        Data is in base64.
        """

        try:
            data = data.decode('base64')
        except:
            raise Base64Error("Data '{}' is NOT correct".format(data))

        return self.is_archive(data, write_sample)

    def is_archive(self, data, write_sample=False):
        """If write_sample=False this function return only a boolean:
            True if data is a archive, else False.
        Else write_sample=True this function return a tuple:
            (is_archive, path_sample)
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

    def _create_sample_result(
        self,
        data,
        filename,
        mail_content_type,
        transfer_encoding,
    ):
        """ Create dict result with basic informations."""

        is_archive, file_ = self.is_archive(data, write_sample=True)
        size = os.path.getsize(file_)

        self._result = {
            'filename': filename,
            'payload': data.encode('base64'),
            'mail_content_type': mail_content_type,
            'content_transfer_encoding': transfer_encoding,
            'size': size,
            'is_archive': is_archive,
        }

        if is_archive:
            self._result['files'] = list()
            temp_dir = tempfile.mkdtemp()
            patoolib.extract_archive(file_, outdir=temp_dir, verbosity=-1)

            for path, subdirs, files in os.walk(temp_dir):
                for name in files:
                    i = os.path.join(path, name)

                    with open(i, 'rb') as f:
                        i_data = f.read()
                        i_filename = os.path.basename(i)
                        i_size = os.path.getsize(i)

                        self._result['files'].append(
                            {
                                'filename': i_filename,
                                'payload': i_data.encode('base64'),
                                'size': i_size,
                            }
                        )
            # Remove temp dir for archived files
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

        # Remove temp file system sample
        if os.path.exists(file_):
            os.remove(file_)

    def _add_fingerprints(self):
        """ Add fingerprints."""

        md5, sha1, sha256, sha512, ssdeep_ = self.fingerprints(
            self._result['payload'].decode('base64')
        )
        self._result['md5'] = md5
        self._result['sha1'] = sha1
        self._result['sha256'] = sha256
        self._result['sha512'] = sha512
        self._result['ssdeep'] = ssdeep_

        if self._result['is_archive']:
            for i in self._result['files']:
                md5, sha1, sha256, sha512, ssdeep_ = self.fingerprints(
                    i['payload'].decode('base64')
                )
                i['md5'] = md5
                i['sha1'] = sha1
                i['sha256'] = sha256
                i['sha512'] = sha512
                i['ssdeep'] = ssdeep_

    def _add_content_type(self):
        mime = magic.Magic(mime=True)
        content_type = mime.from_buffer(
            self._result['payload'].decode('base64')
        )
        self._result['Content-Type'] = content_type

        if self._result['is_archive']:
            for i in self._result['files']:
                content_type = mime.from_buffer(
                    i['payload'].decode('base64'),
                )
                # To manage blacklist content types add Content-Type to the
                # files in archive
                i['Content-Type'] = content_type

    def _add_tika_meta_data(self):
        content_type = self._result['Content-Type']

        # The Apache Tika output of archive contains the contents and metadata
        # of all archived files.
        if content_type in self.tika_content_types:
            self._result['tika'] = self._tika_client.extract_all_content(
                payload=self._result['payload'],
                convert_to_obj=True,
            )

    def _remove_content_type(self):
        """Remove from results the samples with content type in blacklist."""

        if self.blacklist_content_types:
            content_type = self._result['Content-Type']
            if content_type in self.blacklist_content_types:
                self._result = None
                return

            if self._result['is_archive']:
                self._result['files'] = [
                    i
                    for i in self._result['files']
                    if i['Content-Type'] not in self.blacklist_content_types
                ]

    def _add_virustotal_output(self):
        if not self.virustotal_api_key:
            raise VirusTotalApiKeyInvalid("Please add a VirusTotal API key!")

        vt = VirusTotalPublicApi(self.virustotal_api_key)

        sha1 = self._result['sha1']
        result = vt.get_file_report(sha1)
        if result:
            self._result['virustotal'] = result

        if self._result['is_archive']:
            for i in self._result['files']:
                i_sha1 = i['sha1']
                i_result = vt.get_file_report(i_sha1)
                if i_result:
                    i['virustotal'] = i_result

    def parse_sample(
        self,
        data,
        filename,
        mail_content_type,
        transfer_encoding,
    ):
        """Analyze sample and add metadata.
        If it's an archive, extract it and put files in a list of dictionaries.
        """

        # Basic informations without fingerprints
        self._create_sample_result(
            data,
            filename,
            mail_content_type,
            transfer_encoding,
        )

        # Add content type
        self._add_content_type()

        # Blacklist content type
        # If content type in blacklist_content_types result = None
        self._remove_content_type()

        if self._result:

            # Add fingerprints
            self._add_fingerprints()

            # Add tika meta data only for tika_content_type
            if self.tika_enabled:
                self._add_tika_meta_data()

            # Add virustotal output
            if self.virustotal_enabled:
                self._add_virustotal_output()

    def parse_sample_from_base64(
        self,
        data,
        filename,
        mail_content_type,
        transfer_encoding,
    ):
        """Analyze sample and add metadata.
        If it's a archive, extract it and put files in a list of dictionaries.
        Data is in base64.
        """

        try:
            if transfer_encoding == 'base64':
                data = data.decode('base64')
        except:
            raise Base64Error("Data '{}' is NOT correct".format(data))

        return self.parse_sample(
            data,
            filename,
            mail_content_type,
            transfer_encoding,
        )