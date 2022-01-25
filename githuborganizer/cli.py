import click
import github3
import models.gh
import tasks.github
from githuborganizer.services.github import ghapp, get_organization_client
import githuborganizer.tasks.github as tasks
import random
import string
import os
import config


@click.group()
@click.pass_context
def cli(ctx):
    if ctx.parent:
        print(ctx.parent.get_help())


@cli.command(short_help="Obtain an authorization token")
def auth():
    username = click.prompt('Username')
    password = click.prompt('Password', hide_input=True)
    def twofacallback(*args):
        return click.prompt('2fa Code')

    hostid = ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(8))
    note = 'githuborgsync - %s' % (hostid,)
    note_url = 'https://github.com/tedivm/githuborgsync'
    scopes = ['repo']
    auth = github3.authorize(username, password, scopes, note, note_url, two_factor_callback=twofacallback)

    with open("%s/%s" % (os.getcwd(), '/.gitcredentials'), 'w') as fd:
        fd.write(str(auth.id) + '\n')
        fd.write(auth.token + '\n')


@cli.command(short_help="List the settings for an organization or repository")
@click.argument('organization')
@click.argument('repository', default=False)
def settings(organization, repository):
    gh = get_organization_client(organization)
    org = models.gh.Organization(gh, organization)
    if repository:
        repo = org.get_repository(repository)
        click.echo(repo.get_organizer_settings())
    else:
        click.echo(org.configuration)


@cli.command(short_help="Update a single repository's settings")
@click.argument('organization')
@click.argument('repository')
def update_repo(organization, repository):
    tasks.github.update_repository_settings(organization, repository)
    tasks.github.update_repository_labels(organization, repository)
    tasks.github.update_repository_security_settings(organization, repository)


@cli.command(short_help="Update all repositories in an organization")
@click.argument('organization')
def update_repos(organization):
    tasks.github.update_organization_settings(organization, True)


@cli.command(short_help="Update repository teams for an organization")
@click.argument('organization')
def update_team_repos(organization):
    tasks.github.update_organization_teams(organization)


@cli.command(short_help="Update repository teams for an organization")
@click.argument('organization')
@click.argument('team')
def get_team_permissions(organization, team):
    installation = ghapp.get_org_installation(organization)
    gh = get_organization_client(organization)
    org = models.gh.Organization(gh, organization)
    team = org.get_team_by_name(team)
    click.echo(models.gh.team_has_repositories(installation, team))


@cli.command(short_help="List the repositories in an organization")
@click.argument('organization')
def list_repos(organization):
    gh = get_organization_client(organization)
    org = models.gh.Organization(gh, organization)
    for repo in org.get_repositories():
        click.echo(repo.name)


@cli.command(short_help="")
@click.argument('organization')
def list_org_projects(organization):
    gh = get_organization_client(organization)
    org = models.gh.Organization(gh, organization)
    for project in org.get_projects():
        click.echo('%s\t%s' % (project.id, project.name))


@cli.command(short_help="")
@click.argument('organization')
@click.argument('project')
def get_org_project(organization, project):
    gh = get_organization_client(organization)
    org = models.gh.Organization(gh, organization)
    ghproject = org.get_project_by_name(project)
    click.echo('%s\t%s' % (ghproject.id, ghproject.name))


@cli.command(short_help="")
@click.argument('organization')
@click.argument('project')
@click.argument('column')
def get_org_project_column(organization, project, column):
    gh = get_organization_client(organization)
    org = models.gh.Organization(gh, organization)
    project = org.get_project_by_name(project)
    column = project.get_column_by_name(column)
    click.echo('%s\t%s' % (column.id, column.name))


@cli.command(short_help="")
@click.argument('organization')
@click.argument('repository')
@click.argument('project')
def get_repo_project(organization, repository, project):
    gh = get_organization_client(organization)
    org = models.gh.Organization(gh, organization)
    repo = org.get_repository(repository)
    ghproject = repo.get_project_by_name(project)
    click.echo('%s\t%s' % (ghproject.id, ghproject.name))


@cli.command(short_help="")
@click.argument('organization')
@click.argument('repository')
def update_branch_protection(organization, repository):
    tasks.github.update_repo_branch_protection(organization, repository, synchronous=True)


@cli.command(short_help="")
@click.argument('organization')
@click.argument('repository')
@click.argument('issue')
def assign_issue(organization, repository, issue):
    tasks.github.assign_issue(organization, repository, issue)


@cli.command(short_help="")
@click.argument('organization')
@click.argument('repository')
@click.argument('issue')
def label_issue(organization, repository, issue):
    tasks.github.label_issue(organization, repository, issue)


@cli.command(short_help="")
@click.argument('organization')
@click.argument('team')
def update_team_membership(organization, team):
    tasks.github.update_team_members(organization, team)


@cli.command(short_help="")
@click.argument('organization')
def update_org_team_membership(organization):
    tasks.github.update_organization_team_members(organization, synchronous=True)


@cli.command(short_help="")
def app_info():
    for install_id in ghapp.get_installations():
        click.echo('Install ID: %s' % (install_id))
        install = ghapp.get_installation(install_id)
        click.echo(install.get_organization())


@cli.command(short_help="")
@click.argument('organization')
def org_info(organization):
    click.echo(ghapp.get_org_installation(organization))




if __name__ == '__main__':
    cli()
