import requests


class BugzillaAPI(object):
    api_base = 'https://bugzilla.mozilla.org/rest'

    def __init__(self, api_key=None):
        self.session = requests.Session()
        if api_key:
            self.session.headers.update({'X-BUGZILLA-API-KEY': api_key})

    def get(self, url, params=None):
        res = self.session.get(self.api_base + url, params=params)
        res.raise_for_status()
        return res.json()

    def get_attachments_for_bug(self, bug_number):
        response = self.get('/bug/{}/attachment'.format(bug_number), {
            'exclude_fields': 'data'
        })
        return response.get('bugs', {}).get(str(bug_number), [])

    def get_attachment_data(self, id):
        response = self.get('/bug/attachment/{}'.format(id), {
            'include_fields': 'data'
        })
        return response.get('attachments', {}).get(str(id), {}).get('data')
