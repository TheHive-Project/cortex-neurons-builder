#!/usr/bin/env python3

import json
import requests
from dxf import DXF
from registry import Registry
import traceback
from docker.errors import BuildError, APIError
from dxf.exceptions import DXFUnauthorizedError

class Dockerhub(Registry):
    def __init__(self, client, registry):
        super().__init__(client, registry, True)

    def name(self):
        return "dockerhub"

    def last_build_commit(self, namespace, repo, tag):
        """
        Retrieve the commit hash (vcs-ref) from the image manifest.
        
        :param namespace: The namespace of the repository.
        :param repo: The repository name.
        :param tag: The image tag.
        :return: The commit hash if found, otherwise None.
        """
        def auth(_dxf, response):
            #print("DEBUG: Authenticating using provided credentials...")
            try:
                _dxf.authenticate(
                    username=self.username,
                    password=self.password,
                    response=response,
                    actions="*",
                )
            #    print("DEBUG: Authentication successful.")
            except Exception as auth_err:
                print(f"ERROR: Authentication failed: {auth_err}")
                raise  # Propagate the error to be handled by the try/except
    
        try:
            repo_full = f"{namespace}/{repo}"
            print(f"DEBUG: Fetching manifest for repository '{repo_full}' with tag '{tag}' from registry '{self.registry}'")
            
            # init
            dxf = DXF(host=self.registry, repo=repo_full, auth=auth)
            
            # build the manifest URL and make the GET request
            manifest_url = f"manifests/{tag}"
            print(f"DEBUG: Requesting manifest at URL: {manifest_url}")
            response = dxf._request(
                "get",
                manifest_url,
                headers={
                    "Accept": "application/vnd.docker.distribution.manifest.v1+json"
                },
            )
            print("DEBUG: Response received. Decoding JSON content...")
            
            # decode the response content into a Python dictionary.
            metadata = json.loads(response.content.decode("utf-8"))
            #print("DEBUG: Metadata decoded successfully:")
            #print(metadata)
            # extract the commit hash from the metadata
            history = metadata.get("history", [])
            if not history:
                print("ERROR: No history found in metadata.")
                return None
            # check if first history entry contains the v1Compatibility JSON
            v1compat_str = history[0].get("v1Compatibility")
            if not v1compat_str:
                print("ERROR: No v1Compatibility found in the first history entry.")
                return None
            v1compat = json.loads(v1compat_str)
            labels = v1compat.get("config", {}).get("Labels", {})
            commit = labels.get("org.label-schema.vcs-ref")
            if commit:
                print(f"DEBUG: Found commit: {commit}")
            else:
                print("ERROR: Commit label 'org.label-schema.vcs-ref' not found in metadata labels.")
            return commit
        except DXFUnauthorizedError as unauthorized:
            print(f"ERROR: Unauthorized error encountered in last_build_commit - DXFUnauthorizedError: {unauthorized}")
            #traceback.print_exc()
            return None
        except Exception as e:
            print(f"ERROR: last_build_commit failed: {e}")
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
                _config={"username": self.username, "password": self.password},
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
                print(f"DEBUG: repository tag last pushed: {metadata['tag_last_pushed']}")
                print(f"DEBUG: repository tag last updated: {metadata['last_updated']}")
            except KeyError as e:
                print(f"KeyError encountered while accessing metadata: {e}")
            except IndexError as e:
                print(f"IndexError encountered while accessing metadata: {e}")
            return metadata["images"][0]["digest"]
        except Exception as e:
            print("Can't get remote image id: {}".format(e))
            return None
