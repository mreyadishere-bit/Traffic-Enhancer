# Dashcam feasibility — DDPAI MINI2X

**Documentation review:** October 25, 2026. **Hardware tested here:** none. **Egypt retail price and stock:** not verified.

| Camera function | Original MINI2X | MINI2X 2026 |
|---|---|---|
| “Take photo” voice capture | Documented | Documented |
| Associated incident clip | Documented; enable related-video setting | Documented |
| Configurable 20s clip, 10s before + 10s after trigger | Documented | Documented |
| Local camera recording when phone disconnected | Device stores footage, per manual | Device stores footage, per manual |
| Automatic downloading of snapshot/emergency files by **DDPAI app after connecting** | Documented app setting | Documented app setting |
| Public authorized API/SDK to pull files directly into Traffic Enhancer | **Not established** | **Not established** |
| Fully unattended direct Android/iOS integration | **Unverified** | **Unverified** |

Manufacturer references:
- https://www.ddpai.com/manuals/mini2x/
- https://www.ddpai.com/manuals/mini2x-2026/
- https://www.ddpai.com/dash-cams/mini2x-2026/

**Key distinction:** A manufacturer app that downloads evidence into *its own* local album does not automatically grant our app access to the videos. Verify whether downloaded files land in Android's shared media system or iOS Photos, or remain private. The official manual also describes share and download features; these are viable user-assisted MVP options.

### Practical acceptance tests on a physical sample

1. Enable Local Voice Control and associated clip capture, choose 20s.
2. Verify that voice command at T yields actual video covering T−10s to T+10s.
3. Record with mobile disconnected and test retention/power loss.
4. Test whether DDPAI app auto-downloads after reconnect on *each* OS.
5. Locate saved file and check user-authorized MediaStore / Photos / Share access.
6. Verify what happens with app foregrounded/backgrounded, phone locked and Wi-Fi-to-cloud transition.
7. Obtain official vendor support for any direct device API; do not reverse-engineer unapproved private endpoints.
8. Verify current Egyptian seller price under EGP 5,000 and local warranty before purchasing.

At present, **camera → DDPAI app → user share/import → Traffic Enhancer** is the defensible minimum. Only the subsequent **browser file → analysis → report** portion has been implemented in this repository.
