from pathlib import Path
from config import Config, Constants
from csv import DictReader
from requests import Response
from common import nice_request, remix_parse
"""
Here we collect json data from Rouvy, and return it for additional processing
"""


def get_challenges() -> list:
    """
    Collect Ongoing, Upcoming, Joined and Finished challenges from Rouvy.
    :return: A list of challenges.
    """
    # Depending on whom the request is being performed by, we may need to search all 3 options
    challenge_types: list = ['open', 'available', 'finished']
    challenge_list: list = list()
    route = "routes/_main.challenges.status.$status"
    for challenge_type in challenge_types:
        url = f"https://riders.rouvy.com/challenges/status/{challenge_type}.data?_routes={route}"
        result = nice_request(url=url)
        remix_data = remix_parse(result.text, False)
        c_data = remix_data[route]["data"]
        # Remove unneeded bloat
        c_data.pop('latestSpotlight', None)
        c_data.pop('pageMeta', None)
        c_data.pop('page', None)
        if 'challenges' in c_data:
            challenge_list += c_data['challenges']
    return challenge_list


def route_challenge_dict(challenges: list) -> dict:
    """
    Creates a dictionary keyed by route_id for current challenges.
    :param challenges: Challenges to convert into a dictionary.
    :return: A dictionary keyed by route_id for current challenges.
    """
    route_challenge: dict = dict()
    challenge: dict
    for challenge in challenges:
        segment: dict
        for segment in challenge['segments']:
            if segment['value'] is None:  # Rouvy have some grayness in the type of challenge
                route_challenge[str(segment['target'])] = challenge['challenge']
    return route_challenge


def get_event_info(event_id: str) -> dict:
    """
    Collect information about a specific event from Rouvy.
    :param event_id: The ID of the event.
    :return: Event information.
    """
    # Updated for RemixJS
    route = "routes/_main.events_.$id" # filter the data a little
    url = f"https://riders.rouvy.com/events/{event_id}.data?_routes={route}"
    result: Response = nice_request(url=url)
    remix_data: dict = remix_parse(result.text, debug=False)
    race_info: dict = remix_data[route]["data"]
    # Remove unneeded bloat
    race_info.pop('pageMeta', None)
    race_info.get('event', dict()).get('route', dict()).pop('geometry', None)
    race_info.get('event', dict()).get('route', dict()).pop('videoPreview', None)
    return race_info['event']


def get_event_results(event_id: str) -> dict:
    """
    Collect results leaderboard for a specific event from Rouvy.
    :param event_id: The ID of the event.
    :return: A results leaderboard dictionary.
    """
    route = "routes/_main.events_.$id.leaderboard"
    url = f"https://riders.rouvy.com/events/{event_id}/leaderboard.data?_routes={route}"
    result = nice_request(url=url)
    remix_data = remix_parse(result.text, False)
    return remix_data[route]['data']


def get_rouvy_user(username: str) -> dict:
    """
    Collect information about a specific user from Rouvy.
    :param username: Rouvy username.
    :return: User information.
    """
    route = "routes/_main.friends_.search"
    url = f"https://riders.rouvy.com/friends/search.data?query={username}&_routes={route}"
    result = nice_request(url=url)
    remix_data = remix_parse(result.text, False)
    data = remix_data[route]['data']
    for user in data.get('searchUser', list()):
        if str(user['username']) == username:
            return user
    return {'error': 'Rouvy user not found'}


def convert_user_data_to_json() -> dict:
    """
    Converts the legacy user_data.csv into dict / JSON format also collects and includes Rouvy user information.
    ** WARNING ** this is expensive requests wise, and should only be done when required.
    :return: User information as a dict.
    """
    user_data_dict: dict = dict()
    user_data_file: Path = Path(Config.series.data_path, 'user_data.csv')
    if not user_data_file.exists():
        print(f"[X] Expecting 'user_data.csv' to be in the base data directory: {str(Config.series.data_path)}")
        exit(1)
    with user_data_file.open('r', encoding='utf-8') as _f:
        # TODO: Maybe don't YOLO shit like this, anyhow YOLO.
        # YOLO: Totally presume for this csv that columns are always the same and in the same order.
        reader = DictReader(_f, fieldnames=["rvy_username", "rvy_rouvy_name", "rvy_fname", "rvy_sname",
                                            "rvy_strava_url", "rvy_yob", "rvy_gender", "rvy_allow", "extra"])
        next(reader)  # skip header
        user_row: dict
        print('[-] Collecting Rouvy user information', end='')
        for user_row in reader:
            print('.', end='')
            # Remove extra empty column
            user_row.pop('extra', None)
            # Replace data if not allowed, it just makes the logic easy later on
            # TODO: Consider populating with Rouvy data, this will be what the user has set as their public profile
            # TODO: YOB? Why not categories? Elite, Master, Super Master, 60+ or just 10y Age brackets 40-49, 50-59
            if user_row['rvy_allow'] != 'Allow':
                user_row['rvy_fname'] = '--'
                user_row['rvy_sname'] = '--'
                user_row['rvy_yob'] = '--'
                user_row['rvy_gender'] = '--'
            # Add in Rouvy user info if we can find it.
            # TODO: If we can not find the user, maybe retire this rvy user
            user_row['rouvy'] = get_rouvy_user(user_row['rvy_rouvy_name'])
            user_data_dict[user_row['rvy_rouvy_name']] = user_row
        print(' Done')
    return user_data_dict


def get_route_info(route_id: str) -> dict:
    """
    Collect information about a specific route from Rouvy.
    :param route_id: The ID of the route.
    :return: Route information.
    """
    route = "routes/_main.route.$id"
    url = f"https://riders.rouvy.com/route/{route_id}.data?_routes={route}"
    result = nice_request(url=url)
    remix_data = remix_parse(result.text, False)
    route_info = remix_data[route]['data']
    # Remove unneeded bloat
    route_info.pop('legacyRoute', None)  # Hope we never need this
    # Let's keep geometry, you can do some cool things with it.
    # From simple altitude plots to 3d course plots
    # route_info.get('route', dict()).pop('geometry', None)
    route_info.get('route', dict()).pop('thumbnails', None)
    route_info.get('route', dict()).pop('videoPreview', None)
    route_info.get('route', dict()).pop('videoQualities', None)
    route_info.get('route', dict()).pop('splits', None)
    return route_info


if __name__ == '__main__':
    pass
