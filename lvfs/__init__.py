#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2018 Richard Hughes <richard@hughsie.com>
#
# SPDX-License-Identifier: GPL-2.0+
#
# pylint: disable=wrong-import-position,wrong-import-order

import os
import sqlalchemy

from flask import Flask, flash, render_template, message_flashed, request, Response, g
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_mail import Mail
from flask_oauthlib.client import OAuth
from flask_sqlalchemy import SQLAlchemy
from werkzeug.local import LocalProxy

from .pluginloader import Pluginloader
from .util import _error_internal, _event_log
from .dbutils import drop_db, init_db, anonymize_db

app = Flask(__name__)
app_config_fn = os.environ.get('LVFS_APP_SETTINGS', 'custom.cfg')
if os.path.exists(os.path.join('lvfs', app_config_fn)):
    app.config.from_pyfile(app_config_fn)
else:
    app.config.from_pyfile('flaskapp.cfg')
if 'LVFS_CUSTOM_SETTINGS' in os.environ:
    app.config.from_envvar('LVFS_CUSTOM_SETTINGS')

oauth = OAuth(app)

db = SQLAlchemy(app)

mail = Mail(app)

migrate = Migrate(app, db)

@app.cli.command('initdb')
def initdb_command():
    init_db(db)

@app.cli.command('dropdb')
def dropdb_command():
    drop_db(db)

@app.cli.command('anonymizedb')
def anonymizedb_command():
    anonymize_db(db)

def flash_save_eventlog(unused_sender, message, category, **unused_extra):
    is_important = False
    if category in ['danger', 'warning']:
        is_important = True
    _event_log(str(message), is_important)

message_flashed.connect(flash_save_eventlog, app)

lm = LoginManager()
lm.init_app(app)

ploader = Pluginloader('plugins')

@app.teardown_appcontext
def shutdown_session(unused_exception=None):
    db.session.remove()

@lm.user_loader
def load_user(user_id):
    from .models import User
    g.user = db.session.query(User).filter(User.username == user_id).first()
    return g.user

@app.errorhandler(404)
def error_page_not_found(unused_msg=None):
    """ Error handler: File not found """

    # the world is a horrible place
    if request.path in ['/wp-login.php',
                        '/a2billing/common/javascript/misc.js']:
        return Response(response='bad karma', status=404, mimetype="text/plain")
    return render_template('error.html'), 404

from lvfs import views
from lvfs import views_user
from lvfs import views_device
from lvfs import views_firmware
from lvfs import views_vendor
from lvfs import views_component
from lvfs import views_telemetry
from lvfs import views_report
from lvfs import views_metadata
from lvfs import views_settings
from lvfs import views_analytics
from lvfs import views_upload
from lvfs import views_issue
from lvfs import views_search
from lvfs import views_agreement
from lvfs import views_protocol
from lvfs import views_category
from lvfs import views_tests
from lvfs import views_shard
