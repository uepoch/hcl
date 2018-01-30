import os
import json

def get_name(filename):
    return os.path.splitext(filename)[0]

def get_extension(filename):
    return os.path.splitext(filename)[1]

def read_file(pathname):
    with open(pathname, 'r') as desc:
        return desc.read()

def read_json_file(pathname):
    content = read_file(pathname)
    return json.loads(content)

def browse_folder(_dir, action):
    for f in os.listdir(_dir):
        if f.startswith("."):
            # don't take hidden file
            continue
        action(f)