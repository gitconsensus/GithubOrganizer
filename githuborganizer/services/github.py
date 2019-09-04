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



ghapp = GithubOrganizerApp(os.environ['GITHUB_APP_ID'], os.environ['GITHUB_PRIVATE_KEY'])


def get_installation_client(installation_id):
    return ghapp.get_installation(install_id).get_github3_client()

def get_organization_client(organization):
    return ghapp.get_org_installation(organization).get_github3_client()
