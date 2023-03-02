"""
Healthcheck dashboard for improving in lol.
Ingests 7 days of gameplay data and prodcuec health checks for:
    earliest game played
    latest game played
    number of games played
    number of distinct champions played
Potentially will be expanded to include:
    consistency of blocks
consistency of review
"""

import datetime
import json
from PIL.Image import new

import pytz
import matplotlib.pyplot as plt
from numpy import place
import pandas as pd
import streamlit as st
import urllib3

RIOT_API_KEY = st.secrets["RIOT_API_KEY"]
ACCOUNT_ID = st.secrets["ACCOUNT_ID"]
P_UUID = st.secrets["P_UUID"]

st.set_page_config(
    page_title="Healthcheck LoL",
    layout="wide",
    initial_sidebar_state="auto",
    menu_items={
        "Get Help": "https://www.extremelycoolapp.com/help",
        "Report a bug": "https://www.extremelycoolapp.com/bug",
        "About": "# This is a header. This is an *extremely* cool app!",
    },
)

today_start = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
today_end = datetime.datetime.now().replace(hour=23, minute=59, second=59, microsecond=0)


@st.cache_data
def get_match_data_from_to(start: datetime.datetime, end: datetime.datetime):
    # st.write(f"Fetching data from {start} to {end}")
    http = urllib3.PoolManager()
    url = f"https://europe.api.riotgames.com/lol/match/v5/matches/by-puuid/{P_UUID}/ids"
    today_games = http.request(
        method="GET",
        url=url,
        fields={
            "startTime": int(start.timestamp()),
            "endTime": int(end.timestamp()),
            "count": 100,
        },
        headers={"X-Riot-Token": RIOT_API_KEY},
    )
    data = json.loads(today_games.data.decode("utf-8"))
    return data


@st.cache_data
def get_match_data(match_id):
    http = urllib3.PoolManager()
    url = f"https://europe.api.riotgames.com/lol/match/v5/matches/{match_id}"
    today_games = http.request(
        method="GET",
        url=url,
        headers={"X-Riot-Token": RIOT_API_KEY},
    )
    data = json.loads(today_games.data.decode("utf-8"))
    return data


def get_last_week_matches():
    matches = []

    week_start = today_start - datetime.timedelta(6)
    week_end = today_end - datetime.timedelta(1)

    # this is cached
    matches.extend(get_match_data_from_to(week_start, week_end))
    # this is not cached
    matches.extend(get_match_data_from_to(today_start, datetime.datetime.now()))
    return matches


def create_matches_df(matches: list) -> pd.DataFrame:
    df = pd.DataFrame()
    to_be_df = []
    for match_id in matches:
        game_dictionary = {}
        match_data = get_match_data(match_id)
        # skip if not ranked queue
        if match_data["info"]["queueId"] != 420:
            continue
        game_dictionary["start_date"] = datetime.datetime.fromtimestamp(
            match_data["info"]["gameStartTimestamp"] / 1e3, tz=pytz.timezone("Europe/Belgrade")
        )
        game_dictionary["end_date"] = datetime.datetime.fromtimestamp(
            match_data["info"]["gameEndTimestamp"] / 1e3, tz=pytz.timezone("Europe/Stockholm")
        )
        game_dictionary["game_duration"] = match_data["info"]["gameDuration"]
        for i in range(10):
            if match_data["info"]["participants"][i]["puuid"] == P_UUID:
                game_dictionary["championName"] = match_data["info"]["participants"][i][
                    "championName"
                ]
                game_dictionary["championId"] = match_data["info"]["participants"][i]["championId"]
                game_dictionary["kills"] = match_data["info"]["participants"][i]["kills"]
                game_dictionary["deaths"] = match_data["info"]["participants"][i]["deaths"]
                game_dictionary["assists"] = match_data["info"]["participants"][i]["assists"]
                game_dictionary["totalDamageDealtToChampions"] = match_data["info"]["participants"][
                    i
                ]["totalDamageDealtToChampions"]
                game_dictionary["goldEarned"] = match_data["info"]["participants"][i]["goldEarned"]
                game_dictionary["totalMinionsKilled"] = match_data["info"]["participants"][i][
                    "totalMinionsKilled"
                ]
                to_be_df.append(game_dictionary)
        df = pd.DataFrame(to_be_df)
    return df


def highlight_unique_champs(s):
    if 0 < s <= 3:
        color = "green"
    elif s < 5:
        color = "yellow"
    else:
        color = "red"
    return f"background-color: {color}"


def highlight_games_played(s):
    if 9 < s < 14:
        color = "green"
    elif s < 6:
        color = "red"
    else:
        color = "yellow"
    return f"background-color: {color}"


def highlight_start_date(s):
    min_hour = s.hour
    if min_hour < 11:
        color = "green"
    elif 11 <= min_hour < 12:
        color = "yellow"
    else:
        color = "red"
    return f"background-color: {color}"


def highlight_end_date(s):
    max_hour = s.hour
    if max_hour >= 21:
        color = "red"
    elif 18 <= max_hour < 21:
        color = "yellow"
    else:
        color = "green"
    return f"background-color: {color}"



def plot_timeline(df):
    fig, ax = plt.subplots()
    ax.broken_barh(
        list(zip(df["start_date"].values, (df["end_date"] - df["start_date"]).values)), (0, 0.5)
    )
    ax.set_xlim(df["start_date"].min(), df["end_date"].max())
    ax.set_ylim(0, 0.01)
    st.pyplot(fig)


def main(st, main_options, side_options):
    # If btn is pressed or Truetable
    matches = get_last_week_matches()
    df = create_matches_df(matches)
    df['is_in_main'] = df['championName'].isin(main_options)
    df['is_in_side'] = df['championName'].isin(side_options)
    df['out_of_rotation'] = ~(df['championName'].isin(main_options) | df['championName'].isin(side_options))
    new_df = df.groupby(df.start_date.dt.date).agg(
        Daily_Games_Count=("start_date", "count"),
        First_Game_Start_Time=("start_date", "min"),
        Last_Game_Start_Time=("start_date", "max"),
        Unique_Champions=("championName", "nunique"),
        Main_rotation=("is_in_main", "sum"),
        Side_rotation=("is_in_side", "sum"),
        Out_of_rotation=("out_of_rotation", "sum"),
    )
    # get 
    new_df = new_df.sort_values(by="start_date", ascending=False)
    # just time in 'Min' and 'Max' columns
    #new_df['Min'] = new_df['Min'].apply(truncate_miliseconds)
    new_df["Last_Game_Start_Time"] = new_df["Last_Game_Start_Time"].dt.floor('Min').dt.time
    new_df["First_Game_Start_Time"] = new_df["First_Game_Start_Time"].dt.floor('Min').dt.time
    colored_df = (
        new_df.style.applymap(highlight_games_played, subset=["Daily_Games_Count"])
        .applymap(highlight_unique_champs, subset=["Unique_Champions"])
        .applymap(highlight_start_date, subset=["First_Game_Start_Time"])
        .applymap(highlight_end_date, subset=["Last_Game_Start_Time"])
    )
    return colored_df

    # st.subheader("Timeline")
    # plot_timeline(df)

with st.sidebar:
    all_adcs = ['Ziggs','Jhin','Kalista','Zeri', 'Caitlyn', 'Jhin', 'Kai\'Sa','Xayah','Varus','Lucian','Jinx','Ashe']
    options = st.multiselect(
        'Champions in your rotation',
        all_adcs,
        ['Zeri', 'Xayah','Kalista'])
    side_options = st.multiselect(
        'Champions in your situational rotation',
        all_adcs,
        ['Jhin','Ziggs'])

    

    set_options = set(options)
    set_side_options = set(side_options)
    if set_side_options & set_options:
        st.warning("You can't have the same champion in both rotations")
        st.write(f"Setting situational rotation to")
        side_options = list(set_side_options - set_options)



st.title("LoL improvment healthcheck")

placeholder = st.empty()
with placeholder.container():
    colored_df = main(placeholder, options, side_options)

st.subheader("Daily healthcheck")
st.table(colored_df)
if st.button("Refresh"):
    placeholder.empty()
    colored_df = main(placeholder, options, side_options)


# if st.button("Clear All"):
# st.cache_data.clear()
