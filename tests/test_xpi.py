import os
import pytest

from mozilla_addon_signer.xpi import XPI

from . import TESTS_DIR


INVALID_XPI_PATH = os.path.join(TESTS_DIR, 'xpi', 'invalid.xpi')
NO_ID_XPI_PATH = os.path.join(TESTS_DIR, 'xpi', 'no-id.xpi')
UNSIGNED_BOOTSTRAPPED_PATH = os.path.join(TESTS_DIR, 'xpi', 'empty@mozilla.com-1.0.0.xpi')
SIGNED_BOOTSTRAPPED_PATH = os.path.join(TESTS_DIR, 'xpi', 'empty@mozilla.com-1.0.0-signed.xpi')
UNSIGNED_WEBX_PATH = os.path.join(TESTS_DIR, 'xpi', 'nothing-web-extension@mozilla.com-1.0.xpi')
SIGNED_WEBX_PATH = os.path.join(TESTS_DIR, 'xpi',
                                'nothing-web-extension@mozilla.com-1.0-signed.xpi')


class TestXPI(object):
    def test_does_not_exist(self):
        with pytest.raises(XPI.DoesNotExist):
            XPI('not-a-real-file.xpi')

    def test_bad_zip_file(self, tmpdir):
        f = tmpdir.join('not-a-zip.txt')
        f.write('some text')

        with pytest.raises(XPI.BadZipfile):
            XPI(str(f))

    def test_invalid(self):
        with pytest.raises(XPI.InvalidXPI):
            XPI(INVALID_XPI_PATH)

    def test_missing_id(self):
        with pytest.raises(XPI.MissingID):
            XPI(NO_ID_XPI_PATH)

    def test_sha256sum(self):
        xpi = XPI(UNSIGNED_BOOTSTRAPPED_PATH)
        assert xpi.sha256sum == 'd5379e26f2b118c97136846dbbe50bd1c68aad434cf9ce0258b96f424030406e'

    def test_load_bootstrapped(self):
        xpi = XPI(UNSIGNED_BOOTSTRAPPED_PATH)
        assert xpi.type == XPI.BOOTSTRAPPED_ADDON
        assert xpi.id == 'empty@mozilla.com'
        assert xpi.version == '1.0.0'

    def test_load_webextension(self):
        xpi = XPI(UNSIGNED_WEBX_PATH)
        assert xpi.type == XPI.WEB_EXTENSION
        assert xpi.id == 'nothing-web-extension@mozilla.com'
        assert xpi.version == '1.0'

    def test_is_signed(self):
        xpi = XPI(SIGNED_BOOTSTRAPPED_PATH)
        assert xpi.is_signed

    def test_suggested_filename(self):
        xpi = XPI(UNSIGNED_BOOTSTRAPPED_PATH)
        assert xpi.suggested_filename() == 'empty@mozilla.com-1.0.0.xpi'
        assert xpi.suggested_filename(mark_signed=True) == 'empty@mozilla.com-1.0.0-signed.xpi'

        xpi = XPI(SIGNED_BOOTSTRAPPED_PATH)
        assert xpi.suggested_filename() == 'empty@mozilla.com-1.0.0-signed.xpi'
