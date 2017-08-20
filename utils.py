# -*- coding: utf-8 -*-
'''
Copyright © 2017, ACM@UIUC
This file is part of the Groot Project.
The Groot Project is open source software, released under the University of
Illinois/NCSA Open Source License.  You should have received a copy of
this license in a file with the distribution.
'''

from flask import make_response, jsonify
from settings import GROOT_SERVICES_URL, GROOT_ACCESS_TOKEN
import requests
import logging
logger = logging.getLogger('groot_credits_service.utils')


def send_error(message, code=400):
    return make_response(jsonify(dict(error=message)), code)


def send_success(message, code=200):
    return make_response(jsonify(dict(message=message)), code)


def validate_netid(netid):
    # Ask user service to validate netid
    r = requests.get(
        headers={
            'Authorization': GROOT_ACCESS_TOKEN,
            'Accept': 'application/json'
        },
        url=GROOT_SERVICES_URL + '/users/{}/is_member'.format(netid)
    )
    if r.status_code != 200 or not r.json()['data']['is_member']:
        raise ValueError('Not a valid user.')
    return netid


def netid_from_token(token):
    url = '/'.join([GROOT_SERVICES_URL, 'session', token])
    headers = {
        'Authorization': GROOT_ACCESS_TOKEN,
        'Accept': 'application/json'
    }
    r = requests.get(url, headers=headers)
    if r.status_code != 200 or 'token' not in r.json():
        logger.info("Rejecting token")
        raise None
    netid = r.json().get('user')['name']
    logger.info("Authenticated %s from token" % netid)
    return netid


def check_group_membership(netid, group):
    url = '/'.join([GROOT_SERVICES_URL, 'groups', 'committees', group])
    headers = {
        'Authorization': GROOT_ACCESS_TOKEN
    }
    params = {
        'isMember': netid
    }
    r = requests.get(url, headers=headers, params=params)
    return r.json()['isValid']


def is_admin(netid):
    admin_groups = ['top4', 'admin', 'corporate']
    return any(check_group_membership(netid, g) for g in admin_groups)
