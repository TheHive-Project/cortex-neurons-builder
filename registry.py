#!/usr/bin/env python3

import traceback
import datetime
from os.path import isfile, join, basename
import tempfile
from docker.errors import BuildError
import subprocess
import textwrap
import re

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
            raise e

    def name(self):
        return "unknown"

    def login(self):
        try:
            self.client.login(
                username=self.username, password=self.password, registry=self.registry
            )
        except Exception as e:
            print("Login failed: {}".format(e))
            raise e

    def last_build_commit(self, namespace, repo, tag):
        return None

    def test_imports(self, image_tag, command, worker_name):
        print("\n🔍 Testing Python imports in built image...")
        test_code = textwrap.dedent(f'''
            import os, sys, re, os.path as osp

            entrypoint_full = "{command}"
            # Use the worker folder as a fallback if the directory from the command isn't found
            fallback_dir = "{worker_name}"
            if "/" in entrypoint_full:
                dir_part = osp.dirname(entrypoint_full)
                file_part = osp.basename(entrypoint_full)
                # if the directory part does not exist, try fallback
                if not os.path.isdir(dir_part) and os.path.isdir(fallback_dir):
                    dir_part = fallback_dir
                os.chdir(osp.join(os.getcwd(), dir_part))
                entrypoint = file_part
            else:
                entrypoint = entrypoint_full

            if not os.path.exists(entrypoint):
                print("❌ ERROR: {{}} not found inside the container.".format(entrypoint))
                sys.exit(1)

            with open(entrypoint, 'r', encoding='utf-8') as f:
                content = f.readlines()

            imports = [line.strip() for line in content if re.match(r'^\\s*(import|from)\\s+[a-zA-Z0-9_.]+', line)]
            print("🔍 Checking Python imports from", entrypoint)
            for imp in imports:
                try:
                    exec(imp)
                    print("✅", imp, "- SUCCESS")
                except Exception as e:
                    print("❌", imp, "- FAILED:", e)
                    sys.exit(1)
            print("✅ All imports tested successfully!")
        ''')
        try:
            result = subprocess.run(
                ["docker", "run", "--rm", "--entrypoint", "python", image_tag, "-c", test_code],
                capture_output=True, text=True
            )
            print(result.stdout)
            if result.returncode != 0:
                print("⚠️ Import testing FAILED with exit code", result.returncode)
            else:
                print("✅ Import testing succeeded")
        except Exception as e:
            print("Error during import testing:", e)

    def build_docker(self, namespace, base_path, worker_path, flavor, git_commit_sha):
        worker_name = basename(worker_path)

        def build(dockerfile):
            try:
                (image, output) = self.client.images.build(
                    path=join(base_path, worker_path),
                    dockerfile=dockerfile,
                    pull=True,
                    labels={
                        "schema-version": "1.0",
                        "org.label-schema.build-date": datetime.datetime.now().isoformat("T") + "Z",
                        "org.label-schema.name": worker_name,
                        "org.label-schema.description": flavor["description"].replace("'", "''")[:100],
                        "org.label-schema.url": "https://thehive-project.org",
                        "org.label-schema.vcs-url": "https://github.com/TheHive-Project/Cortex-Analyzers",
                        "org.label-schema.vcs-ref": git_commit_sha,
                        "org.label-schema.vendor": "TheHive Project",
                        "org.label-schema.version": flavor["version"],
                    },
                    tag=f"{namespace}/{flavor['repo']}",
                )
                for line in output:
                    if "stream" in line:
                        print(f" > {line['stream'].strip()}")
            except Exception as e:
                print(f"build failed for worker {worker_name}")
                traceback.print_exc()
                raise e

        if isfile(join(base_path, worker_path, "Dockerfile")):
            build(None)
        else:
            # Define the base images to try, in order
            base_images = ["python:3-alpine", "python:3-slim", "python:3"]
            last_exception = None

            for base in base_images:
                # For Alpine, add extra APK commands to install required tools
                if base.startswith("python:3-alpine"):
                    #alpine_setup = (
                    #    "RUN apk update && apk upgrade && apk add --no-cache --update py3-pip && rm -rf /var/cache/apk/*\n"
                    #)
                    alpine_setup = ""
                else:
                    alpine_setup = ""
                
                dockerfile_content = f"""  
                FROM {base}
                {alpine_setup}WORKDIR /worker

                COPY requirements.txt {worker_name}/
                RUN test ! -e {worker_name}/requirements.txt || pip install --no-cache-dir -r {worker_name}/requirements.txt

                COPY . {worker_name}/
                ENTRYPOINT ["python", "{flavor['command']}"]
                """
                print(f"Trying build for worker {worker_name} using base image {base}...")
                with tempfile.NamedTemporaryFile() as f:
                    f.write(dockerfile_content.encode("utf-8"))
                    f.flush()
                    try:
                        build(f.name)
                        image_tag = f"{namespace}/{flavor['repo']}"
                        print(f"Build succeeded for worker {worker_name} using base image {base}.")
                        # Test the imports before pushing.
                        try:
                            self.test_imports(image_tag, flavor['command'], worker_name)
                        except Exception as e:
                            print("Import testing encountered an error:", e)
                        return  # Build succeeded; exit the function
                    except BuildError as be:
                        print(f"BuildError encountered with base image {base} for worker {worker_name}.")
                        last_exception = be

            print(f"All build attempts failed for worker {worker_name}.")
            raise last_exception




    def push_image(self, namespace, repo, tag):
        return None

    def get_remote_image_id(self, namespace, repo, tag):
        return None

    def correctly_pushed(self, namespace, repo, tag):
        image_tag = "{}/{}:{}".format(namespace, repo, tag)
        if not self.default_registry:
            image_tag = "{}/{}".format(self.registry, image_tag)
        local_id = self.client.images.get_registry_data(
            image_tag,
            auth_config={"username": self.username, "password": self.password},
        ).id
        remote_id = self.get_remote_image_id(namespace, repo, tag)
        if remote_id is None:
            return True
        try:
            print(f"DEBUG: Comparing local_id and remote_id, local_id: {local_id}, remote_id: {remote_id}")
        except NameError as e:
            print(f"Error: {e}. Ensure 'local_id' and 'remote_id' are defined before comparing.")
        return local_id == remote_id