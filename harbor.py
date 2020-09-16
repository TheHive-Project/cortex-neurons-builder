#!/usr/bin/env python3

import json
import requests
from registry import Registry


class Harbor(Registry):

    def __init__(self, client, registry):
        super().__init__(client, registry, False)

    def name(self):
        return "harbor"

    def last_build_commit(self, namespace, repo, tag):
        try:
            resp = requests.get(
                'https://{}/api/repositories/{}/{}/tags/{}/manifest'.format(self.registry, namespace, repo, tag),
                auth=(self.username, self.password))

            metadata = json.loads(resp.content.decode('utf-8'))
            return json.loads(metadata['config'])['config']['Labels']['org.label-schema.vcs-ref']
        except Exception as e:
            print("last_build_commit failed: {}".format(e))
            return None

    def push_image(self, namespace, repo, tag):
        image = '{}/{}'.format(namespace, repo)
        image_tag = '{}/{}:{}'.format(self.registry, image, tag)
        print('Push Docker image {} on harbor ({})'.format(image_tag, self.name()))
        self.client.api.tag(image, image_tag)
        image = '{}/{}/{}'.format(self.registry, namespace, repo)
        self.client.images.push(image, tag=tag)

    def get_remote_image_id(self, namespace, repo, tag):
        try:
            resp = requests.get(
                'https://{}/api/repositories/{}/{}/tags/{}'.format(self.registry, namespace, repo, tag),
                auth=(self.username, self.password))

            metadata = json.loads(resp.content.decode('utf-8'))
            return metadata['digest']
        except Exception as e:
            return None
