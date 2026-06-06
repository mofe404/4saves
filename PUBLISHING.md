# Publishing 4Saves

## 1. Create The GitHub Repo

Create a new GitHub repository named:

```text
4saves
```

Do not add a README or license on GitHub if this folder already has them.

## 2. Confirm Repo URLs

The publish copy is already configured for:

```text
https://github.com/mofe404/4saves
```

## 3. Commit Locally

```bash
git add .
git commit -m "Initial 4Saves release"
```

## 4. Connect To GitHub

```bash
git remote add origin https://github.com/mofe404/4saves.git
git push -u origin main
```

## 5. Keep Updates Coming

For regular updates:

```bash
git add .
git commit -m "Describe the update"
git push
```

For normal users, publish a new GitHub Release. They can download the latest ZIP from:

```text
https://github.com/mofe404/4saves/releases/latest
```

If users installed from the downloaded folder with `pipx`, they can reinstall from the new downloaded folder:

```bash
pipx install --force .
```

Developer installs from git can update with:

```bash
4saves update
```

## 6. Release Ideas

- Add a demo GIF to the README.
- Create GitHub releases for stable versions.
- Use the release ZIP link in social posts instead of telling users to clone.
- Add issue templates for bug reports and feature requests.
- Publish to PyPI once the app feels stable, so users can run `pipx install 4saves` and `pipx upgrade 4saves`.
