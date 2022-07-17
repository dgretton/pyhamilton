""" Exposes methods to read/write configuration files, as well as configuration values. """

import os

CONFIG_DIR = os.path.join(os.path.expanduser('~'), ".pyhamilton")

BASE_URL = os.environ.get("BASE_URL")

if not os.path.exists(CONFIG_DIR):
  os.mkdir(CONFIG_DIR)


def get_file_path(path):
  return os.path.join(CONFIG_DIR, path)
