import json

from config import Config
from datetime import datetime, timedelta
import time
from collector_json import get_event_info
from common import json_date_to_datetime, nice_request, remix_parse
from enums import RouvyEventType, RouvyEventOrganizer, RouvyEventStatus
from dataclasses import dataclass
"""
That magic that finds rvy events for rvy races
"""


@dataclass
class EventFilter:
    route_id: str = None
    laps: int = None
    race_date: datetime = None

    def is_outside_race_date(self, event_start: datetime) -> bool:
        if self.race_date is None:
            return False
        extra_hours: int = Config.race_finder.allow_plus_n_hours
        return event_start < self.race_date or event_start > (self.race_date + timedelta(days=1, hours=extra_hours))

    def is_laps_ok(self, laps: int) -> bool:
        if self.laps is None:
            return True
        return laps == self.laps

    def is_route_ok(self, route_id: str) -> bool:
        if self.route_id is None:
            return True
        return route_id == self.route_id


def find_fake_commute(date_from: datetime, date_to: datetime) -> list:
    race_title: str = "fake commute"
    return find_events(race_title, date_from, date_to)


def find_events(race_title: str, date_from: datetime, date_to: datetime,
                event_type: RouvyEventType = RouvyEventType.RACE,
                smart_trainers_only: bool = True,
                event_filter: EventFilter = EventFilter()) -> list:
    events: list = list()
    # search prams
    date_from_str:  str = date_from.strftime("%Y-%m-%d")
    date_to_str:    str = date_to.strftime("%Y-%m-%d")
    print(f'[-] Searching')

    # Updated to handel RemixJS data
    remix_data = dict()
    offset = 0
    route = "routes/_main.events.search"
    while True:
        url = (f"https://riders.rouvy.com/events/search.data?"
               f"searchQuery={race_title}&"
               f"smartTrainersOnly={str(smart_trainers_only).lower()}&"
               f"type={event_type.value}&"
               f"dateRange=custom&"
               f"dateFrom={date_from_str}&"
               f"dateTo={date_to_str}&"
               f"offset={offset}&"
               f"_routes={route}")
        result = nice_request(url=url)
        remix_data = remix_parse(result.text)
        x = remix_data.get(route, {}).get('data',{}).get('events', dict())
        result_count = len(x)
        if result_count == 0:
            break
        offset += result_count

        for event in remix_data[route]['data']['events']:
            event_start: datetime = json_date_to_datetime(event['startDateTime'])
            # Extra part day filtering
            if event_filter.is_outside_race_date(event_start):
                continue  # Skip events outside the allowed time window
            if not event_filter.is_laps_ok(event["laps"]):
                continue  # Skip events that do not have the correct number of laps
            print(f'[-] Found: {event["title"]}')
            event_info: dict = get_event_info(event['id'])
            # Check the actual route id, it is not in the search results :(
            if not event_filter.is_route_ok(event_info["routeDetail"]["id"]):
                print('[X] Rejected: Route incorrect')
                continue
            # All good we have an actual valid rvy_racing event...
            events.append(event_info)

    return sorted(events, key=lambda d: d['startDateTime'])


def find_race_events(race_date: datetime, route_id: str, laps: int) -> list:
    """
    Get a list of events in datetime order that match the provided values
    :param race_date: UTC Day of the race
    :param route_id: The route id  for the race
    :param laps: The number of laps
    :return: A list of events in datetime order
    """
    race_title: str = "rvy_racing"  # It feels bad having this as a static string here
    date_from: datetime = race_date + timedelta(days=Config.race_finder.search_back_days)
    date_to: datetime = race_date + timedelta(days=Config.race_finder.search_froward_days)

    event_filter = EventFilter(route_id=route_id, laps=laps, race_date=race_date)
    return find_events(race_title, date_from, date_to, event_filter=event_filter)


if __name__ == '__main__':
    pass
