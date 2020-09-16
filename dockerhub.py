#!/usr/bin/env python3

import json
import requests
from dxf import DXF
from registry import Registry


class Dockerhub(Registry):

    def __init__(self, client, registry):
        super().__init__(client, registry, True)

    def name(self):
        return "dockerhub"

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

    def push_image(self, namespace, repo, tag):
        image = '{}/{}'.format(namespace, repo)
        image_tag = '{}:{}'.format(image, tag)
        print('Push Docker image {} ({})'.format(image_tag, self.name()))
        self.client.api.tag(image, image_tag)
        self.client.images.push(image, tag=tag, auth_config={"username": self.username, "password": self.password})

    def get_remote_image_id(self, namespace, image, tag):
        try:
            resp = requests.get(
                'https://hub.docker.com/v2/repositories/{}/{}/tags/{}'.format(namespace, image, tag),
                auth=(self.username, self.password))

            metadata = json.loads(resp.content.decode('utf-8'))
            return metadata['images'][0]['digest']
        except Exception as e:
            return None
