"""Build profile.svg: a neofetch-style card with colored ASCII avatar and live GitHub stats.

Stdlib only so the GitHub Action needs no installs. Needs GITHUB_TOKEN in env.
Edit INFO below to change what the card says.
"""
import datetime as dt
import html
import json
import os
import time
import urllib.error
import urllib.request

USER = "VishiATChoudhary"
WIDTH = 60  # chars per info line

# (key, value) rows. None = blank line. ("# Title", None) = section header.
INFO = [
    ("@", f"vishi@github"),
    ("OS", "macOS, Linux (when the GPUs are free)"),
    ("Uptime", "{uptime}"),
    ("Host", "Technical University of Munich"),
    ("Kernel", "Computer Science student"),
    ("Shell", "zsh + Claude Code + Codex"),
    None,
    ("Languages.Programming", "Python, TypeScript, Go, JS"),
    ("Languages.Markup", "LaTeX, Markdown, MDX"),
    None,
    ("Building.Agents", "synapse, theorem, graft, toolJev"),
    ("Building.Life", "vishlang, reels, freebies, Kali"),
    None,
    ("# Contact", None),
    ("Website", "vishi.dev"),
    ("GitHub", USER),
    None,
    ("# GitHub Stats", None),
    ("Repos", "{repos} {{Contributed: {contributed}}}"),
    ("Stars", "{stars}"),
    ("Commits", "{commits}"),
    ("Followers", "{followers}"),
    ("Lines of Code", "{loc}"),
]

API = "https://api.github.com"


def req(url, body=None):
    token = os.environ["GITHUB_TOKEN"]
    r = urllib.request.Request(
        url,
        data=json.dumps(body).encode() if body else None,
        headers={"Authorization": f"bearer {token}", "User-Agent": "profile-card"},
    )
    with urllib.request.urlopen(r, timeout=30) as resp:
        return resp.status, json.loads(resp.read() or "null")


def gql(query, **variables):
    _, data = req(f"{API}/graphql", {"query": query, "variables": variables})
    if data.get("errors"):
        raise RuntimeError(data["errors"])
    return data["data"]


def fetch_stats():
    d = gql(
        """query($login:String!){user(login:$login){
          createdAt followers{totalCount}
          repositories(ownerAffiliations:OWNER, first:100, privacy:PUBLIC){
            totalCount nodes{name isFork stargazerCount}}
          repositoriesContributedTo(contributionTypes:[COMMIT,PULL_REQUEST,REPOSITORY]){totalCount}
        }}""",
        login=USER,
    )["user"]
    created = dt.datetime.fromisoformat(d["createdAt"].replace("Z", "+00:00"))
    repos = d["repositories"]["nodes"]

    # Commits: sum contribution years (API caps each query at one year).
    commits = 0
    now = dt.datetime.now(dt.timezone.utc)
    start = created
    while start < now:
        end = min(start + dt.timedelta(days=365), now)
        c = gql(
            """query($login:String!,$from:DateTime!,$to:DateTime!){user(login:$login){
              contributionsCollection(from:$from,to:$to){totalCommitContributions restrictedContributionsCount}}}""",
            login=USER, **{"from": start.isoformat(), "to": end.isoformat()},
        )["user"]["contributionsCollection"]
        commits += c["totalCommitContributions"] + c["restrictedContributionsCount"]
        start = end

    return {
        "created": created,
        "repos": d["repositories"]["totalCount"],
        "contributed": d["repositoriesContributedTo"]["totalCount"],
        "stars": sum(r["stargazerCount"] for r in repos),
        "followers": d["followers"]["totalCount"],
        "commits": commits,
        "loc": lines_of_code([r["name"] for r in repos if not r["isFork"]]),
    }


def lines_of_code(names):
    """Additions/deletions by USER across own repos. Stats endpoint returns 202 while computing."""
    add = dele = 0
    pending = list(names)
    for _ in range(4):
        retry = []
        for name in pending:
            try:
                status, data = req(f"{API}/repos/{USER}/{name}/stats/contributors")
            except urllib.error.HTTPError:
                continue
            if status == 202:
                retry.append(name)
                continue
            for c in data or []:
                if c["author"] and c["author"]["login"].lower() == USER.lower():
                    add += sum(w["a"] for w in c["weeks"])
                    dele += sum(w["d"] for w in c["weeks"])
        if not retry:
            break
        pending = retry
        time.sleep(5)
    return add, dele


def uptime(since):
    today = dt.date.today()
    y = today.year - since.year
    m = today.month - since.month
    d = today.day - since.day
    if d < 0:
        m -= 1
        d += 30
    if m < 0:
        y -= 1
        m += 12
    return f"{y} years, {m} months, {d} days"


# ---------- SVG ----------
FONT = 14
CW = FONT * 0.602  # monospace glyph width
LH = 20
PAD = 28
STEP = 0.07  # seconds between lines appearing


def esc(s):
    return html.escape(s, quote=False)


def info_lines(s):
    a, dl = s["loc"]
    vals = {
        "uptime": uptime(s["created"]),
        "repos": s["repos"],
        "contributed": s["contributed"],
        "stars": f"{s['stars']:,}",
        "commits": f"{s['commits']:,}",
        "followers": f"{s['followers']:,}",
    }
    rows = []
    for row in INFO:
        if row is None:
            rows.append("")
            continue
        k, v = row
        if k == "@":
            rows.append(f'<tspan class="key">{esc(v)}</tspan> <tspan class="dim">{"─" * (WIDTH - len(v) - 1)}</tspan>')
        elif k.startswith("# "):
            t = k[2:]
            rows.append(f'<tspan class="dim">- </tspan><tspan class="head">{esc(t)}</tspan> <tspan class="dim">{"─" * (WIDTH - len(t) - 3)}</tspan>')
        elif k == "Lines of Code":
            total = f"{a - dl:,}"
            tail = f" ( {a:,}++, {dl:,}-- )"
            dots = WIDTH - len(k) - 4 - len(total) - len(tail)
            rows.append(
                f'<tspan class="dim">. </tspan><tspan class="key">{k}</tspan>:<tspan class="dim"> {"." * max(dots, 1)} </tspan>'
                f'<tspan class="val">{total}</tspan> ( <tspan class="add">{a:,}++</tspan>, <tspan class="del">{dl:,}--</tspan> )'
            )
        else:
            v = v.format(**vals)
            dots = WIDTH - len(k) - 5 - len(v)
            rows.append(
                f'<tspan class="dim">. </tspan><tspan class="key">{esc(k)}</tspan>:<tspan class="dim"> {"." * max(dots, 1)} </tspan>'
                f'<tspan class="val">{esc(v)}</tspan>'
            )
    return rows


def build_svg(stats):
    data = json.load(open(os.path.join(os.path.dirname(__file__), "..", "assets", "ascii.json")))
    art, afont, alh = data["rows"], data["font"], data["lh"]
    info = info_lines(stats)
    art_w = len(art[0]) * afont * 0.602
    info_x = PAD + art_w + 36
    art_h = len(art) * alh
    width = int(info_x + WIDTH * CW + PAD)
    height = int(PAD * 2 + max(art_h, (len(info) + 1) * LH))
    art_top = PAD + max(0, ((len(info) + 1) * LH - art_h) / 2)

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="{FONT}px">',
        "<style>",
        ".bg{fill:#0d1117}.key{fill:#ffa657}.val{fill:#a5d6ff}.dim{fill:#484f58}.head{fill:#e6edf3}"
        ".add{fill:#3fb950}.del{fill:#f85149}text{fill:#c9d1d9;white-space:pre}"
        ".art{filter:saturate(1.2)}",
        "@media (prefers-color-scheme: light){.bg{fill:#f6f8fa}.key{fill:#953800}.val{fill:#0a3069}.dim{fill:#afb8c1}"
        ".head{fill:#1f2328}.add{fill:#1a7f37}.del{fill:#cf222e}text{fill:#1f2328}.art{filter:brightness(.72) saturate(1.3)}}",
        ".l{opacity:0;animation:in .35s ease-out forwards}"
        "@keyframes in{from{opacity:0;transform:translateX(-6px)}to{opacity:1;transform:none}}"
        ".cur{animation:blink 1s steps(1) infinite}@keyframes blink{50%{opacity:0}}",
        "</style>",
        f'<rect class="bg" width="{width}" height="{height}" rx="12"/>',
        f'<g class="art" font-size="{afont}px">',
    ]
    for i, row in enumerate(art):
        spans = "".join(f'<tspan fill="{c}">{esc(ch)}</tspan>' for ch, c in row)
        out.append(f'<text class="l" style="animation-delay:{i * 0.9 / len(art):.2f}s" x="{PAD}" y="{art_top + alh * (i + 1):.1f}">{spans}</text>')
    out.append("</g>")
    for i, line in enumerate(info):
        if line:
            out.append(f'<text class="l" style="animation-delay:{0.3 + i * STEP:.2f}s" x="{info_x:.0f}" y="{PAD + LH * (i + 1)}">{line}</text>')
    cy = PAD + LH * (len(info) + 1)
    out.append(
        f'<text class="l" style="animation-delay:{0.3 + len(info) * STEP:.2f}s" x="{info_x:.0f}" y="{cy}">'
        f'<tspan class="key">vishi</tspan><tspan class="dim">@github:~$ </tspan><tspan class="cur">▍</tspan></text>'
    )
    out.append("</svg>")
    # grow canvas for prompt line
    svg = "\n".join(out)
    if cy + PAD > height:
        svg = svg.replace(f'height="{height}"', f'height="{cy + PAD}"').replace(f"0 0 {width} {height}", f"0 0 {width} {cy + PAD}")
    return svg


if __name__ == "__main__":
    svg = build_svg(fetch_stats())
    path = os.path.join(os.path.dirname(__file__), "..", "profile.svg")
    open(path, "w").write(svg)
    print("wrote", os.path.abspath(path))
