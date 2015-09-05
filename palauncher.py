#!/usr/bin/python3
import urllib.request
import urllib.parse
import urllib.error
import threading
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

def find_man_thread(start, stop, titleFolder, downloadUrl, authSuffix):
    print(start, stop, titleFolder, downloadUrl, authSuffix)
    for bid in range(start, stop):

        mfnm = 'PA_Linux_%s.gz' % str(bid)

        recComp = (titleFolder, mfnm, authSuffix)
        resource = '/%s/%s%s' % recComp

        try:
            manifestCompressed = get_request(downloadUrl, resource, disturb=False)
            print(bid)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue
            else:
                raise e

def find_manifest_versions(streamData):

    # Stream info
    buildId = streamData['BuildId']#'80187'

    titleFolder = streamData['TitleFolder']
    downloadUrl = streamData['DownloadUrl']
    authSuffix = streamData['AuthSuffix']

    threadCount = 2
    firstBuild = 80150
    lastBuild = int(buildId)

    count = int((lastBuild - firstBuild) / threadCount)


    prevBuild = None
    threads = []

    for i in range(threadCount):
        if i == 0:
            prevBuild = firstBuild -1

        start = prevBuild + 1
        stop = start + count

        if i == (threadCount - 1):
            stop = lastBuild + 1

        threadArgs = (start, stop, titleFolder, downloadUrl, authSuffix)
        thread = threading.Thread(target=find_man_thread, args=threadArgs)
        threads.append(thread)

        prevBuild = stop

    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

class Stream(object):
    def __init__(self, streamData):

        # Stream info
        self.buildId = streamData['BuildId']#'80187'
        self.titleFolder = streamData['TitleFolder']
        self.titleId = streamData['TitleId']
        self.description = streamData['Description']
        self.downloadUrl = streamData['DownloadUrl']
        self.manifestName = streamData['ManifestName']#'PA_Linux_80187.gz'
        self.streamName = streamData['StreamName']
        self.authSuffix = streamData['AuthSuffix']

        # Manifest info
        self.manifest = None


    def aquire_manifest(self):

        recComp = (self.titleFolder, self.manifestName, self.authSuffix)
        resource = '/%s/%s%s' % recComp

        try:
            manifestCompressed = get_request(self.downloadUrl, resource, disturb=False)

            manifestJson = gzip.decompress(manifestCompressed).decode('utf-8')

            self.manifest = json.loads(manifestJson)

        except urllib.error.HTTPError as e:
            if e.code == 404:
                print(self.manifestName, 'Not found')
            else:
                raise e


    def bundle_download(self):
        bundles = self.manifest['bundles']

        # path = os.getcwd() + '/' + location

        totalLeftover = 0

        print("Total Bundle Cout:", len(bundles))

        for i, bundle in enumerate(bundles):

            bsize = int(bundle['size'])

            bundleUsedSize = 0

            #skipDownload = True
            #for entry in bundle['entries']:
                #if 'version.txt' in entry['filename']:
            skipDownload = False

            if skipDownload:
                print('bundle %s skipped' % i)
                continue


            print('Bundle #%i' % i, 'Total Size:%s' % bsize)

            recComp = (self.titleFolder, bundle['checksum'], self.authSuffix)
            resource = '/%s/hashed/%s%s' % recComp
            
            bundleData = get_request(self.downloadUrl, resource, disturb=False)

            entryOffsetDupeCheck = []

            for entry in bundle['entries']:
                print(entry['filename'])

                #if there is no checksumZ there is no compression.
                if entry['checksumZ'] == '':
                    entrySize = int(entry['size'])
                    entryOffset = int(entry['offset'])

                    if entryOffset not in entryOffsetDupeCheck:
                        entryOffsetDupeCheck.append(entryOffset)
                        bundleUsedSize += entrySize
                    else:
                        print("DUPLICATE OFFSET FOUND!!!!!")

                    #(entrySize, entryOffset)

                    entryData = bundleData[entryOffset:entryOffset+entrySize]#gzip.decompress()

                    print('Bundle Entry Length:', len(bundleData[entryOffset:entryOffset+entrySize]))

                else:
                    entrySize = int(entry['sizeZ'])
                    entryOffset = int(entry['offset'])

                    if entryOffset not in entryOffsetDupeCheck:
                        entryOffsetDupeCheck.append(entryOffset)
                        bundleUsedSize += entrySize
                    else:
                        print("DUPLICATE OFFSET FOUND!!!!!")

                    entryData = gzip.decompress(bundleData[entryOffset:entryOffset+entrySize])

                    print('Bundle Entry Length:', len(bundleData[entryOffset:entryOffset+entrySize]))


                # Ubers servers don't support the Range header :(
                # headers = {'Range': '1-2'}

            leftover = bsize - bundleUsedSize
            totalLeftover += leftover
            print('Unindexed size: ', leftover)

        print(totalLeftover / 1000 / 1000)



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

    #for stream in uber.streams:
    #    if stream['StreamName'] == 'stable':
    #        find_manifest_versions(stream)

    stream = uber.select_stream(selectedStream['name'])

    stream.aquire_manifest()
    stream.bundle_download()
