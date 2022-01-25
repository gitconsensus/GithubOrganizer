from fastapi import FastAPI
from typing import Dict, Any
from starlette.requests import Request
from githuborganizer.services.github import ghapp, get_organization_client
import githuborganizer.tasks.github as tasks

app = FastAPI()


@app.post("/githook")
def github_webhook(data: Dict[str, Any], request: Request):

    if 'github-event' in data:
        event = data['github-event']
    else:
        event = request.headers.get('X-GitHub-Event', False)


    if not event:
        return 'No event detected.'

    if event == 'issues':
        return issue_payload(data)

    if event == 'repository':
        return repository_payload(data)

    if event == 'installation':
        return installation_payload(data)

    if event == 'installation_repositories':
        return installation_repositories(data)

    return 'No relevant events.'



def issue_payload(payload):
    if payload['action'] not in ['opened', 'transferred']:
        return
    issue_number = payload['issue']['number']
    repository = payload['repository']['name']
    organization = payload['repository']['full_name'].split('/')[0]
    tasks.assign_issue.delay(organization, repository, issue_number)
    tasks.label_issue.delay(organization, repository, issue_number)
    return 'Processing issue #%s on %s/%s.' % (issue_number, organization, repository)


def repository_payload(payload):
    if payload['action'] not in ['created', 'unarchived']:
        return
    organization = payload['repository']['owner']['login']
    repository = payload['repository']['name']
    tasks.update_repository_settings.delay(organization, repository)
    tasks.update_repository_labels.delay(organization, repository)
    return 'Processing %s/%s.' % (organization, repository)


def installation_payload(payload):
    if payload['action'] == 'deleted':
        return
    install_id = payload['installation']['id']
    install = ghapp.get_installation(install_id)
    organization = install.get_organization()
    tasks.update_organization_settings.delay(organization)
    return 'Processing organization %s.' % organization


def installation_repositories(payload):
    if payload['action'] != 'added':
        return
    for repository in payload['repositories_added']:
        organization = repository['full_name'].split('/')[0]
        tasks.update_repository_settings.delay(organization, repository['name'])
        tasks.update_repository_labels.delay(organization, repository['name'])
    return 'Processing new repositories.'
