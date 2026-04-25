"""Unit tests for bot.core.schemas (Pydantic models)."""

import pytest
from pydantic import ValidationError

from bot.core.enums import CampusLivingLocations, PickupLocations
from bot.core.schemas import (
    Identity,
    LLMOutputError,
    LLMOutputNominal,
    LLMPassenger,
    LocationQuery,
    Passenger,
    RidesUser,
)


class TestIdentity:
    """Tests for the Identity schema."""

    def test_username_gets_at_prefix(self):
        ident = Identity(name="Alice", username="alice")
        assert ident.username == "@alice"

    def test_username_already_has_at(self):
        ident = Identity(name="Alice", username="@alice")
        assert ident.username == "@alice"

    def test_username_none(self):
        ident = Identity(name="Alice")
        assert ident.username is None

    def test_name_required(self):
        with pytest.raises(ValidationError):
            Identity(username="alice")

    def test_empty_name(self):
        ident = Identity(name="")
        assert ident.name == ""


class TestLocationQuery:
    """Tests for the LocationQuery schema."""

    def test_valid_query(self):
        q = LocationQuery(
            start_location=PickupLocations.MUIR,
            end_location=PickupLocations.SIXTH,
        )
        assert q.start_location == PickupLocations.MUIR
        assert q.end_location == PickupLocations.SIXTH

    def test_same_start_end(self):
        q = LocationQuery(
            start_location=PickupLocations.ERC,
            end_location=PickupLocations.ERC,
        )
        assert q.start_location == q.end_location

    def test_invalid_location_raises(self):
        with pytest.raises(ValidationError):
            LocationQuery(start_location="nonexistent", end_location=PickupLocations.MUIR)


class TestRidesUser:
    """Tests for the RidesUser schema."""

    def test_valid_rides_user(self):
        user = RidesUser(
            identity=Identity(name="Bob", username="bob"),
            location=CampusLivingLocations.ERC,
        )
        assert user.identity.name == "Bob"
        assert user.location == CampusLivingLocations.ERC

    def test_invalid_location(self):
        with pytest.raises(ValidationError):
            RidesUser(
                identity=Identity(name="Bob"),
                location="Mars",
            )


class TestPassenger:
    """Tests for the Passenger schema."""

    def test_valid_passenger(self):
        p = Passenger(
            identity=Identity(name="Charlie", username="charlie"),
            living_location=CampusLivingLocations.SIXTH,
            pickup_location=PickupLocations.SIXTH,
        )
        assert p.identity.username == "@charlie"
        assert p.living_location == CampusLivingLocations.SIXTH
        assert p.pickup_location == PickupLocations.SIXTH

    def test_missing_fields_raise(self):
        with pytest.raises(ValidationError):
            Passenger(identity=Identity(name="X"))


class TestLLMPassenger:
    """Tests for the LLMPassenger schema."""

    def test_valid(self):
        p = LLMPassenger(name="Alice", location=PickupLocations.MUIR)
        assert p.name == "Alice"

    def test_invalid_location(self):
        with pytest.raises(ValidationError):
            LLMPassenger(name="Alice", location="InvalidPlace")


class TestLLMOutputNominal:
    """Tests for the LLMOutputNominal schema."""

    def test_valid_structure(self):
        data = {
            "Driver0": [
                {"name": "Alice", "location": PickupLocations.MUIR},
                {"name": "Bob", "location": PickupLocations.ERC},
            ],
            "Driver1": [],
        }
        output = LLMOutputNominal.model_validate(data)
        assert len(output.root["Driver0"]) == 2
        assert output.root["Driver1"] == []

    def test_empty_assignment(self):
        output = LLMOutputNominal.model_validate({})
        assert output.root == {}


class TestLLMOutputError:
    """Tests for the LLMOutputError schema."""

    def test_valid_error(self):
        output = LLMOutputError.model_validate({"error": "Something went wrong"})
        assert output.root["error"] == "Something went wrong"
