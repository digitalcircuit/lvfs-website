#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2018 Richard Hughes <richard@hughsie.com>
#
# SPDX-License-Identifier: GPL-2.0+

from flask import request, url_for, redirect, flash, g, render_template
from flask_login import login_required

from lvfs import app, db

from .models import Issue, Condition, Report, Firmware
from .util import _error_internal, _error_permission_denied

@app.route('/lvfs/issue/all')
@login_required
def issue_all():

    # security check
    if not g.user.check_acl('@view-issues'):
        return _error_permission_denied('Unable to view issues')

    # only show issues with the correct group_id
    issues = []
    for issue in db.session.query(Issue).order_by(Issue.priority.desc()).all():
        if issue.check_acl('@view'):
            issues.append(issue)
    return render_template('issue-list.html',
                           category='firmware',
                           issues=issues)

@app.route('/lvfs/issue/add', methods=['POST'])
@login_required
def issue_add():

    # security check
    if not Issue().check_acl('@create'):
        return _error_permission_denied('Unable to add report')

    # ensure has enough data
    for key in ['url']:
        if key not in request.form:
            return _error_internal('No %s form data found!', key)

    # already exists
    if db.session.query(Issue).\
            filter(Issue.url == request.form['url']).first():
        flash('Failed to add issue: The URL already exists', 'info')
        return redirect(url_for('.issue_all'))

    # add issue
    issue = Issue(url=request.form['url'], vendor_id=g.user.vendor_id)
    db.session.add(issue)
    db.session.commit()
    flash('Added issue', 'info')
    return redirect(url_for('.issue_details', issue_id=issue.issue_id))

@app.route('/lvfs/issue/<issue_id>/condition/add', methods=['POST'])
@login_required
def issue_condition_add(issue_id):

    # ensure has enough data
    for key in ['key', 'value', 'compare']:
        if key not in request.form:
            return _error_internal('No %s form data found!' % key)

    # security check
    issue = db.session.query(Issue).\
                filter(Issue.issue_id == issue_id).first()
    if not issue:
        flash('No issue found', 'info')
        return redirect(url_for('.issue_conditions', issue_id=issue_id))
    if not issue.check_acl('@modify'):
        return _error_permission_denied('Unable to add condition to report')

    # already exists
    if db.session.query(Condition).\
            filter(Condition.key == request.form['key']).\
            filter(Condition.issue_id == issue_id).first():
        flash('Failed to add condition to issue: Key %s already exists' % request.form['key'], 'info')
        return redirect(url_for('.issue_conditions', issue_id=issue_id))

    # add condition
    db.session.add(Condition(issue_id,
                             request.form['key'],
                             request.form['value'],
                             request.form['compare']))
    db.session.commit()
    flash('Added condition', 'info')
    return redirect(url_for('.issue_conditions', issue_id=issue_id))

@app.route('/lvfs/issue/<issue_id>/condition/<int:condition_id>/delete')
@login_required
def issue_condition_delete(issue_id, condition_id):

    # disable issue
    issue = db.session.query(Issue).\
                filter(Issue.issue_id == issue_id).first()
    if not issue:
        flash('No issue found', 'info')
        return redirect(url_for('.issue_all'))

    # security check
    if not issue.check_acl('@modify'):
        return _error_permission_denied('Unable to delete condition from report')

    # get issue
    condition = db.session.query(Condition).\
            filter(Condition.issue_id == issue_id).\
            filter(Condition.condition_id == condition_id).first()
    if not condition:
        flash('No condition found', 'info')
        return redirect(url_for('.issue_all'))

    # delete
    issue.enabled = False
    db.session.delete(condition)
    db.session.commit()
    flash('Deleted condition, and disabled issue for safety', 'info')
    return redirect(url_for('.issue_conditions', issue_id=condition.issue_id))

@app.route('/lvfs/issue/<int:issue_id>/delete')
@login_required
def issue_delete(issue_id):

    # get issue
    issue = db.session.query(Issue).\
            filter(Issue.issue_id == issue_id).first()
    if not issue:
        flash('No issue found', 'info')
        return redirect(url_for('.issue_all'))

    # security check
    if not issue.check_acl('@modify'):
        return _error_permission_denied('Unable to delete report')

    # delete
    for condition in issue.conditions:
        db.session.delete(condition)
    db.session.delete(issue)
    db.session.commit()
    flash('Deleted issue', 'info')
    return redirect(url_for('.issue_all'))

def _issue_fix_report_failures(issue):

    # process each report
    change_cnt = 0
    for report in db.session.query(Report).all():

        # already has a report
        if report.issue_id != 0:
            continue

        # it matches the new issue
        data = report.to_flat_dict()
        if not issue.matches(data):
            continue

        # check we can apply changes to this firmware
        fw = db.session.query(Firmware).\
                filter(Firmware.firmware_id == report.firmware_id).first()
        if not fw.check_acl('@delete'):
            continue

        # fix issue ID so we look better in the analytics pages
        report.issue_id = issue.issue_id
        change_cnt += 1

    # save changes
    if change_cnt:
        db.session.commit()

    # return number of changes
    return change_cnt

@app.route('/lvfs/issue/<int:issue_id>/modify', methods=['POST'])
@login_required
def issue_modify(issue_id):

    # find issue
    issue = db.session.query(Issue).\
                filter(Issue.issue_id == issue_id).first()
    if not issue:
        flash('No issue found', 'info')
        return redirect(url_for('.issue_all'))

    # security check
    if not issue.check_acl('@modify'):
        return _error_permission_denied('Unable to modify report')

    # issue cannot be enabled if it has no conditions
    if 'enabled' in request.form and not issue.conditions:
        flash('Issue can not be enabled without conditions', 'warning')
        return redirect(url_for('.issue_details', issue_id=issue_id))

    # modify issue
    issue.enabled = bool('enabled' in request.form)
    for key in ['url', 'name', 'description']:
        if key in request.form:
            setattr(issue, key, request.form[key])
    db.session.commit()

    # if we enabled a new issue try to tag failures as known-failures
    cnt_fixed = 0
    if issue.enabled:
        cnt_fixed = _issue_fix_report_failures(issue)

    # success
    if cnt_fixed > 0:
        flash('Modified issue (fixing %i reports)' % cnt_fixed, 'info')
    else:
        flash('Modified issue', 'info')
    return redirect(url_for('.issue_details', issue_id=issue_id))

@app.route('/lvfs/issue/<int:issue_id>/details')
@login_required
def issue_details(issue_id):

    # find issue
    issue = db.session.query(Issue).\
            filter(Issue.issue_id == issue_id).first()
    if not issue:
        flash('No issue found', 'info')
        return redirect(url_for('.issue_all'))

    # security check
    if not issue.check_acl('@view'):
        return _error_permission_denied('Unable to view issue details')

    # show details
    return render_template('issue-details.html',
                           category='firmware',
                           issue=issue)

@app.route('/lvfs/issue/<int:issue_id>/priority/<op>')
@login_required
def issue_priority(issue_id, op):

    # find issue
    issue = db.session.query(Issue).\
            filter(Issue.issue_id == issue_id).first()
    if not issue:
        flash('No issue found', 'info')
        return redirect(url_for('.issue_all'))

    # security check
    if not issue.check_acl('@modify'):
        return _error_permission_denied('Unable to change issue priority')

    # change integer priority
    if op == 'up':
        issue.priority += 1
    elif op == 'down':
        issue.priority -= 1
    else:
        return _error_internal('Operation %s invalid!', op)
    db.session.commit()

    # show details
    return redirect(url_for('.issue_all'))

@app.route('/lvfs/issue/<int:issue_id>/reports')
@login_required
def issue_reports(issue_id):

    # find issue
    issue = db.session.query(Issue).\
            filter(Issue.issue_id == issue_id).first()
    if not issue:
        flash('No issue found', 'info')
        return redirect(url_for('.issue_all'))

    # security check
    if not issue.check_acl('@view'):
        return _error_permission_denied('Unable to view issue reports')

    # check firmware details are available to this user, and check if it matches
    reports = []
    reports_hidden = []
    reports_cnt = 0
    for report in db.session.query(Report).all():
        data = report.to_flat_dict()
        if not issue.matches(data):
            continue
        reports_cnt += 1

        # limit this to the latest 10 reports
        if reports_cnt < 10:
            fw = db.session.query(Firmware).\
                    filter(Firmware.firmware_id == report.firmware_id).first()
            if not fw.check_acl('@view'):
                reports_hidden.append(report)
                continue
            reports.append(report)

    # show reports
    return render_template('issue-reports.html',
                           category='firmware',
                           issue=issue,
                           reports=reports,
                           reports_hidden=reports_hidden,
                           reports_cnt=reports_cnt)

@app.route('/lvfs/issue/<int:issue_id>/conditions')
@login_required
def issue_conditions(issue_id):

    # find issue
    issue = db.session.query(Issue).\
            filter(Issue.issue_id == issue_id).first()
    if not issue:
        flash('No issue found', 'info')
        return redirect(url_for('.issue_all'))

    # security check
    if not issue.check_acl('@view'):
        return _error_permission_denied('Unable to view issue conditions')

    # show details
    return render_template('issue-conditions.html',
                           category='firmware',
                           issue=issue)
