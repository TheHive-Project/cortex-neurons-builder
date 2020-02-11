#!/usr/bin/env python3

import argparse
import datetime
import fileinput
import json
import sys
import tempfile
from os import listdir, environ
from os.path import isdir, isfile, join

import docker
import git
import requests
from dxf import DXF


def last_build_commit(args, repo, tag):
    def auth(_dxf, response):
        _dxf.authenticate(username=args.user, password=args.password, response=response, actions='*')

    try:
        dxf = DXF(host=args.registry, repo='{}/{}'.format(args.namespace, repo), auth=auth)
        r = dxf._request('get', 'manifests/' + tag,
                         headers={'Accept': 'application/vnd.docker.distribution.manifest.v1+json'})
        metadata = json.loads(r.content.decode('utf-8'))
        return json.loads(metadata['history'][0]['v1Compatibility'])['config']['Labels']['org.label-schema.vcs-ref']
    except:
        return None


def patch_requirements(filename):
    if isfile(filename):
        for req in fileinput.input(files=filename, inplace=1):
            if req.strip() == 'cortexutils':
                sys.stdout.write('git+https://github.com/TheHive-Project/cortexutils.git@feature/docker\n')
            else:
                sys.stdout.write(req)


def list_flavor(path):
    if isdir(path):
        for flavor_filename in listdir(path):
            if isfile(join(path, flavor_filename)) and flavor_filename.endswith('.json'):
                with open(join(path, flavor_filename)) as flavor_file:
                    flavor = json.load(flavor_file)
                    yield flavor
    else:
        return []


def worker_is_updated(args, flavor, worker_name):
    tag = flavor['version'] if args.stable else 'devel'
    last_commit = last_build_commit(args, flavor['name'].lower(), tag)
    if last_commit is None:
        print('No previous Docker image found for worker {}, build it'.format(flavor['name'].lower()))
        return True
    try:
        repo = git.Repo(args.base_path)
        head = repo.head.commit
        for change in head.diff(other=last_commit):
            if change.a_path.startswith(join(args.worker_path, worker_name)) or \
                    change.b_path.startswith(join(args.worker_path, worker_name)):
                print('Previous Docker image of worker {} has been built from commit {}, changed detected, rebuild it'
                      .format(flavor['name'].lower(), last_commit))
                return True
        print('Previous Docker image of worker {} has been built from commit {}, no change detected'
              .format(flavor['name'].lower(), last_commit))
        return False
    except:
        return True


def git_commit_sha(args):
    return git.Repo(args.base_path).head.commit.hexsha


def build_docker(args, worker_name, flavor):
    def build(dockerfile):
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
                    'org.label-schema.vcs-ref': git_commit_sha(args),
                    'org.label-schema.vendor': 'TheHive Project',
                    'org.label-schema.version': flavor['version']
                },
                tag='{}/{}'.format(args.namespace, flavor['repo']))
        for line in output:
            if 'stream' in line:
                print(' > {}'.format(line['stream'].strip()))

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


def docker_repository_exists(args, repo):
    resp = requests.get(
        'https://cloud.docker.com/v2/repositories/{}/{}/'.format(args.namespace, repo),
        auth=(args.user, args.password))
    return resp.status_code == 200


def docker_create_repository(args, flavor):
    print('Create repository {}/{}'.format(args.namespace, flavor['repo']))
    resp = requests.post(
        'https://cloud.docker.com/repositories/',
        auth=(args.user, args.password),
        json={
            'namespace': args.namespace,
            'name': flavor['repo'],
            'description': flavor['description'][:100],
            'is_private': False
        })
    resp.raise_for_status()


def docker_push_image(args, repo, tag):
    image = '{}/{}'.format(args.namespace, repo)
    image_tag = '{}:{}'.format(image, tag)
    print('Push Docker image {}'.format(image_tag))
    args.docker_client.api.tag(image, image_tag)
    args.docker_client.images.push(image, tag=tag)


def build_workers(args):
    for worker_name in args.workers:
        updated_flavors = [flavor
                           for flavor in list_flavor(join(args.worker_path, worker_name))
                           if args.force or worker_is_updated(args, flavor, worker_name)]
        # patch_requirements(join(args.worker_path, worker_name, 'requirements.txt'))
        for flavor in updated_flavors:
            flavor['repo'] = flavor['name'].lower()
            print('Worker {} has been updated'.format(flavor['name']))
            build_docker(args, worker_name, flavor)
            if not docker_repository_exists(args, flavor['repo']):
                print('Repository {} does not exist'.format(flavor['repo']))
                docker_create_repository(args, flavor)
            tag = flavor['version'] if args.stable else 'devel'
            docker_push_image(args, flavor['repo'], tag)
            if '.' in tag:
                docker_push_image(args, flavor['repo'], tag.split('.', 1)[0])


def main():
    namespace = environ.get('PLUGIN_NAMESPACE')
    user = environ.get('PLUGIN_USER')
    password = environ.get('PLUGIN_PASSWORD')
    registry = environ.get('PLUGIN_REGISTRY', 'registry-1.docker.io')
    stable = environ.get('PLUGIN_STABLE') is not None
    worker_path = environ.get('PLUGIN_WORKER_PATH', 'analyzers')
    parser = argparse.ArgumentParser()
    parser.add_argument('-n', '--namespace',
                        required=namespace is None,
                        default=namespace,
                        help='Namespace of docker images')
    parser.add_argument('-u', '--user',
                        required=user is None,
                        default=user,
                        help='Username to authenticate to the Docker registry')
    parser.add_argument('-p', '--password',
                        required=password is None,
                        default=password,
                        help='Password to authenticate to the Docker registry')
    parser.add_argument('-r', '--registry',
                        default=registry,
                        help='Hostname of the Docker registry')
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
    args.docker_client.login(args.user, args.password)
    if args.workers is None:
        args.workers = listdir(args.worker_path)
    build_workers(args)


if __name__ == '__main__':
    main()
