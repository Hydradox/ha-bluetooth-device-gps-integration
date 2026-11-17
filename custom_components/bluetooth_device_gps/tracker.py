"""Push-based manager: follows phones while connected and parks vehicles on disconnect."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_call_later, async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_DISCONNECT_GRACE,
    CONF_FIX_TIMEOUT,
    CONF_LIVE_MIN_INTERVAL,
    CONF_MACS,
    CONF_MAX_ACCURACY,
    CONF_PHONES,
    CONF_PICTURE,
    DEFAULT_DISCONNECT_GRACE,
    DEFAULT_FIX_TIMEOUT,
    DEFAULT_LIVE_MIN_INTERVAL,
    DEFAULT_MAX_ACCURACY,
    DOMAIN,
    EVENT_DEPARTED,
    EVENT_PARKED,
    ISSUE_NO_BLUETOOTH_SENSOR,
    LIVE_FIX_MAX_AGE,
    LOGGER,
    PHASE_CONNECTED,
    PHASE_PARKED,
    PHASE_SETTLING,
    SOURCE_LAST_LIVE,
    SOURCE_LIVE,
    SOURCE_MANUAL,
    SOURCE_REQUESTED,
    SOURCE_STALE,
    STORAGE_VERSION,
    SUBENTRY_VEHICLE,
)
from .helpers import Fix, fix_from_state, pick_best_fix
from .providers import Phone, discover_phones

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.config_entries import ConfigEntry

# A phone is asked for a fix at most once in this window, however many vehicles wait for it.
REQUEST_DEDUP = timedelta(seconds=5)
SAVE_DELAY = 10


class Vehicle:
    """State of one vehicle (one config subentry)."""

    def __init__(self, subentry_id: str, name: str, macs: set[str], picture: str | None) -> None:
        """Initialise a parked vehicle without a location."""
        self.subentry_id = subentry_id
        self.name = name
        self.macs = frozenset(macs)
        self.picture = picture
        self.fix: Fix | None = None
        self.source: str | None = None
        self.phase = PHASE_PARKED
        self.parked_at: datetime | None = None
        self.last_driver: str | None = None
        self.holders: set[str] = set()  # device ids of the phones connected right now
        self.departures: dict[str, datetime] = {}  # when each phone left
        self.disconnected_at: datetime | None = None
        self.collect_phones: set[str] = set()
        self.collecting = False
        self.last_live_write: datetime | None = None
        self.timer: CALLBACK_TYPE | None = None  # fix timeout (or restart debounce)
        self.grace_timer: CALLBACK_TYPE | None = None  # minimum time before parking
        self.grace_done = False
        self.candidate: Fix | None = None  # first accurate fix after the disconnect
        self._listeners: list[Callable[[], None]] = []
        self._event_listeners: list[Callable[[str, dict[str, Any]], None]] = []

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> CALLBACK_TYPE:
        """Call `listener` on every change; returns the unsubscribe function."""
        self._listeners.append(listener)

        @callback
        def remove() -> None:
            self._listeners.remove(listener)

        return remove

    @callback
    def notify(self) -> None:
        """Tell the entities something changed."""
        for listener in list(self._listeners):
            listener()

    @callback
    def async_add_event_listener(
        self, listener: Callable[[str, dict[str, Any]], None]
    ) -> CALLBACK_TYPE:
        """Call `listener(event_type, data)` for every parked/departed event."""
        self._event_listeners.append(listener)

        @callback
        def remove() -> None:
            self._event_listeners.remove(listener)

        return remove

    @callback
    def fire_event(self, event_type: str) -> None:
        """Tell the event entity that the vehicle was parked or departed."""
        data: dict[str, Any] = {
            "latitude": self.fix.latitude if self.fix else None,
            "longitude": self.fix.longitude if self.fix else None,
            "accuracy": self.fix.accuracy if self.fix else None,
            "location_source": self.source,
            "last_driver": self.last_driver,
            "parked_at": self.parked_at.isoformat() if self.parked_at else None,
        }
        for listener in list(self._event_listeners):
            listener(event_type, data)

    @callback
    def cancel_timer(self) -> None:
        """Cancel the pending timers."""
        if self.timer:
            self.timer()
            self.timer = None
        if self.grace_timer:
            self.grace_timer()
            self.grace_timer = None

    def as_dict(self) -> dict[str, Any]:
        """Serialise what must survive a restart."""
        return {
            "latitude": self.fix.latitude if self.fix else None,
            "longitude": self.fix.longitude if self.fix else None,
            "accuracy": self.fix.accuracy if self.fix else None,
            "fix_time": self.fix.time.isoformat() if self.fix else None,
            "source": self.source,
            "phase": self.phase,
            "parked_at": self.parked_at.isoformat() if self.parked_at else None,
            "last_driver": self.last_driver,
        }

    def restore(self, data: dict[str, Any]) -> None:
        """Load what `as_dict` saved."""
        if data.get("latitude") is not None and data.get("longitude") is not None:
            fix_time = dt_util.parse_datetime(data.get("fix_time") or "") or dt_util.utcnow()
            self.fix = Fix(data["latitude"], data["longitude"], data.get("accuracy"), fix_time)
        self.source = data.get("source")
        self.phase = data.get("phase") or PHASE_PARKED
        self.parked_at = dt_util.parse_datetime(data.get("parked_at") or "")
        self.last_driver = data.get("last_driver")


class BluetoothGpsManager:
    """Owns the vehicles and reacts to the phones' Bluetooth and location sensors."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialise the manager (nothing is subscribed until `async_start`)."""
        self.hass = hass
        self.entry = entry
        self.vehicles: dict[str, Vehicle] = {}
        self._phones: dict[str, Phone] = {}
        self._phone_unsubs: list[CALLBACK_TYPE] = []
        self._last_request: dict[str, datetime] = {}
        self._warned: set[str] = set()
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )

    # ---- options -------------------------------------------------------------------------

    def _option(self, key: str, default: float) -> float:
        return self.entry.options.get(key, default)

    @property
    def _grace(self) -> timedelta:
        return timedelta(seconds=self._option(CONF_DISCONNECT_GRACE, DEFAULT_DISCONNECT_GRACE))

    @property
    def _fix_timeout(self) -> float:
        return self._option(CONF_FIX_TIMEOUT, DEFAULT_FIX_TIMEOUT)

    @property
    def _max_accuracy(self) -> float:
        return self._option(CONF_MAX_ACCURACY, DEFAULT_MAX_ACCURACY)

    # ---- lifecycle -----------------------------------------------------------------------

    async def async_start(self) -> None:
        """Load the saved state, discover the phones and evaluate every vehicle."""
        saved = await self._store.async_load() or {}
        for subentry in self.entry.subentries.values():
            if subentry.subentry_type != SUBENTRY_VEHICLE:
                continue
            vehicle = Vehicle(
                subentry.subentry_id,
                subentry.title,
                set(subentry.data[CONF_MACS]),
                subentry.data.get(CONF_PICTURE),
            )
            vehicle.restore(saved.get(subentry.subentry_id, {}))
            self.vehicles[subentry.subentry_id] = vehicle

        self._discover()
        self.entry.async_on_unload(
            self.hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, self._on_registry_updated)
        )
        for vehicle in self.vehicles.values():
            self._evaluate(vehicle)

    async def async_stop(self) -> None:
        """Cancel everything pending and save the state."""
        for vehicle in self.vehicles.values():
            vehicle.cancel_timer()
        self._unsubscribe_phones()
        await self._store.async_save(self._data_to_save())

    @callback
    def _data_to_save(self) -> dict[str, Any]:
        return {sid: vehicle.as_dict() for sid, vehicle in self.vehicles.items()}

    @callback
    def _changed(self, vehicle: Vehicle) -> None:
        vehicle.notify()
        self._store.async_delay_save(self._data_to_save, SAVE_DELAY)

    # ---- phone discovery -----------------------------------------------------------------

    @callback
    def _unsubscribe_phones(self) -> None:
        for unsub in self._phone_unsubs:
            unsub()
        self._phone_unsubs.clear()

    @callback
    def _on_registry_updated(self, event: Event) -> None:
        if event.data.get("entity_id", "").split(".")[0] in ("sensor", "device_tracker"):
            before = {(p.device_id, p.sensor_id, p.tracker_id) for p in self._phones.values()}
            self._discover()
            after = {(p.device_id, p.sensor_id, p.tracker_id) for p in self._phones.values()}
            if before != after:
                for vehicle in self.vehicles.values():
                    self._evaluate(vehicle)

    @callback
    def _discover(self) -> None:
        """(Re)build the phone list and resubscribe to their sensors."""
        allowed = set(self.entry.options.get(CONF_PHONES) or [])
        found = discover_phones(self.hass, allowed)
        for device_id, phone in found.items():
            if (old := self._phones.get(device_id)) and old.sensor_id == phone.sensor_id:
                phone.connected = old.connected
        self._phones = found
        self._unsubscribe_phones()

        for phone in found.values():
            self._update_connected(phone, self.hass.states.get(phone.sensor_id))
        if found:
            self._phone_unsubs.append(
                async_track_state_change_event(
                    self.hass, [p.sensor_id for p in found.values()], self._on_bluetooth_event
                )
            )
            trackers = [p.tracker_id for p in found.values() if p.tracker_id]
            if trackers:
                self._phone_unsubs.append(
                    async_track_state_change_event(self.hass, trackers, self._on_tracker_event)
                )
            ir.async_delete_issue(self.hass, DOMAIN, ISSUE_NO_BLUETOOTH_SENSOR)
        else:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                ISSUE_NO_BLUETOOTH_SENSOR,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_NO_BLUETOOTH_SENSOR,
            )

    # ---- Bluetooth events ----------------------------------------------------------------

    @staticmethod
    def _update_connected(phone: Phone, state: State | None) -> None:
        """Refresh the connected MACs; unavailable/unknown keep the previous value."""
        if state is None:
            return
        if (connected := phone.provider.parse_connected(state)) is not None:
            phone.connected = connected

    @callback
    def _on_bluetooth_event(self, event: Event) -> None:
        entity_id = event.data["entity_id"]
        phone = next((p for p in self._phones.values() if p.sensor_id == entity_id), None)
        if phone is None:
            return
        self._update_connected(phone, event.data.get("new_state"))
        for vehicle in self.vehicles.values():
            self._evaluate(vehicle)

    @callback
    def _evaluate(self, vehicle: Vehicle) -> None:
        """Compare the current holders with the previous ones and move the state machine."""
        now = dt_util.utcnow()
        holders = {p.device_id for p in self._phones.values() if vehicle.macs & p.connected}
        previous = vehicle.holders
        vehicle.holders = holders

        for device_id in previous - holders:
            vehicle.departures[device_id] = now

        if holders:
            vehicle.cancel_timer()
            vehicle.collecting = False
            vehicle.departures.clear()
            joined = holders - previous
            if joined:
                vehicle.last_driver = self._phones[min(joined)].name
            changed = bool(joined) or previous != holders
            departed = vehicle.phase == PHASE_PARKED
            if vehicle.phase != PHASE_CONNECTED:
                if departed:
                    vehicle.fire_event(EVENT_DEPARTED)  # still carries the parking spot
                vehicle.phase = PHASE_CONNECTED
                vehicle.parked_at = None
                changed = True
            if changed:
                self._changed(vehicle)
            self._apply_live(vehicle)
        elif previous:
            # The last phone left: ask for the location right away. Parking waits for the grace
            # period, and a reconnect before that cancels it.
            vehicle.disconnected_at = now
            self._begin_settle(vehicle)
        elif (
            vehicle.phase in (PHASE_CONNECTED, PHASE_SETTLING)
            and vehicle.timer is None
            and not vehicle.collecting
        ):
            # Restored as driving/settling but nobody holds it: Home Assistant was down or
            # the phone is not reporting yet. Give it the grace period, then settle (no phone is
            # known to have left, so nothing is requested and the position is kept).
            vehicle.disconnected_at = now
            self._start_debounce(vehicle)

    @callback
    def _start_debounce(self, vehicle: Vehicle) -> None:
        vehicle.cancel_timer()
        vehicle.collecting = False
        vehicle.phase = PHASE_SETTLING
        vehicle.timer = async_call_later(
            self.hass,
            self._grace.total_seconds(),
            callback(lambda _now: self._begin_settle(vehicle)),
        )
        self._changed(vehicle)

    # ---- live following ------------------------------------------------------------------

    def _phone_fix(self, phone: Phone) -> Fix | None:
        return fix_from_state(self.hass.states.get(phone.tracker_id)) if phone.tracker_id else None

    @callback
    def _on_tracker_event(self, event: Event) -> None:
        entity_id = event.data["entity_id"]
        phone = next((p for p in self._phones.values() if p.tracker_id == entity_id), None)
        if phone is None:
            return
        for vehicle in self.vehicles.values():
            if vehicle.phase == PHASE_CONNECTED and phone.device_id in vehicle.holders:
                self._apply_live(vehicle)
            elif vehicle.collecting and phone.device_id in vehicle.collect_phones:
                self._update_candidate(vehicle)
                self._finish_if_ready(vehicle)

    @callback
    def _apply_live(self, vehicle: Vehicle) -> None:
        """Move the vehicle to the best fix among the phones connected to it."""
        fixes = [
            fix
            for device_id in vehicle.holders
            if (phone := self._phones.get(device_id)) and (fix := self._phone_fix(phone))
        ]
        best = pick_best_fix(fixes)
        if best is None or best == vehicle.fix:
            return
        if vehicle.fix and best.time < vehicle.fix.time:
            return  # never jump back to an older fix
        interval = self._option(CONF_LIVE_MIN_INTERVAL, DEFAULT_LIVE_MIN_INTERVAL)
        now = dt_util.utcnow()
        if (
            interval
            and vehicle.last_live_write
            and (now - vehicle.last_live_write).total_seconds() < interval
        ):
            return
        vehicle.fix, vehicle.source, vehicle.last_live_write = best, SOURCE_LIVE, now
        self._changed(vehicle)

    # ---- settling ------------------------------------------------------------------------

    @callback
    def _begin_settle(self, vehicle: Vehicle) -> None:
        """Ask the phones that just left for a fresh fix, now, and collect until the timeout."""
        vehicle.cancel_timer()
        departures = vehicle.departures
        last = max(departures.values(), default=vehicle.disconnected_at)
        vehicle.disconnected_at = last
        vehicle.phase = PHASE_SETTLING
        vehicle.candidate = None
        vehicle.grace_done = False
        vehicle.collect_phones = {
            device_id
            for device_id, left_at in departures.items()
            if device_id in self._phones and last - left_at <= self._grace
        }
        if not vehicle.collect_phones:
            # Nobody to ask (restart while parked elsewhere, phone removed): keep what we have.
            self._finish_settle(vehicle)
            return
        vehicle.collecting = True
        for device_id in vehicle.collect_phones:
            self._request_location(self._phones[device_id])
        vehicle.timer = async_call_later(
            self.hass, self._fix_timeout, callback(lambda _now: self._finish_settle(vehicle))
        )
        vehicle.grace_timer = async_call_later(
            self.hass, self._grace.total_seconds(), callback(lambda _now: self._grace_over(vehicle))
        )
        self._update_candidate(vehicle)
        self._changed(vehicle)

    @callback
    def _grace_over(self, vehicle: Vehicle) -> None:
        """Park now if a good fix is already in, as the minimum time has passed."""
        vehicle.grace_timer = None
        vehicle.grace_done = True
        self._finish_if_ready(vehicle)

    @callback
    def _request_location(self, phone: Phone) -> None:
        now = dt_util.utcnow()
        if (last := self._last_request.get(phone.device_id)) and now - last < REQUEST_DEDUP:
            return
        self._last_request[phone.device_id] = now
        self.entry.async_create_task(
            self.hass,
            self._async_request(phone),
            f"{DOMAIN} request location {phone.name}",
        )

    async def _async_request(self, phone: Phone) -> None:
        try:
            asked = await phone.provider.async_request_location(self.hass, phone)
        except HomeAssistantError as err:
            LOGGER.debug("Location request to %s failed: %s", phone.name, err)
            return
        if not asked:
            LOGGER.debug("Cannot request a fix from %s", phone.name)

    def _collected(self, vehicle: Vehicle) -> list[Fix]:
        """Return the fixes of the departed phones that arrived after the disconnect."""
        since = vehicle.disconnected_at
        fixes = []
        for device_id in vehicle.collect_phones:
            fix = self._phone_fix(self._phones[device_id]) if device_id in self._phones else None
            if fix and (since is None or fix.time > since):
                fixes.append(fix)
        return fixes

    @callback
    def _update_candidate(self, vehicle: Vehicle) -> None:
        """Remember the first fix that is accurate enough.

        It is the one closest in time to the disconnect, so before the user walked away.
        Later fixes (still arriving during the grace period) must not replace it.
        """
        if vehicle.candidate is not None:
            return
        accurate = [
            fix
            for fix in self._collected(vehicle)
            if fix.accuracy is not None and fix.accuracy <= self._max_accuracy
        ]
        if accurate:
            vehicle.candidate = min(accurate, key=lambda fix: fix.time)

    @callback
    def _finish_if_ready(self, vehicle: Vehicle) -> None:
        """Park once there is a good fix and the grace period is over."""
        if vehicle.candidate is not None and vehicle.grace_done:
            self._finish_settle(vehicle)

    @callback
    def _finish_settle(self, vehicle: Vehicle) -> None:
        """Park the vehicle at the best fix available."""
        vehicle.cancel_timer()
        vehicle.collecting = False
        candidate = vehicle.candidate
        collected = pick_best_fix(self._collected(vehicle))
        live = vehicle.fix if vehicle.source == SOURCE_LIVE else None
        if (
            live
            and vehicle.disconnected_at
            and live.time < vehicle.disconnected_at - timedelta(seconds=LIVE_FIX_MAX_AGE)
        ):
            live = None

        chosen = candidate or pick_best_fix(f for f in (collected, live) if f)

        if chosen is None:
            vehicle.source = SOURCE_STALE if vehicle.fix else None
            self._warn_once(vehicle)
        else:
            vehicle.source = SOURCE_LAST_LIVE if chosen is live else SOURCE_REQUESTED
            vehicle.fix = chosen
        vehicle.phase = PHASE_PARKED
        vehicle.parked_at = dt_util.utcnow()
        vehicle.departures.clear()
        vehicle.collect_phones = set()
        vehicle.candidate = None
        self._changed(vehicle)
        vehicle.fire_event(EVENT_PARKED)

    def _warn_once(self, vehicle: Vehicle) -> None:
        if vehicle.subentry_id not in self._warned:
            self._warned.add(vehicle.subentry_id)
            LOGGER.warning(
                "No usable location for %s after disconnect: keeping the last known position. "
                "Check the phone's location permission and that its device tracker "
                "has GPS coordinates",
                vehicle.name,
            )

    # ---- services ------------------------------------------------------------------------

    @callback
    def async_set_location(
        self, vehicle: Vehicle, latitude: float, longitude: float, accuracy: float | None
    ) -> None:
        """Manual override of the location (service)."""
        vehicle.fix = Fix(latitude, longitude, accuracy, dt_util.utcnow())
        vehicle.source = SOURCE_MANUAL
        self._changed(vehicle)
