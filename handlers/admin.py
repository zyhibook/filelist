#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
后台管理模块，记录用户云存储认证信息
'''

from bson import ObjectId
import tornado.web

from .common import BaseHandler
from .blueprint import Blueprint

bp = Blueprint(__name__)


@bp.route('/admin')
class AdminHandler(BaseHandler):

    @tornado.web.authenticated
    async def get(self):
        self.render('admin.html')

    @tornado.web.authenticated
    async def post(self):
        kindle = self.get_argument('kindle', '')
        if not kindle.find('@') >= 0:
            return self.finish({'err': 1, 'msg': '请设置正确的邮箱'})
        self.app.db.users.update_one({'_id': self.current_user._id}, {'$set': {'kindle': kindle}})
        self.finish({'err': 0})


@bp.route('/manage/share')
class ShareHandler(BaseHandler):

    @tornado.web.authenticated
    async def get(self):
        entries = self.query('share', query={"username": self.current_user.username})
        self.render('share.html', entries=entries)

    @tornado.web.authenticated
    async def post(self):
        id = self.get_argument('id', None)
        if not id:
            return self.finish({'err': 1, 'msg': 'id未指定'})
        self.app.db.share.delete_one({'_id': ObjectId(id)})
        self.finish({'err': 0})


@bp.route('/manage/user')
class ManageHandler(BaseHandler):

    @tornado.web.authenticated
    async def get(self):
        if not self.current_user.admin:
            raise tornado.web.HTTPError(403)
        entries = self.query('users')
        self.render('manage.html', entries=entries)

    @tornado.web.authenticated
    async def post(self):
        email_set = set([self.app.config['admin']['email'],'ywgx@xabcloud.com','ywgx@filelist.cn'])
        if not self.current_user.admin:
            return self.finish({'err': 1, 'msg': '用户无权限'})
        id = self.get_argument('id', None)
        if not id:
            return self.finish({'err': 1, 'msg': '用户未指定'})
        id = ObjectId(id)
        user = self.app.db.users.find_one({'_id': id})
        if not user:
            return self.finish({'err': 1, 'msg': '用户不存在'})
        if self.current_user.email in email_set and user._id != self.current_user._id:
            action = self.get_argument('action', None)
            if action == 'admin':
                if user.admin:
                    self.app.db.users.update_one({'_id': id}, {'$unset': {'admin': 1}})
                else:
                    self.app.db.users.update_one({'_id': id}, {'$set': {'admin': True}})
            elif action == 'delete':
                self.app.db.users.delete_one({'_id': id})
        else:
            return self.finish({'err': 1, 'msg': '用户无权限'})
        self.finish({'err': 0})
