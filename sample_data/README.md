# Sample Data

This folder contains realistic fake patient data for local demos, testing, and queue verification.

## Files

- `sample_patients.json` - 10 fake emergency-room patient records
- `expected_queue_order.json` - expected waiting-queue order after loading the sample patients

## How To Use

Run the seeding script from the project root:

```bash
python backend/seed_sample_data.py
```

That script rebuilds the schema, inserts the sample patients, and refreshes the in-memory queue.

## Notes

- The sample patients use fixed UUIDs so test runs stay predictable.
- The sample set covers the full priority range from 5 down to 1.
- Queue aging can move long-waiting patients up over time, so the live order may change after the app has been running.
