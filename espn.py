"""
ESPN Cross-League Scoreboard and Live Drama Index Tracker.

This script fetches data from the ESPN Scoreboard REST API endpoints for active 
sports (NFL, MLB, NBA), checks for game broadcast time overlaps, and checks 
overlap to determine which game has more drama to watch.
"""

__author__ = "Kristina Tiralosi"
__copyright__ = "Copyright 2026"
__license__ = "MIT"
__version__ = "1.0.0"
__maintainer__ = "Kristina Tiralosi"
__status__ = "Development"

from datetime import datetime
from datetime import timedelta
import json
import logging
import requests
import sys

"""
Initialize Logger

This sets up the logging format for the entire script
"""
def initialize_logger():
    # Configure the root logger
    logging.basicConfig(
        level=logging.INFO,
        format='{asctime} {levelname:<8} [{name}] {message}',
        datefmt='%Y-%m-%d %H:%M:%S',
        style='{'
    )
    # Setup logger
    return logging.getLogger('espn.demo')

"""
Get Live Response

Hit ESPN API to get a list of current games
"""
def get_live_response(sport_name, league):
    try:
        # Hit API
        response = requests.get(f'https://site.api.espn.com/apis/site/v2/sports/{sport_name}/{league}/scoreboard')
        response.raise_for_status()

    except requests.exceptions.HTTPError as e:
        # Catch the error if cannot be hit
        logger.error(f"Bad response for {sport_name}: {response.status_code}", file=sys.stderr)
        sys.exit(1)

    return response

"""
Parse Event Dates

Get a list of games with metadata by event dates
"""
def parse_event_dates(response, sport, duration):
    #Convert JSON to dict
    json_dict = json.loads(response.content)
    events = json_dict['events']
    event_list = []
    #Loop through events
    for event in events:
        # Get the basic event data 
        logger.debug(event)
        event_name = event['name']
        timestamp = event['date']
        event_date = datetime.fromisoformat(timestamp)
        logger.info(f'{event['name']} at {event_date.strftime("%B %d, %Y at %I:%M %p UTC")}')
        # Get game statistics
        status_dict = event.get("status", {})
        game_state = status_dict.get("type", {}).get("state")
        game_period = int(status_dict.get("period", 1))
        competitors = ((event.get("competitions", [{}]))[0]).get("competitors", [])
        if len(competitors) >= 2:
            # Safely pull the score values as strings and convert them to integers
            score_team_1 = int(competitors[0].get("score", 0))
            score_team_2 = int(competitors[1].get("score", 0))
            score_gap = abs(score_team_1 - score_team_2)
        else:
            score_gap = 0
        # Add the data to the list
        event_dict = {
            "sport_type": sport,
            "event_name": event_name,
            "game_date": event_date,
            "avg_duration": duration,
            "est_duration": get_game_window(sport, event_date, duration),
            "game_state": game_state,
            "game_period": game_period,
            "score_gap": score_gap
        }
        event_list.append(event_dict)

    return event_list

"""
Find Conflicted Games

Find games whose game times will overlap
"""
def find_conflicted_games(event_list):
    # Sort all durations by the start date
    game_intervals = sorted(
        [(event["event_name"], event["est_duration"]) for event in event_list],
        key=lambda x: x[1][0]
    )
    
    # Create overlap list
    overlap_list = []

    # Compare each event with the next one
    for i in range(len(game_intervals) - 1):
        current_end = game_intervals[i][1][1]
        next_start = game_intervals[i+1][1][0]
        
        # If the current interval ends after the next one begins, they overlap
        if current_end >= next_start:
            logger.info(f"Overlap between {game_intervals[i][0]} and {game_intervals[i+1][0]}!")
            overlap_list.append([game_intervals[i][0], game_intervals[i+1][0]])

    return overlap_list

"""
Get Game Window

Get estimated runtime of the game
"""
def get_game_window(sport, start_time, avg_duration):
    # Get the expected duration of the game
    end_time = start_time + avg_duration
    return start_time, end_time

"""
Compare Game Drama

Create scoring rubric to score dramatic live or post games
"""
def compare_game_drama(event_list, overlap_list):
    # Try to determine which is more important to watch
    for [game1, game2] in overlap_list:
        # Calculate drama scores
        score1 = calculate_game_drama(event_list, game1)
        score2 = calculate_game_drama(event_list, game2)
        # Conclude which is more interesting
        if score1 > score2:
            logger.info(f'{game1} is the game to watch')
        elif score2 > score1:
            logger.info(f'{game2} is the game to watch')
        else:
            logger.info(f'{game1} vs {game2} are at same time, you choose!')

def calculate_game_drama(event_list, game_name):
    # Get the game metadata
    game_event = next((e for e in event_list if e["event_name"] == game_name), None)
    
    logger.debug(f'Game Name: {game_name}')

    if game_event is None:
        logger.warning(f"Could not find live event metadata for {game_name}")
        return 0

    # Separate games by their current state
    if game_event['game_state'] == 'pre':
        logger.debug('Total Drama Score: 0')
        return 0
    elif game_event['game_state'] == 'post':
        totalDrama = 5
    else:
        totalDrama = 10

    # Universal Score Gap scoring logic
    if game_event['score_gap'] == 0:
        totalDrama += 50
    elif 1 <= game_event['score_gap'] <= 3:
        totalDrama += 40
    elif 4 <= game_event['score_gap'] <= 7:
        totalDrama += 25
    elif 8 <= game_event['score_gap'] <= 11:
        totalDrama += 10
    else:
        totalDrama += 0

    # Universal Game Period progression scoring logic
    if game_event['game_period'] >= 9:
        totalDrama += 50
    elif game_event['game_period'] in [4, 7, 8]:
        totalDrama += 40
    elif game_event['game_period'] in [3, 5, 6]:
        totalDrama += 20
    else:
        totalDrama += 5

    # 6. The Clutch-Tie Bonus check
    if game_event['score_gap'] == 0 and game_event['game_period'] >= 4:
        totalDrama += 10

    logger.debug(f'Total Drama Score: {totalDrama}')
    return totalDrama

if __name__ == "__main__":

    # Currently in season sports and average durations
    SEED_SPORTS = {
        'football': {
            'league': 'nfl',
            'duration': timedelta(hours=3, minutes=15)
        },
        'baseball': {
            'league': 'mlb',
            'duration': timedelta(hours=2, minutes=45)
        },
        'basketball': {
            'league': 'nba',
            'duration': timedelta(hours=2, minutes=30)
        }
    }
    
    # Start logger
    logger = initialize_logger()

    # Create empty list
    event_list = []
    # Loop through the sports
    logger.info("{:-^80}".format(f" Check The Game Schedules "))
    for sport, data in SEED_SPORTS.items():
        response = get_live_response(sport, data['league'])
        logger.info("{:-^80}".format(f" Sport: {sport} | League: {data['league']} | Avg Duration: {data['duration']} "))
        event_list.extend(parse_event_dates(response, sport, data['duration']))

    # Find conflicted game schedules
    logger.info("{:-^80}".format(f" Check the Schedule For Conflicting Games "))
    overlap_list = find_conflicted_games(event_list)

    # Calculate drama scores
    logger.info("{:-^80}".format(f" Calculate Which Game Is Worth Watching "))
    compare_game_drama(event_list, overlap_list)