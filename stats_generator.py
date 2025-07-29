#!/usr/bin/python3

import asyncio
import os
import re
import aiohttp
from github_stats import Stats

# Dark theme SVG templates embedded as constants
OVERVIEW_TEMPLATE = """<svg width="360" height="210" xmlns="http://www.w3.org/2000/svg">
<style>
svg {
  font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Helvetica, Arial, sans-serif, Apple Color Emoji, Segoe UI Emoji;
  font-size: 14px;
  line-height: 21px;
}

#background {
  width: calc(100% - 10px);
  height: calc(100% - 10px);
  fill: #0d1117;
  stroke: #30363d;
  stroke-width: 1px;
  rx: 6px;
  ry: 6px;
}

foreignObject {
  width: calc(100% - 10px - 32px);
  height: calc(100% - 10px - 32px);
}

table {
  width: 100%;
  border-collapse: collapse;
  table-layout: auto;
}

th {
  padding: 0.5em;
  padding-top: 0;
  text-align: left;
  font-size: 14px;
  font-weight: 600;
  color: #A7C7E7;
}

td {
  margin-bottom: 16px;
  margin-top: 8px;
  padding: 0.25em;
  font-size: 12px;
  line-height: 18px;
  color: #c9d1d9;
}

tr {
  transform: translateX(-200%);
  animation-duration: 2s;
  animation-name: slideInLeft;
  animation-function: ease-in-out;
  animation-fill-mode: forwards;
}

@keyframes slideInLeft {
  from {
    transform: translateX(-200%);
  }
  to {
    transform: translateX(0%);
  }
}
</style>
<defs>
    <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#A7C7E7;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#B5EAD7;stop-opacity:1" />
    </linearGradient>
</defs>
<g>
<rect x="5" y="5" id="background"/>
<g>
<foreignObject x="21" y="21" width="318" height="168">
<div xmlns="http://www.w3.org/1999/xhtml">

<table>
  <thead><tr style="animation-delay: 0ms"><th colspan="2">📊 GitHub Overview</th></tr></thead>
  <tbody>
    <tr style="animation-delay: 150ms"><td>🎯 Total Repositories</td><td>{{ repos }}</td></tr>
    <tr style="animation-delay: 300ms"><td>⭐ Total Stars Earned</td><td>{{ stars }}</td></tr>
    <tr style="animation-delay: 450ms"><td>🍴 Total Forks</td><td>{{ forks }}</td></tr>
    <tr style="animation-delay: 600ms"><td>📈 Total Contributions (2025)</td><td>{{ contributions }}</td></tr>
    <tr style="animation-delay: 750ms"><td>📝 Lines of Code Changed</td><td>{{ lines_changed }}</td></tr>
    <tr style="animation-delay: 900ms"><td>👀 Profile Views</td><td>{{ views }}</td></tr>
  </tbody>
</table>

</div>
</foreignObject>
</g>
</g>
</svg>"""

LANGUAGES_TEMPLATE = """<svg width="360" height="300" xmlns="http://www.w3.org/2000/svg">
<style>
svg {
  font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Helvetica, Arial, sans-serif, Apple Color Emoji, Segoe UI Emoji;
  font-size: 14px;
  line-height: 21px;
}

#background {
  width: calc(100% - 10px);
  height: calc(100% - 10px);
  fill: #0d1117;
  stroke: #30363d;
  stroke-width: 1px;
  rx: 6px;
  ry: 6px;
}

.progress {
  display: flex;
  height: 8px;
  overflow: hidden;
  background-color: #30363d;
  border-radius: 6px;
  outline: 1px solid transparent;
}

.progress-item {
  outline: 2px solid #30363d;
  outline-offset: -1px;
}

.lang {
  font-weight: 600;
  margin-right: 4px;
  color: #c9d1d9;
  opacity: 0;
  animation-duration: 2s;
  animation-name: fadeInLeft;
  animation-function: ease-in-out;
  animation-fill-mode: forwards;
}

.percent {
  color: #8b949e;
  opacity: 0;
  animation-duration: 2s;
  animation-name: fadeInLeft;
  animation-function: ease-in-out;
  animation-fill-mode: forwards;
}

ul {
  list-style: none;
  padding-left: 0;
  margin-top: 0;
  margin-bottom: 0;
}

li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.25em 0;
}

.octicon {
  margin-right: 0.5em;
  margin-left: 0.5em;
  width: 16px;
  height: 16px;
}

@keyframes fadeInLeft {
  from {
    opacity: 0;
    transform: translateX(-200%);
  }
  to {
    opacity: 1;
    transform: translateX(0%);
  }
}

foreignObject {
  width: calc(100% - 10px - 32px);
  height: calc(100% - 10px - 32px);
}

h2 {
  margin-top: 0;
  margin-bottom: 0.5em;
  font-size: 14px;
  font-weight: 600;
  color: #A7C7E7;
  opacity: 0;
  animation-duration: 2s;
  animation-name: fadeInLeft;
  animation-function: ease-in-out;
  animation-fill-mode: forwards;
}
</style>
<defs>
    <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#A7C7E7;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#B5EAD7;stop-opacity:1" />
    </linearGradient>
</defs>
<g>
<rect x="5" y="5" id="background"/>
<g>
<foreignObject x="21" y="21" width="318" height="258">
<div xmlns="http://www.w3.org/1999/xhtml">

<h2>💻 Most Used Languages</h2>
<div class="progress">
{{ progress }}
</div>
<ul>
{{ lang_list }}
</ul>

</div>
</foreignObject>
</g>
</g>
</svg>"""


def generate_output_folder() -> None:
    """Create the output folder if it does not already exist"""
    if not os.path.isdir("generated"):
        os.mkdir("generated")


async def generate_overview(s: Stats) -> None:
    """Generate an SVG badge with summary statistics"""
    output = OVERVIEW_TEMPLATE

    output = re.sub("{{ stars }}", f"{await s.stargazers:,}", output)
    output = re.sub("{{ forks }}", f"{await s.forks:,}", output)
    output = re.sub("{{ contributions }}", f"{await s.total_contributions:,}", output)
    changed = (await s.lines_changed)[0] + (await s.lines_changed)[1]
    output = re.sub("{{ lines_changed }}", f"{changed:,}", output)
    output = re.sub("{{ views }}", f"{await s.views:,}", output)
    output = re.sub("{{ repos }}", f"{len(await s.repos):,}", output)

    generate_output_folder()
    with open("generated/overview.svg", "w") as f:
        f.write(output)


async def generate_languages(s: Stats) -> None:
    """Generate an SVG badge with summary languages used"""
    output = LANGUAGES_TEMPLATE

    progress = ""
    lang_list = ""
    sorted_languages = sorted((await s.languages).items(), reverse=True,
                              key=lambda t: t[1].get("size"))
    delay_between = 150
    for i, (lang, data) in enumerate(sorted_languages):
        color = data.get("color")
        color = color if color is not None else "#000000"
        progress += (f'<span style="background-color: {color};'
                     f'width: {data.get("prop", 0):0.3f}%;" '
                     f'class="progress-item"></span>')
        lang_list += f"""
<li style="animation-delay: {i * delay_between}ms;">
<svg xmlns="http://www.w3.org/2000/svg" class="octicon" style="fill:{color};"
viewBox="0 0 16 16" version="1.1" width="16" height="16"><path
fill-rule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8z"></path></svg>
<span class="lang">{lang}</span>
<span class="percent">{data.get("prop", 0):0.2f}%</span>
</li>

"""

    output = re.sub(r"{{ progress }}", progress, output)
    output = re.sub(r"{{ lang_list }}", lang_list, output)

    generate_output_folder()
    with open("generated/languages.svg", "w") as f:
        f.write(output)


async def main() -> None:
    """Generate all badges"""
    access_token = os.getenv("ACCESS_TOKEN")
    if not access_token:
        access_token = os.getenv("GITHUB_TOKEN")
        print("⚠️  Using GITHUB_TOKEN - limited permissions may cause incomplete data")
        print("💡 For full stats, create a Personal Access Token and set it as ACCESS_TOKEN secret")
    
    if not access_token:
        raise Exception("A personal access token is required!")
    
    user = os.getenv("GITHUB_ACTOR", "Dhairya3391")
    exclude_repos = os.getenv("EXCLUDED")
    exclude_repos = ({x.strip() for x in exclude_repos.split(",")} if exclude_repos else None)
    exclude_langs = os.getenv("EXCLUDED_LANGS")
    exclude_langs = ({x.strip() for x in exclude_langs.split(",")} if exclude_langs else None)
    
    print(f"🔍 Generating stats for user: {user}")
    print(f"🔍 Excluded repos: {exclude_repos}")
    print(f"🔍 Excluded languages: {exclude_langs}")
    
    async with aiohttp.ClientSession() as session:
        s = Stats(user, access_token, session, exclude_repos=exclude_repos, exclude_langs=exclude_langs)
        await asyncio.gather(generate_languages(s), generate_overview(s))


if __name__ == "__main__":
    asyncio.run(main())
