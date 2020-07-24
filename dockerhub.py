#!/usr/bin/env python3

import json
from dxf import DXF
from registry import Registry


class Dockerhub(Registry):

    def last_build_commit(self, namespace, repo, tag):
        def auth(_dxf, response):
            _dxf.authenticate(username=self.username, password=self.password, response=response, actions='*')

        try:
            dxf = DXF(host=self.registry, repo='{}/{}'.format(namespace, repo), auth=auth)
            r = dxf._request('get', 'manifests/' + tag,
                             headers={'Accept': 'application/vnd.docker.distribution.manifest.v1+json'})
            metadata = json.loads(r.content.decode('utf-8'))
            return json.loads(metadata['history'][0]['v1Compatibility'])['config']['Labels']['org.label-schema.vcs-ref']
        except Exception as e:
            print("last_build_commit failed: {}".format(e))
            return None

    def push_image(self, namespace, repo, tag, client):
        image = '{}/{}'.format(namespace, repo)
        image_tag = '{}:{}'.format(image, tag)
        print('Push Docker image {} ({})'.format(image_tag, type(self).__name__))
        client.api.tag(image, image_tag)
        client.images.push(image, tag=tag)
