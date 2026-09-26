"""Trips: form validation, packing workflow, ownership (audit P0 #5, P2 #22)."""
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase

from .models import Trip


def _future(days=7):
    return date.today() + timedelta(days=days)


class TripViewTests(TestCase):
    def setUp(self):
        self.client = Client(SERVER_NAME="127.0.0.1")
        self.user = User.objects.create_user("tripper", password="pw12345!")
        self.client.force_login(self.user)

    def _payload(self, **overrides):
        payload = {"name": "Goa getaway", "destination": "Panaji, Goa",
                   "start_date": _future(7).isoformat(),
                   "end_date": _future(10).isoformat(), "notes": "beach week"}
        payload.update(overrides)
        return payload

    def test_list_and_form_pages_render(self):
        self.assertEqual(self.client.get("/trips/").status_code, 200)
        response = self.client.get("/trips/add/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Start date")

    def test_create_trip_renders_packing_list(self):
        response = self.client.post("/trips/add/", self._payload())
        self.assertEqual(response.status_code, 302)
        trip = Trip.objects.get(name="Goa getaway")
        self.assertEqual(trip.owner, self.user)
        self.assertTrue(trip.packing, "packing list should be generated")
        detail = self.client.get(f"/trips/{trip.pk}/")
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "Toiletry kit")

    def test_end_date_before_start_date_is_rejected(self):
        response = self.client.post("/trips/add/", self._payload(
            start_date=_future(10).isoformat(), end_date=_future(7).isoformat()))
        self.assertEqual(response.status_code, 200)  # form re-rendered
        self.assertContains(response, "cannot be before the start date",
                            status_code=200)
        self.assertFalse(Trip.objects.filter(name="Goa getaway").exists())

    def test_unreasonably_long_trip_is_rejected(self):
        response = self.client.post("/trips/add/", self._payload(
            end_date=_future(400).isoformat()))
        self.assertContains(response, "longer than", status_code=200)
        self.assertFalse(Trip.objects.exists())

    def test_destination_required(self):
        response = self.client.post("/trips/add/", self._payload(destination="   "))
        self.assertContains(response, "Where are you going?", status_code=200)
        self.assertFalse(Trip.objects.exists())

    def test_edit_trip(self):
        trip = Trip.objects.create(name="Old", destination="Panaji, Goa",
                                   start_date=_future(5), end_date=_future(6),
                                   owner=self.user)
        response = self.client.post(f"/trips/{trip.pk}/edit/",
                                    self._payload(name="Renamed"))
        self.assertEqual(response.status_code, 302)
        trip.refresh_from_db()
        self.assertEqual(trip.name, "Renamed")

    def test_toggle_and_delete_require_post(self):
        trip = Trip.objects.create(name="T", destination="Panaji, Goa",
                                   start_date=_future(5), end_date=_future(6),
                                   packing=[{"name": "Socks", "qty": 2, "type": "essential",
                                             "packed": False}],
                                   owner=self.user)
        self.assertEqual(self.client.get(f"/trips/{trip.pk}/toggle/0/").status_code, 405)
        self.assertEqual(self.client.get(f"/trips/{trip.pk}/delete/").status_code, 405)
        self.client.post(f"/trips/{trip.pk}/toggle/0/")
        trip.refresh_from_db()
        self.assertTrue(trip.packing[0]["packed"])
        self.client.post(f"/trips/{trip.pk}/delete/")
        self.assertFalse(Trip.objects.filter(pk=trip.pk).exists())

    def test_ownership_isolation(self):
        other = User.objects.create_user("not-me", password="pw12345!")
        trip = Trip.objects.create(name="Secret", destination="Panaji, Goa",
                                   start_date=_future(5), end_date=_future(6),
                                   owner=other)
        self.assertEqual(self.client.get(f"/trips/{trip.pk}/").status_code, 404)
        self.assertEqual(self.client.post(f"/trips/{trip.pk}/delete/").status_code, 404)
        # Their trip is not listed either.
        listing = self.client.get("/trips/")
        self.assertNotContains(listing, "Secret")

    def test_anonymous_local_first_trip_works(self):
        anon = Client(SERVER_NAME="127.0.0.1")
        response = anon.post("/trips/add/", self._payload(name="Local trip"))
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(Trip.objects.get(name="Local trip").owner)