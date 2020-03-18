#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#*************************************************
# Description : ~/xlabs/filelist/handlers/db_utils.py
# Version     : 2.0
# Author      : XABCLOUD.COM
#*************************************************
import os
from urllib.parse import quote_plus

import pymongo
import redis

from .utils import DictWrapper

__all__ = ['Mongo', 'MongoClient', 'Redis']


class Cursor(pymongo.cursor.Cursor):

    def __next__(self, *args, **kwargs):
        return DictWrapper(super(Cursor, self).next(*args, **kwargs))

    next = __next__


class Collection(pymongo.collection.Collection):

    def find(self, *args, **kwargs):
        kwargs.update({'no_cursor_timeout': True})
        return Cursor(self, *args, **kwargs)

    def find_one(self, *args, **kwargs):
        return DictWrapper(super(Collection, self).find_one(*args, **kwargs))

    def find_one_and_update(self, *args, **kwargs):
        return DictWrapper(super(Collection, self).find_one_and_update(*args, **kwargs))

    def find_one_and_delete(self, *args, **kwargs):
        return DictWrapper(super(Collection, self).find_one_and_delete(*args, **kwargs))


class Database(pymongo.database.Database):

    def __getitem__(self, name):
        return Collection(self, name)

    def _fix_outgoing(self, son, collection):
        return DictWrapper(super(Database, self)._fix_outgoing(son, collection))

    def get_id(self, collection):
        ret = self.ids.find_one_and_update({'_id': collection},
                                           {'$inc': {'seq': 1}},
                                           upsert=True,
                                           projection={'seq': True, '_id': False},
                                           return_document=True)
        return ret['seq']


class MongoClient(pymongo.MongoClient):

    def __init__(self, host='localhost', port=27017, user=None, pwd=None, **kwargs):
        if os.environ.get("env") != "debug":
            host = os.environ.get("MONGO_HOST", host)
            port = os.environ.get("MONGO_PORT", port)
            user = os.environ.get("MONGO_USER", user)
            pwd = os.environ.get("MONGO_PWD", pwd)

        if os.environ.get("env") != "debug" and os.environ.get('MONGO_URI'):
            uri = os.environ['MONGO_URI']
        elif user and pwd:
            uri = f"mongodb://{quote_plus(user)}:{quote_plus(pwd)}@{host}:{port}"
        else:
            uri = f"mongodb://{host}:{port}"
        super(MongoClient, self).__init__(uri, **kwargs)

    def __getitem__(self, name):
        return Database(self, name)

    def __getattr__(self, name):
        return Database(self, name)


class Mongo(Database):

    def __init__(self, db='test', **kwargs):
        client = MongoClient(**kwargs)
        super(Mongo, self).__init__(client, db)


class Redis(redis.StrictRedis):

    def __init__(self, host='127.0.0.1', port=6379, pwd='io', db=0, **kwargs):
        if os.environ.get("env") != "debug":
            host = os.environ.get("REDIS_HOST", host)
            port = int(os.environ.get("REDIS_PORT", port))
            password = os.environ.get("REDIS_PWD", pwd)
            db = int(os.environ.get("REDIS_DB", db))

        kwargs.setdefault('decode_responses', True)
        pool = redis.ConnectionPool(db=db, host=host, port=port, password=password, **kwargs)
        super().__init__(connection_pool=pool)

    def clear(self, pattern='*'):
        if pattern == '*':
            self.flushdb()
        else:
            keys = [x for x in self.scan_iter(pattern)]
            if keys:
                self.delete(*keys)
