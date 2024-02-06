#!/usr/bin/env python3

import json
import requests
from dxf import DXF
from registry import Registry
import traceback
from docker.errors import BuildError, APIError

class Dockerhub(Registry):
    def __init__(self, client, registry):
        super().__init__(client, registry, True)

    def name(self):
        return "dockerhub"

    def last_build_commit(self, namespace, repo, tag):
        def auth(_dxf, response):
            _dxf.authenticate(
                username=self.username,
                password=self.password,
                response=response,
                actions="*",
            )

        try:
            dxf = DXF(
                host=self.registry, repo="{}/{}".format(namespace, repo), auth=auth
            )
            r = dxf._request(
                "get",
                "manifests/" + tag,
                headers={
                    "Accept": "application/vnd.docker.distribution.manifest.v1+json"
                },
            )
            metadata = json.loads(r.content.decode("utf-8"))
            return json.loads(metadata["history"][0]["v1Compatibility"])["config"][
                "Labels"
            ]["org.label-schema.vcs-ref"]
        except Exception as e:
            print("last_build_commit failed: {}".format(e))
            traceback.print_exc()
            return None

    def push_image(self, namespace, repo, tag):
        try:
            image = "{}/{}".format(namespace, repo)
            image_tag = "{}:{}".format(image, tag)
            print("Pushing Docker image {} ({})".format(image_tag, self.name()))

            # Tagging the image
            self.client.api.tag(image, image_tag)

            # Pushing the image
            self.client.images.push(
                image,
                tag=tag,
                auth_config={"username": self.username, "password": self.password},
            )
        except BuildError as be:
            print("Build error occurred: {}".format(be))
            # Handle build-specific error
        except APIError as ae:
            print("API error occurred: {}".format(ae))
            # Handle API-specific error
        except TypeError as te:
            print("Type error: {}".format(te))
            # Handle type error
        except Exception as e:
            print("An unexpected error occurred: {}".format(e))
            # Handle other exceptions

    def get_remote_image_id(self, namespace, image, tag):
        try:
            resp = requests.get(
                "https://hub.docker.com/v2/repositories/{}/{}/tags/{}".format(
                    namespace, image, tag
                ),
                auth=(self.username, self.password),
            )

            metadata = json.loads(resp.content.decode("utf-8"))
            try:
                print(f"DEBUG: remote image last pushed: {metadata['images'][0]['last_pushed']}")
                print(f"DEBUG: remote image status: {metadata['images'][0]['status']}")
                print(f"DEBUG: repository tag status: {metadata['status']}")
                print(f"DEBUG: repository tag last updated: {metadata['last_updated']}")
                print(f"DEBUG: repository tag last pushed: {metadata['tag_last_pushed']}")
            except KeyError as e:
                print(f"KeyError encountered while accessing metadata: {e}")
            except IndexError as e:
                print(f"IndexError encountered while accessing metadata: {e}")
            return metadata["images"][0]["digest"]
        except Exception as e:
            print("Can't get remote image id: {}".format(e))
            return None
