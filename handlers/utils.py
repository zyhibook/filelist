#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#*************************************************
# Description : ~/xlabs/filelist/handlers/utils.py
# Version     : 2.0
# Author      : XABCLOUD.COM
#*************************************************
import asyncio
import collections
import datetime
import functools
import json
import os
import smtplib
import socket
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText
from email.utils import COMMASPACE
from email.utils import formatdate

import aiosmtplib
import numpy as np

def property_wraps(method):
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        key = f'_{method.__name__}'
        if not hasattr(self, key):
            setattr(self, key, method(self, *args, **kwargs))
        return getattr(self, key)
    return wrapper

class Dict(dict):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for key, value in self.items():
            self.__setitem__(key, value)

    def to_dict(self):
        return DictUnwrapper(self)

    def __delattr__(self, key):
        try:
            del self[key]
            return True
        except Exception:
            return False

    def __getattr__(self, key):
        try:
            return self[key]
        except Exception:
            return None

    def __setitem__(self, key, value):
        super().__setitem__(key, DictWrapper(value))

    __setattr__ = __setitem__

    def __getstate__(self):
        return self.__dict__

    def __setstate__(self, state):
        self.__dict__.update(state)


class DefaultDict(collections.defaultdict):

    def __delattr__(self, key):
        try:
            del self[key]
            return True
        except Exception:
            return False

    def __getattr__(self, key):
        return self[key]

def DictWrapper(*args, **kwargs):
    if args and len(args) == 1:
        if isinstance(args[0], collections.defaultdict):
            return DefaultDict(args[0].default_factory, args[0])
        elif isinstance(args[0], dict):
            return Dict(args[0])
        elif isinstance(args[0], (tuple, list)):
            return type(args[0])(map(DictWrapper, args[0]))
        else:
            return args[0]
    elif args:
        return type(args)(map(DictWrapper, args))
    else:
        return Dict(**kwargs)


def DictUnwrapper(doc):
    if isinstance(doc, DefaultDict):
        return collections.defaultdict(doc.default_factory, doc)
    if isinstance(doc, Dict):
        return dict(map(lambda x: (x[0], DictUnwrapper(x[1])), doc.items()))
    if isinstance(doc, (tuple, list)):
        return type(doc)(map(DictUnwrapper, doc))
    return doc


class JSONEncoder(json.encoder.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, set):
            return list(obj)
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, datetime.datetime):
            return obj.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(obj, datetime.date):
            return obj.strftime('%Y-%m-%d')
        try:
            return super().default(obj)
        except Exception:
            return str(obj)

def get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        return s.getsockname()[0]
    except Exception:
        return '127.0.0.1'
    finally:
        s.close()


class EmailBase:

    def __init__(self, sender=None, smtp=None, user=None, pwd=None):
        self.sender = sender or os.environ.get('EMAIL_SENDER')
        self.smtp = smtp or os.environ.get('EMAIL_SMTP')
        self.user = user or os.environ.get('EMAIL_USER')
        self.pwd = pwd or os.environ.get('EMAIL_PWD')

    def pack(self, receivers, title=None, content=None, files=None, cc=None):
        msg = MIMEMultipart()

        if content:
            mime = MIMEText(content, 'html', 'utf-8')
            msg.attach(mime)

        if files:
            if isinstance(files, (str, bytes)):
                files = [files]
            for i, fname in enumerate(files):
                att = MIMEApplication(open(fname, 'rb').read())
                att.add_header('Content-ID', f'<{i}>')
                att.add_header('X-Attachment-Id', str(i))
                att.add_header('Content-Type', 'application/octet-stream')
                att.add_header('Content-Disposition', 'attachment', filename=('gbk','',os.path.basename(fname)))
                msg.attach(att)

        if cc:
            if not isinstance(cc, list):
                cc = [cc]
            msg['cc'] = COMMASPACE.join(cc)

        msg['subject'] = title
        msg['date'] = formatdate(localtime=True)
        msg['from'] = self.sender
        if not isinstance(receivers, list):
            receivers = [receivers]
        msg['to'] = COMMASPACE.join(receivers)
        return msg


class Email(EmailBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = smtplib.SMTP()
        # self.client = smtplib.SMTP('localhost')
        # self.sender = self.client.local_hostname

    def send(self, *args, **kwargs):
        msg = self.pack(*args, **kwargs)
        self.client.connect()
        self.client.docmd('ehlo', self.smtp)
        self.client.login(self.user, self.pwd)
        self.client.send_message(msg)
        self.client.quit()

class AioEmail(EmailBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = aiosmtplib.SMTP(port=465,timeout=810,hostname=self.smtp,use_tls=True)
        # self.client = smtplib.SMTP('localhost')
        # self.sender = self.client.hostname
    try:
        async def send(self, *args, **kwargs):
            msg = self.pack(*args, **kwargs)
            await self.client.connect()
            await self.client.login(self.user,self.pwd)
            await self.client.send_message(msg)
            await self.client.quit()
    except:
        pass
