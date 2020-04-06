#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#*************************************************
# Description : ~/xlabs/filelist/handlers/disk.py
# Version     : 2.0
# Author      : XABCLOUD.COM
#*************************************************
import asyncio
import datetime
import json
import logging
import math
import os
import re
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor
from handlers.db_utils import Redis
from urllib import parse
from pathlib import Path

from bson import ObjectId
import markdown
import tornado.escape
import tornado.httpserver
import tornado.ioloop
import tornado.web
import yaml
from tornado.concurrent import run_on_executor

from .blueprint import Blueprint
from .common import BaseHandler

bp = Blueprint(__name__)
rd = Redis()


@bp.route('/')
class HomeHandler(BaseHandler):

    def get(self):
        self.redirect(f'/public')


@bp.route(r'/(public|home)')
@bp.route(r'/share/?(.*)')
class IndexHandler(tornado.web.StaticFileHandler, BaseHandler):
    executor = ThreadPoolExecutor(5)
    default = {
        'ppt.png': ['.ppt', '.pptx'],
        'word.png': ['.doc', '.docx'],
        'excel.png': ['.xls', '.xlsx'],
        'pdf.png': ['.pdf'],
        'txt.png': ['.txt'],
        'image.png': ['.png', '.jpg', '.jpeg', '.bmp', '.gif'],
        'audio.png': ['.amr', '.ogg', '.wav', '.mp3', '.flac', '.m4a'],
        'video.png': ['.rmvb', '.rm', '.mkv', '.mp4', '.avi', '.wmv'],
        'rar.png': ['.rar', '.tar', '.tgz', '.gz', '.bz2', '.bz', '.xz', '.zip', '.7z'],
        'c.png': ['.c', '.h'],
        'cpp.png': ['.cpp'],
        'python.png': ['.py', '.pyc'],
        'shell.png': ['.sh'],
        'go.png': ['.go'],
        'java.png': ['.java', '.javac', '.class', '.jar'],
        'javascript.png': ['.js'],
        'vue.png': ['.vue'],
        'html.png': ['.html'],
        'css.png': ['.css', '.less', '.sass', '.scss'],
        'json.png': ['.json', '.yml', '.yaml'],
        'markdown.png': ['.md', '.markdown'],
        'ini.png': ['.ini'],
        'db.png': ['.db', '.sql', '.dump'],
        'kindle.jpg': ['.mobi', '.awz', '.awz3'],
        'svg.jpg': ['.svg'],
        'lua.png': ['.lua'],
        'win.png': ['.exe'],
        'mac.png': ['.pkg'],
        'key.png': ['.key'],
        'pki.png': ['.crt', '.pem'],
    }
    icon = {}
    for key, value in default.items():
        for v in value:
            icon[v] = key

    def __init__(self, application, request, **kwargs):
        tornado.web.RequestHandler.__init__(self, application, request, **kwargs)
        self.f = self.get_argument('f', None)
        self.w = self.get_argument('w', None)
        self.h = self.get_argument('h', None)
        self.cache = self.app.cache
        self.logger = logging

    def initialize(self, **kwargs):
        self.default_filename = None

    def compute_etag(self):
        if hasattr(self, 'absolute_path'):
            return super().compute_etag()

    @run_on_executor
    def search(self, q):
        entries = []
        files = list(self.app.cache[self.dirname].values())
        for _, docs in files:
            for doc in docs:
                if doc[0].name.find(q) >= 0:
                    entries.append(doc)
        page, count = self.args.page, self.args.count
        self.args.total = len(entries)
        self.args.pages = int(math.ceil(len(entries) / count))
        entries = entries[(page - 1) * count:page * count]
        return entries

    @run_on_executor
    def listdir(self, path):
        entries = self.app.scan_dir(path, self.dirname)
        page, count = self.args.page, self.args.count
        self.args.total = len(entries)
        self.args.pages = int(math.ceil(len(entries) / count))
        entries = entries[(page - 1) * count:page * count]
        return entries

    def get_nodes(self, root):
        nodes = []
        dirname = self.dirname
        key = root
        if key in self.app.cache[dirname]:
            entries = self.app.cache[dirname][key][1]
            for doc in entries:
                if doc[3]:
                    nodes.append({'title': doc[0].name, 'href': f'{self.request.path}?path={doc[0]}', 'children': self.get_nodes(self.app.root / dirname / doc[0])})
                else:
                    nodes.append({'title': doc[0].name, 'href': f'{self.request.path}?path={doc[0]}'})
        return nodes

    def set_headers(self):
        super().set_headers()
        self.set_header('Pragma', 'no-cache')
        self.set_header('Cache-Control', 'no-cache')
        if self.args.f == 'download':
            self.set_header('Content-Type', 'application/octet-stream; charset=UTF-8')

    def send_html(self, html):
        self.finish(f'''<html><head>
<link href="/static/src/css/atom-one-dark.min.css" rel="stylesheet">
</head><body>{html}
<script src="/static/src/js/highlight.min.js"></script>
<script>hljs.initHighlightingOnLoad()</script>
</body></html>''')

    def init(self, mode):
        if mode == 'home' and not self.current_user:
            return self.redirect('/signin')
        if mode == 'public' and self.request.method in ['POST', 'DELETE', 'HEAD'] and not (self.current_user and self.current_user.admin):
            return self.finish({'err': 1, 'msg': '无权限'})

        self.mode = mode
        if mode in ['public', 'home']:
            name = self.get_argument('path', '').lstrip('/')
            self.dirname = self.current_user.username if mode == 'home' else 'admin'
        else:
            doc = self.app.db.share.find_one({'_id': ObjectId(mode)})
            if not (doc and doc.expired_at >= datetime.datetime.now()):
                self.app.db.share.delete_one({'_id': ObjectId(mode)})
                return self.render('message.html', msg="文件分享已过期")

            name = self.get_argument('path', doc.path).lstrip('/')
            self.dirname = doc.dirname

        self.root = self.app.root / self.dirname
        self.path = self.root / name
        if (self.path.is_file() and str(self.path.parent).find('/..') >= 0) or (not self.path.is_file() and str(self.path).find('/..') >= 0):
            raise tornado.web.HTTPError(403)
        return name

    async def get(self, mode, include_body=True):
        name = self.init(mode)
        if self._finished:
            return
        path = self.path

        if self.args.q:
            entries = await self.search(self.args.q)
            self.render('index.html', entries=entries, nodes='[]')
        elif self.args.f == 'tree':
            nodes = self.get_nodes(path)
            self.finish({'nodes': nodes})
        elif self.args.f == 'download':
            rd.incr("FILELIST:"+name)
            zh = re.compile(u'[\u4e00-\u9fa5]+')
            if zh.search(path.name):
                self.set_header('Content-Disposition', f"attachment;filename*=UTF-8''{parse.quote(path.name.encode('UTF-8'))}")
            else:
                self.set_header('Content-Disposition', f'attachment;filename={parse.quote(path.name)}')
            await super().get(name, include_body)
        elif path.is_file():
            rd.incr("FILELIST:"+name)
            if path.suffix.lower() in ['.yml', '.yaml']:
                doc = yaml.load(open(path),Loader=yaml.FullLoader)
                self.finish(doc)
            elif path.suffix.lower() in ['.md', '.markdown']:
                exts = ['markdown.extensions.extra', 'markdown.extensions.codehilite', 'markdown.extensions.tables', 'markdown.extensions.toc']
                html = markdown.markdown(path.read_text(), extensions=exts)
                self.send_html(html)
            elif path.suffix.lower() == '.ipynb':
                with tempfile.NamedTemporaryFile('w+', suffix=f'.html', delete=True) as fp:
                    command = f'jupyter nbconvert --to html --template full --output {fp.name} {path}'
                    dl = await asyncio.create_subprocess_shell(command)
                    await dl.wait()
                    self.finish(fp.read().replace('<link rel="stylesheet" href="custom.css">', ''))
            elif path.suffix.lower() in ['.md','.txt','.py','.lua','.sh', '.h', '.c', '.cpp', '.js', '.css', '.html', '.java', '.go', '.ini', '.vue','.conf','.yml','.yaml','.ipynb']:
                try:
                    self.send_html(f'''<pre><code>{ tornado.escape.xhtml_escape(path.read_text()) }</code></pre>''')
                except:
                    self.send_html(f'''<pre><code>{ tornado.escape.xhtml_escape(path.read_text(encoding='unicode_escape')) }</code></pre>''')
            elif path.suffix.lower() in ['.jpg', '.jpeg', '.ico','.bmp', '.png','.mp3', '.mp4', '.ogg', '.pdf']:
                await super().get(name, include_body)
            elif mode not in ['public', 'home']:
                zh = re.compile(u'[\u4e00-\u9fa5]+')
                if zh.search(path.name):
                    self.set_header('Content-Disposition', f"attachment;filename*=UTF-8''{parse.quote(path.name.encode('UTF-8'))}")
                else:
                    self.set_header('Content-Disposition', f'attachment;filename={parse.quote(path.name)}')
                await super().get(name, include_body)
            else:
                zh = re.compile(u'[\u4e00-\u9fa5]+')
                if zh.search(path.name):
                    self.set_header('Content-Disposition', f"attachment;filename*=UTF-8''{parse.quote(path.name.encode('UTF-8'))}")
                else:
                    self.set_header('Content-Disposition', f'attachment;filename={parse.quote(path.name)}')
                await super().get(name, include_body)
        else:
            entries = await self.listdir(path)
            nodes = self.get_nodes(path) if self.get_cookie('tree') else []
            self.render('index.html', entries=entries, nodes=json.dumps(nodes))

    async def execute(self, path):
        cwd = os.getcwd()
        os.chdir(path.parent)
        command = ''
        if path.suffix.lower() in ['.gz', '.bz2', '.xz'] and path.name.find('.tar') >= 0 or path.suffix.lower() in ['.tgz']:
            command = f'tar xf {path.name}'
        elif path.suffix.lower() in ['.gz']:
            command = f'gzip -d {path.name}'
        elif path.suffix.lower() in ['.bz2', '.bz']:
            command = f'bzip2 -d {path.name}'
        elif path.suffix.lower() in ['.zip']:
            command = f'unzip {path.name}'
        elif path.is_dir():
            command = f'tar czf {path.name}.tgz {path.name}'
        dl = await asyncio.create_subprocess_shell(command)
        code = await dl.wait()
        os.chdir(cwd)
        return code

    async def head(self, mode):
        self.init(mode)
        if self._finished:
            return

        code = await self.execute(self.path)
        self.finish(str(code))

    async def delete(self, mode):
        self.init(mode)
        if self._finished:
            return
        path1 = self.path
        path2 = Path(str(self.root)+"/"+(parse.unquote(self.request.uri.split("/"+mode+"?path=")[1])))
        path3 = Path(str(self.root)+"/"+(self.request.uri.split("/"+mode+"?path=")[1]))
        if path1.exists():
            if path1.is_file():
                path1.unlink()
                rd.delete("FILELIST:"+str(path1).split(str(self.root)+"/")[1])
            else:
                shutil.rmtree(path1,ignore_errors=True)
                for e in rd.keys("FILELIST:"+str(path1).split(str(self.root)+"/")[1]+"/*"):
                    rd.delete(e)
            self.finish(f'{path1} removed')
        elif path2.exists():
            if path2.is_file():
                path2.unlink()
                rd.delete("FILELIST:"+str(path2).split(str(self.root)+"/")[1])
            else:
                shutil.rmtree(path2,ignore_errors=True)
                for e in rd.keys("FILELIST:"+str(path2).split(str(self.root)+"/")[1]+"/*"):
                    rd.delete(e)
            self.finish(f'{path2} removed')
        elif path3.exists():
            if path3.is_file():
                path3.unlink()
                rd.delete("FILELIST:"+str(path3).split(str(self.root)+"/")[1])
            else:
                shutil.rmtree(path3,ignore_errors=True)
                for e in rd.keys("FILELIST:"+str(path3).split(str(self.root)+"/")[1]+"/*"):
                    rd.delete(e)
            self.finish(f'{path3} removed')
        else:
            self.finish(f'{path1} not exists')

    async def post(self, mode):
        self.init(mode)
        if self._finished:
            return
        if self.request.files:
            for items in self.request.files.values():
                for item in items:
                    filename = self.path /re.sub('[\.\+]+','.',item['filename'])
                    dirname = filename.parent
                    dirname.exists() or os.makedirs(dirname)
                    filename.write_bytes(item['body'])
            self.finish('upload success')
        else:
            self.finish('files not found')

    async def put(self, mode):
        name = self.init(mode)
        if self._finished:
            return

        action = self.get_argument('action', 'share')
        if action == 'share':
            if mode == 'public' and not (self.current_user and self.current_user.admin):
                return self.finish({'err': 1, 'msg': '需要管理员登录'})

            days = int(self.get_argument('days', 1))
            created_at = datetime.datetime.now().replace(microsecond=0)
            expired_at = created_at + datetime.timedelta(days=days)
            doc = {
                'dirname': self.dirname,
                'path': name,
                'username': self.current_user.username,
                'created_at': created_at,
                'expired_at': expired_at,
            }
            ret = self.app.db.share.insert_one(doc)
            self.finish({'err': 0, 'id': str(ret.inserted_id)})
        else:
            if self.current_user:
                if self.path.is_file():
                    if not self.current_user.kindle:
                        self.finish({'err': 1, 'msg': '未设置 Kindle 推送邮箱'})
                    elif self.path.stat().st_size > 52428800:
                        self.finish({'err': 1, 'msg': '附件需要小于50MB'})
                    else:
                        await self.app.email.send(self.current_user.kindle, 'convert', files=str(self.path))
                        self.finish({'err': 0})
                else:
                    self.finish({'err': 1, 'msg': '不是文件'})
            else:
                self.finish({'err': 1, 'msg': '请先登录'})
