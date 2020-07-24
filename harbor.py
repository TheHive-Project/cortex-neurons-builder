#!/usr/bin/env python3

import json
import requests
from registry import Registry


class Harbor(Registry):

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

    def push_image(self, namespace, repo, tag, client):
        image = '{}/{}'.format(namespace, repo)
        image_tag = '{}/{}:{}'.format(self.registry, image, tag)
        print('Push Docker image {} on harbor ({})'.format(image_tag, type(self).__name__))
        client.api.tag(image, image_tag)
        image = '{}/{}/{}'.format(self.registry, namespace, repo)
        client.images.push(image, tag=tag)
