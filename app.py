# -*- coding: utf-8 -*-

import flask
import mwapi
import mwoauth
import os
import random
import requests
import requests_oauthlib
import string
import toolforge
import yaml


app = flask.Flask(__name__)

app.before_request(toolforge.redirect_to_https)

toolforge.set_user_agent('speedpatrolling', email='mail@lucaswerkmeister.de')
user_agent = requests.utils.default_user_agent()

__dir__ = os.path.dirname(__file__)
try:
    with open(os.path.join(__dir__, 'config.yaml')) as config_file:
        app.config.update(yaml.safe_load(config_file))
except FileNotFoundError:
    print('config.yaml file not found, assuming local development setup')
    app.secret_key = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(64))

if 'oauth' in app.config:
    consumer_token = mwoauth.ConsumerToken(app.config['oauth']['consumer_key'], app.config['oauth']['consumer_secret'])


@app.template_global()
def csrf_token():
    if 'csrf_token' not in flask.session:
        flask.session['csrf_token'] = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(64))
    return flask.session['csrf_token']

@app.template_global()
def form_value(name):
    if 'repeat_form' in flask.g and name in flask.request.form:
        return (flask.Markup(r' value="') +
                flask.Markup.escape(flask.request.form[name]) +
                flask.Markup(r'" '))
    else:
        return flask.Markup()

@app.template_global()
def form_attributes(name):
    return (flask.Markup(r' id="') +
            flask.Markup.escape(name) +
            flask.Markup(r'" name="') +
            flask.Markup.escape(name) +
            flask.Markup(r'" ') +
            form_value(name))

@app.template_filter()
def user_link(user_name):
    return (flask.Markup(r'<a href="https://www.wikidata.org/wiki/User:') +
            flask.Markup.escape(user_name.replace(' ', '_')) +
            flask.Markup(r'">') +
            flask.Markup(r'<bdi>') +
            flask.Markup.escape(user_name) +
            flask.Markup(r'</bdi>') +
            flask.Markup(r'</a>'))

@app.template_global()
def user_logged_in():
    return 'oauth_access_token' in flask.session

@app.template_global()
def authentication_area():
    if 'oauth' not in app.config:
        return flask.Markup()

    if not user_logged_in():
        return (flask.Markup(r'<a id="login" class="navbar-text" href="') +
                flask.Markup.escape(flask.url_for('login')) +
                flask.Markup(r'">Log in</a>'))

    access_token = mwoauth.AccessToken(**flask.session['oauth_access_token'])
    identity = mwoauth.identify('https://www.wikidata.org/w/index.php',
                                consumer_token,
                                access_token)

    return (flask.Markup(r'<span class="navbar-text">Logged in as ') +
            user_link(identity['username']) +
            flask.Markup(r'</span>'))

def authenticated_session():
    if 'oauth_access_token' in flask.session:
        access_token = mwoauth.AccessToken(**flask.session['oauth_access_token'])
        auth = requests_oauthlib.OAuth1(client_key=consumer_token.key, client_secret=consumer_token.secret,
                                        resource_owner_key=access_token.key, resource_owner_secret=access_token.secret)
        return mwapi.Session(host='https://www.wikidata.org', auth=auth, user_agent=user_agent)
    else:
        return None

def unpatrolled_changes():
    session = authenticated_session()
    for result in session.get(action='query',
                              list='recentchanges',
                              rcprop=['ids'],
                              rcshow='unpatrolled',
                              rclimit='max',
                              continuation=True):
        for change in result['query']['recentchanges']:
            yield change['revid']

def user_rights():
    session = authenticated_session()
    if session is None:
        return []
    return session.get(action='query',
                       meta='userinfo',
                       uiprop='rights')['query']['userinfo']['rights']

@app.template_global()
def user_can_patrol():
    return 'patrol' in user_rights()

@app.template_global()
def user_can_rollback():
    return 'rollback' in user_rights()


@app.route('/')
def index():
    return flask.render_template('index.html')

@app.route('/diff/')
def any_diff():
    if not user_logged_in():
        return flask.redirect(flask.url_for('login'))
    for id in unpatrolled_changes():
        skipped_ids = flask.session.get('skipped_ids', [])
        if id in skipped_ids:
            continue
        return flask.redirect(flask.url_for('diff', id=id))

@app.route('/diff/<int:id>/')
def diff(id):
    return flask.render_template('diff.html',
                                 id=id)

@app.route('/diff/<int:id>/skip', methods=['POST'])
def diff_skip(id):
    if not submitted_request_valid():
        return 'CSRF error', 400
    skipped_ids = flask.session.get('skipped_ids', [])
    skipped_ids.append(id)
    flask.session['skipped_ids'] = skipped_ids
    return flask.redirect(flask.url_for('any_diff'))

@app.route('/diff/<int:id>/patrol', methods=['POST'])
def diff_patrol(id):
    if not submitted_request_valid():
        return 'CSRF error', 400
    session = authenticated_session()
    token = session.get(action='query',
                        meta='tokens',
                        type='patrol')['query']['tokens']['patroltoken']
    session.post(action='patrol',
                 revid=id,
                 token=token)
    return flask.redirect(flask.url_for('any_diff'))

@app.route('/diff/<int:id>/rollback', methods=['POST'])
def diff_rollback(id):
    if not submitted_request_valid():
        return 'CSRF error', 400
    session = authenticated_session()
    token = session.get(action='query',
                        meta='tokens',
                        type='rollback')['query']['tokens']['rollbacktoken']
    results = session.get(action='query',
                          revids=[str(id)],
                          prop='revisions',
                          rvprop='user',
                          formatversion='2')
    for page in results['query']['pages']:
        pageid = page['pageid']
        user = page['revisions'][0]['user']
        break
    session.post(action='rollback',
                 pageid=pageid,
                 user=user,
                 token=token)
    return flask.redirect(flask.url_for('any_diff'))

@app.route('/login')
def login():
    redirect, request_token = mwoauth.initiate('https://www.wikidata.org/w/index.php', consumer_token, user_agent=user_agent)
    flask.session['oauth_request_token'] = dict(zip(request_token._fields, request_token))
    return flask.redirect(redirect)

@app.route('/oauth/callback')
def oauth_callback():
    request_token = mwoauth.RequestToken(**flask.session['oauth_request_token'])
    access_token = mwoauth.complete('https://www.wikidata.org/w/index.php', consumer_token, request_token, flask.request.query_string, user_agent=user_agent)
    flask.session['oauth_access_token'] = dict(zip(access_token._fields, access_token))
    return flask.redirect(flask.url_for('index'))


def full_url(endpoint, **kwargs):
    scheme=flask.request.headers.get('X-Forwarded-Proto', 'http')
    return flask.url_for(endpoint, _external=True, _scheme=scheme, **kwargs)

def submitted_request_valid():
    """Check whether a submitted POST request is valid.

    If this method returns False, the request might have been issued
    by an attacker as part of a Cross-Site Request Forgery attack;
    callers MUST NOT process the request in that case.
    """
    real_token = flask.session.pop('csrf_token', None)
    submitted_token = flask.request.form.get('csrf_token', None)
    if not real_token:
        # we never expected a POST
        return False
    if not submitted_token:
        # token got lost or attacker did not supply it
        return False
    if submitted_token != real_token:
        # incorrect token (could be outdated or incorrectly forged)
        return False
    if not flask.request.referrer.startswith(full_url('index')):
        # correct token but not coming from the correct page; for
        # example, JS running on https://tools.wmflabs.org/tool-a is
        # allowed to access https://tools.wmflabs.org/tool-b and
        # extract CSRF tokens from it (since both of these pages are
        # hosted on the https://tools.wmflabs.org domain), so checking
        # the Referer header is our only protection against attackers
        # from other Toolforge tools
        return False
    return True

@app.after_request
def denyFrame(response):
    """Disallow embedding the tool’s pages in other websites.

    If other websites can embed this tool’s pages, e. g. in <iframe>s,
    other tools hosted on tools.wmflabs.org can send arbitrary web
    requests from this tool’s context, bypassing the referrer-based
    CSRF protection.
    """
    response.headers['X-Frame-Options'] = 'deny'
    return response
