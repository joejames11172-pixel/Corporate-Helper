# Corporate Helper

Shared helper core and platform adapters for local machine operations and authenticated master delegation.

Initial Alpine HTTPS browser broker is installed separately; the repository currently adds the SMS queue/routing contract and pure validated rules. Messaging and failover are not deployed yet.

See [ROUTING_AND_SMS.md](ROUTING_AND_SMS.md). Keep machine configuration, contacts, credentials, private keys and queue records out of Git.

Run tests: `python3 -m unittest discover -s tests -p test_queue_contract.py -v`.
