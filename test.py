import pandas as pd

df = pd.read_csv("data/search_links.csv")

search_links = dict(zip(df['Keywords'], df['Links']))

print(f"{key} : {value}" for key, value in search_links.items())

for key, value in search_links.items():
    print(f'"{key}" : "{value}",')
