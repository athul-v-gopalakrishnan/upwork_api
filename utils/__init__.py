import pandas as pd

def generate_search_links(file_path:str="data/search_links.csv"):
    """Generate a dictionary of search links from a CSV file."""
    df = pd.read_csv(file_path)
    search_links = dict(zip(df['Keywords'], df['Links']))
    return search_links