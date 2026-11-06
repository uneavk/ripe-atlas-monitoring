import unittest

from app.models import normalize_ping, normalize_probe_status, validate_minimum


class ModelTests(unittest.TestCase):
    def test_normalize_ping_and_loss(self) -> None:
        raw = {
            "msm_id": 1001,
            "prb_id": 42,
            "timestamp": 1789420364,
            "af": 4,
            "sent": 3,
            "rcvd": 2,
            "result": [{"rtt": 10.0}, {"rtt": 20.0}, {"x": "timeout"}],
        }
        event = normalize_ping(raw, "stream")
        self.assertEqual(event["loss_pct"], 33.3333)
        self.assertEqual(event["rtt_avg"], 15.0)
        self.assertEqual(validate_minimum(event), (True, None))

    def test_event_id_is_stable(self) -> None:
        raw = {"msm_id": 1001, "prb_id": 42, "timestamp": 100, "sent": 1, "rcvd": 1, "result": [{"rtt": 5.0}]}
        self.assertEqual(normalize_ping(raw, "stream")["event_id"], normalize_ping(raw, "backfill")["event_id"])


    def test_invalid_sent_goes_to_rejection(self) -> None:
        raw = {"msm_id": 1001, "prb_id": 42, "timestamp": 100, "sent": 0, "rcvd": 0, "result": []}
        valid, reason = validate_minimum(normalize_ping(raw, "stream"))
        self.assertFalse(valid)
        self.assertEqual(reason, "INVALID_SENT")


    def test_probe_status(self) -> None:
        event = normalize_probe_status({"prb_id": 42, "timestamp": 100, "event": "disconnect"})
        self.assertEqual(event["event_type"], "probe_status")
        self.assertEqual(validate_minimum(event), (True, None))


if __name__ == "__main__":
    unittest.main()
