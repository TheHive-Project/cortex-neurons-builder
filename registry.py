#!/usr/bin/env python3

import git


class Registry:

    def __init__(self, client, registry_string, default_registry):
        try:
            self.username = registry_string.split(":")[0]
            self.password = registry_string.split(":")[1].split("@")[0]
            self.registry = registry_string.split("@")[1]
            self.client = client
            self.default_registry = default_registry
        except Exception as e:
            print("Exception: " + str(e))
            print("Wrong format in the registry credentials")

    def login(self):
        try:
            self.client.login(username=self.username,
                              password=self.password,
                              registry=self.registry)
        except Exception as e:
            print("Login failed: {}".format(e))

    def last_build_commit(self, namespace, repo, tag):
        return None

    def worker_is_updated(self, args, flavor, worker_name, list_summary):
        tag = flavor['version'] if args.stable else 'devel'
        last_commit = self.last_build_commit(args.namespace, flavor['name'].lower(), tag)
        if last_commit is None:
            print('No previous Docker image found for worker {}, build it ({})'
                  .format(flavor['name'].lower(), type(self).__name__))
            return True
        try:
            repo = git.Repo(args.base_path)
            head = repo.head.commit
            for change in head.diff(other=last_commit):
                if change.a_path.startswith("analyzers/" + worker_name) or \
                        change.b_path.startswith("analyzers/" + worker_name):
                    print(
                        'Previous Docker image of worker {} has been built from commit {}, changed detected, '
                        'rebuild it ({})'
                        .format(flavor['name'].lower(), last_commit, type(self).__name__))
                    return True
            print('Previous Docker image of worker {} has been built from commit {}, no change detected ({})'
                  .format(flavor['name'].lower(), last_commit, type(self).__name__))
            list_summary[0].append('{} ({})'.format(flavor['name'], type(self).__name__))
            return False
        except Exception as e:
            print("Worker update check failed: {}".format(e))
            return True

    def push_image(self, namespace, repo, tag):
        return None

    def get_remote_image_id(self, namespace, repo, tag):
        return None

    def correctly_pushed(self, namespace, repo, tag):
        image_tag = '{}/{}:{}'.format(namespace, repo, tag)
        if not self.default_registry:
            image_tag = '{}/{}'.format(self.registry, image_tag)
        local_id = self.client.images.get_registry_data(image_tag, auth_config={"username": self.username,
                                                                                "password": self.password}).id
        remote_id = self.get_remote_image_id(namespace, repo, tag)
        return local_id == remote_id
