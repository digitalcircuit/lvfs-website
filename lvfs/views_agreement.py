#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2018 Richard Hughes <richard@hughsie.com>
#
# SPDX-License-Identifier: GPL-2.0+

from flask import request, flash, url_for, redirect, render_template, g
from flask_login import login_required

from lvfs import app, db

from .util import admin_login_required
from .models import Agreement

@app.route('/lvfs/agreement')
@app.route('/lvfs/agreement/<int:agreement_id>')
@login_required
def agreement_show(agreement_id=None):
    # find the right version
    if agreement_id:
        agreement = db.session.query(Agreement).\
                        filter(Agreement.agreement_id == agreement_id).first()
    else:
        agreement = db.session.query(Agreement).\
                        order_by(Agreement.version.desc()).first()
    if not agreement:
        agreement = Agreement(version=1, text='No agreement text found')
        db.session.add(agreement)
        db.session.commit()
    return render_template('agreement.html', agreement=agreement)

@app.route('/lvfs/agreement/list')
@login_required
@admin_login_required
def agreement_list():

    # find the right version
    agreements = db.session.query(Agreement).all()
    return render_template('agreement-list.html',
                           category='admin',
                           agreements=agreements)

@app.route('/lvfs/agreement/create')
@login_required
@admin_login_required
def agreement_create():

    # create something
    agreement = Agreement(version=1, text='New agreement text')
    db.session.add(agreement)
    db.session.commit()
    flash('Created agreement')
    return redirect(url_for('.agreement_modify', agreement_id=agreement.agreement_id))

@app.route('/lvfs/agreement/<int:agreement_id>/accept')
@login_required
def agreement_confirm(agreement_id):

    # find the object for the ID
    agreement = db.session.query(Agreement).\
                    filter(Agreement.agreement_id == agreement_id).first()
    if not agreement:
        flash('No argreement ID found', 'warning')
        return redirect(url_for('.agreement_show'))

    # already agreed to a newer version
    if g.user.agreement and g.user.agreement.version >= agreement.version:
        flash('You already agreed to this version of the agreement', 'info')
        return redirect(url_for('.agreement_show'))

    # save this
    g.user.agreement_id = agreement.agreement_id
    db.session.commit()
    flash('Recorded acceptance of the agreement')
    return redirect(url_for('.upload'))

@app.route('/lvfs/agreement/decline')
@app.route('/lvfs/agreement/<int:agreement_id>/decline')
@login_required
def agreement_decline(agreement_id=None):
    g.user.agreement_id = None
    db.session.commit()
    flash('Recorded decline of the agreement %i' % agreement_id)
    return redirect(url_for('.index'))

@app.route('/lvfs/agreement/<int:agreement_id>/modify', methods=['GET', 'POST'])
@login_required
@admin_login_required
def agreement_modify(agreement_id):

    # match
    agreement = db.session.query(Agreement).\
                    filter(Agreement.agreement_id == agreement_id).first()
    if not agreement:
        flash('No agreement with that ID', 'danger')
        return redirect(url_for('.agreement_list'))

    # view
    if request.method != 'POST':
        return render_template('agreement-admin.html', agreement=agreement)

    # change
    if 'version' in request.form:
        agreement.version = int(request.form['version'])
    if 'text' in request.form:
        agreement.text = request.form['text']
    db.session.commit()
    flash('Modified agreement')
    return redirect(url_for('.agreement_modify', agreement_id=agreement_id))

@app.route('/lvfs/agreement/<int:agreement_id>/delete')
@login_required
@admin_login_required
def agreement_delete(agreement_id):

    # match
    agreement = db.session.query(Agreement).\
                    filter(Agreement.agreement_id == agreement_id).first()
    if not agreement:
        flash('No agreement with that ID', 'danger')
        return redirect(url_for('.agreement_list'))

    # change
    db.session.delete(agreement)
    db.session.commit()
    flash('Deleted agreement')
    return redirect(url_for('.agreement_list'))
