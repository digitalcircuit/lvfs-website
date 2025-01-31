#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 Richard Hughes <richard@hughsie.com>
#
# SPDX-License-Identifier: GPL-2.0+
#
# pylint: disable=protected-access,wrong-import-position

import os
import sys
import csv
import datetime

# allows us to run this from the project root
sys.path.append(os.path.realpath('.'))

from lvfs import db, ploader

from lvfs.models import Test, Firmware
from lvfs.pluginloader import PluginError

if __name__ == '__main__':

    now = datetime.date.today()
    fn = 'chipsec-{}.csv'.format(datetime.date.isoformat(now))
    with open(fn, 'w') as csvfile:
        fieldnames = ['filename', 'vendor', 'shards', 'msg']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        # run chipsec on each firmware file
        plugin = ploader.get_by_id('chipsec')
        for fw in db.session.query(Firmware).order_by(Firmware.firmware_id.asc()).all():
            test = Test(None)
            if fw.is_deleted:
                continue
            if not fw.remote.is_public:
                continue
            if not plugin._require_test_for_fw(fw):
                continue
            print('Processing {}: {} for {}'.format(fw.firmware_id, fw.filename, fw.vendor.group_id))
            data = {'filename' : fw.filename,
                    'vendor' : fw.vendor.group_id}
            try:
                plugin.run_test_on_fw(test, fw)
            except PluginError as e:
                print('An exception occurred', str(e))
                data['msg'] = str(e)
            else:
                data['shards'] = len(fw.md_prio.shards)

                # capture message
                msg = [attr.title for attr in test.attributes]
                data['msg'] = ','.join(msg)

                # remove the elapsed time to keep diff clean
                idx = data['msg'].find('time elapsed')
                if idx != -1:
                    data['msg'] = data['msg'][:idx].strip()

                if not len(fw.md_prio.shards):
                    print('No shards: {}'.format(data['msg']))
                else:
                    print('Got {} shards: {}'.format(len(fw.md_prio.shards), data['msg']))

            # unallocate the cached blob as it's no longer needed
            fw.blob = None
            writer.writerow(data)
