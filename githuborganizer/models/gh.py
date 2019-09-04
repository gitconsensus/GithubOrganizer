import base64
import datetime
import githuborganizer.config as config
from githuborganizer import cache
import github3
from github3apps import GithubApp
import json
import requests
import yaml
import os

DEFAULT_LABEL_COLOR = '000000'
CACHE_SHORT = 5 * 60 # Five minutes
CACHE_MEDIUM = 60 * 60 # One hour
CACHE_LONG = 24 * 60 * 60 # One day

def issue_has_projects(installation, organization, repository, issue):
    query = '''
    {
      repository(owner:"%s", name:"%s") {
        issue(number:%s) {
          projectCards (archivedStates: NOT_ARCHIVED, first: 1) {
            edges {
              node {
                id
              }
            }
          }
        }
      }
    }
    ''' % (organization, repository, issue)
    results = installation.graphql({'query': query})
    return len(results['data']['repository']['issue']['projectCards']['edges']) > 0


class Organization:

    def __repr__(self):
        return 'OrganizerOrganization %s' % self.name

    def __str__(self):
        return self.__repr__()

    def __init__(self, client, organization):
        @cache.cache(expire=CACHE_SHORT)
        def get_configuration(org_name):
            try:
                config_repository = client.repository(org_name, '.github')
                return yaml.safe_load(config_repository.file_contents('organizer.yaml').decoded.decode('utf-8'))
            except:
                return False

        self.client = client
        self.name = organization
        self.configuration = get_configuration(organization)
        self.ghorg = self.client.organization(organization)


    def get_repositories(self):
        for repository in self.ghorg.repositories():
            if 'exclude_repositories' in self.configuration:
                if repository.name in self.configuration['exclude_repositories']:
                    continue
            if repository.archived:
                continue
            yield Repository(self.client, self, repository.name, repository)

    def get_repository(self, name):
        return Repository(self.client, self, name)

    def get_projects(self):
        for project in self.ghorg.projects():
            yield Project(self.client, project, self)

    def get_project_by_name(self, name):
        @cache.cache(expire=CACHE_MEDIUM)
        def org_get_project_id_from_name(org, name):
            for project in org.ghorg.projects():
                if project.name == name:
                    return project.id
            return False
        id = org_get_project_id_from_name(self, name)
        if not id:
            return False
        return Project(self.client, self.ghorg.project(id), self)



class Repository:

    def __repr__(self):
        return 'OrganizerRepository %s' % self.name

    def __str__(self):
        return self.__repr__()

    def __init__(self, client, organization, repo_name, ghrep=None):
        self.client = client
        self.organization = organization
        self.name = repo_name

        if ghrep:
            self.ghrep = ghrep
        else:
            self.ghrep = self.client.repository(self.organization.name, self.name)

    def update_settings(self):
        self.ghrep.edit(self.name,
            has_issues = self.organization.configuration.get('has_issues', None),
            has_wiki = self.organization.configuration.get('has_wiki', None),
            has_downloads = self.organization.configuration.get('has_downloads', None),
            has_projects = self.organization.configuration.get('has_projects', None),
            allow_rebase_merge = self.organization.configuration.get('allow_rebase_merge', None),
            allow_squash_merge = self.organization.configuration.get('allow_squash_merge', None),
            allow_merge_commit = self.organization.configuration.get('allow_merge_commit', None),
        )

    def get_labels(self):
        labels = {}
        for label in self.ghrep.labels():
            labels[label.name] = label
        return labels

    def update_labels(self):

        current_labels = self.get_labels() #[x.name for x in self.ghrep.labels()]

        # Remove any labels not in the configuration
        if self.organization.configuration.get('labels_clean', False):
            label_names = [x['name'] for x in self.organization.configuration.get('labels', [])]
            for active_label in self.ghrep.labels():
                if active_label.name not in label_names:
                    active_label.delete()

        for config_label in self.organization.configuration.get('labels', []):
            if config_label.get('old_name'):
                label_object = self.ghrep.label(config_label['old_name'])
                if label_object:
                    label_object.update(
                        config_label['name'],
                        config_label.get('color', DEFAULT_LABEL_COLOR),
                        config_label.get('description', None))
                    continue

            if config_label['name'] in current_labels:
                label_object = current_labels[config_label['name']] #self.ghrep.label(config_label['name'])
                if not label_matches(config_label, label_object):
                    label_object.update(
                        config_label['name'],
                        config_label.get('color', DEFAULT_LABEL_COLOR),
                        config_label.get('description', None))
            else:
                self.ghrep.create_label(
                    config_label['name'],
                    config_label.get('color', DEFAULT_LABEL_COLOR),
                    config_label.get('description', None))

    def update_issues(self):

        if not self.organization.configuration.get('issues', False):
            return False
        if not self.organization.configuration['issues'].get('auto_assign_project', False):
            return False

        issue_config = self.organization.configuration['issues']


        if 'organization' in issue_config:
            project = self.organization.ghorg.project(self.organization.configuration['issues']['name'])
        else:
            project = self.ghrep.project(self.organization.configuration['issues']['name'])
        project_column = project.column(self.organization.configuration['issues']['column'])

        for issue in self.ghrep.issues(state='open', sort='created', direction='asc'):
            project_column.create_card_with_issue(issue)

    def get_projects(self):
        for project in self.ghrep.projects():
            yield Project(self.client, project, self.organization)

    def get_project_by_name(self, name):
        @cache.cache(expire=CACHE_MEDIUM)
        def repo_get_project_id_from_name(repo, name):
            for project in repo.get_projects():
                if project.name == name:
                    return project.id
            return False
        id = repo_get_project_id_from_name(self, name)
        if not id:
            return False
        return Project(self.client, self.ghrep.project(id), self.organization)

    def get_issues(self):
        for issue in self.ghrep.issues(state = 'Open'):
            yield issue

    def get_issue(self, issue_id):
        return self.ghrep.issue(issue_id)

    def get_autoassign_project(self):
        if not self.organization.configuration:
            return False
        configuration = self.organization.configuration
        if not 'issues' in configuration:
            return False
        if not 'project_autoassign' in configuration['issues']:
            return False
        autoassign = configuration['issues']['project_autoassign']
        if autoassign['organization']:
            return self.organization.get_project_by_name(autoassign['name'])
        if autoassign['repository']:
            return self.organization.get_repository(autoassign['repository']).get_project_by_name(autoassign['name'])
        return self.get_project_by_name(autoassign['name'])

    def get_autoassign_column(self):
        configuration = self.organization.configuration
        project = self.get_autoassign_project()
        if not project:
            return False
        return project.get_column_by_name(configuration['issues']['project_autoassign']['column'])


class Project:

    def __repr__(self):
        return 'OrganizerProject %s' % self.id

    def __str__(self):
        return self.__repr__()

    def __init__(self, client, project, organization):
        self.client = client
        self.ghproject = project
        self.organization = organization
        self.id = project.id
        self.name = project.name

    def get_column(self, id):
        return self.ghproject.column(id)

    def get_columns(self):
        for column in self.ghproject.columns():
            yield column

    def get_column_by_name(self, name):
        @cache.cache(expire=CACHE_MEDIUM)
        def get_column_id_from_name(project, name):
            for column in project.get_columns():
                if column.name == name:
                    return column.id
            return False
        id = get_column_id_from_name(self, name)
        if not id:
            return False
        return self.get_column(id)


def label_matches(config_label, label):
    if label.color != config_label.get('color', DEFAULT_LABEL_COLOR):
        return False
    if label.description != config_label.get('description', None):
        return False
    return True
