# -*- coding: utf-8 -*-

import bs4
import decorator
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

import unicodescripts


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


@decorator.decorator
def memoize(func, *args, **kwargs):
    if args or kwargs:
        raise TypeError('only memoize functions with no arguments')
    key = '_memoize_' + func.__name__
    if key not in flask.g:
        setattr(flask.g, key, func())
    return getattr(flask.g, key)


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

    identity = identify()
    return (flask.Markup(r'<span class="navbar-text"><span class="d-none d-sm-inline">Logged in as </span>') +
            user_link(identity['username']) +
            flask.Markup(r'</span>'))

@memoize
def authenticated_session():
    if 'oauth_access_token' in flask.session:
        access_token = mwoauth.AccessToken(**flask.session['oauth_access_token'])
        auth = requests_oauthlib.OAuth1(client_key=consumer_token.key, client_secret=consumer_token.secret,
                                        resource_owner_key=access_token.key, resource_owner_secret=access_token.secret)
        return mwapi.Session(host='https://www.wikidata.org', auth=auth, user_agent=user_agent)
    else:
        return None

@memoize
def identify():
    if 'oauth_access_token' in flask.session:
        access_token = mwoauth.AccessToken(**flask.session['oauth_access_token'])
        return mwoauth.identify('https://www.wikidata.org/w/index.php',
                                consumer_token,
                                access_token)
    else:
        return None


def unpatrolled_changes():
    session = authenticated_session()
    for result in session.get(action='query',
                              list='recentchanges',
                              rcprop=['ids'],
                              rcshow='unpatrolled',
                              rctype=['edit'], # TODO consider including 'new' as well
                              rclimit='max',
                              continuation=True):
        for change in result['query']['recentchanges']:
            yield change['revid']

@memoize
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

@app.route('/settings/', methods=['GET', 'POST'])
def settings():
    scripts = dict.fromkeys(unicodescripts.all_scripts(), False)
    del(scripts['Common'])
    del(scripts['Inherited'])
    if flask.request.method == 'POST':
        if not submitted_request_valid():
            return 'CSRF error', 400
        flask.session['supported_scripts'] = [script for script in flask.request.form.getlist('script') if script in scripts]
    for script in flask.session.get('supported_scripts', ['Latin']):
        scripts[script] = True
    return flask.render_template('settings.html',
                                 scripts=scripts)

@app.route('/diff/')
def any_diff():
    if not user_logged_in():
        return flask.redirect(flask.url_for('login'))
    skipped_ids = flask.session.get('skipped_ids', [])
    skipped_ids.sort(reverse=True)
    del skipped_ids[1000:]
    flask.session['skipped_ids'] = skipped_ids
    supported_scripts = flask.session.get('supported_scripts')
    for id in unpatrolled_changes():
        if id in skipped_ids:
            continue
        if supported_scripts is not None:
            diff_body = authenticated_session().get(action='compare',
                                                    fromrev=id,
                                                    torelative='prev',
                                                    prop=['diff'],
                                                    formatversion=2)['compare']['body']
            script = primary_script_of_diff(diff_body)
            if script is not None and script not in supported_scripts:
                continue
        return flask.redirect(flask.url_for('diff', id=id))

@app.route('/diff/<int:id>/')
def diff(id):
    session = authenticated_session()
    results = session.get(action='compare',
                          fromrev=id,
                          torelative='prev',
                          prop=['title', 'user', 'parsedcomment', 'diff'],
                          formatversion=2)['compare']
    return flask.render_template('diff.html',
                                 id=id,
                                 title=results['totitle'],
                                 old_user=results['fromuser'],
                                 new_user=results['touser'],
                                 old_comment=fix_markup(results['fromparsedcomment']),
                                 new_comment=fix_markup(results['toparsedcomment']),
                                 body=fix_markup(results['body']))

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
    results = session.get(action='query',
                          meta='tokens',
                          type='rollback',
                          revids=[str(id)],
                          prop='revisions',
                          rvprop='user',
                          formatversion='2')
    token = results['query']['tokens']['rollbacktoken']
    page = results['query']['pages'][0]
    pageid = page['pageid']
    user = page['revisions'][0]['user']
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


def fix_markup(html):
    soup = bs4.BeautifulSoup(html, 'html.parser')
    for link in soup.select('a[href]'):
        href = link['href']
        if href.startswith('/') and not href.startswith('//'):
            link['href'] = 'https://www.wikidata.org' + href
    return flask.Markup(str(soup))

def primary_script_of_diff(html):
    soup = bs4.BeautifulSoup(html, 'html.parser')
    elements = [content for content in soup.contents if type(content) is bs4.Tag]
    texts = []
    for i in range(0, len(elements), 2):
        lineno = elements[i].get_text()
        if (lineno.startswith('label / ') or
            lineno.startswith('description /') or
            lineno.startswith('aliases /') or
            lineno.startswith('links /')):
            texts += (element.get_text() for element in elements[i+1].select('.diff-addedline, .diff-deletedline'))
        elif lineno.startswith('Property /') and elements[i+1].select('.wb-monolingualtext-language-name'):
            texts += (element.get_text() for element in elements[i+1].select('.wb-monolingualtext-value'))
    scripts = scripts_of_text(char for text in texts for char in text)
    if scripts:
        return scripts[0]
    else:
        return None

def scripts_of_text(text):
    scripts = {}
    for char in text:
        script = unicodescripts.script(char)
        if script not in {'Common', 'Inherited', 'Unknown'}:
            scripts[script] = scripts.get(script, 0) + 1
    common_scripts = sorted(scripts.items(), key=lambda item: item[1], reverse=True)
    return [script for script, count in common_scripts]

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
def deny_frame(response):
    """Disallow embedding the tool’s pages in other websites.

    If other websites can embed this tool’s pages, e. g. in <iframe>s,
    other tools hosted on tools.wmflabs.org can send arbitrary web
    requests from this tool’s context, bypassing the referrer-based
    CSRF protection.
    """
    response.headers['X-Frame-Options'] = 'deny'
    return response
