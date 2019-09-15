from githuborganizer import celery
import githuborganizer.models.gh as gh
from githuborganizer.services.github import ghapp, get_organization_client


@celery.task(rate_limit='4/h', max_retries=0)
def process_installs(synchronous = False):
    print('Initiating run of all installations.')
    for install_id in ghapp.get_installations():
        print('Install ID: %s' % (install_id))
        install = ghapp.get_installation(install_id)
        if synchronous:
            update_organization_settings(install.get_organization())
        else:
            update_organization_settings.delay(install.get_organization())


@celery.task(max_retries=0)
def update_organization_settings(org_name, synchronous = False):
    print('Configuring all repos in %s.' % (org_name))
    ghclient = get_organization_client(org_name)
    org = gh.Organization(ghclient, org_name)
    if not org.configuration:
        print('Organization %s does not have a configuration file in %s/github' % (org_name, org_name))
        return False
    for repo in org.get_repositories():
        organizer_settings = repo.get_organizer_settings()
        if synchronous:
            update_repository_settings(org_name, repo.name)
            if 'labels' in org.configuration:
                update_repository_labels(org_name, repo.name)
            if 'dependency_security' in organizer_settings:
                update_repository_security_settings(org_name, repo.name)
        else:
            update_repository_settings.delay(org_name, repo.name)
            if 'labels' in org.configuration:
                update_repository_labels.delay(org_name, repo.name)
            if 'dependency_security' in organizer_settings:
                update_repository_security_settings.delay(org_name, repo.name)


@celery.task(max_retries=0)
def update_repository_settings(org_name, repo_name):
    print('Updating the settings of repository %s/%s.' % (org_name, repo_name))
    ghclient = get_organization_client(org_name)
    org = gh.Organization(ghclient, org_name)
    repo = org.get_repository(repo_name)
    repo.update_settings()


@celery.task(max_retries=0)
def update_repository_security_settings(org_name, repo_name):
    print('Updating the dependency security settings of repository %s/%s.' % (org_name, repo_name))
    ghclient = get_organization_client(org_name)
    org = gh.Organization(ghclient, org_name)
    repo = org.get_repository(repo_name)
    repo.update_security_scanning()


@celery.task(max_retries=0)
def update_repository_labels(org_name, repo_name):
    print('Updating the labels of repository %s/%s.' % (org_name, repo_name))
    ghclient = get_organization_client(org_name)
    org = gh.Organization(ghclient, org_name)
    repo = org.get_repository(repo_name)
    repo.update_labels()


@celery.task(default_retry_delay=65*60)
def assign_issues(org_name, repo_name, synchronous = False):
    ghclient = get_organization_client(org_name)
    org = gh.Organization(ghclient, org_name)
    repo = org.get_repository(repo_name)
    column = repo.get_autoassign_column()
    if not column:
        return False
    for issue in repo.get_issues():
        if synchronous:
            assign_issue(org_name, repo_name, issue.number)
        else:
            assign_issue.delay(org_name, repo_name, issue.number)


@celery.task(default_retry_delay=65*60)
def assign_issue(org_name, repo_name, issue_number):
    installation = ghapp.get_org_installation(org_name)
    ghclient = installation.get_github3_client()
    org = gh.Organization(ghclient, org_name)
    repo = org.get_repository(repo_name)
    column = repo.get_autoassign_column()
    if not column:
        print('No autoassign column found')
        return False
    if gh.issue_has_projects(installation, org_name, repo_name, issue_number):
        print('Already assigned to a project')
        return False
    print('Assigning issue %s to column %s' % (issue_number, column.name))
    issue = repo.get_issue(issue_number)
    if not column.create_card_with_issue(issue):
        print('Unable to assign issue %s to column %s' % (issue_number, column.name))
