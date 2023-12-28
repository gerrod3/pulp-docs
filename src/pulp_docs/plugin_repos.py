"""
The classes representing plugins git/git-hub repositories.

Their purpose is to facilitate declaring and downloading the source-code.
"""
from __future__ import annotations

import shutil
import tarfile
import tempfile
import typing as t
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

import httpx
import yaml

WORKDIR = Path("tests/fixtures").absolute()
RESTAPI_TEMPLATE = "https://docs.pulpproject.org/{}/restapi.html"


@dataclass
class Repo:
    """
    A git/gh repository representation.
    
    The real repository content is plugin sourcecode and markdown documentation.
    """
    title: str
    name: str
    owner: str = "pulp"
    local_basepath: Path = WORKDIR

    @property
    def local_url(self):
        """Return local url for respository as {self.local_basepath}/{self.name}"""
        return self.local_basepath / self.name

    @property
    def rest_api_link(self):
        return RESTAPI_TEMPLATE.format(self.name)

    def download(self, dest_dir: Path, from_local: bool = False) -> Path:
        """
        Download repository source from url into the {dest_dir} Path.

        For remote download, uses GitHub API to get latest source code:
        https://docs.github.com/en/rest/releases/releases?apiVersion=2022-11-28#get-the-latest-release

        Args:
            dest: The destination directory where source files will be saved.
            from_local: If true, the repo is copied from the local path {self.local_url} instead of being
                        downloaded from remote.
        """
        # Copy from local filesystem
        if from_local is True:
            shutil.copytree(self.local_url, dest_dir, ignore=shutil.ignore_patterns(
                "tests", "*venv*", "__pycache__"))
            return self.local_basepath

        # or Download from remote
        latest_release_link_url = "https://api.github.com/repos/{}/{}/releases/latest".format(
            self.owner, self.name)

        print("Fetching latest release with:", latest_release_link_url)
        response = httpx.get(latest_release_link_url)
        latest_release_tar_url = response.json()["tarball_url"]

        print("Downloadng tarball from:", latest_release_tar_url)
        response = httpx.get(latest_release_tar_url, follow_redirects=True)
        bytes_data = BytesIO(response.content)

        print("Extracting tarball to:", dest_dir)
        with tempfile.TemporaryDirectory() as tmpdir:
            with tarfile.open(fileobj=bytes_data) as tar:
                tar.extractall(tmpdir, filter="data")
            # workaround because I cant know the name of the extracted dir with tarfile lib
            dirname = Path(tmpdir) / tar.getmembers()[0].name.split()[0]
            shutil.move(str(dirname.absolute()), str(dest_dir.absolute()))
        # Reference:
        # https://www.python-httpx.org/quickstart/#binary-response-content
        # https://docs.python.org/3/library/tarfile.html#tarfile.TarFile.extractall
        return dest_dir


@dataclass
class Repos:
    """A collection of Repos"""
    core: Repo
    content: t.List[Repo] = field(default_factory=list)
    other: t.List[Repo] = field(default_factory=list)

    @property
    def all(self):
        return [self.core] + self.content + self.other

    @classmethod
    def from_yaml(cls, path: str):
        """
        Load repositories listing from yaml file (repolist.yml)

        Example:
            ```yaml
            repos:
                core:
                  name:
                  title:
                content:
                  - name: pulp_rpm
                    title: Rpm Package
                  - name: pulp_maven
                    title: Maven
            ```
        """
        file = Path(path)
        if not file.exists():
            raise ValueError("File does not exist:", file)

        with open(file, "r") as f:
            data = yaml.load(f, Loader=yaml.SafeLoader)
        repos = data["repos"]
        core_repo = Repo(**repos["core"][0])
        content_repos = [Repo(**repo) for repo in repos["content"]]
        other_repos = [Repo(**repo) for repo in repos["other"]]
        return Repos(core=core_repo, content=content_repos, other=other_repos)

    @classmethod
    def test_fixtures(cls):
        """Factory of test Repos. Uses fixtures shipped in package data."""
        DEFAULT_CORE = Repo("Pulp Core", "core")
        DEFAULT_CONTENT_REPOS = [
            Repo("Rpm Packages", "new_repo1"),
            Repo("Debian Packages", "new_repo2"),
            Repo("Maven", "new_repo3"),
        ]
        return Repos(core=DEFAULT_CORE, content=DEFAULT_CONTENT_REPOS)