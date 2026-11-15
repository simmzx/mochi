# Uploading MOCHI to GitHub

The repository is ready to push: ~11.6 MB, 254 files, no build caches, no secrets. Pick one of the
three routes below.

---

## Option A — Git command line (recommended)

### 0. One-time setup

```powershell
winget install --id Git.Git -e --source winget    # skip if `git --version` already works
git config --global user.name  "ZHANG XIANG"
git config --global user.email "your-email@example.com"
```

### 1. Create an empty repository on GitHub

Go to <https://github.com/new>:

* **Repository name:** `mochi`
* **Visibility:** Public (the report links to it)
* **Do not** tick "Add a README", ".gitignore" or a licence — the upload already contains them.

### 2. Push

From the project folder (`...\mochi`, the one containing `README.md`):

```powershell
git init -b main
git add -A
git commit -m "MOCHI: self-evolving multi-agent system for end-to-end AI drug discovery"
git remote add origin https://github.com/simmzx/mochi.git
git push -u origin main
```

or run the helper script, which does exactly the same with checks:

```powershell
pwsh ./scripts/upload_to_github.ps1 -RepoUrl https://github.com/simmzx/mochi.git
```

When git asks for a password, paste a **personal access token** (GitHub → Settings → Developer
settings → Personal access tokens → *Tokens (classic)* → scope `repo`), not your account password.
Git Credential Manager (installed with Git for Windows) will offer a browser sign-in instead.

---

## Option B — GitHub Desktop (no terminal)

1. Install GitHub Desktop and sign in.
2. **File → Add local repository…** → choose the `mochi` folder.
3. It offers to create a repository — accept (keep the name `mochi`, branch `main`).
4. Write the commit message and press **Commit to main**.
5. **Publish repository** → untick "Keep this code private" if it should be public.

---

## Option C — Upload through the browser (no git history)

1. Create the empty repository as in Option A.
2. On the repository page choose **Add file → Upload files**.
3. Drag the *contents* of the `mochi` folder (not the folder itself) and commit.

This works because everything is under 25 MB per file and 100 MB in total, but it produces a
single commit with no history — Option A is preferable.

---

## After the upload

* Open <https://github.com/simmzx/mochi> and check that the README renders with the scenario table.
* Confirm the report is browsable: `paper/MOCHI_Final_Project_Report_LaTeX.pdf`.
* Optional: **Releases → Draft a new release**, tag `v1.0`, attach the report and slide PDFs.
* Optional: add the repository link to the report metadata (already present in §A.4) and to the
  presentation's closing slide (already present).

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `remote: Repository not found` | the repository was not created, or the URL has a typo |
| `failed to push some refs` / `unrelated histories` | the GitHub repo already has a commit (e.g. a README): `git pull --rebase origin main --allow-unrelated-histories` then push again |
| `Authentication failed` | use a personal access token as the password, or sign in through GitHub Desktop |
| `file is 100 MB+` | not applicable here (largest file is a 1.3 MB PDF), but `git lfs track "*.pdf"` is the general remedy |
| Line endings look changed | `.gitattributes` already normalises text to LF; run `git add --renormalize .` once after cloning on Windows |

## What is intentionally excluded

`cache/` (HTTP responses, ~170 MB, regenerated on demand), `__pycache__/`, `.dsh-office-*` render
scratch directories, `.env` (your API key) and the LaTeX build by-products. `outputs/` **is**
included on purpose: it holds the four canonical runs behind every number in the report.
