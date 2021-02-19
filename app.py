# -*- coding: utf-8 -*-

import bs4
import decorator
import flask
import ipaddress
import mwapi
import mwoauth
import os
import random
import requests
import requests_oauthlib
import string
import toolforge
import yaml

import ids
import scripts
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


def log(type, message):
    if app.config.get('DEBUG_' + type, False):
        print('[%s] %s' % (type, message))


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

def is_ip_address(val):
    try:
        ipaddress.ip_address(val)
        return True
    except ValueError:
        return False

@app.template_filter()
def user_link(user_name):
    if is_ip_address(user_name):
        user_link_prefix = 'https://www.wikidata.org/wiki/Special:Contributions/'
    else:
        user_link_prefix = 'https://www.wikidata.org/wiki/User:'
    return (flask.Markup(r'<a href="') +
            flask.Markup(user_link_prefix) +
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

    session = authenticated_session()
    if session is None:
        return (flask.Markup(r'<a id="login" class="navbar-text" href="') +
                flask.Markup.escape(flask.url_for('login')) +
                flask.Markup(r'">Log in</a>'))

    userinfo = get_userinfo()
    return (flask.Markup(r'<span class="navbar-text"><span class="d-none d-sm-inline">Logged in as </span>') +
            user_link(userinfo['name']) +
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
def any_session():
    return authenticated_session() or mwapi.Session(host='https://www.wikidata.org', user_agent=user_agent)

@memoize
def get_userinfo():
    session = authenticated_session()
    if session is None:
        return None
    return session.get(action='query',
                       meta='userinfo',
                       uiprop=['rights'])['query']['userinfo']


def user_rights():
    userinfo = get_userinfo()
    if userinfo is None:
        return []
    return userinfo['rights']

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
    del scripts['Common']
    del scripts['Inherited']
    if flask.request.method == 'POST':
        if not submitted_request_valid():
            return 'CSRF error', 400
        flask.session['supported_scripts'] = [script for script in flask.request.form.getlist('script') if script in scripts]
        return flask.redirect(flask.url_for('index'), code=303)
    supported_scripts = flask.session.get('supported_scripts', None)
    scripts_guessed_from_babel = False
    if supported_scripts is None:
        supported_scripts = user_scripts_from_babel()
        scripts_guessed_from_babel = True
        if 'Latin' not in supported_scripts:
            # if they use this tool, they can read Latin, even if it’s not in their Babel
            supported_scripts.append('Latin')
    for script in supported_scripts:
        scripts[script] = True
    return flask.render_template('settings.html',
                                 scripts_guessed_from_babel=scripts_guessed_from_babel,
                                 scripts=scripts)

@app.route('/diff/')
def any_diff():
    if not user_logged_in():
        return flask.redirect(flask.url_for('login'))
    skipped_rev_ids = ids.get(flask.session, 'skipped_rev_ids')
    ignored_page_ids = ids.get(flask.session, 'ignored_page_ids')
    ignored_user_fake_ids = ids.get(flask.session, 'ignored_user_fake_ids')
    supported_scripts = flask.session.get('supported_scripts')
    try:
        for rev_id in ids.unpatrolled_changes(authenticated_session()):
            if rev_id in skipped_rev_ids:
                continue
            if ids.rev_id_to_page_id(rev_id, any_session()) in ignored_page_ids:
                continue
            if ids.rev_id_to_user_fake_id(rev_id, any_session()) in ignored_user_fake_ids:
                continue
            if ids.rev_id_to_show_patrol_footer(rev_id, authenticated_session()):
                continue
            if supported_scripts is not None:
                diff_body = any_session().get(action='compare',
                                              fromrev=rev_id,
                                              torelative='prev',
                                              prop=['diff'],
                                              uselang='en',
                                              formatversion=2)['compare']['body']
                script = scripts.primary_script_of_diff(diff_body)
                if script is not None and script not in supported_scripts:
                    continue
            return flask.redirect(flask.url_for('diff', rev_id=rev_id))
    except mwapi.errors.APIError as error:
        # TODO use errorformat='html' once mwapi supports it (mediawiki-utilities/python-mwapi#34)
        info_html = any_session().get(action='parse',
                                      text=error.info,
                                      prop=['text'],
                                      wrapoutputclass=None,
                                      disablelimitreport=True,
                                      contentmodel='wikitext',
                                      formatversion=2)['parse']['text']
        return flask.render_template('permission-error.html',
                                     info=fix_markup(info_html))

@app.route('/diff/<int:rev_id>/')
def diff(rev_id):
    session = any_session()
    results = session.get(action='compare',
                          fromrev=rev_id,
                          torelative='prev',
                          prop=['title', 'user', 'parsedcomment', 'diff'],
                          formatversion=2)['compare']
    return flask.render_template('diff.html',
                                 rev_id=rev_id,
                                 title=results['totitle'],
                                 had_csrf_error=getattr(flask.g, 'had_csrf_error', False),
                                 old_user=results['fromuser'],
                                 new_user=results['touser'],
                                 old_comment=fix_markup(results['fromparsedcomment']),
                                 new_comment=fix_markup(results['toparsedcomment']),
                                 body=fix_markup(results['body']))

@app.route('/diff/<int:rev_id>/skip', methods=['POST'])
def diff_skip(rev_id):
    if not submitted_request_valid():
        return flask.redirect(flask.url_for('any_diff'))

    ids.append(flask.session, 'skipped_rev_ids', rev_id)

    user_fake_id = ids.rev_id_to_user_fake_id(rev_id, any_session())
    page_id = ids.rev_id_to_page_id(rev_id, any_session())

    if user_fake_id in ids.get(flask.session, 'skipped_user_fake_ids'):
        if user_fake_id not in ids.get(flask.session, 'acted_user_fake_ids'):
            ids.append(flask.session, 'ignored_user_fake_ids', user_fake_id)

    if page_id in ids.get(flask.session, 'skipped_page_ids'):
        if page_id not in ids.get(flask.session, 'acted_page_ids'):
            ids.append(flask.session, 'ignored_page_ids', page_id)
            if user_fake_id not in ids.get(flask.session, 'skipped_user_fake_ids'):
                ids.append(flask.session, 'skipped_user_fake_ids', user_fake_id)
    else:
        ids.append(flask.session, 'skipped_page_ids', page_id)

    return flask.redirect(flask.url_for('any_diff'))

@app.route('/diff/<int:rev_id>/patrol', methods=['POST'])
def diff_patrol(rev_id):
    if not submitted_request_valid():
        flask.g.had_csrf_error = True
        return diff(rev_id)
    session = authenticated_session()
    ids.append(flask.session, 'acted_page_ids', ids.rev_id_to_page_id(rev_id, session))
    ids.append(flask.session, 'acted_user_fake_ids', ids.rev_id_to_user_fake_id(rev_id, session))
    token = session.get(action='query',
                        meta='tokens',
                        type='patrol')['query']['tokens']['patroltoken']
    session.post(action='patrol',
                 revid=rev_id,
                 token=token)
    return flask.redirect(flask.url_for('any_diff'))

@app.route('/diff/<int:rev_id>/rollback', methods=['POST'])
def diff_rollback(rev_id):
    if not submitted_request_valid():
        flask.g.had_csrf_error = True
        return diff(rev_id)
    session = authenticated_session()
    ids.append(flask.session, 'acted_page_ids', ids.rev_id_to_page_id(rev_id, session))
    ids.append(flask.session, 'acted_user_fake_ids', ids.rev_id_to_user_fake_id(rev_id, session))
    results = session.get(action='query',
                          meta='tokens',
                          type='rollback',
                          revids=[str(rev_id)],
                          prop='revisions',
                          rvprop='user',
                          formatversion='2')
    token = results['query']['tokens']['rollbacktoken']
    page = results['query']['pages'][0]
    pageid = page['pageid']
    user = page['revisions'][0]['user']
    try:
        session.post(action='rollback',
                     pageid=pageid,
                     user=user,
                     token=token)
    except mwapi.errors.APIError as error:
        # TODO use errorformat='html' once mwapi supports it (mediawiki-utilities/python-mwapi#34)
        info_html = session.get(action='parse',
                                text=error.info,
                                prop=['text'],
                                wrapoutputclass=None,
                                disablelimitreport=True,
                                contentmodel='wikitext',
                                formatversion=2)['parse']['text']
        return flask.render_template('rollback-error.html',
                                     rev_id=rev_id,
                                     user=user,
                                     info=fix_markup(info_html))
    else:
        return flask.redirect(flask.url_for('any_diff'))

@app.route('/login')
def login():
    redirect, request_token = mwoauth.initiate('https://www.wikidata.org/w/index.php', consumer_token, user_agent=user_agent)
    flask.session['oauth_request_token'] = dict(zip(request_token._fields, request_token))
    flask.session.permanent = True
    return flask.redirect(redirect)

@app.route('/oauth/callback')
def oauth_callback():
    request_token = mwoauth.RequestToken(**flask.session.pop('oauth_request_token'))
    access_token = mwoauth.complete('https://www.wikidata.org/w/index.php', consumer_token, request_token, flask.request.query_string, user_agent=user_agent)
    flask.session['oauth_access_token'] = dict(zip(access_token._fields, access_token))
    flask.session.pop('csrf_token', None)
    return flask.redirect(flask.url_for('index'))

@app.route('/logout')
def logout():
    flask.session.clear()
    return flask.redirect(flask.url_for('index'))


def fix_markup(html):
    soup = bs4.BeautifulSoup(html, 'html.parser')
    for link in soup.select('a[href]'):
        href = link['href']
        if href.startswith('/') and not href.startswith('//'):
            link['href'] = 'https://www.wikidata.org' + href
    return flask.Markup(str(soup))

def user_scripts_from_babel():
    session = authenticated_session()
    if not session:
        return ['Latin']
    user_name = session.get(action='query',
                            meta='userinfo')['query']['userinfo']['name']
    languages = session.get(action='query',
                            meta='babel',
                            babuser=user_name)['query']['babel'].keys()
    autonyms = language_autonyms(languages)
    return scripts.scripts_of_text(char for autonym in autonyms.values() for char in autonym)

def language_autonyms(language_codes):
    wikitext = ''
    for language_code in language_codes:
        wikitext += '<span><dt>' + language_code + '</dt><dd>{{#language:' + language_code + '|' + language_code + '}}</dd></span>'
    html = any_session().get(action='parse',
                             text=wikitext,
                             contentmodel='wikitext',
                             prop=['text'],
                             wrapoutputclass='',
                             disablelimitreport=True,
                             formatversion=2)['parse']['text']
    soup = bs4.BeautifulSoup(html.strip(), 'html.parser')
    autonyms = {}
    for span in soup.contents:
        language_code = span.dt.string
        autonym = span.dd.string
        autonyms[language_code] = autonym
    return autonyms

def full_url(endpoint, **kwargs):
    scheme=flask.request.headers.get('X-Forwarded-Proto', 'http')
    return flask.url_for(endpoint, _external=True, _scheme=scheme, **kwargs)

def submitted_request_valid():
    """Check whether a submitted POST request is valid.

    If this method returns False, the request might have been issued
    by an attacker as part of a Cross-Site Request Forgery attack;
    callers MUST NOT process the request in that case.
    """
    real_token = flask.session.get('csrf_token')
    submitted_token = flask.request.form.get('csrf_token')
    if not real_token:
        # we never expected a POST
        log('CSRF', 'no real token')
        return False
    if not submitted_token:
        # token got lost or attacker did not supply it
        log('CSRF', 'no submitted token')
        return False
    if submitted_token != real_token:
        # incorrect token (could be outdated or incorrectly forged)
        log('CSRF', 'token mismatch')
        return False
    if not (flask.request.referrer or '').startswith(full_url('index')):
        # correct token but not coming from the correct page; for
        # example, JS running on https://tools.wmflabs.org/tool-a is
        # allowed to access https://tools.wmflabs.org/tool-b and
        # extract CSRF tokens from it (since both of these pages are
        # hosted on the https://tools.wmflabs.org domain), so checking
        # the Referer header is our only protection against attackers
        # from other Toolforge tools
        log('CSRF', 'referrer mismatch: should start with %s, got %s' % (full_url('index'), flask.request.referrer))
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
