# Getting the app online

## 1. Streamlit Community Cloud (easiest, free)

1. **Put the project in GitHub**  
   Create a repo and push this folder (include `app.py`, `app/`, `assets/`, `data/`, `requirements.txt`). Don’t commit secrets or large binaries you don’t need.

2. **Go to [share.streamlit.io](https://share.streamlit.io)**  
   Sign in with GitHub and click “New app”.

3. **Configure the app**  
   - **Repository**: your GitHub repo  
   - **Branch**: usually `main`  
   - **Main file path**: `app.py`  
   - **App URL**: pick a subdomain (e.g. `eq-multibox-planner`)

4. **Deploy**  
   Streamlit will install from `requirements.txt` and run `streamlit run app.py`. The first run may take a minute; after that it’s usually faster. Updates: push to the same branch and the app will redeploy.

**Note:** Community Cloud apps spin down when idle. The first click after a while can take 30–60 seconds (cold start); after that, interactions use caching and feel snappier.

---

## How to edit the app and get changes online

Your app is already at **https://multibox-planner.streamlit.app/** and is tied to your GitHub repo. To change the app and have the live site update:

1. **Edit the code on your computer**  
   Open the project in Cursor (or any editor) and change `app.py`, files in `app/`, `data/`, or `assets/` as needed.

2. **Push the changes to GitHub**  
   - **If you used “upload files”** and don’t have Git installed:  
     On GitHub, open your repo → go to the file you changed (e.g. `app.py`) → click the pencil icon (Edit) → paste in your new version → scroll down → **Commit changes**.  
     For multiple files, repeat or drag-and-drop updated files into the repo (same as the first upload).  
   - **If you use Git** (e.g. GitHub Desktop or command line):  
     Commit your changes, then push to the `main` branch.

3. **Redeploy**  
   Streamlit Cloud watches your repo. After you commit and push (or save edits on GitHub), it will redeploy automatically. Go to [share.streamlit.io](https://share.streamlit.io), open your app, and check the “Source” / “Rerun” if you want to force a refresh. Usually within a minute the live app at https://multibox-planner.streamlit.app/ will show your updates.

**Tip:** If you start editing a lot, installing [GitHub Desktop](https://desktop.github.com/) makes “commit + push” a few clicks instead of re-uploading files by hand.

---

## 2. Other options

- **Railway / Render / Fly.io**  
  Deploy as a web service, set the start command to `streamlit run app.py --server.port=8080 --server.address=0.0.0.0`, and point the platform at `requirements.txt`. You may need a `Procfile` or similar (e.g. `web: streamlit run app.py --server.port=$PORT --server.address=0.0.0.0`).

- **Your own server (VPS)**  
  Install Python, clone the repo, run `pip install -r requirements.txt` and `streamlit run app.py --server.port=8501 --server.address=0.0.0.0`. Use a process manager (systemd, supervisord) or reverse proxy (nginx) if you want it to stay up and use HTTPS.

---

## 3. Speed when it’s “online”

- **Cold start:** First load or after idle can be slower; that’s normal for free hosting.
- **After load:** Data, assets, and recommendation results are cached. The first time you pick a given combination (era, box size, rules, etc.) it may take a moment; if you pick the same again (or switch back), results show up much faster.

The banner above recommendations links to:  
`https://www.redguides.com/amember/aff/go/vanman2099`  
(opens in a new tab).
