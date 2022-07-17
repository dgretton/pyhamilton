""" Wrappers for the Platform API """

import http
import json
import requests
import typing
import uuid

import pyhamilton.cmd.project_manager.config as config
from pyhamilton.cmd.project_manager.errors import (
  NotAuthorizedError,
  ProjectNotFoundError,
  ProjectFileNotFoundError
)


def _url_for(uri):
  if not uri.startswith("/"):
    raise ValueError("uri must start with /")
  return config.BASE_URL.rstrip("/") + uri


def _get_cookies():
  path = config.get_file_path("cookies.txt")
  cookies = http.cookiejar.MozillaCookieJar(path)
  try:
    cookies.load()
  except http.cookiejar.LoadError:
    pass
  return cookies


def _get_session():
  s = requests.Session()
  s.cookies = _get_cookies()
  return s


def login(email, password):
  """ Login to the Platform API.

  This will save the cookies to a file named "cookies.txt" in the `CONFIG_DIR`.
  """
  
  s = _get_session()

  json_data = {
    'email': email,
    'password': password,
  }
  url = _url_for("/auth/login")
  response = s.post(url, json=json_data)

  if response.status_code == 401:
    raise NotAuthorizedError("Wrong email or password")
  
  s.cookies.save()


def create_project(name: str) -> dict:
  """ Create a new project. Returns the project information. """

  s = _get_session()

  json_data = {
    'name': 'project',
  }

  url = _url_for("/platform/projects")
  response = s.post(url, json=json_data)

  if response.status_code == 400:
    raise ValueError(response.get("error"))
  
  return json.loads(response.text)


def get_project_by_id(id_: uuid.UUID) -> dict:
  """ Get a project by ID."""

  s = _get_session()

  url = _url_for(f"/platform/projects/{id_}") 
  response = s.get(url)

  if response.status_code == 404:
    raise ProjectNotFoundError(f"Project with ID {id_} not found")

  return json.loads(response.text)


def upload_files(file_paths: typing.List[str], project_id: uuid.UUID) -> typing.List[dict]:
  """ Upload a file to the Platform API.

  This will return a list of dictionaries containing information about the
  uploaded files.

  Args:
    file_paths: A list of paths to files to upload.
  """

  s = _get_session()

  files = []
  for fp in file_paths:
    files.append(('files', open(fp, 'rb')))
  files.append(('project_id', (None, str(project_id))))

  url = _url_for("/platform/files")
  response = s.post(url, files=files)
  data = json.loads(response.text)

  if response.status_code == 400:
    raise ValueError(response.get("error"))
  
  return data
    

def get_file_by_id(id_: uuid.UUID) -> dict:
  """ Get information about a file by its ID. """
  s = _get_session()
  url = _url_for(f"/platform/files/{id_}") 
  response = s.get(url)

  if response.status_code == 404:
    raise ProjectFileNotFoundError(f"File with ID {id_} not found")

  return json.loads(response.text)


def download_file(id_: uuid.UUID, path: str):
  """ Download a file by ID. """
  s = _get_session()
  url = _url_for(f"/platform/files/{id_}/download")
  response = s.get(url)

  if response.status_code == 404:
    raise ProjectFileNotFoundError(f"File with ID {id_} not found")

  with open(path, "wb") as f:
    f.write(response.content)

