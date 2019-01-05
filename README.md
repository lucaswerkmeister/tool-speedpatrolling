# SpeedPatrolling

[This tool](https://tools.wmflabs.org/speedpatrolling/) helps Wikidata editors to patrol recent changes.

For more information,
please see the tool’s [on-wiki documentation page](https://www.wikidata.org/wiki/User:Lucas_Werkmeister/SpeedPatrolling).

## Toolforge setup

On Wikimedia Toolforge, this tool runs under the `speedpatrolling` tool name.
Source code resides in `~/www/python/src/`,
a virtual environment is set up in `~/www/python/venv/`,
logs end up in `~/uwsgi.log`.

If the web service is not running for some reason, run the following command:
```
webservice --backend=kubernetes python start
```
If it’s acting up, try the same command with `restart` instead of `start`.

To update the service, run the following commands after becoming the tool account:
```
source ~/www/python/venv/bin/activate
cd ~/www/python/src
git fetch
git diff @ @{u} # inspect changes
git merge --ff-only @{u}
pip3 install -r requirements.txt
webservice --backend=kubernetes python restart
```

## Local development setup

You can also run the tool locally, which is much more convenient for development
(for example, Flask will automatically reload the application any time you save a file).

```
git clone https://phabricator.wikimedia.org/source/tool-speedpatrolling.git
cd tool-speedpatrolling
pip3 install -r requirements.txt
FLASK_APP=app.py FLASK_ENV=development flask run
```

If you want, you can do this inside some virtualenv too.

Note that your possibilities to work on this tool are rather limited
unless you request your own OAuth consumer and configure it in a `config.yaml` file –
without OAuth credentials, the tool cannot even load a list of unpatrolled changes.

## License

The code in this repository is released under the AGPL v3, as provided in the `LICENSE` file.
