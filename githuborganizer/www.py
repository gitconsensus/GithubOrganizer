from fastapi import FastAPI
from typing import Dict, Any
from starlette.requests import Request
import githuborganizer.tasks.github as tasks
import os

app = FastAPI()


@app.post("/githook")
def github_webhook(data: Dict[str, Any], request: Request):

    if 'github-event' in data:
        event = data['github-event']
    else:
        event = request.headers.get('X-GitHub-Event', False)

    if not event:
        return 'No event detected.'

    if os.environ.get('VALIDATE_WEBHOOKS', False):
        if not validate_signature(await request.body(), request.headers.get('X-Hub-Signature', False)):
            return 'Invalid Signature'

    if event == 'issues':
        return issue_payload(data)

    if event == 'repository':
        return repository_payload(data)

    if event == 'installation':
        return installation_payload(data)

    if event == 'installation_repositories':
        return installation_repositories(data)

    return 'No relevant events.'


def validate_signature(data, header_signature):
    # Enforce secret
    secret = os.environ.get('GITHUB_WEBHOOK_SECRET', False)
    if not secret:
        return True

    # Only SHA1 is supported
    header_signature = request.headers.get('X-Hub-Signature')
    if not header_signature:
        abort(403)

    sha_name, signature = header_signature.split('=')
    if sha_name != 'sha1':
        return False

    # HMAC requires the key to be bytes, but data is string
    mac = hmac.new(str(secret), msg=request.data, digestmod='sha1')

    if not hmac.compare_digest(str(mac.hexdigest()), str(signature)):
        return False

    return True


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
    update_organization_settings.delay(organization)
    return 'Processing organization %s.' % organization


def installation_repositories(payload):
    if payload['action'] != 'added':
        return
    for repository in payload['repositories_added']:
        organization = repository['full_name'].split('/')[0]
        tasks.update_repository_settings.delay(organization, repository['name'])
        tasks.update_repository_labels.delay(organization, repository['name'])
    return 'Processing new repositories.'
