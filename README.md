# StreamSelect

A desktop app that turns the huge, messy catalog of an IPTV subscription into a library you can actually browse. The raw channel and movie names, with their language codes, quality tags and other clutter, are read once and split into title, year, language, region and quality, copies of the same title are grouped together, and posters, plots and cast are added, so you can search, filter and find what you want instead of scrolling a list of hundreds of thousands of rows.

Runs on Linux, macOS and Windows. Plays through mpv. Free and open source under GPLv3.

**StreamSelect includes no channels, streams or content, and doesn't sell or recommend any. You need your own source.**

## Who it's for

People who watch on a computer and want to use what a computer is good at: a big screen, a keyboard and a mouse, and the speed to search and sort a huge catalog. StreamSelect organizes everything your sources carry so the things you care about are easy to find, and gets out of the way once something plays. Videos open in a plain mpv window you can leave in a corner while you work, or make full screen.

It never hides anything on its own. It suggests and sorts, and you decide what to filter out.

## What it does

StreamSelect reads every name once and splits it into title, year, language, region and quality, groups copies of the same title together, and adds posters, plots and cast. Everything below works on that organized library. Add as many sources as you like; their catalogs are merged into one.

### Finding things

- **One search box** for titles, alternate titles, actors, directors and the languages spoken in a stream. Results are grouped by what matched, and can be shown as posters.
- **Filters** for genre, language, region, quality, decade, collection, streaming platform and subtitle language. Save a combination you use often (a "recipe") and it stays on the Discover page as a row of matching titles that updates as your catalog changes.
- **Global exclusions** hide anything you never want to see, such as a language you don't speak, everywhere in the app.
- **New content is never hidden silently.** When a source adds new categories, regions or languages, StreamSelect shows you what's new after the refresh and lets you include or exclude each one.
- **You can see what your filters are hiding.** When filters hold results back, the app says how many and lets you show them, so you don't miss something because you filtered too aggressively.
- **Copies of the same title are combined.** The same movie in five languages across three sources shows once in recommendations and suggestions, with the other versions listed under it.
- **Recommendations** come from what you like and dislike, matched on genres, cast, directors and plot keywords. Each one shows why it was picked, and you can mute any genre, person or keyword.

### Keeping track

- A watch list of shows and keywords, with alerts when something matching is on now or coming up.
- Alerts when a series you follow has new episodes, checked on a schedule you choose.
- A list of what you plan to watch next, favorites, history, and resume positions for movies and episodes.
- A TV guide from your provider's program listings, including very large ones: what's on now, the full schedule with columns you can sort, and upcoming live events.

### Playing things

- **Everything plays in mpv** on every platform, so mpv's features work on your streams. The window is plain, so you can leave it in a corner while you work or make it full screen (F11 in the app).
- **Watch more than one thing at once.** Each source gets its own player window, so a game from one source and a show from another can play side by side. Starting the second doesn't cut off the first, which matters when each source only allows one connection.
- **Even out the volume.** Normalize volume brings quiet dialogue up without making explosions louder, so you stop riding the volume. You can also mix 5.1 surround down to stereo or mono, which helps on laptop speakers and headphones where voices in the center channel get lost.
- **Change things while it plays.** Click the buffer and speed figures at the top of the window to switch audio language or subtitles, change the sound settings above, or skip to another item in what's playing next.

### Staying connected

- **Every server address is used.** Providers often give several addresses, and one being slow or down is a common reason streams fail. StreamSelect keeps track of how each address performs, tries the most reliable and fastest first, and moves on to the next when one fails, so you aren't swapping addresses by hand.
- **Stream diagnosis** in the Tools menu measures how fast a stream arrives against what the video needs and runs a speed test of your own connection to compare. It tells you in plain words whether the problem is the provider or your internet, suggests a buffer setting that would help, and can switch to it for you.
- **Connection problems are explained.** When a source won't connect, the app says why and what to try: a wrong username or password, an expired subscription, an address that isn't an Xtream server, a provider refusing you (often because of a VPN), a temporary lockout after failed logins, or nothing answering at all.

### Comparing your sources

Each source has an Analytics tab that helps you decide whether it's worth keeping:

- What only that source carries, and how much of it your other sources also have
- Movie, series and live counts, guide coverage, titles by region, and days left on the account
- How often plays start, what time of day they fail, and which server addresses work
- What you actually watch there, and how much of its connection limit you use

### Details

Posters, plots, cast and ratings come from your provider. Add your own free TMDb or OMDb API key in Settings for more.

## Download

Get the latest build from the [releases page](https://github.com/StreamSelect/streamselect/releases/latest). mpv is included in all three.

| Platform | File | Notes |
|---|---|---|
| Linux | `StreamSelect.flatpak` | `flatpak install --user StreamSelect.flatpak` |
| macOS (Apple Silicon) | `.dmg` | Not signed. See below. |
| Windows | `StreamSelect-windows-x64.zip` | Unzip and run. The least tested of the three. |

**macOS says the app is "damaged":** it isn't. The app isn't signed, so macOS blocks it. Move it to Applications, then run:

```bash
xattr -cr /Applications/StreamSelect.app
```

There's no Intel Mac build.

## Getting started

1. Open StreamSelect and add a source.
2. Enter your server address, username and password, or paste the M3U link your provider sent you. If it's an Xtream link, StreamSelect takes the address and login from it.
3. Wait for the first refresh to finish. A large catalog can take a few minutes.

Double-click anything to play it. Right-click for everything else. Press `?` for the keyboard shortcuts.

## Current limits

- Recording and downloading are built but hidden while they're tested.
- Xtream accounts only. An Xtream M3U link works, but a plain M3U playlist file or a non-Xtream M3U URL doesn't.
- The app checks for new versions and takes you to the download, but it doesn't install them itself.

## Run from source

You need Python 3.14 and [mpv](https://mpv.io).

```bash
git clone https://github.com/StreamSelect/streamselect.git
cd streamselect
python3.14 -m venv venv
venv/bin/pip install -r requirements.txt
./run.sh
```

## Where your data lives

Everything stays on your computer. On Linux:

| What | Where |
|---|---|
| Settings | `~/.config/streamselect/` |
| Library database | `~/.local/share/streamselect/streamselect.db` |
| Logs | `~/.config/streamselect/logs/` |
| Image cache | `~/.cache/streamselect/` |

The app connects to your sources and, if you add keys, to TMDb and OMDb. It contacts GitHub to check for updates, which you can turn off in Settings. Diagnose also downloads a small test file from Cloudflare to compare against your source's speed.

## Troubleshooting

- **A source won't connect:** check the address and login, and try them in your provider's own portal. The Add Source screen says why a connection failed.
- **A stream won't play or keeps stalling:** select it and choose Stream diagnosis from the Tools menu. It checks whether the problem is the source or your connection.
- **Quiet voices and loud explosions:** click the buffer and speed figures at the top of the window and turn on Normalize volume.
- **Anything else:** open an issue and attach the log from the logs folder. Remove your source's address and login from it first.

## License

[GNU General Public License v3.0](LICENSE)
