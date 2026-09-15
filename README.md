# Blackjack Strategy Solver

A blackjack expected-value solver with Jeju and Macau rule sets. The Streamlit interface calculates the recommended action for a hand and generates basic-strategy tables.

## Local setup

Use the Miniforge `bj` environment. The environment name must be activated before starting the application:

```powershell
conda activate bj
conda install -c conda-forge pandas streamlit
streamlit run streamlit_app.py
```

Open the local URL printed by Streamlit. The layout adapts to a mobile browser.

## GitHub and Streamlit Community Cloud

1. Create a new GitHub repository and push this project, including `requirements.txt` and `streamlit_app.py`.
2. At [Streamlit Community Cloud](https://share.streamlit.io/), select **Create app** and authorize GitHub.
3. Select the repository, branch, and `streamlit_app.py` as the main file.
4. Deploy. Community Cloud installs dependencies from `requirements.txt` automatically.

Do not commit credentials. `.streamlit/secrets.toml` is ignored by Git.

## Notes

The solver models an infinite shoe. The configured `decks` field is not currently used to remove dealt cards from the probability distribution.