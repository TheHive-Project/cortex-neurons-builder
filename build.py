#!/usr/bin/env python3

import argparse
import datetime
import json
import tempfile
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


def build_docker(args, flavor, worker_name):
    def build(dockerfile):
        try:
            (image, output) = args.docker_client.images.build(
                path=join(args.worker_path, worker_name),
                dockerfile=dockerfile,
                pull=True,
                labels={
                    'schema-version': '1.0',
                    'org.label-schema.build-date': datetime.datetime.now().isoformat('T') + 'Z',
                    'org.label-schema.name': worker_name,
                    'org.label-schema.description': flavor['description'].replace("'", "''")[:100],
                    'org.label-schema.url': 'https://thehive-project.org',
                    'org.label-schema.vcs-url': 'https://github.com/TheHive-Project/Cortex-Analyzers',
                    'org.label-schema.vcs-ref': git_commit_sha(args.base_path),
                    'org.label-schema.vendor': 'TheHive Project',
                    'org.label-schema.version': flavor['version']
                },
                tag='{}/{}'.format(args.namespace, flavor['repo']))
            for line in output:
                if 'stream' in line:
                    print(' > {}'.format(line['stream'].strip()))
        except:
            print("build failed")
            traceback.print_exc()

    if isfile(join(args.worker_path, worker_name, 'Dockerfile')):
        build(None)
    else:
        dockerfile_content = """  
FROM python:3

WORKDIR /worker
COPY . {worker_name}
RUN test ! -e {worker_name}/requirements.txt || pip install --no-cache-dir -r {worker_name}/requirements.txt
ENTRYPOINT {command}
        """.format(worker_name=worker_name, command=flavor['command'])

        with tempfile.NamedTemporaryFile() as f:
            f.write(str.encode(dockerfile_content))
            f.flush()
            build(f.name)


def git_commit_sha(base_path):
    return git.Repo(base_path).head.commit.hexsha


def build_workers(args, list_summary):
    for worker_name in args.workers:
        list_builds = []
        for registry in args.registry:
            updated_flavors = [flavor
                               for flavor in list_flavor(join(args.worker_path, worker_name))
                               if args.force or registry.worker_is_updated(args, flavor, worker_name, list_summary)]

            for flavor in updated_flavors:
                try:
                    flavor['repo'] = flavor['name'].lower()
                    print('Worker {} has been updated'.format(flavor['name']))

                    if flavor['name'] not in list_builds:
                        build_docker(args, flavor, worker_name)
                        list_builds.append(flavor['name'])

                    tag = flavor['version'] if args.stable else 'devel'
                    registry.push_image(args.namespace, flavor['repo'], tag, args.docker_client)

                    if '.' in tag:
                        registry.push_image(args.namespace, flavor['repo'], tag.split('.', 1)[0],
                                            args.docker_client)
                    list_summary[1].append('{} ({})'.format(flavor['name'], type(registry).__name__))
                except Exception as e:
                    print("build workers failed: {}".format(e))
                    traceback.print_exc()
                    list_summary[2].append('{} ({}) -> {}'
                                           .format(flavor['name'], type(registry).__name__, e))


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
                        help='Name of the worker to build')
    parser.add_argument('--path',
                        default=worker_path,
                        dest='worker_path',
                        help='Path of the workers')
    parser.add_argument('--base-path',
                        default='.',
                        help='Path of the git repository')
    parser.add_argument('-f', '--force',
                        action='store_true',
                        help='Force build Docker image even without any change')
    args = parser.parse_args()
    args.docker_client = docker.from_env()
    args.registry = []

    for registry in args.registry_dockerhub:
        registry = Dockerhub(registry)
        registry.login(args.docker_client)
        args.registry.append(registry)

    for registry in args.registry_harbor:
        registry = Harbor(registry)
        registry.login(args.docker_client)
        args.registry.append(registry)

    if args.workers is None:
        args.workers = listdir(args.worker_path)

    list_summary = [[], [], []]
    build_workers(args, list_summary)
    display_list_summary(list_summary)


if __name__ == '__main__':
    main()
