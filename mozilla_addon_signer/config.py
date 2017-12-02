import configparser

from mozilla_addon_signer import CONFIG_PATH


class Config(object):
    _path = None

    def __init__(self, path):
        self.config = configparser.ConfigParser()
        self.path = path

    @property
    def path(self):
        return self._path

    @path.setter
    def path(self, value):
        if value != self._path:
            self._path = value
            with open(self._path, 'a+') as f:
                f.seek(0)
                self.config.read_file(f)

    @staticmethod
    def _parse_key(key):
        keys = key.split('.', 1)
        if len(keys) < 2:
            raise KeyError()
        return keys

    def get(self, key, default=None):
        keys = self._parse_key(key)

        try:
            value = self.config[keys[0]][keys[1]]
        except KeyError:
            return default

        return value

    def set(self, key, value, delete_none=True):
        keys = self._parse_key(key)

        if not keys[0] in self.config:
            self.config[keys[0]] = {}

        if value is None and self.has(key):
            self.delete(key)
        elif value is not None:
            self.config[keys[0]][keys[1]] = value

    def delete(self, key):
        keys = self._parse_key(key)
        del self.config[keys[0]][keys[1]]

    def has(self, key):
        keys = self._parse_key(key)
        try:
            return keys[1] in self.config[keys[0]]
        except KeyError:
            return False

    def save(self):
        with open(self.path, 'w') as f:
            self.config.write(f)


try:
    config = Config(CONFIG_PATH)
except FileNotFoundError:
    config = Config(None)
