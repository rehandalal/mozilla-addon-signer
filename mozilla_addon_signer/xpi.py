import hashlib
import os
import tempfile
import zipfile


class XPI(object):
    _hashed = None

    class DoesNotExist(Exception):
        pass

    class BadZipfile(zipfile.BadZipfile):
        pass

    def __init__(self, path):
        if not os.path.isfile(path):
            raise XPI.DoesNotExist()

        self.path = path

        tmpdir = tempfile.mkdtemp()

        try:
            with zipfile.ZipFile(path, 'r') as zf:
                zf.extractall(tmpdir)
        except zipfile.BadZipfile:
            raise XPI.BadZipfile()

        self.certificate_path = os.path.join(tmpdir, 'META-INF', 'mozilla.rsa')
        self.is_signed = os.path.exists(self.certificate_path)

    @property
    def sha256sum(self):
        if not self._hashed:
            with self.open() as f:
                self._hashed = hashlib.sha256(f.read()).hexdigest()
        return self._hashed

    def open(self, mode='rb'):
        return open(self.path, mode)
