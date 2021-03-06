"""RSS/Atom feed reader for Home Assistant."""
from datetime import datetime
from logging import getLogger
import voluptuous as vol
from homeassistant.helpers.event import track_utc_time_change

REQUIREMENTS = ['feedparser==5.2.1']
_LOGGER = getLogger(__name__)
DOMAIN = "feedreader"
EVENT_FEEDREADER = "feedreader"
# pylint: disable=no-value-for-parameter
CONFIG_SCHEMA = vol.Schema({
    DOMAIN: {
        'urls': [vol.Url()],
    }
}, extra=vol.ALLOW_EXTRA)


# pylint: disable=too-few-public-methods
class FeedManager(object):
    """Abstraction over feedparser module."""

    def __init__(self, url, hass):
        """Initialize the FeedManager object, poll every hour."""
        self._url = url
        self._feed = None
        self._hass = hass
        # Initialize last entry timestamp as epoch time
        self._last_entry_timestamp = datetime.utcfromtimestamp(0).timetuple()
        _LOGGER.debug('Loading feed %s', self._url)
        self._update()
        track_utc_time_change(hass, lambda now: self._update(),
                              minute=0, second=0)

    def _log_no_entries(self):
        """Send no entries log at debug level."""
        _LOGGER.debug('No new entries in feed %s', self._url)

    def _update(self):
        """Update the feed and publish new entries in the event bus."""
        import feedparser
        _LOGGER.info('Fetching new data from feed %s', self._url)
        self._feed = feedparser.parse(self._url,
                                      etag=None if not self._feed
                                      else self._feed.get('etag'),
                                      modified=None if not self._feed
                                      else self._feed.get('modified'))
        if not self._feed:
            _LOGGER.error('Error fetching feed data from %s', self._url)
        else:
            if self._feed.bozo != 0:
                _LOGGER.error('Error parsing feed %s', self._url)
            # Using etag and modified, if there's no new data available,
            # the entries list will be empty
            elif len(self._feed.entries) > 0:
                _LOGGER.debug('Entries available in feed %s', self._url)
                self._publish_new_entries()
                self._last_entry_timestamp = \
                    self._feed.entries[0].published_parsed
            else:
                self._log_no_entries()

    def _publish_new_entries(self):
        """Publish new entries to the event bus."""
        new_entries = False
        for entry in self._feed.entries:
            # Consider only entries newer then the latest parsed one
            if entry.published_parsed > self._last_entry_timestamp:
                new_entries = True
                entry.update({'feed_url': self._url})
                self._hass.bus.fire(EVENT_FEEDREADER, entry)
        if not new_entries:
            self._log_no_entries()


def setup(hass, config):
    """Setup the feedreader component."""
    urls = config.get(DOMAIN)['urls']
    feeds = [FeedManager(url, hass) for url in urls]
    return len(feeds) > 0
