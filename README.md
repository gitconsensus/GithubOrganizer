# GithubOrgSync

The GitHub Organization Manager makes it easy to enforce standards across your organization.

GitHub itself has a lot of great tools - Branch Protection, Dependency Vulnerability Scanning, Projects and Labels, Issue Tracking, and so much more. The problem is that it's a serious pain for organizations that have a lot of repositories to make sure that all of their repos are being managed in the same way. Something as simple as ensuring all Pull Requests get reviewed before merging has to be managed on a project by project basis. This can be particularly painful for organizations that have compliance requirements.

The GitHub Organization Manager gets around that by letting you define your standards in one place and enforce them throughout your organization. It allows you to define a default standard that will apply to every repository, or a variety of standards that you can apply to different repositories based on their needs. When a new repository is created these standards will automatically apply, saving admins from dealing with manual setup each time.

## Installation

This app can be installed [directly on Github](https://github.com/apps/organization-manager). Since this is [an open source project](https://github.com/gitconsensus/GithubOrganizer) self hosting is also an option, although it's a bit trickier.

Once installed you'll need to create a file named `organizer.yaml` in the `.github` repository within your in your GitHub organization. This file will contain all of the settings you want to have applied to your organization.

# How it works

## Organizing Repository Settings

The simplest way to get started is to set default rules for all repositories.

```yml
repositories:
  default:
    features:
      has_issues: true
      has_wiki: false
      has_projects: true
      has_downloads: true
```

You can also set repository specific rules. Here we disable the wiki in all repositories except for `example_repo`.

```yml
repositories:
  default:
    features:
      has_issues: true
      has_wiki: false
      has_projects: false
      has_downloads: false
  example_repo:
    features:
      has_issues: true
      has_wiki: true
      has_projects: false
      has_downloads: false
```

Of course, putting individual rules for every repository can be rather burdensome. Another option is to define option groups - you can even extend existing option groups (like `default`) and make only the changes you need.

In this example we keep the default repository settings but add a new set, `production`, which requires code reviews before pull requests get merged into the main branch.

```yml
repositories:
  default:
    features:
      has_issues: true
      has_wiki: false
      has_projects: false
      has_downloads: false
  production:
    extends: default
    branches:
      main:
        enforce_admins: true
        required_status_checks:
          require_review: true
```

### Assigning Repositories to Settings Groups

This project offers two ways to assign repositories to the non-default group, Repository Topics and Inline Definitions.

Repository Topics let the admins of the repository assign a topic to that repo and pick up the settings based off of that. This means no changes are required to the organization's settings file. The prefix `gho-` is added to the topic (turning the `production` category into the topic `gho-production`) to tell the GitHub Organization Manager which settings to apply to the repository.

Another option is to define the options in the configuration file itself. The benefit of this is that settings are applied via Pull Request, which allows another level of enforcement and auditing. In this example we add `ExampleWebsite` and `.github` to the `production` category. To force people to use the config file it is also possible to disable topic assignment with the top level `topics_for_assignment` option (which is enabled by default).

```yml
# Optional- topic assignment and inline assignment can work together.
topics_for_assignment: false

repositories:
  default:
    features:
      has_issues: true
      has_wiki: false
      has_projects: false
      has_downloads: false
  production:
    extends: default
    branches:
      main:
        enforce_admins: true
        required_status_checks:
          require_review: true
  ExampleWebsite: production
  .github: production
```

### Configuring Repository Features

Each repository has a variety of GitHub features, such as projects and wikis, that this project can ensure are enabled or disabled.

```yml
repositories:
  default:
    features:
      has_issues: true
      has_wiki: false
      has_projects: true
      has_downloads: true
```

### Set Allowed Merge Types

Organizations can enforce specific merge types, preventing people from using the wrong type accidentally.

```yml
repositories:
  default:
    merges:
      allow_squash_merge: true
      allow_merge_commit: true
      allow_rebase_merge: true
```

### Automatically Label Issues

Issues can have labels applied automatically based on their repository. In this case every repository will automatically get labeled as `dev`, with two additional repositories (`example_repo` and `another_repo`) get tagged with `dev` and `production`, as they inherit the production rules.

```yml
repositories:
  default:
    issues:
      auto_label:
        - dev
  production:
    issues:
      auto_label:
        - dev
        - production
  example_repo: production
  another_repo: production
```

### Assign Issues to Projects

Issues can get assigned to projects automatically, prevent issues from getting lost in the shuffle if someone forgets to assign one on creation. These projects can be either local repository projects or organization level projects.

```yml
repositories:
  default:
    issues:
      project_autoassign:
        organization: true
        name: TestProject
        column: To do
```

### Assign Teams and Permissions

Another important use case is adding teams to repositories. This makes it easy to add default teams to all repositories as well as special teams to specific repositories or repository groups.

```yml
repositories:
  default:
    teams:
      devs: Push # Pull, Push, Admin
      admins: Admin # Pull, Push, Admin
      support: Pull # Pull, Push, Admin
  production:
    teams:
      devs: Pull
      infra: Push
```

### Set Branch Protection

Branch protection is an important piece of quality control, and can even be part of an organization's compliance program. Branch protection can be set globally, with additional requirements:

```yml
repositories:
  default:
    branches:
      main:
        enforce_admins: false
        required_status_checks:
          require_review: true

  production:
    branches:
      main:
        enforce_admins: true
        required_status_checks:
          require_review: true

      prod:
        enforce_admins: true
        required_status_checks:
          require_review: true
          strict: true
```

Branch protection has a lot of potential configuration options, including:

- **dismiss_stale_reviews**: will dismiss reviews if they become stale (such as having a new commits).
- **require_code_owner_reviews**: will require the code owner (if one is set) to perform a review.
- **enforce_admins**: will remove the ability for admins to override the protections to force a merge.
- **required_approving_review_count**: sets a specific number of people required to approve reviews.

In addition the `required_status_checks` has a few options of its own -

- **strict**: requires a pull request to be up to date with the branch before it can be merged.
- **context**: when empty all tests must pass, otherwise it takes an array individual tests (such `ci/circleci` or `coverage/coveralls`) which must pass.
- **require_review**: when set to true at least one review must occur before a pull request can be merged into the branch.

```yml
repositories:
  default:
    branches:
      main:
        dismiss_stale_reviews: false
        require_code_owner_reviews: false
        enforce_admins: false
        required_approving_review_count: 5
        required_status_checks:
          strict: false
```

### Enforce Dependency Security

A fantastic new feature of GitHub is that it can scan your repositories for upstream vulnerabilities, and even make pull requests to resolve them. This feature is opt in, making it easy to forget. This project allows you to set it on the organization level, so you never have to worry about accidentally leaving a repository vulnerable.


```yml
repositories:
  default:
    dependency_security:
      alerts: true
      automatic_fixes: true
```

## Teams

This function will create teams and keep their members up to date with the list in the configuration file, adding and removing members as needed.

```yml
teams:
  admins:
    members:
      - tedivm
  devs:
    members:
      - tedivm
      - AliLynne
```

## Labels

### Manage Organization Labels

Keeping labels in sync can be a huge chore when an organization has a large number of repositories. This project keeps labels in sync, optionally cleaning up labels which aren't in the organization file.

```yml
labels_clean: true

labels:
  # Built in labels.

  - name: bug
    description: "Something isn't working"
    color: d73a4a

  - name: documentation
    description: "Improvements or additions to documentation"
    color: 0075ca

  - name: duplicate
    description: "This issue or pull request already exists"
    color: cfd3d7

  - name: good first issue
    description: "Good for newcomers"
    color: 7057ff

  - name: enhancement
    description: "New feature or request"
    color: a2eeef

  - name: help wanted
    description: "Extra attention is needed"
    color: 008672

  - name: invalid
    description: "This doesn't seem right"
    color: e4e669

  - name: question
    description: "Further information is requested"
    color: d876e3

  - name: wontfix
    description: "This will not be worked on"
    color: ffffff

  # Teams/Groups

  - name: infra
    color: db5cb3

  - name: dev
    color: aaffe0
```

## Automatically Label Repository Issues

A common request is to give all issues in a specific repository labels, without having to define a per-repository set of configurations. This can be done with the `repos` setting for the label.

```yml
labels:
  - name: infra
    description: "Infrastructure Team"
    color: d73a4a
    repos:
      - infra-terraform
      - infra-puppet
```

## Enforce and Migrate Default Branches

With the GitHub Organization Manager it is possible to enforce default branches across an organization. It is important to note that this is one of the most intrusive features of this project and should be used with care, as the project will actually branch the existing default branch to create the new one if needed (it will not delete the old branch). This can cause a serious disruption for developers if they are not told about this in advance. However, for organizations that are making a conscious effort to change their default branch names, this can remove a lot of manual work.

In this example we set the default branch to `main`

```yml
repositories:
  # All Repositories not assigned to other groups.
  default:
    issues:
      auto_label:
        - dev
    dependency_security:
      alerts: true
      automatic_fixes: true
    branches:
      main:
        default: true
        enforce_admins: true
        required_status_checks:
          strict: true
          require_review: true
```

## Examples

### Simple Example

This example applies the same rules to every repository.

```yml
repositories:
  # All Repositories not assigned to other groups.
  default:
    issues:
      auto_label:
        - dev
    dependency_security:
      alerts: true
      automatic_fixes: true
    merges:
      allow_squash_merge: false
      allow_merge_commit: false
      allow_rebase_merge: true
    features:
      has_issues: true
      has_wiki: false
      has_projects: false
      has_downloads: false
    branches:
      main:
        enforce_admins: true
        required_status_checks:
          strict: true
          require_review: true

labels_clean: true

labels:
  # Built in labels.

  - name: bug
    description: "Something isn't working"
    color: d73a4a

  - name: documentation
    description: "Improvements or additions to documentation"
    color: 0075ca

  - name: duplicate
    description: "This issue or pull request already exists"
    color: cfd3d7

  - name: good first issue
    description: "Good for newcomers"
    color: 7057ff

  - name: enhancement
    description: "New feature or request"
    color: a2eeef

  - name: help wanted
    description: "Extra attention is needed"
    color: 008672

  - name: invalid
    description: "This doesn't seem right"
    color: e4e669

  - name: question
    description: "Further information is requested"
    color: d876e3

  - name: wontfix
    description: "This will not be worked on"
    color: ffffff
```

## Full Example

This example has one set of default repository rules, as well as special rules for production repositories and some another rule for websites. The production rules are based off of the default rules, and then the website rules extend those.

```yml
teams:
  Admins:
    members:
      - tedivm
  Developers:
    members:
      - tedivm
      - AliLynne
  Website:
    members:
      - tedivm
      - AliLynne

repositories:
  # All Repositories not assigned to other groups.
  default:
    teams_clean: true
    teams:
      Admins: admin
      Developers: push
    issues:
      auto_label:
        - dev
      project_autoassign:
        organization: true
        name: Primary Planning
        column: New Issues and Tasks
    dependency_security:
      alerts: true
      automatic_fixes: true
    merges:
      allow_squash_merge: false
      allow_merge_commit: false
      allow_rebase_merge: true
    features:
      has_issues: true
      has_wiki: false
      has_projects: false
      has_downloads: false

  # Any repository specifically assigned to "production".
  production:
    extends: default
    teams_clean: true
    teams:
      Admins: admin
      Developers: pull
    issues:
      auto_label:
        - dev
        - prod
      project_autoassign:
        organization: true
        name: Primary Planning
        column: New Issues and Tasks
    branches:
      main:
        enforce_admins: true
        required_status_checks:
          strict: true
          require_review: true

  # Give the website team access to these repos.
  website:
    extends: default
    teams:
      Admins: admin
      Website: pull

  # Individual repository assignments-
  # this can be used instead of using Repository Topics.
  .github: production
  GithubOrganizer: production
  GitConsensusService: production
  GitConsensusCLI: production
  organizer.gitconsensus.com: website
  www.gitconsensus.com: website

labels_clean: true

labels:
  # Built in labels.

  - name: bug
    description: "Something isn't working"
    color: d73a4a

  - name: documentation
    description: "Improvements or additions to documentation"
    color: 0075ca
    repos:
      - organizer.gitconsensus.com
      - www.gitconsensus.com

  - name: duplicate
    description: "This issue or pull request already exists"
    color: cfd3d7

  - name: good first issue
    description: "Good for newcomers"
    color: 7057ff

  - name: enhancement
    description: "New feature or request"
    color: a2eeef

  - name: help wanted
    description: "Extra attention is needed"
    color: 008672

  - name: invalid
    description: "This doesn't seem right"
    color: e4e669

  - name: question
    description: "Further information is requested"
    color: d876e3

  - name: wontfix
    description: "This will not be worked on"
    color: ffffff

  # Useful labels

  - name: security
    color: db5cb3

  - name: refactor
    color: db5cb3
    repos:
      - test_rep

  - name: stability
    color: db5cb3

  - name: needs discussion
    color: "e08155"
```