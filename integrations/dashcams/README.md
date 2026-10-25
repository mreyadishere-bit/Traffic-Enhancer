# Dashcam adapter contract — not implemented yet

The DDPAI MINI2X is a **candidate**, not an integrated device. No connection attempt, vendor SDK, or real hardware test has occurred.

A future adapter interface should define:

- discoverDevices()
- requestConnection()
- getDeviceCapabilities()
- listIncidentClips()
- downloadIncidentClip()
- verifyDownloadedClip()
- acknowledgeImport()
- disconnectDevice()

Each method must report \`supported_and_tested\`, \`requires_user_action\`, \`unsupported\`, or \`unverified\`. Never generate fake devices, clips, connection status or success states.

Two independent transports must be tracked: **camera → phone** and **phone → cloud**. Native Android and iOS supported share/import pathways should precede any undocumented vendor-specific synchronization. More detail in [camera feasibility](../../docs/CAMERA_FEASIBILITY.md).
