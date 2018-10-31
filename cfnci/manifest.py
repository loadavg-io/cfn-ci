import json


class Manifest(object):
    def __init__(self, path='cfn-manifest.json'):
        self.__dict__['path'] = path
        self.__dict__['manifest'] = None
        self._load()

    def _load(self):
        try:
            with open(self.path, 'r') as manifest_file:
                self.__dict__['manifest'] = json.load(manifest_file)
        except FileNotFoundError:
            self.__dict__['manifest'] = {}

    def save(self):
        with open(self.path, 'w') as manifest_file:
            json.dump(self.manifest, manifest_file, indent=2)

    def __getattr__(self, key):
        try:
            return super().__getattr__(key)
        except AttributeError:
            try:
                return self.manifest[key]
            except KeyError:
                raise AttributeError(key)

    def __setattr__(self, key, value):
        self.manifest[key] = value

    def __dir__(self):
        result = super().__dir__()
        result.extend(self.manifest.keys())
        return result
