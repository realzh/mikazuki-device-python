import tomlkit
import pathlib

config_file = pathlib.Path("config.toml")
config_file.touch()


def read(path: str, default_value=None):
    keys = path.split(".")
    doc = tomlkit.parse(config_file.read_text(encoding="utf8"))
    try:
        node = doc
        for key in keys:
            node = node[key]
        return node
    except:
        return default_value


def write(path: str, value):
    keys = path.split(".")
    doc = tomlkit.parse(config_file.read_text(encoding="utf8"))
    node = doc
    for key in keys[:-1]:
        if key not in node:
            node[key] = {}
        node = node[key]
    node[keys[-1]] = value
    config_file.write_text(tomlkit.dumps(doc), encoding="utf8")
