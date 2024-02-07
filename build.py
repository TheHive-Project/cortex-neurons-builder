#!/usr/bin/env python3

import argparse

import json

import docker
import git
import traceback
import sys
from os import listdir, environ
from os.path import isfile, join, isdir
from dockerhub import Dockerhub
from harbor import Harbor


def list_flavor(path):
    if isdir(path):
        for flavor_filename in listdir(path):
            if isfile(join(path, flavor_filename)) and flavor_filename.endswith('.json'):
                with open(join(path, flavor_filename)) as flavor_file:
                    flavor = json.load(flavor_file)
                    yield flavor
    else:
        return []


def git_commit_sha(base_path):
    return git.Repo(base_path).head.commit.hexsha


def worker_is_updated(args, registry, flavor, worker_path, list_summary):
    tag = flavor['version'] if args.stable else 'devel'
    last_commit = registry.last_build_commit(args.namespace, flavor['name'].lower(), tag)
    if last_commit is None:
        print('No previous Docker image found for worker {}, build it ({})'
              .format(flavor['name'].lower(), registry.name()))
        return True
    try:
        repo = git.Repo(args.base_path)
        head = repo.head.commit
        for change in head.diff(other=last_commit):
            if change.a_path.startswith(worker_path) or \
                    change.b_path.startswith(worker_path):
                print(
                    'Previous Docker image of worker {} has been built from commit {}, changed detected, '
                    'rebuild it ({})'
                    .format(flavor['name'].lower(), last_commit, registry.name()))
                return True
        print('Previous Docker image of worker {} has been built from commit {}, no change detected ({})'
              .format(flavor['name'].lower(), last_commit, registry.name()))
        list_summary[0].append('{} ({})'.format(flavor['name'], registry.name()))
        return False
    except Exception as e:
        print("Worker update check failed: {}".format(e))
        return True


def build_workers(args, list_summary):
    git_commit = git_commit_sha(args.base_path)
    for worker_path in args.workers:
        list_builds = []
        for registry in args.registry:
            updated_flavors = [flavor
                               for flavor in list_flavor(join(args.base_path, worker_path))
                               if args.force or worker_is_updated(args, registry, flavor, worker_path, list_summary)]

            for flavor in updated_flavors:
                try:
                    flavor['repo'] = flavor['name'].lower()
                    print('Worker {} has been updated'.format(flavor['name']))

                    if flavor['name'] not in list_builds:
                        registry.build_docker(args.namespace, args.base_path, worker_path, flavor, git_commit)
                        list_builds.append(flavor['name'])

                    tag = flavor['version'] if args.stable else 'devel'
                    registry.push_image(args.namespace, flavor['repo'], tag)
                    if '.' in tag:
                        registry.push_image(args.namespace, flavor['repo'], tag.split('.', 1)[0])
                    if not registry.correctly_pushed(args.namespace, flavor['repo'], tag):
                        # raise Exception(
                        #     "Neurons {}/{}:{} is not correctly pushed on {}"
                        #     .format(args.namespace, flavor['repo'], tag, registry.name()))
                        print(f"WARN: Neurons {args.namespace}/{flavor['repo']}:{tag} digest check failed on {registry.name()}. This however, does not mean a push failed. Data returned by this function or call may not be up-to-date in some instances.")
                    list_summary[1].append('{} ({})'.format(flavor['name'], registry.name()))
                except Exception as e:
                    print("build workers failed: {}".format(e))
                    traceback.print_exc()
                    list_summary[2].append('{} ({}) -> {}'
                                           .format(flavor['name'], registry.name(), e))


def display_list_summary(list_summary):
    sys.stderr.flush()
    sys.stdout.flush()

    if len(list_summary[0]) != 0:
        for update in list_summary[0]:
            print('[SKIPPED] {}'.format(update))

    if len(list_summary[1]) != 0:
        for update in list_summary[1]:
            print('[SUCCEED] {}'.format(update))

    if len(list_summary[2]) != 0:
        for update in list_summary[2]:
            print('[FAILED]  {}'.format(update))
        exit(1)


def main():
    namespace = environ.get('PLUGIN_NAMESPACE')
    stable = environ.get('PLUGIN_STABLE') is not None
    worker_path = environ.get('PLUGIN_WORKER_PATH', 'analyzers')
    force = environ.get('PLUGIN_FORCE', False)

    registry_dockerhub = (environ.get('PLUGIN_REGISTRY_DOCKERHUB') or "").split(",")
    if registry_dockerhub[0] == "":
        registry_dockerhub.pop()

    registry_harbor = (environ.get('PLUGIN_REGISTRY_HARBOR') or "").split(",")
    if registry_harbor[0] == "":
        registry_harbor.pop()

    parser = argparse.ArgumentParser()
    parser.add_argument('-n', '--namespace',
                        required=namespace is None,
                        default=namespace,
                        help='Namespace of docker images')
    parser.add_argument('-rd', '--registry_dockerhub',
                        action='append',
                        default=registry_dockerhub,
                        help='Username, password and hostname for Docker Hub (username:password@hostname)')
    parser.add_argument('-rh', '--registry_harbor',
                        action='append',
                        default=registry_harbor,
                        help='Username, password and hostname for Harbor (username:password@hostname)')
    parser.add_argument('-s', '--stable',
                        action='store_true',
                        default=stable,
                        help='Add release tags')
    parser.add_argument('-w', '--worker',
                        action='append',
                        dest='workers',
                        help='Path of the worker (relative to base path) to build')
    parser.add_argument('--path',
                        default=worker_path,
                        dest='worker_path',
                        help='Path of the workers, relative to base path')
    parser.add_argument('--base-path',
                        default='.',
                        help='Path of the git repository')
    parser.add_argument('-f', '--force',
                        default=force,
                        action='store_true',
                        help='Force build Docker image even without any change')
    args = parser.parse_args()
    args.docker_client = docker.from_env()
    args.registry = []

    for registry_string in args.registry_dockerhub:
        registry = Dockerhub(args.docker_client, registry_string)
        registry.login()
        args.registry.append(registry)

    for registry_string in args.registry_harbor:
        registry = Harbor(args.docker_client, registry_string)
        registry.login()
        args.registry.append(registry)

    if args.workers is None:
        args.workers = listdir(args.worker_path)
    args.workers = [join(args.worker_path, w) for w in args.workers]

    list_summary = [[], [], []]
    build_workers(args, list_summary)
    display_list_summary(list_summary)


if __name__ == '__main__':
    main()
