import os, pickle
latest_urls_path = 'latest_urls.pkl'
if os.path.exists(latest_urls_path):
    with open(latest_urls_path, 'rb') as f:
        latest_urls = pickle.load(f)
for key, vlal in latest_urls.items():
    print(f"{key} : {vlal}")