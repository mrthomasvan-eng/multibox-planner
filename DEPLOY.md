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

**Note:** Community Cloud apps spin down when idle. The first click after a while can take 30–60 seconds (cold start); after that, interactions use the same caching we added and feel snappier.

---

## 2. Other options

- **Railway / Render / Fly.io**  
  Deploy as a web service, set the start command to `streamlit run app.py --server.port=8080 --server.address=0.0.0.0`, and point the platform at `requirements.txt`. You may need a `Procfile` or similar (e.g. `web: streamlit run app.py --server.port=$PORT --server.address=0.0.0.0`).

- **Your own server (VPS)**  
  Install Python, clone the repo, run `pip install -r requirements.txt` and `streamlit run app.py --server.port=8501 --server.address=0.0.0.0`. Use a process manager (systemd, supervisord) or reverse proxy (nginx) if you want it to stay up and use HTTPS.

---

## 3. Speed when it’s “online”

- **Cold start:** First load or after idle can be slower; that’s normal for free/cheap hosting.
- **After load:** Asset and data loading are cached, so changing constraints only recomputes recommendations and redraws the UI. If it still feels slow, the next lever is to cache or simplify the recommender for repeated inputs (e.g. same era/box size).

The banner above recommendations links to:  
`https://www.redguides.com/amember/aff/go/vanman2099`  
(opens in a new tab).
