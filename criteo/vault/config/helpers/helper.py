import os
import logging
import hcl
import jinja2
import yaml

from inspect import getsource, getfullargspec
from functools import wraps

# TODO: Use glob standard package when devtools upgrade python to 3.5
import glob2

from criteo.vault.config.variables import MURPHY_MATCHER


def argument_checker(name, validator, message=""):
    def wrap(f):
        argspec = getfullargspec(f)
        arg_index = argspec.args.index(name)

        @wraps(f)
        def arg_check(*args, **kwargs):
            value = kwargs.get(name, None) or args[arg_index]
            if not validator(value):
                if message:
                    raise ValueError(message.format(name=name, value=value))
                else:
                    raise ValueError(
                        "Function {} failed with validator {} ran with {}".format(f.__name__, getsource(validator),
                                                                                  value))
            return f(*args, **kwargs)

        return arg_check

    return wrap


def go_vcs_root(test, dirs=(".git",), default=None):
    prev, test = None, os.path.abspath(test)
    while prev != test:
        if any(os.path.isdir(os.path.join(test, d)) for d in dirs):
            os.chdir(test)
            return test
        prev, test = test, os.path.abspath(os.path.join(test, os.pardir))
    if not default:
        raise Exception("Can't find root directory, please run inside the directory or give a default value")
    else:
        logging.info("Can't find VCS root. Fallbacking to {}".format(default))
    return default


def vaultify_path(file_path):
    return get_name("/".join(file_path.split("/")[1:]))


def render_template(file_path, ctx):
    path, filename = os.path.split(file_path)
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(path or './')
    ).get_template(filename).render(ctx)


def get_name(filename):
    return os.path.splitext(filename)[0]


def get_extension(filename):
    return os.path.splitext(filename)[1] if len(os.path.splitext(filename)) > 1 else ""


def read_file(pathname):
    with open(pathname, 'r') as f:
        return f.read()


def write_file(pathname, content):
    os.makedirs(os.path.dirname(pathname), exist_ok=True)
    with open(pathname, 'w') as f:
        return f.write(content)


def crawl_map(fn, *patterns, ignored_pattern=""):
    entries = []
    for pattern in patterns:
        new_entries = [x for x in glob2.glob(pattern) if
                       not (x in entries or (ignored_pattern and ignored_pattern in x))]
        for f in sorted(new_entries):
            fn(f)


def assert_valid_client(client):
    assert client.is_authenticated()
    assert client.is_initialized()
    assert not client.is_sealed()


def add_policy_to_ldap_entity_file(file_path, *policy_names, prefix_cleanup=None):
    entity = parse(file_path) if os.path.exists(file_path) else None
    if not entity or "policies" not in entity or not entity["policies"]:
        write_file(file_path, hcl.dumps({"policies": policy_names}))
        logging.debug("Successfully created %s and assigned %s to it", file_path, policy_names)
    else:
        if prefix_cleanup:
            entity["policies"] = [x for x in entity["policies"] if not x.startswith(prefix_cleanup)]
        entity["policies"] += policy_names
        entity["policies"] = list(set(entity["policies"]))
        write_file(file_path, hcl.dumps(entity, indent=4))
        logging.debug("Updated %s and assigned %s to it", file_path, policy_names)


def get_parser(extension):
    # HCL being a superset of json(like yaml), no need for json package
    if extension == ".json" or extension == ".hcl":
        return hcl
    if extension == ".yaml" or extension == ".yml":
        return yaml
    return None


def parse(filename):
    with open(filename) as f:
        parser = get_parser(get_extension(filename))
        if parser is not None:
            return parser.load(f)
        else:
            return {'value': f.read()}


def sanitize_murphy_description(description=""):
    return MURPHY_MATCHER.sub("", description, count=1)
