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

from __future__ import absolute_import, print_function, unicode_literals

import Queue
import glob
import os
import shutil
import time
from spouts.abstracts import AbstractSpout
from modules.errors import ImproperlyConfigured
from modules.utils import MailItem


MAIL_PATH = "path"


class FilesMailSpout(AbstractSpout):
    outputs = ['mail_path', 'mail_server', 'mailbox',
               'priority', 'trust', 'kind_data']

    def initialize(self, stormconf, context):
        super(FilesMailSpout, self).initialize(stormconf, context)

        self._check_conf()
        self._queue = Queue.PriorityQueue()
        self._queue_tail = set()
        self._count = 1
        self._what = self.conf["post_processing"]["what"].lower()
        self._waiting_sleep = float(self.conf["waiting.sleep"])
        self._load_mails()

    def _check_conf(self):
        self._where = self.conf["post_processing"]["where"]
        if not self._where:
            raise ImproperlyConfigured(
                "where in '{}' is NOT configurated".format(
                    self.spouts_conf))

        self._where_failed = self.conf["post_processing"]["where.failed"]
        if not self._where_failed:
            raise ImproperlyConfigured(
                "where.failed in '{}' is NOT configurated".format(
                    self.spouts_conf))

        if not os.path.exists(self._where):
            os.makedirs(self._where)

        if not os.path.exists(self._where_failed):
            os.makedirs(self._where_failed)

    def _load_mails(self):
        """This function load mails in a priority queue. """

        self.log("Loading new mails for spout")

        mailboxes = self.conf['mailboxes']
        for k, v in mailboxes.iteritems():
            if not os.path.exists(v['path_mails']):
                raise ImproperlyConfigured(
                    "Mail path '{}' does NOT exist".format(v['path_mails']))

            all_mails = set(glob.glob(os.path.join(
                v['path_mails'], '{}'.format(v['files_pattern']))))

            # put new mails in queue
            for mail in (all_mails - self._queue_tail):
                self._queue_tail.add(mail)
                self._queue.put(
                    MailItem(
                        filename=mail,
                        mail_server=v['mail_server'],
                        mailbox=k,
                        priority=v['priority'],
                        trust=v['trust_string']))

    def next_tuple(self):

        # If queue is not empty
        if not self._queue.empty():

            # After reload.mails mails put new items in priority queue
            if (self._count % self.conf['reload.mails']):
                self._count += 1

            # put new mails in priority queue
            else:
                # Reload general spout conf
                self._conf_loader()

                # Reload new mails
                self._load_mails()
                self._count = 1

            mail = self._queue.get(block=True)
            self.emit([
                mail.filename,
                mail.mail_server,
                mail.mailbox,
                mail.priority,
                mail.trust,
                MAIL_PATH],
                tup_id=mail.filename)

        # If queue is empty
        else:
            self.log("Queue mails is empty", "debug")
            time.sleep(self._waiting_sleep)
            self._load_mails()

    def ack(self, tup_id):
        """Acknowledge tup_id, that is the path_mail. """

        if os.path.exists(tup_id):
            if self._what == "remove":
                os.remove(tup_id)
            else:
                shutil.move(tup_id, self._where)

        try:
            # Remove from tail analyzed mail
            self._queue.task_done()
            self._queue_tail.remove(tup_id)
            self.log("Mails to process: {}".format(len(self._queue_tail)))
        except KeyError:
            pass

    def fail(self, tup_id):
        self.log("Mail '{}' failed".format(tup_id))

        if os.path.exists(tup_id):
            shutil.move(tup_id, self._where_failed)

        self.ack(tup_id)
