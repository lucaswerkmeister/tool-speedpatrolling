# SpeedPatrolling

[This tool](https://speedpatrolling.toolforge.org/) helps Wikidata editors to patrol recent changes.

For more information,
please see the tool’s [on-wiki documentation page](https://www.wikidata.org/wiki/User:Lucas_Werkmeister/SpeedPatrolling).

## Toolforge setup

On Wikimedia Toolforge, this tool runs under the `speedpatrolling` tool name,
using the [Toolforge Components Service](https://wikitech.wikimedia.org/wiki/Help:Toolforge/Deploy_your_tool) to coordinate
building a container with the [Toolforge Build Service](https://wikitech.wikimedia.org/wiki/Help:Toolforge/Build_Service)
and then deploying that for the webservice and background runner.
The components configuration is in the `toolforge.yaml` file.

To start a new deployment,
run the following command on Toolforge after becoming the tool account:

```sh
toolforge components deployment create
```

This should automatically kick off an image build and restart the webservice at the end.

### Details and troubleshooting

To inspect the overall deployment status, run:

```sh
toolforge components deployment show
```

To debug the image build step, it may be useful to trigger an image build explicitly –
you can add `--ref=foobar` to build from the `foobar` branch instead of the `main` branch:

```sh
toolforge build start https://gitlab.wikimedia.org/toolforge-repos/speedpatrolling
```

The web frontent is a Flask WSGI app using gunicorn,
and runs as the `speedpatrolling` job,
which you may inspect with commands like these:

```sh
toolforge jobs show speedpatrolling
toolforge jobs logs speedpatrolling
kubectl get deployment speedpatrolling
kubectl exec -it deployment/speedpatrolling -- bash
```

### Configuration

The tool reads configuration from both the `config.yaml` file (if it exists)
and from any environment variables starting with `TOOL_*`.
The config file is more convenient for local development;
the environment variables are used on Toolforge:
list them with `toolforge envvars list`.
Nested dicts are specified with envvar names where `__` separates the key components,
so that e.g. the following are equivalent:

```sh
toolforge envvars create TOOL_OAUTH__CONSUMER_KEY 271b735e0cf895694f2ee7a3ae7a2dbc
```

```yaml
OAUTH:
    CONSUMER_KEY: 271b735e0cf895694f2ee7a3ae7a2dbc
```

For the available configuration variables, see the `config.yaml.example` file.

### Update

To update the tool, build a new version of the image as described above,
then restart the webservice:

```sh
toolforge build start --use-latest-versions https://gitlab.wikimedia.org/toolforge-repos/speedpatrolling
webservice restart
```

## Local development setup

You can also run the tool locally, which is much more convenient for development
(for example, Flask will automatically reload the application any time you save a file).

```
git clone https://gitlab.wikimedia.org/toolforge-repos/speedpatrolling.git
cd speedpatrolling
pip3 install -r requirements.txt -r dev-requirements.txt
flask --debug run
```

If you want, you can do this inside some virtualenv too.

Note that your possibilities to work on this tool are rather limited
unless you request your own OAuth consumer and configure it in a `config.yaml` file –
without OAuth credentials, the tool cannot even load a list of unpatrolled changes.

## Contributing

To send a patch, you can submit a
[merge request on GitLab](https://gitlab.wikimedia.org/toolforge-repos/speedpatrolling) or a
[pull request on GitHub](https://github.com/lucaswerkmeister/tool-speedpatrolling).
(E-mail / patch-based workflows are also acceptable.)

## License

The code in this repository is released under the AGPL v3, as provided in the `LICENSE` file.
