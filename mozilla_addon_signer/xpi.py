import hashlib
import json
import os
import tempfile
import zipfile

import untangle


class XPI(object):
    WEB_EXTENSION = 'WEB_EXTENSION'
    BOOTSTRAPPED_ADDON = 'BOOTSTRAPPED_ADDON'

    _hashed = None
    addon_data = {}
    type = WEB_EXTENSION

    class DoesNotExist(Exception):
        pass

    class BadZipfile(zipfile.BadZipfile):
        pass

    class InvalidXPI(Exception):
        pass

    class MissingID(Exception):
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

        rdf_path = os.path.join(tmpdir, 'install.rdf')
        manifest_path = os.path.join(tmpdir, 'manifest.json')

        if os.path.exists(rdf_path):
            # Bootstrapped addon
            self.type = XPI.BOOTSTRAPPED_ADDON
            install_rdf = untangle.parse(rdf_path)
            self.addon_data = install_rdf.RDF.Description
        elif os.path.exists(manifest_path):
            # Web extension
            with open(manifest_path) as f:
                manifest = json.loads(f.read())
            self.addon_data = manifest
            try:
                manifest['applications']['gecko']['id']
            except KeyError:
                raise self.MissingID()
        else:
            raise self.InvalidXPI()

    @property
    def sha256sum(self):
        if not self._hashed:
            with self.open() as f:
                self._hashed = hashlib.sha256(f.read()).hexdigest()
        return self._hashed

    @property
    def id(self):
        if self.type == XPI.BOOTSTRAPPED_ADDON:
            return self.addon_data.em_id.cdata
        else:
            return self.addon_data['applications']['gecko']['id']

    @property
    def version(self):
        if self.type == XPI.BOOTSTRAPPED_ADDON:
            return self.addon_data.em_version.cdata
        else:
            return self.addon_data.get('version')

    def suggested_filename(self, mark_signed=False):
        suffix = '-signed' if self.is_signed or mark_signed else ''
        suggested = self.id
        if self.version:
            suggested += '-{}'.format(self.version)
        return '{}{}.xpi'.format(suggested, suffix)

    def open(self, mode='rb'):
        return open(self.path, mode)
