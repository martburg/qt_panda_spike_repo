import pygame, time

pygame.init()
pygame.joystick.init()

print("count:", pygame.joystick.get_count())
joys = []
for i in range(pygame.joystick.get_count()):
    j = pygame.joystick.Joystick(i)
    j.init()
    info = {
        "i": i,
        "name": j.get_name(),
        "guid": getattr(j, "get_guid", lambda: None)(),
        "axes": j.get_numaxes(),
        "buttons": j.get_numbuttons(),
        "hats": j.get_numhats(),
    }
    joys.append(j)
    print(info)

print("\nMove ONE axis on the Thrustmaster now...")
for _ in range(200):
    pygame.event.pump()
    for j in joys:
        # watch first few axes to keep output manageable
        vals = [j.get_axis(k) for k in range(min(4, j.get_numaxes()))]
        if any(abs(v) > 0.2 for v in vals):
            print("ACTIVE:", j.get_id(), j.get_name(), "axes0-3:", vals)
            raise SystemExit
    time.sleep(0.02)

print("No axis activity detected.")