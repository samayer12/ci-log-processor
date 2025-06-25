from ghapi.all import GhApi
import os

github_token = os.environ["GITHUB_TOKEN"]

api = GhApi(owner="defenseunicorns", repo="pepr", token=github_token)

print(api.git.get_ref("heads/main"))