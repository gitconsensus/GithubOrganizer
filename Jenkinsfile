import com.global.hooks.BuildDocker

setup

def dockerHook = new BuildDocker(
    steps: this,
    registry: "873328514756.dkr.ecr.eu-west-1.amazonaws.com",
    images: ["organisation-manager-www": ["path": ".", "dockerfile": "docker/dockerfile.www"],
             "organisation-manager-worker": ["path": ".", "dockerfile": "docker/dockerfile.worker"]
            ]
)

buildCode([
    aws: [role: "jenkins-devops", account: "873328514756"],
    hooks: [dockerHook]
])
