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
from copy import copy


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


def team_has_repositories(installation, team):
    # GET /teams/:team_id/repos
    results = installation.rest(
        'get',
        'teams/%s/repos' % (team.id),
        payload=False,
        accepts=['application/vnd.github.hellcat-preview+json']
    )
    repositories = {}
    for repo in results:
        repositories[repo['name']] = []
        for permission in repo['permissions']:
            if repo['permissions'][permission]:
                repositories[repo['name']].append(permission)
    return repositories


def branch_protection(
    installation,
    repository,
    branch,
    required_status_checks = None,
    enforce_admins = False,
    required_pull_request_reviews = None,
    restrictions = None,
    required_linear_history = False,
    allow_force_pushes = False,
    allow_deletions = False,
    required_approving_review_count = 1,
    require_code_owner_reviews = False,
    dismiss_stale_reviews = True
    ):

    # required_status_checks
    # - strict - boolean
    # - contexts - array, leave empty for "all"
    if required_status_checks:
        if 'contexts' not in required_status_checks:
            required_status_checks['contexts'] = []
        if 'strict' not in required_status_checks:
            required_status_checks['strict'] = False

    # enforce_admins - boolean
    enforce_admins = bool(enforce_admins)

    # required_pull_request_reviews
    # - dismissal_restrictions - object (optional)
    #   - users - array
    #   - teams - array
    # - dismiss_stale_reviews - boolean
    # - require_code_owner_reviews - boolean
    # - required_approving_review_count - integer
    if required_status_checks:
        if 'require_review' in required_status_checks:
            del required_status_checks['require_review']
            if 'required_approving_review_count' not in required_status_checks:
                required_status_checks['required_approving_review_count'] = 1

    # restrictions
    # - users - array
    # - teams - array
    # - apps - array
    if restrictions:
        for field in ['users', 'teams', 'apps']:
            if field not in restrictions:
                restrictions[field] = []

    if required_pull_request_reviews:
        required_pull_request_reviews_payload = {
            'dismissal_restrictions': {'users':[], 'teams': []},
            'dismiss_stale_reviews': dismiss_stale_reviews,
            'require_code_owner_reviews': require_code_owner_reviews,
            'required_approving_review_count': required_approving_review_count
        }
    else:
        required_pull_request_reviews_payload = None

    request_payload = {
        'required_status_checks': required_status_checks,
        'enforce_admins': enforce_admins,
        'required_pull_request_reviews': required_pull_request_reviews_payload,
        'restrictions': restrictions,
        'required_linear_history': required_linear_history,
        'allow_force_pushes': allow_force_pushes,
        'allow_deletions': allow_deletions
    }


    print(json.dumps(request_payload))

    results = installation.rest(
        'put',
        'repos/%s/%s/branches/%s/protection' % (repository.organization.name, repository.name, branch),
        payload=request_payload,
        accepts=['application/vnd.github.luke-cage-preview+json']
    )


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
                try:
                    config_repository = client.repository(org_name, '.organizer')
                    return yaml.safe_load(config_repository.file_contents('organizer.yaml').decoded.decode('utf-8'))
                except:
                    return False

        self.client = client
        self.name = organization
        self.configuration = get_configuration(organization)
        self._ghorg = False


    @property
    def ghorg(self):
        '''Lazy loading the client to reduce API calls when we don't actually need them.'''
        if not self._ghorg:
            self._ghorg = self.client.organization(self.name)
        return self._ghorg


    def get_repositories(self):
        for repository in self.ghorg.repositories():
            if 'exclude_repositories' in self.configuration:
                if repository.name in self.configuration['exclude_repositories']:
                    continue
            if self.configuration.get('exclude_forks', False) and repository.fork:
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

    def get_team_by_name(self, name):
        @cache.cache(expire=CACHE_MEDIUM)
        def org_get_team_id_from_name(org, name):
            accepts = ['application/vnd.github.hellcat-preview+json']
            endpoint = 'orgs/%s/teams/%s' % (org.name, name)
            results = self.client.app.rest('get', endpoint, accepts=accepts)
            if not results:
                return False
            return results['id']
        id = org_get_team_id_from_name(self, name.replace(' ', '-'))
        if not id:
            return False
        return self.ghorg.team(id)



class Repository:

    def __repr__(self):
        return 'OrganizerRepository %s/%s' % (self.organization.name, self.name)

    def __str__(self):
        return self.__repr__()

    def __init__(self, client, organization, repo_name, ghrep=None):
        self.client = client
        self.organization = organization
        self.name = repo_name
        self._ghrep = False
        if ghrep:
            self._ghrep = ghrep

    @property
    def ghrep(self):
        '''Lazy loading the client to reduce API calls when we don't actually need them.'''
        if not self._ghrep:
            self._ghrep = self.client.repository(self.organization.name, self.name)
        return self._ghrep

    def update_settings(self):
        organizer_settings = self.get_organizer_settings()
        self.ghrep.edit(self.name,
            has_issues = organizer_settings.get('features', {}).get('has_issues', None),
            has_wiki = organizer_settings.get('features', {}).get('has_wiki', None),
            has_downloads = organizer_settings.get('features', {}).get('has_downloads', None),
            has_projects = organizer_settings.get('features', {}).get('has_projects', None),
            allow_rebase_merge = organizer_settings.get('merges', {}).get('allow_rebase_merge', None),
            allow_squash_merge = organizer_settings.get('merges', {}).get('allow_squash_merge', None),
            allow_merge_commit = organizer_settings.get('merges', {}).get('allow_merge_commit', None),
            delete_branch_on_merge = organizer_settings.get('delete_branch_on_merge', None)
        )

    def update_default_branch(self):
        org_settings = self.get_organizer_settings()
        if 'branches' not in org_settings:
            return

        # If this repo is a fork then leave it alone.
        if self.ghrep.source:
            return

        for branch in org_settings['branches']:
            settings = org_settings['branches'][branch]
            if "default" not in settings:
                continue
            if not settings["default"]:
                continue
            if self.ghrep.default_branch == branch:
                return

            # Fails if branch exists, creates it from current default branch otherwise.
            # Saves us at least one API call to see if the branch exists
            try:
                self.create_branch(branch)
            except:
                pass
            return self.ghrep.edit(self.name, default_branch=branch)



    def get_labels(self):
        labels = {}
        for label in self.ghrep.labels():
            labels[label.name] = label
        return labels


    def get_topics(self):
        topics = {}
        return self.ghrep.topics().names


    def get_organizer_settings(self, name = False, maxdepth = 5):
        topic_assignment = False
        if self.organization.configuration.get("topics_for_assignment", True):
            topics = self.get_topics()
            topic_assignments = [x for x in topics if x.startswith("gho-")]
            if len(topic_assignments) == 1:
                topic_assignment = topic_assignments[0][4:]

        if not self.organization.configuration:
            return False
        elif 'repositories' not in self.organization.configuration:
            '''Convert from the old style configuration to the current version'''
            settings = copy(self.organization.configuration)
            settings['merges'] = {}
            settings['features'] = {}
            if 'labels' in settings:
                del settings['labels']
            for feature in ['has_issues', 'has_wiki', 'has_downloads', 'has_projects']:
                if feature in settings:
                    settings['features'][feature] = settings[feature]
                    del settings[feature]
            for merge in ['allow_rebase_merge', 'allow_squash_merge', 'allow_merge_commit']:
                if merge in settings:
                    settings['merges'][merge] = settings[merge]
                    del settings[merge]
            return settings
        elif name and name in self.organization.configuration['repositories']:
            settings = self.organization.configuration['repositories'][name]
        elif topic_assignment and topic_assignment in self.organization.configuration['repositories']:
            settings = self.organization.configuration['repositories'][topic_assignment]
        elif not name and self.name in self.organization.configuration['repositories']:
            settings = self.organization.configuration['repositories'][self.name]
        elif 'default' in self.organization.configuration['repositories']:
            settings = self.organization.configuration['repositories']['default']
        if not settings:
            return False

        if isinstance(settings, str):
            settings = {'extends':settings}

        if 'extends' in settings and maxdepth > 0:
            parent = self.get_organizer_settings(name=settings['extends'], maxdepth=maxdepth-1)
            if parent:
                parent.update(settings)
                settings = parent
            del settings['extends']

        return settings

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
        organizer_settings = self.get_organizer_settings()
        if not organizer_settings:
            return False
        if 'auto_assign_project' not in organizer_settings['issues']:
            return False

        issue_config = organizer_settings['issues']

        if 'organization' in issue_config:
            project = self.organization.ghorg.project(issue_config['name'])
        else:
            project = self.ghrep.project(issue_config['name'])
        project_column = project.column(issue_config['column'])

        for issue in self.ghrep.issues(state='open', sort='created', direction='asc'):
            project_column.create_card_with_issue(issue)

    def update_security_scanning(self):
        organizer_settings = self.get_organizer_settings()
        if not organizer_settings:
            return False
        if 'dependency_security' not in organizer_settings:
            return False
        sec = organizer_settings['dependency_security']
        if 'alerts' in sec:
            self.toggle_vulnerability_alerts(sec['alerts'])
        if 'automatic_fixes' in sec:
            self.toggle_security_fixes(sec['automatic_fixes'])

    def toggle_vulnerability_alerts(self, enable):
        flag = 'application/vnd.github.dorian-preview+json'
        endpoint = 'repos/%s/%s/vulnerability-alerts' % (self.organization.name, self.name)
        verb = 'PUT' if enable else 'DELETE'
        return self.client.app.rest(verb, endpoint, accepts=flag)

    def toggle_security_fixes(self, enable):
        flag = 'application/vnd.github.london-preview+json'
        endpoint = 'repos/%s/%s/automated-security-fixes' % (self.organization.name, self.name)
        verb = 'PUT' if enable else 'DELETE'
        return self.client.app.rest(verb, endpoint, accepts=flag)

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
        organizer_settings = self.get_organizer_settings()
        if not organizer_settings:
            return False
        if not 'issues' in organizer_settings:
            return False
        if not 'project_autoassign' in organizer_settings['issues']:
            return False
        autoassign = organizer_settings['issues']['project_autoassign']
        if autoassign['organization']:
            return self.organization.get_project_by_name(autoassign['name'])
        if autoassign['repository']:
            return self.organization.get_repository(autoassign['repository']).get_project_by_name(autoassign['name'])
        return self.get_project_by_name(autoassign['name'])

    def get_autoassign_column(self):
        organizer_settings = self.get_organizer_settings()
        project = self.get_autoassign_project()
        if not project:
            return False
        return project.get_column_by_name(organizer_settings['issues']['project_autoassign']['column'])

    def get_autoassign_labels(self):
        organizer_settings = self.get_organizer_settings()
        if 'issues' in organizer_settings and 'auto_label' in organizer_settings['issues']:
            labels = set(organizer_settings['issues']['auto_label'])
        else:
            labels = set([])
        if 'labels' in self.organization.configuration:
            for label in self.organization.configuration['labels']:
                if 'repos' in label and self.name in label['repos']:
                    labels.add(label['name'])
        if len(labels) > 0:
            return labels
        return False

    def create_branch(self, branch_name):
        current_default_branch = self.ghrep.branch(self.ghrep.default_branch)
        self.ghrep.create_branch_ref(branch_name, current_default_branch.latest_sha())


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
