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

For normal users, share this terminal install command:

```bash
pipx install https://github.com/mofe404/4saves/archive/refs/heads/main.zip
```

For updates:

```bash
pipx install --force https://github.com/mofe404/4saves/archive/refs/heads/main.zip
```

Also create GitHub releases for users who prefer manual downloads:

```text
https://github.com/mofe404/4saves/releases/latest
```

## 6. Release Ideas

- Add a demo GIF to the README.
- Create GitHub releases for stable versions.
- Use the terminal install command in social posts instead of telling users to clone.
- Add issue templates for bug reports and feature requests.
- Publish to PyPI once the app feels stable, so users can run `pipx install 4saves` and `pipx upgrade 4saves`.
