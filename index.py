#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#*************************************************
# Description : ~/xlabs/filelist/index.py
# Version     : 2.0
# Author      : XABCLOUD.COM
#*************************************************
import collections
import hashlib
import uuid
import datetime
import os
import threading
import time
import yaml
from pathlib import Path
from tornado.curl_httpclient import CurlAsyncHTTPClient
from tornado.options import define
from tornado.options import options

from handlers.admin import bp as bp_admin
from handlers.blueprint import Application
from handlers.db_utils import Mongo
from handlers.db_utils import Redis
from handlers.disk import bp as bp_disk
from handlers.user import bp as bp_user
from handlers.utils import AioEmail

config = yaml.load(open('config.yml'),Loader=yaml.FullLoader)
define("root", default=config['root'], help="upload server root", type=str)
define("all", default=False, help="show all files", type=bool)

class Application(Application):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.root = Path(options.root).expanduser()
        self.db = Mongo('dl')
        self.rd = Redis()
        self.email = AioEmail(smtp='smtp.exmail.qq.com', sender='service@filelist.cn', user='service@filelist.cn', pwd="xGrS"+"2Kch"[::-1]+"Hx4y95mF")
        self.http = CurlAsyncHTTPClient()
        self.cache = collections.defaultdict(dict)
        self.config = config

    def scan_dir(self, root, dirname):
        root = Path(root)
        if not root.exists():
            return []

        st_mtime = root.stat().st_mtime
        if root in self.cache[dirname] and st_mtime == self.cache[dirname][root][0]:
            entries = self.cache[dirname][root][1]
        else:
            entries = []
            for item in root.iterdir():
                if not item.exists():
                    continue
                if not options.all and item.name.startswith('.'):
                    continue
                path = item.relative_to(self.root / dirname)
                stat = item.stat()
                filesize = stat.st_size
                if filesize / (1024 * 1024 * 1024.0) >= 1:
                    size = '%.1f GB' % (filesize / (1024 * 1024 * 1024.0))
                elif filesize / (1024 * 1024.0) >= 1:
                    size = '%.1f MB' % (filesize / (1024 * 1024.0))
                else:
                    size = '%.1f KB' % (filesize / 1024.0)
                mtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime))
                sum = int(self.rd.get("FILELIST:"+str(path))) if self.rd.exists("FILELIST:"+str(path)) else 0
                entries.append([path, mtime, size, item.is_dir(),sum])
            entries.sort(key=lambda x: str(x[1]).lower(), reverse=True)
            self.cache[dirname][root] = [st_mtime, entries]
        return entries

    def scan_thread(self):
        for root, _, _ in os.walk(self.path):
            if root == '.':
                self.scan_dir(root)
            else:
                root = root.lstrip('./')
                if not options.all and any([p.startswith('.') for p in root.split('/')]):
                    continue
                self.scan_dir(root)

    def scan(self):
        t = threading.Thread(target=self.scan_thread)
        t.daemon = True
        t.start()

def main():
    db = Mongo('dl')
    admin = yaml.load(open('config.yml'),Loader=yaml.FullLoader)['admin']
    doc = {
        'username': 'admin',
        'password': hashlib.md5(f"ywgx_{admin['password']}".encode()).hexdigest(),
        'token': uuid.uuid4().hex,
        'created_at': datetime.datetime.now().replace(microsecond=0),
        'email': admin['email'],
        'admin': True,
    }
    if not db.users.find_one({'username': 'admin', 'email': admin['email']}):
        db.users.update_one({'username': 'admin'}, {'$set': doc}, upsert=True)
    app = Application()
    app.register(bp_disk, bp_user, bp_admin)
    app.run()

if __name__ == '__main__':
    main()
