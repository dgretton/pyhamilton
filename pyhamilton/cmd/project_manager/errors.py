class ProjectManagerError(Exception):
  pass


class NotAuthorizedError(ProjectManagerError):
  pass


class ProjectNotFoundError(ProjectManagerError):
  pass


class ProjectFileNotFoundError(ProjectManagerError):
  pass

