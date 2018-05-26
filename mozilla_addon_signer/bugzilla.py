import requests


BUG_NUMBER_TYPE_EXC_MESSAGE = 'Bug number must be int or str, not {}'


class BugzillaAPI(object):
    api_base = 'https://bugzilla.mozilla.org/rest'

    class APIException(Exception):
        pass

    def __init__(self, api_key=None):
        self.session = requests.Session()
        if api_key:
            self.session.headers.update({'X-BUGZILLA-API-KEY': api_key})

    def request(self, method, endpoint, params=None, data=None, json=None):
        url = self.api_base + endpoint
        res = self.session.request(method, url, params=params, json=json, data=data)
        res.raise_for_status()
        data = res.json()
        if data.get('error', False):
            raise self.APIException(data)
        return data

    def get(self, endpoint, params=None):
        return self.request('GET', endpoint, params=params)

    def post(self, endpoint, json=None, data=None):
        return self.request('POST', endpoint, json=json, data=data)

    def put(self, endpoint, json=None, data=None):
        return self.request('PUT', endpoint, json=json, data=data)

    def get_bug(self, bug_number):
        return Bug(self, bug_number)

    def get_attachments_for_bug(self, bug_number):
        return self.get_bug(bug_number).get_attachments()

    def get_attachment_data(self, bug_number):
        return self.get_bug(bug_number).get_attachment_data()

    def create_attachment_for_bug(self, bug_number, attachment_data, file_name, summary,
                                  content_type):
        return (self.get_bug(bug_number)
                .create_attachment(attachment_data, file_name, summary, content_type))

    def who_am_i(self):
        return self.get('/whoami')


class Bug(object):
    def __init__(self, api, bug_number):
        self.api = api
        assert type(bug_number) in [int, str], BUG_NUMBER_TYPE_EXC_MESSAGE.format(type(bug_number))
        self.bug_number = bug_number

    def get_attachments(self):
        response = self.api.get('/bug/{}/attachment'.format(self.bug_number), {
            'exclude_fields': 'data'
        })
        return response.get('bugs', {}).get(str(self.bug_number), [])

    def get_attachment_data(self):
        response = self.api.get('/bug/attachment/{}'.format(self.bug_number), {
            'include_fields': 'data'
        })
        return response.get('attachments', {}).get(str(self.bug_number), {}).get('data')

    def create_attachment(self, attachment_data, file_name, summary, content_type):
        response = self.api.post('/bug/{}/attachment'.format(self.bug_number), data={
            'ids': [self.bug_number],
            'data': attachment_data,
            'file_name': file_name,
            'summary': summary,
            'content_type': content_type,
        })
        return response

    def get_flags(self):
        response = self.api.get('/bug/{}'.format(self.bug_number), {'include_fields': 'flags'})
        return response['bugs'][0]['flags']

    def set_flags(self, flags):
        response = self.api.put('/bug/{}'.format(self.bug_number), {"flags": flags})
        return response
