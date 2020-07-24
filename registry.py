#!/usr/bin/env python3

import git


class Registry:

    def __init__(self, registry):
        try:
            self.username = registry.split(":")[0]
            self.password = registry.split(":")[1].split("@")[0]
            self.registry = registry.split("@")[1]
        except Exception as e:
            print("Exception: " + str(e))
            print("Wrong format in the registry credentials")

    def login(self, client):
        try:
            client.login(username=self.username,
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

    def push_image(self, namespace, repo, tag, client):
        return None
