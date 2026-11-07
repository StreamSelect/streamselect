# StreamSelect

A desktop app that turns the huge, messy catalog of an IPTV subscription into a library you can actually browse. Channel and movie names like `EN| 4K - The Matrix (1999) MULTI-SUB` are read once and split into title, year, language, region and quality, copies of the same title are grouped together, and posters, plots and cast are added, so you can search, filter and find what you want instead of scrolling a list of hundreds of thousands of rows.

Runs on Linux, macOS and Windows. Plays through mpv. Free and open source under GPLv3.

**StreamSelect includes no channels, streams or content, and doesn't sell or recommend any. You need your own source.**

## Who it's for

People who watch on a computer and want to use what a computer is good at: a big screen, a keyboard and a mouse, and the speed to search and sort a huge catalog. StreamSelect organizes everything your sources carry so the things you care about are easy to find, and gets out of the way once something plays. Videos open in a plain mpv window you can leave in a corner while you work, or make full screen.

It never hides anything on its own. It suggests and sorts, and you decide what to filter out.

## What it does

**Compares your sources.** Each source has an Analytics tab that helps you decide whether it's worth keeping:

- What only that source carries, and how much of it your other sources also have
- Movie, series and live counts, guide coverage, titles by region, and days left on the account
- How often plays start, what time of day they fail, and which server addresses work
- What you actually watch there, and how much of its connection limit you use

**Lets you combine filters and save them.** Pick any mix of genre, region, language, decade, collection, quality, streaming platform and subtitle language, and you see every matching title and how many there are. Save a combination you like and it stays on the Discover page as a row of matching titles, which updates as your sources change.

**Handles several sources and several addresses per source.** Add as many sources as you have and their catalogs are blended into one library. A source can have more than one server address: StreamSelect tries them in order of how reliably and quickly each one has answered, and keeps using the ones that work.

**Combines copies of the same title.** The same movie in five languages across three sources shows once in recommendations and suggestions, with the other versions listed under it.

**Tracks what you want to watch:**

- A watch list of shows and keywords, with alerts when something matching is on now or coming up
- Alerts when a series you follow gets new episodes
- A list of what you plan to watch next, favorites, history, and resume positions for movies and episodes

**Searches across everything.** One search box covers titles, alternate titles, cast, directors and the languages spoken in a stream. Results are grouped by what matched, and can be shown as posters. Filters cover language, region, quality, streaming platform and category, and you can hide anything you never want to see, everywhere in the app.

**Shows the TV guide.** Reads your provider's program guide, including very large ones: what's on right now, the full schedule with columns you can sort, and upcoming live events.

**Recommends.** Likes and dislikes feed a recommendation list based on genres, cast, directors and plot keywords. It shows why something was recommended, and you can mute any genre, person or keyword.

**Lets you adjust a stream while it plays.** Click the buffer and speed figures at the top of the window to change the audio language or subtitles, even out quiet dialogue and loud effects, mix surround sound down to stereo or mono, or skip to another item in what's playing next. If a stream is unreliable, a one-click test in the Tools menu tells you whether the problem is the source or your connection. You can also watch two sources at once in separate windows.

**Pulls in details.** Posters, plots, cast and ratings come from your provider. Add your own free TMDb or OMDb API key in Settings for more.

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
