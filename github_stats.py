#!/usr/bin/python3

import asyncio
import os
from typing import Dict, List, Optional, Set, Tuple

import aiohttp
import requests


###############################################################################
# Main Classes
###############################################################################

class Queries(object):
    """
    Class with functions to query the GitHub GraphQL (v4) API and the REST (v3)
    API. Also includes functions to dynamically generate GraphQL queries.
    """

    def __init__(self, username: str, access_token: str,
                 session: aiohttp.ClientSession, max_connections: int = 10):
        self.username = username
        self.access_token = access_token
        self.session = session
        self.semaphore = asyncio.Semaphore(max_connections)

    async def query(self, generated_query: str) -> Dict:
        """
        Make a request to the GraphQL API using the authentication token from
        the environment
        :param generated_query: string query to be sent to the API
        :return: decoded GraphQL JSON output
        """
        headers = {
            "Authorization": f"Bearer {self.access_token}",
        }
        try:
            async with self.semaphore:
                r = await self.session.post("https://api.github.com/graphql",
                                            headers=headers,
                                            json={"query": generated_query})
            return await r.json()
        except:
            print("aiohttp failed for GraphQL query")
            # Fall back on non-async requests
            async with self.semaphore:
                r = requests.post("https://api.github.com/graphql",
                                  headers=headers,
                                  json={"query": generated_query})
                return r.json()

    async def query_rest(self, path: str, params: Optional[Dict] = None) -> Dict:
        """
        Make a request to the REST API
        :param path: API path to query
        :param params: Query parameters to be passed to the API
        :return: deserialized REST JSON output
        """

        for _ in range(60):
            headers = {
                "Authorization": f"token {self.access_token}",
            }
            if params is None:
                params = dict()
            if path.startswith("/"):
                path = path[1:]
            try:
                async with self.semaphore:
                    r = await self.session.get(f"https://api.github.com/{path}",
                                               headers=headers,
                                               params=tuple(params.items()))
                if r.status == 202:
                    print(f"A path returned 202. Retrying...")
                    await asyncio.sleep(2)
                    continue

                result = await r.json()
                if result is not None:
                    return result
            except:
                print("aiohttp failed for rest query")
                # Fall back on non-async requests
                async with self.semaphore:
                    r = requests.get(f"https://api.github.com/{path}",
                                     headers=headers,
                                     params=tuple(params.items()))
                    if r.status_code == 202:
                        print(f"A path returned 202. Retrying...")
                        await asyncio.sleep(2)
                        continue
                    elif r.status_code == 200:
                        return r.json()
        print("There were too many 202s. Data for this repository will be incomplete.")
        return dict()

    @staticmethod
    def repos_overview(owned_cursor: str = "") -> str:
        """
        :param owned_cursor: optional cursor to continue pagination
        :return: GraphQL query with repository overview data
        """
        return f"""{{
  viewer {{
    name
    login
    contributionsCollection {{
      totalCommitContributions
      totalPullRequestReviewContributions
      totalRepositoryContributions
      totalIssueContributions
      totalPullRequestContributions
      totalRepositoriesWithContributedCommits
      totalRepositoriesWithContributedIssues
      totalRepositoriesWithContributedPullRequestReviews
      totalRepositoriesWithContributedPullRequests
    }}
    repositories(first: 100, orderBy: {{field: STARGAZERS, direction: DESC}}{owned_cursor}) {{
      pageInfo {{
        hasNextPage
        endCursor
      }}
      nodes {{
        nameWithOwner
        name
        owner {{ login }}
        isFork
        stargazerCount
        forkCount
        primaryLanguage {{ name }}
        languages(first: 10, orderBy: {{field: SIZE, direction: DESC}}) {{
          edges {{
            size
            node {{
              name
              color
            }}
          }}
        }}
      }}
    }}
  }}
}}"""

    @staticmethod
    def contributions_calendar(username: str, start_date: str) -> str:
        """
        :param username: GitHub username
        :param start_date: start date in YYYY-MM-DD format
        :return: GraphQL query for contributions calendar
        """
        return f"""{{
  user(login: "{username}") {{
    contributionsCollection(from: "{start_date}T00:00:00Z") {{
      totalCommitContributions
      contributionCalendar {{
        totalContributions
        weeks {{
          contributionDays {{
            contributionCount
            date
          }}
        }}
      }}
    }}
  }}
}}"""


class Stats(object):
    """
    Retrieve and store statistics about GitHub usage.
    """

    def __init__(
        self,
        username: str,
        access_token: str,
        session: aiohttp.ClientSession,
        exclude_repos: Optional[Set] = None,
        exclude_langs: Optional[Set] = None,
        exclude_forks: bool = False,
    ):
        self.username = username
        self._stargazers = None
        self._forks = None
        self._total_contributions = None
        self._lines_changed = None
        self._views = None
        self._repos = None
        self._repos_lock = asyncio.Lock()
        self._languages = None
        self._name = None
        self.queries = Queries(username, access_token, session)

        self._exclude_repos = set() if exclude_repos is None else exclude_repos
        self._exclude_langs = set() if exclude_langs is None else exclude_langs
        self._exclude_forks = exclude_forks

    async def to_dict(self) -> Dict:
        """
        :return: summary of all available statistics
        """
        return {{
            "name": await self.name,
            "stargazers": await self.stargazers,
            "forks": await self.forks,
            "total_contributions": await self.total_contributions,
            "lines_changed": await self.lines_changed,
            "views": await self.views,
            "repos": len(await self.repos),
            "languages": await self.languages,
        }}

    @property
    async def name(self) -> str:
        """
        :return: GitHub display name (or username if display name is not set)
        """
        if self._name is not None:
            return self._name
        repos = await self.repos
        if repos:
            self._name = repos[0].get("owner", {}).get("login", self.username)
        else:
            self._name = self.username
        return self._name

    @property
    async def stargazers(self) -> int:
        """
        :return: total number of stargazers on user's repositories
        """
        if self._stargazers is not None:
            return self._stargazers
        repos = await self.repos
        self._stargazers = sum(repo.get("stargazerCount", 0) for repo in repos)
        return self._stargazers

    @property
    async def forks(self) -> int:
        """
        :return: total number of forks of user's repositories
        """
        if self._forks is not None:
            return self._forks
        repos = await self.repos
        self._forks = sum(repo.get("forkCount", 0) for repo in repos)
        return self._forks

    @property
    async def total_contributions(self) -> int:
        """
        :return: total number of contributions for the current year
        """
        if self._total_contributions is not None:
            return self._total_contributions

        from datetime import datetime
        start_date = f"{{datetime.now().year}}-01-01"
        query = self.queries.contributions_calendar(self.username, start_date)
        result = await self.queries.query(query)

        user_data = result.get("data", {}).get("user")
        if user_data:
            contributions_collection = user_data.get("contributionsCollection", {})
            self._total_contributions = contributions_collection.get("totalCommitContributions", 0)
        else:
            self._total_contributions = 0

        return self._total_contributions

    @property
    async def lines_changed(self) -> Tuple[int, int]:
        """
        :return: total number of lines changed (additions, deletions)
        """
        if self._lines_changed is not None:
            return self._lines_changed

        # This is a simplified implementation - actual line counting would require
        # more complex GraphQL queries or REST API calls
        self._lines_changed = (0, 0)
        return self._lines_changed

    @property
    async def views(self) -> int:
        """
        :return: total number of repository views (requires owner access)
        """
        if self._views is not None:
            return self._views

        # This requires owner access to repositories
        self._views = 0
        return self._views

    @property
    async def repos(self) -> List[Dict]:
        """
        :return: list of user's repositories with statistics
        """
        async with self._repos_lock:
            if self._repos is not None:
                return self._repos

            self._repos = []

            owned_cursor = ""

            while True:
                query = self.queries.repos_overview(owned_cursor)
                result = await self.queries.query(query)

                if "data" not in result or "viewer" not in result["data"]:
                    break

                viewer = result["data"]["viewer"]

                # Process owned repositories
                owned_repos = viewer.get("repositories", {})
                for repo in owned_repos.get("nodes", []):
                    if repo.get("nameWithOwner") not in self._exclude_repos:
                        if not (self._exclude_forks and repo.get("isFork")):
                            self._repos.append(repo)

                # Check pagination
                owned_has_next = owned_repos.get("pageInfo", {}).get("hasNextPage", False)

                if owned_has_next:
                    owned_cursor = f', after: "{{owned_repos["pageInfo"]["endCursor"]}}"'
                else:
                    owned_cursor = ""

                if not owned_has_next:
                    break

            return self._repos

    @property
    async def languages(self) -> Dict:
        """
        :return: summary of languages used across all repositories
        """
        if self._languages is not None:
            return self._languages

        repos = await self.repos
        language_totals = {}

        for repo in repos:
            if repo["nameWithOwner"] in self._exclude_repos:
                continue

            languages = repo.get("languages", {}).get("edges", [])
            for lang_data in languages:
                size = lang_data.get("size", 0)
                name = lang_data.get("node", {}).get("name")
                color = lang_data.get("node", {}).get("color")

                if name in self._exclude_langs:
                    continue

                if name not in language_totals:
                    language_totals[name] = {
                        "size": size,
                        "color": color
                    }
                else:
                    language_totals[name]["size"] += size

        # Calculate percentages
        total_size = sum(lang_data["size"] for lang_data in language_totals.values())
        if total_size > 0:
            for lang, data in language_totals.items():
                data["prop"] = data["size"] / total_size * 100

        self._languages = language_totals
        return self._languages