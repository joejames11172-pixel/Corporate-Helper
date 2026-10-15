# Corporate Helper automatic LAN channel

Only the master opens authenticated helper connections, only to literal IPv4 addresses on its actual connected private LAN subnet. Non-masters listen and send connectionless discovery readiness replies; they never dial peers. Pin both the master client certificate and each enrolled peer server certificate. Subnet membership alone never grants access.

Master: master_agent.py, OpenRC boot startup, broadcast discovery UDP 18768, TLS peer channel TCP 18766, local broker relay /operator/peer. Source address binds to the actual interface; policy is checked before socket creation and every reconnect. Retry failures after 30 seconds. No DNS, proxy, redirect or Internet fallback for helper peers.

Windows: Install.cmd and install_windows.py configure the compatible bundled runtime, machine-scoped DPAPI enrollment with restricted ACLs, a SYSTEM ONSTART task, a watchdog and subnet-scoped firewall ports. peer_service.py listens for master TLS and local authenticated IPC at 127.0.0.1:18765. The native host uses framed stdio and never opens a LAN connection. Source is written for Python 3.4 compatibility.

The personalized installer and private enrollment must remain in the private distribution folder, never in this repository. A distinct enrollment is required for every additional machine. Public source alone is not a pre-enrolled installer.

Corporate Extension 0.4.0 automatically grants its active Gemini chat, maintains the local native-host connection, and has two primary controls: On/Off and Settings. No repeated addresses, identities, passwords or hourly pairing. Other AI JSON DOM adapters remain to implement.

Nine native policy/queue/framing tests and nine extension tests pass locally. Windows DPAPI, task/firewall/native-host startup and Supermium interaction must be verified on the actual machine before production acceptance. Existing SSH forwards and the Gateway are preserved; Windows-initiated helper SSH supervision is superseded by the master-only channel requirement.

Configuration/enrollment files are local protected machine configuration. Business files remain on Drive; requests and captures are held only in memory. Certificate rotation and additional-machine provisioning remain lifecycle work.
