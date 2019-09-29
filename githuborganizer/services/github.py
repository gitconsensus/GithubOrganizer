import base64
import datetime
from githuborganizer import config
import github3
from github3apps import GithubApp, GithubAppInstall
import json
import requests
import yaml
import os

class GithubOrganizerApp(GithubApp):

    def get_installation(self, installation_id):
        return GithubOrganizerAppInstall(self, installation_id)

    def get_org_installation(self, organization):
        url = 'orgs/%s/installation' % (organization)
        res = self.request(url)
        return self.get_installation(res['id'])


class GithubOrganizerAppInstall(GithubAppInstall):

    def get_github3_client(self):
        client = super().get_github3_client()
        client.app = self
        return client

    def get_organization(self):
        url = 'https://api.github.com/installation/repositories'
        res = self.request(url)
        repodata = res.json()
        if repodata['total_count'] < 1:
            return False
        return repodata['repositories'][0]['owner']['login']

    def graphql(self, payload):
        url = 'https://api.github.com/graphql'
        headers = {'Authorization': 'token %s' % self.get_auth_token()}
        r = requests.post(url=url, json=payload, headers=headers)
        r.raise_for_status()
        return r.json()

    def rest(self, verb, endpoint=False, payload=False, accepts=False, url=False):
        accepts_all = ['application/json', 'application/vnd.github.v3+json']
        if accepts:
            if isinstance(accepts, str):
                accepts_all.append(accepts)
            else:
                accepts_all += accepts
        if not url:
            url = 'https://api.github.com/%s' % endpoint
        headers = {
            'Authorization': 'token %s' % self.get_auth_token(),
            'Accept': ', '.join(accepts_all)
            }
        if payload:
            r = requests.request(verb, url, headers=headers, json=payload)
        else:
            r = requests.request(verb, url, headers=headers)
        r.raise_for_status()
        if len(r.content) <= 0:
            return True

        next = get_next(r)
        if next:
            results = r.json()
            results.append(self.rest('get', url=url, accepts=accepts))
            return results

        return r.json()


def get_next(r):
    link = r.headers.get('link', False)
    if not link:
        return False

    # Should be a comma separated string of links
    links = link.split(',')

    for link in links:
        # If there is a 'next' link return the URL between the angle brackets, or None
        if 'rel="next"' in link:
            return link[link.find("<")+1:link.find(">")]
    return False


ghapp = GithubOrganizerApp(os.environ['GITHUB_APP_ID'], os.environ['GITHUB_PRIVATE_KEY'])


def get_installation_client(installation_id):
    return ghapp.get_installation(install_id).get_github3_client()

def get_organization_client(organization):
    return ghapp.get_org_installation(organization).get_github3_client()
