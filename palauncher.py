#!/usr/bin/python3
import urllib.request
import urllib.parse
import platform
import getpass
import json
import gzip
import ssl
import os

platformMap = {
    'Darwin': 'OSX',
    'Linux': 'Linux',
    'Windows': 'Windows',
}

platformName = platformMap[platform.platform().split('-', 1)[0]]

_sslContext = ssl.create_default_context()

def post_request(domain, resource, data, headers={}, disturb=True):
    url = '%s%s' % (domain, resource)

    encodedData = data.encode('ascii')

    request = urllib.request.Request(url, encodedData, headers)
    response = urllib.request.urlopen(request, context=_sslContext)

    responseData = response.read()
    response.close()

    if disturb:
        return responseData.decode('utf-8')
    else:
        return responseData

def get_request(domain, resource, headers={}, disturb=True):
    url = '%s%s' % (domain, resource)

    request = urllib.request.Request(url, headers=headers)
    response = urllib.request.urlopen(request, context=_sslContext)

    responseData = response.read()
    response.close()

    if disturb:
        return responseData.decode('utf-8')
    else:
        return responseData

class Stream(object):
    def __init__(self, streamData):

        # Stream info
        self.buildId = streamData['BuildId']
        self.titleFolder = streamData['TitleFolder']
        self.titleId = streamData['TitleId']
        self.description = streamData['Description']
        self.downloadUrl = streamData['DownloadUrl']
        self.manifestName = streamData['ManifestName']
        self.streamName = streamData['StreamName']
        self.authSuffix = streamData['AuthSuffix']

        # Manifest info
        self.manifest = None


    def aquire_manifest(self):

        recComp = (self.titleFolder, self.manifestName, self.authSuffix)

        resource = '/%s/%s%s' % recComp

        manifestCompressed = get_request(self.downloadUrl, resource, disturb=False)

        manifestJson = gzip.decompress(manifestCompressed).decode('utf-8')

        self.manifest = json.loads(manifestJson)


class UberConnect(object):
    def __init__(self, dev=False):

        if dev:
            self.uberUrl = 'https://uberentdev.com'
        else:
            self.uberUrl = 'https://uberent.com'

        self.loginSession = None
        self.streams = None

    def login(self, username, password):
        '''Login to the uber servers.'''
        resource = '/GC/Authenticate'

        loginData = {
            'TitleId': 4,
            'AuthMethod': 'UberCredentials',
            'UberName': username,
            'Password': password,
        }

        headers = {'Content-Type': 'application/json'}

        jsonLogin = json.dumps(loginData)

        jsonResponse = post_request(self.uberUrl, resource, jsonLogin, headers)
        
        self.loginSession = json.loads(jsonResponse)

    def aquire_streams(self):
        '''Request and aquire stream lis.'''
        resource = '/Launcher/ListStreams?Platform=%s' % platformName

        headers = {'X-Authorization': self.loginSession['SessionTicket']}

        jsonStreams = get_request(self.uberUrl, resource, headers)

        self.streams = json.loads(jsonStreams)['Streams']

    def stream_info(self):
        '''Return basic information about all streams.
           Can be used for user prompts, but also will be needed for correctly
           selecting a stream to download.
        '''
        streams = []
        for stream in self.streams:

            streamInfo = {}
            streamInfo['name'] = stream['StreamName']
            streamInfo['id'] = stream['BuildId']
            streamInfo['description'] = stream['Description']
            streams.append(streamInfo)

        return streams

    def select_stream(self, name):
        '''Select a stream by name, returning a Stream object if it exists.'''

        for stream in self.streams:
            if stream['StreamName'] == name:
                return Stream(stream)
        return None


if __name__ == '__main__':
    username = input('Username: ')
    password = getpass.getpass()
    uber = UberConnect()
    uber.login(username, password)
    uber.aquire_streams()
    streamInfo = uber.stream_info()

    print('\n\nSelect Build:\n')
    for i, stream in enumerate(streamInfo):
        print('    %s.\t' % (i+1), stream['name'], stream['id'])
        print('\t', stream['description'], '\n')

    selectedStream = streamInfo[int(input('> '))-1]

    stream = uber.select_stream(selectedStream['name'])

    stream.aquire_manifest()

    stream.manifest

