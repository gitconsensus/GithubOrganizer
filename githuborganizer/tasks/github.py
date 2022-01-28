from githuborganizer import celery
import githuborganizer.models.gh as gh
from githuborganizer.services.github import ghapp, get_organization_client


@celery.task(rate_limit='4/h', max_retries=0)
def process_installs(synchronous = False):
    print('Initiating run of all installations.')
    for install_id in ghapp.get_installations():
        print('Install ID: %s' % (install_id))
        install = ghapp.get_installation(install_id)
        organization = install.get_organization()
        if synchronous:
            update_organization_settings(organization)
            update_organization_teams(organization)
            update_organization_team_members(organization)
        else:
            update_organization_settings.delay(organization)
            update_organization_teams.delay(organization)
            update_organization_team_members.delay(organization)


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
            if 'branches' in organizer_settings:
                update_repo_branch_protection(org_name, repo.name, synchronous=True)
        else:
            update_repository_settings.delay(org_name, repo.name)
            if 'labels' in org.configuration:
                update_repository_labels.delay(org_name, repo.name)
            if 'dependency_security' in organizer_settings:
                update_repository_security_settings.delay(org_name, repo.name)
            if 'branches' in organizer_settings:
                update_repo_branch_protection.delay(org_name, repo.name)


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
def update_repo_branch_protection(org_name, repo_name, synchronous = False):
    ghclient = get_organization_client(org_name)
    org = gh.Organization(ghclient, org_name)
    repo = org.get_repository(repo_name)
    settings = repo.get_organizer_settings()
    if 'branches' not in settings:
        return
    for branch in settings['branches']:
        if synchronous:
            update_branch_protection(org_name, repo_name, branch)
        else:
            update_branch_protection.delay(org_name, repo_name, branch)


@celery.task(max_retries=0)
def update_branch_protection(org_name, repo_name, branch):
    ghclient = get_organization_client(org_name)
    org = gh.Organization(ghclient, org_name)
    repo = org.get_repository(repo_name)
    settings = repo.get_organizer_settings()
    if 'branches' not in settings:
        return
    if branch not in settings['branches']:
        return
    print('Updating branch protection for %s in %s/%s.' % (branch, org_name, repo_name))
    bsettings = settings['branches'][branch]

    gh.branch_protection(
        installation=ghclient.app,
        repository=repo,
        branch=branch,
        required_status_checks=bsettings.get('required_status_checks', None),
        enforce_admins=bsettings.get('enforce_admins', False),
        required_pull_request_reviews=bsettings.get('required_pull_request_reviews', None),
        restrictions=bsettings.get('restrictions', None),
        required_linear_history=bsettings.get('required_linear_history', False),
        allow_force_pushes=bsettings.get('allow_force_pushes', False),
        allow_deletions=bsettings.get('allow_deletions', False),
        required_approving_review_count=bsettings.get('required_approving_review_count', 1),
        require_code_owner_reviews=bsettings.get('require_code_owner_reviews',False),
        dismiss_stale_reviews=bsettings.get('dismiss_stale_reviews', True)
        )


@celery.task(max_retries=0)
def update_repository_default_branch(org_name, repo_name):
    ghclient = get_organization_client(org_name)
    org = gh.Organization(ghclient, org_name)
    repo = org.get_repository(repo_name)
    repo.update_default_branch()


@celery.task(max_retries=0)
def update_repository_labels(org_name, repo_name):
    print('Updating the labels of repository %s/%s.' % (org_name, repo_name))
    ghclient = get_organization_client(org_name)
    org = gh.Organization(ghclient, org_name)
    repo = org.get_repository(repo_name)
    repo.update_labels()


@celery.task(max_retries=0)
def update_organization_teams(org_name):
    ghclient = get_organization_client(org_name)
    org = gh.Organization(ghclient, org_name)
    repositories = [x for x in org.get_repositories()]
    for ghteam in org.ghorg.teams():
        repo_permissions = gh.team_has_repositories(org.client.app, ghteam)
        for repository in repositories:
            repo_config = repository.get_organizer_settings()
            current = repo_permissions.get(repository.name, [])
            repo_full_name = '%s/%s' % (org.name, repository.name)
            if 'teams' in repo_config and ghteam.name in repo_config['teams']:
                permission = repo_config['teams'][ghteam.name]
                if permission not in current:
                    print('Team %s adding %s permission on %s.' % (ghteam.name, permission, repo_full_name))
                    ghteam.add_repository(repo_full_name, permission)
                elif permission == 'pull' and len(current) > 1:
                    print('Team %s setting %s permission on %s.' % (ghteam.name, permission, repo_full_name))
                    ghteam.add_repository(repo_full_name, permission)
                elif permission == 'push' and len(current) > 2:
                    print('Team %s setting %s permission on %s.' % (ghteam.name, permission, repo_full_name))
                    ghteam.add_repository(repo_full_name, permission)
            elif repo_config.get('teams_clean', False) and len(current) > 0:
                print('Team %s removing %s permissions on %s.' % (ghteam.name, ', '.join(current), repo_full_name))
                ghteam.remove_repository(repo_full_name)


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


@celery.task(default_retry_delay=65*60)
def label_issue(org_name, repo_name, issue_number):
    installation = ghapp.get_org_installation(org_name)
    ghclient = installation.get_github3_client()
    org = gh.Organization(ghclient, org_name)
    repo = org.get_repository(repo_name)
    autoassign_labels = repo.get_autoassign_labels()
    if not autoassign_labels:
        return
    issue = repo.get_issue(issue_number)
    for label in autoassign_labels:
        issue.add_labels(label)


@celery.task(max_retries=0)
def update_organization_team_members(org_name, synchronous = False):
    installation = ghapp.get_org_installation(org_name)
    ghclient = installation.get_github3_client()
    org = gh.Organization(ghclient, org_name)
    if not org.configuration:
        print('Organization %s does not have a configurations.' % (org_name))
        return
    if not 'teams' in org.configuration:
        return
    for team in org.configuration['teams']:
        if synchronous:
            update_team_members(org_name, team)
        else:
            update_team_members.delay(org_name, team)


@celery.task(max_retries=0)
def update_team_members(org_name, team_name):
    installation = ghapp.get_org_installation(org_name)
    ghclient = installation.get_github3_client()
    org = gh.Organization(ghclient, org_name)
    if not 'teams' in org.configuration:
        return
    if not team_name in org.configuration['teams']:
        return
    settings = org.configuration['teams'][team_name]
    if not 'members' in settings:
        return
    try:
        team = org.get_team_by_name(team_name)
    except:
        print('Creating team %s in organization %s' % (team_name, org_name))
        team = org.ghorg.create_team(team_name)
    existing = []
    for member in team.members():
        existing.append(member.login)
        if member.login not in settings['members']:
            print('Removing %s from team "%s" in organization "%s"' % (member.login, team_name, org_name))
            team.revoke_membership(member.login)
    for member in settings['members']:
        if member not in existing:
            print('Adding %s to team "%s" in organization "%s"' % (member, team_name, org_name))
            team.add_or_update_membership(member)
