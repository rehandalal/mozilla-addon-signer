import hashlib
import os
import tempfile
import zipfile

import untangle


class XPI(object):
    _hashed = None
    addon_data = {}

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

        install_rdf = untangle.parse(os.path.join(tmpdir, 'install.rdf'))
        self.addon_data = install_rdf.RDF.Description

    @property
    def sha256sum(self):
        if not self._hashed:
            with self.open() as f:
                self._hashed = hashlib.sha256(f.read()).hexdigest()
        return self._hashed

    @property
    def id(self):
        return self.addon_data.em_id.cdata

    @property
    def version(self):
        return self.addon_data.em_version.cdata

    def suggested_filename(self, mark_signed=False):
        suffix = '-signed' if self.is_signed or mark_signed else ''
        return '{}-{}{}.xpi'.format(self.id, self.version, suffix)

    def open(self, mode='rb'):
        return open(self.path, mode)
